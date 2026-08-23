"""Admin-Seite: Ueberblick, Aufloesung, CSV-Export.

Der Export ist der eigentliche Zweck der ganzen Uebung - jede aufgeloeste
Prognose ist ein Outcome-Label. Die CSV-Zeile ist so gebaut, dass sie ohne
Nacharbeit als Trainingszeile taugt: eine Zeile je Scout x Fall x Prognose,
mit der Bewertung als Kontext daneben.
"""
import csv
import io
import json

import db
import logik


def uebersicht(con, pack_slug=None):
    pack = db.aktives_pack(con, pack_slug)
    if pack is None:
        return {"pack": None, "faelle": [], "scouts": []}
    faelle = db.faelle_von(con, pack["id"])
    fall_ids = [f["id"] for f in faelle]

    scouts = con.execute(
        "SELECT * FROM scouts WHERE aktiv = 1 ORDER BY name").fetchall()
    bew = {(b["scout_id"], b["fall_id"]): b for b in con.execute(
        "SELECT * FROM bewertungen")}
    aufl = {(r["fall_id"], r["frage"]): dict(r)
            for r in con.execute("SELECT * FROM aufloesungen")}

    return {
        "pack": {"slug": pack["slug"], "titel": pack["titel"],
                 "status": pack["status"]},
        "faelle": [{
            "id": f["id"], "name": f["name"], "verein": f["verein"],
            "abgaben": sum(1 for s in scouts
                           if (s["id"], f["id"]) in bew
                           and bew[(s["id"], f["id"])]["abgegeben"]),
            "aufloesungen": {k[1]: v["ergebnis"]
                             for k, v in aufl.items() if k[0] == f["id"]},
        } for f in faelle],
        "scouts": [{
            "id": s["id"], "name": s["name"], "code": s["code"],
            "abgegeben": sum(1 for fid in fall_ids
                             if (s["id"], fid) in bew
                             and bew[(s["id"], fid)]["abgegeben"]),
            "offen": len(fall_ids) - sum(1 for fid in fall_ids
                                         if (s["id"], fid) in bew
                                         and bew[(s["id"], fid)]["abgegeben"]),
        } for s in scouts],
    }


def aufloesen(con, fall_id, frage, ergebnis, quelle=""):
    if ergebnis not in (0, 1):
        raise ValueError("ergebnis muss 0 oder 1 sein")
    with con:
        con.execute(
            """INSERT INTO aufloesungen (fall_id, frage, ergebnis, quelle, aufgeloest_am)
               VALUES (?,?,?,?,?)
               ON CONFLICT(fall_id, frage) DO UPDATE SET
                 ergebnis = excluded.ergebnis,
                 quelle = excluded.quelle,
                 aufgeloest_am = excluded.aufgeloest_am""",
            (fall_id, frage, ergebnis, quelle, db.jetzt()))
    return {"fall_id": fall_id, "frage": frage, "ergebnis": ergebnis}


SPALTEN = [
    "pack", "fall_id", "ext_id", "spieler", "position", "positionsgruppe",
    "jahrgang", "verein", "liga", "scout", "scout_code", "abgegeben_am",
    "sekunden", "level_heute", "level_ceiling", "modell_level",
    "prognose_frage", "prognose_wahrscheinlichkeit", "modell_wahrscheinlichkeit",
    "ergebnis", "aufgeloest_am", "quelle", "notiz",
]


def bewertungen_csv(con, pack_slug=None):
    """Eine Zeile je Scout x Fall x Prognose. Die Bewertungsantworten haengen
    als eigene Spalten hinten dran, dynamisch nach Fragebogen."""
    if pack_slug:
        faelle = con.execute(
            """SELECT f.*, p.slug AS pack_slug FROM faelle f
               JOIN packs p ON p.id = f.pack_id WHERE p.slug = ?""",
            (pack_slug,)).fetchall()
    else:
        faelle = con.execute(
            """SELECT f.*, p.slug AS pack_slug FROM faelle f
               JOIN packs p ON p.id = f.pack_id""").fetchall()
    faelle = {f["id"]: f for f in faelle}

    scouts = {s["id"]: s for s in con.execute("SELECT * FROM scouts")}
    aufl = {(r["fall_id"], r["frage"]): r
            for r in con.execute("SELECT * FROM aufloesungen")}

    bew = [b for b in con.execute(
        "SELECT * FROM bewertungen WHERE abgegeben = 1 ORDER BY fall_id, scout_id")
        if b["fall_id"] in faelle]

    fragen = sorted({k for b in bew for k in json.loads(b["antworten_json"])})
    kopf = SPALTEN + [f"bew_{k}" for k in fragen]
    leit = logik.leitfrage()
    zweit = next((f["key"] for f in logik.fragebogen()["level"]["fragen"]
                  if f["key"] != leit), None)

    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=";", lineterminator="\n")
    w.writerow(kopf)

    for b in bew:
        f = faelle[b["fall_id"]]
        s = scouts.get(b["scout_id"])
        antw = json.loads(b["antworten_json"])
        lvl = json.loads(b["level_json"])
        prog = json.loads(b["prognosen_json"])
        modell_alles = json.loads(f["modell_json"]) or {}
        modell = modell_alles.get("prognose", {})
        m_level = (modell_alles.get("level") or {}).get(leit, "")
        for frage, p in sorted(prog.items()):
            a = aufl.get((f["id"], frage))
            w.writerow([
                f["pack_slug"], f["id"], f["ext_id"], f["name"], f["position"],
                logik.positionsgruppe(f["position"]),
                f["jahrgang"], f["verein"], f["liga"],
                s["name"] if s else "", s["code"] if s else "",
                b["geaendert_am"], b["sekunden"],
                lvl.get(leit, ""), lvl.get(zweit, "") if zweit else "", m_level,
                frage, p, modell.get(frage, ""),
                a["ergebnis"] if a else "", a["aufgeloest_am"] if a else "",
                a["quelle"] if a else "",
                b["notiz"].replace("\n", " "),
            ] + [antw.get(k, "") for k in fragen])

    return puffer.getvalue()
