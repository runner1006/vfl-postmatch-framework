#!/usr/bin/env python3
"""Betriebswerkzeug der Scout League. Alles, was nicht im Browser passiert.

    python3 scoutleague/cli.py scouts    --namen "Zoran,Miguel,..."
    python3 scoutleague/cli.py pack      --datei pakete/kw35.json
    python3 scoutleague/cli.py status    --slug kw35-2026 --auf geschlossen
    python3 scoutleague/cli.py aufloesen --fall 3 --frage top5_12m --ergebnis 1
    python3 scoutleague/cli.py export    > ergebnis.csv
    python3 scoutleague/cli.py demo      # Demo-Pack + 10 Codes zum Ausprobieren
"""
import argparse
import json
import os
import secrets
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import db        # noqa: E402
import export    # noqa: E402
import logik     # noqa: E402

# Ohne I, O, 0, 1 - Codes werden vorgelesen und abgetippt.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def code_erzeugen(n=6):
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


# --------------------------------------------------------------------- Scouts
def scouts_anlegen(con, namen, rolle="scout"):
    angelegt = []
    with con:
        for name in namen:
            name = name.strip()
            if not name:
                continue
            vorhanden = con.execute(
                "SELECT * FROM scouts WHERE name = ?", (name,)).fetchone()
            if vorhanden:
                angelegt.append((name, vorhanden["code"], "bestand"))
                continue
            for _ in range(20):
                code = code_erzeugen()
                if not con.execute("SELECT 1 FROM scouts WHERE code = ?",
                                   (code,)).fetchone():
                    break
            else:
                raise RuntimeError("Kein freier Code gefunden.")
            con.execute(
                """INSERT INTO scouts (code, name, rolle, angelegt_am)
                   VALUES (?,?,?,?)""", (code, name, rolle, db.jetzt()))
            angelegt.append((name, code, "neu"))
    return angelegt


# ----------------------------------------------------------------- Case Packs
def index_zu_skala(wert):
    """Aggregierter Index 0-100 auf die 1-5-Skala des Fragebogens.

    Linear, mit Grenzen bei 10 und 90 statt 0 und 100: die Indexraender sind
    duenn besetzt, und ein Modell, das nie 1 oder 5 sagt, waere als Referenz
    fuer die Spreizung unbrauchbar. Wird nur benutzt, wenn der Case Pack keine
    eigene Modellerwartung mitliefert.
    """
    w = max(10.0, min(90.0, float(wert)))
    return round(1.0 + 4.0 * (w - 10.0) / 80.0, 2)


def pack_importieren(con, pfad):
    with open(pfad, encoding="utf-8") as f:
        daten = json.load(f)

    fb = logik.fragebogen()
    fragen = {q["key"] for q in fb["bewertung"]["fragen"]}
    prognosen = {p["key"] for p in fb["prognosen"]}
    param_pflicht = {p["parameter"] for p in fb["prognosen"] if p.get("parameter")}

    for pflicht in ("slug", "titel", "faelle"):
        if pflicht not in daten:
            raise SystemExit(f"Feld '{pflicht}' fehlt in {pfad}.")
    if not daten["faelle"]:
        raise SystemExit("Der Case Pack enthaelt keine Faelle.")

    # Alles vorab pruefen, damit ein halb importierter Pack gar nicht erst
    # entstehen kann.
    aufbereitet = []
    for i, fall in enumerate(daten["faelle"], 1):
        wo = f"Fall {i} ({fall.get('name', 'ohne Namen')})"
        if not fall.get("name"):
            raise SystemExit(f"{wo}: 'name' fehlt.")
        indizes = fall.get("indizes") or {}
        modell = fall.get("modell") or {}
        m_bew = dict(modell.get("bewertung") or {})
        m_prog = dict(modell.get("prognose") or {})

        for k in list(m_bew):
            if k not in fragen:
                raise SystemExit(f"{wo}: Modellbewertung '{k}' steht nicht im "
                                 f"Fragebogen.")
        for k in list(m_prog):
            if k not in prognosen:
                raise SystemExit(f"{wo}: Modellprognose '{k}' steht nicht im "
                                 f"Fragebogen.")
            if not 0.0 <= float(m_prog[k]) <= 1.0:
                raise SystemExit(f"{wo}: Modellprognose '{k}' muss zwischen 0 "
                                 f"und 1 liegen.")

        # Fehlende Modellbewertungen aus den Indizes ableiten, wo moeglich
        for k in fragen:
            if k not in m_bew and k in indizes:
                m_bew[k] = index_zu_skala(indizes[k])

        fehlend = sorted(prognosen - set(m_prog))
        if fehlend:
            print(f"  Hinweis: {wo} ohne Modellprognose fuer "
                  f"{', '.join(fehlend)} - dort entfaellt das Sofort-Feedback.",
                  file=sys.stderr)

        params = fall.get("parameter") or {}
        for p in param_pflicht:
            if p not in params:
                print(f"  Hinweis: {wo} ohne Parameter '{p}' - die zugehoerige "
                      f"Prognosefrage bleibt unspezifisch.", file=sys.stderr)

        aufbereitet.append((fall, indizes, {"bewertung": m_bew, "prognose": m_prog},
                            params))

    with con:
        con.execute(
            """INSERT INTO packs (slug, titel, status, schliesst_am, angelegt_am)
               VALUES (?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET
                 titel = excluded.titel,
                 schliesst_am = excluded.schliesst_am""",
            (daten["slug"], daten["titel"], daten.get("status", "offen"),
             daten.get("schliesst_am"), db.jetzt()))
        pack_id = con.execute("SELECT id FROM packs WHERE slug = ?",
                              (daten["slug"],)).fetchone()["id"]

        for i, (fall, indizes, modell, params) in enumerate(aufbereitet, 1):
            ext = fall.get("ext_id") or f"{daten['slug']}-{i:02d}"
            con.execute(
                """INSERT INTO faelle
                     (pack_id, ext_id, name, position, jahrgang, verein, liga,
                      fuss, video_url, indizes_json, modell_json,
                      parameter_json, reihenfolge)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(pack_id, ext_id) DO UPDATE SET
                     name = excluded.name, position = excluded.position,
                     jahrgang = excluded.jahrgang, verein = excluded.verein,
                     liga = excluded.liga, fuss = excluded.fuss,
                     video_url = excluded.video_url,
                     indizes_json = excluded.indizes_json,
                     modell_json = excluded.modell_json,
                     parameter_json = excluded.parameter_json,
                     reihenfolge = excluded.reihenfolge""",
                (pack_id, ext, fall["name"], fall.get("position", ""),
                 fall.get("jahrgang"), fall.get("verein", ""),
                 fall.get("liga", ""), fall.get("fuss", ""),
                 fall.get("video_url", ""), json.dumps(indizes, ensure_ascii=False),
                 json.dumps(modell, ensure_ascii=False),
                 json.dumps(params, ensure_ascii=False), i))

    return daten["slug"], len(aufbereitet)


# ----------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="Scout League - Betrieb")
    sub = p.add_subparsers(dest="befehl", required=True)

    s = sub.add_parser("scouts", help="Scouts anlegen und Codes ausgeben")
    s.add_argument("--namen", required=True, help="kommagetrennt")
    s.add_argument("--rolle", default="scout")

    s = sub.add_parser("codes", help="alle bestehenden Codes ausgeben")

    s = sub.add_parser("pack", help="Case Pack aus JSON importieren")
    s.add_argument("--datei", required=True)

    s = sub.add_parser("status", help="Case Pack oeffnen oder schliessen")
    s.add_argument("--slug", required=True)
    s.add_argument("--auf", required=True, choices=["offen", "geschlossen"])

    s = sub.add_parser("aufloesen", help="Prognose gegen die Realitaet aufloesen")
    s.add_argument("--fall", type=int, required=True)
    s.add_argument("--frage", required=True)
    s.add_argument("--ergebnis", type=int, required=True, choices=[0, 1])
    s.add_argument("--quelle", default="")

    s = sub.add_parser("export", help="CSV auf stdout")
    s.add_argument("--slug", default=None)

    s = sub.add_parser("stand", help="Wer hat was abgegeben")
    s.add_argument("--slug", default=None)

    s = sub.add_parser("demo", help="Demo-Pack und zehn Codes anlegen")

    a = p.parse_args()
    db.schema()
    con = db.verbinden()
    try:
        if a.befehl == "scouts":
            for name, code, art in scouts_anlegen(con, a.namen.split(","), a.rolle):
                print(f"{code}  {name}" + ("" if art == "neu" else "   (bestand)"))

        elif a.befehl == "codes":
            for r in con.execute("SELECT code, name, aktiv FROM scouts ORDER BY name"):
                print(f"{r['code']}  {r['name']}"
                      + ("" if r["aktiv"] else "   (gesperrt)"))

        elif a.befehl == "pack":
            slug, n = pack_importieren(con, a.datei)
            print(f"Case Pack '{slug}' importiert: {n} Faelle.")

        elif a.befehl == "status":
            with con:
                con.execute("UPDATE packs SET status = ? WHERE slug = ?",
                            (a.auf, a.slug))
            print(f"{a.slug} ist jetzt {a.auf}.")

        elif a.befehl == "aufloesen":
            export.aufloesen(con, a.fall, a.frage, a.ergebnis, a.quelle)
            print(f"Fall {a.fall} / {a.frage} = {a.ergebnis}.")

        elif a.befehl == "export":
            sys.stdout.write(export.bewertungen_csv(con, a.slug))

        elif a.befehl == "stand":
            u = export.uebersicht(con, a.slug)
            if not u["pack"]:
                print("Kein Case Pack vorhanden.")
                return
            print(f"{u['pack']['titel']}  ({u['pack']['status']})\n")
            for f in u["faelle"]:
                print(f"  Fall {f['id']:>3}  {f['name']:<28} {f['abgaben']} Abgaben")
            print()
            for s_ in u["scouts"]:
                print(f"  {s_['code']}  {s_['name']:<22} "
                      f"{s_['abgegeben']} abgegeben, {s_['offen']} offen")

        elif a.befehl == "demo":
            slug, n = pack_importieren(
                con, os.path.join(HIER, "pakete", "demo.json"))
            namen = [f"Testscout {i}" for i in range(1, 11)]
            print(f"Demo-Pack '{slug}' mit {n} Faellen angelegt.\n")
            for name, code, _art in scouts_anlegen(con, namen):
                print(f"{code}  {name}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
