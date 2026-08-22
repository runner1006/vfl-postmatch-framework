#!/usr/bin/env python3
"""Zeichnet die Antworten eines laufenden Servers auf, damit die Vorschau
echte Daten zeigt statt erfundener.

    python3 scoutleague/cli.py demo
    SCOUTLEAGUE_ADMIN_TOKEN=... python3 scoutleague/serve.py --port 8099 &
    python3 scoutleague/vorschau_daten.py --port 8099 --token ... \
        --ziel vorschau_daten.json

Fuellt das Feld mit den uebrigen Testscouts, laesst den ersten Scout zwei von
sechs Faellen abgeben - so zeigt die Vorschau beide Zustaende - und schreibt
danach jede API-Antwort weg.
"""
import argparse
import json
import random
import urllib.request


def klient(basis):
    def ruf(pfad, koerper=None, code=None, admin=None, roh=False):
        r = urllib.request.Request(
            basis + pfad,
            data=json.dumps(koerper).encode() if koerper else None,
            method="POST" if koerper else "GET")
        r.add_header("Content-Type", "application/json")
        if code:
            r.add_header("X-Scout-Code", code)
        if admin:
            r.add_header("X-Admin-Token", admin)
        text = urllib.request.urlopen(r, timeout=15).read().decode()
        return text if roh else json.loads(text)
    return ruf


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8099)
    p.add_argument("--token", required=True, help="SCOUTLEAGUE_ADMIN_TOKEN")
    p.add_argument("--codes", required=True,
                   help="Datei mit den Scout-Codes, eine Zeile je Scout")
    p.add_argument("--ziel", default="vorschau_daten.json")
    p.add_argument("--seed", type=int, default=12)
    a = p.parse_args()

    random.seed(a.seed)
    ruf = klient(f"http://127.0.0.1:{a.port}")
    codes = [z.split()[0] for z in open(a.codes, encoding="utf-8")
             if z.split() and len(z.split()[0]) == 6]
    if len(codes) < 3:
        raise SystemExit("Mindestens drei Scout-Codes noetig.")

    pack = ruf("/api/pack", code=codes[0])
    leit, ceiling = [q["key"] for q in pack["fragebogen"]["level"]["fragen"]]
    prognosen = [q["key"] for q in pack["fragebogen"]["prognosen"]]

    def abgeben(code, fall, level, ceil, streuung):
        ruf("/api/bewertung", {
            "fall_id": fall["id"], "level": {leit: level, ceiling: ceil},
            "antworten": {at["key"]: max(1, min(5, round(
                fall["indizes"].get(at["key"], 60) / 20
                + random.gauss(0, streuung)))) for at in fall["attribute"]},
            "prognosen": {q: round(min(.95, max(.05, random.random())), 2)
                          for q in prognosen},
            "notiz": "", "sekunden": random.randint(120, 300),
            "abgeben": True}, code=code)

    # Das Feld absichtlich ungleich besetzen: einer klumpt auf eine Stufe,
    # einer ist mild, einer streng. Sonst haette der Kalibrier-Report nichts
    # zu zeigen.
    for i, code in enumerate(codes[1:]):
        for fall in pack["faelle"]:
            basis = fall["indizes"].get("profile_percentile", 60) / 12
            if i == 1:
                level = 5
            elif i == 2:
                level = max(1, min(10, round(basis + 2)))
            elif i == 3:
                level = max(1, min(10, round(basis - 2)))
            else:
                level = max(1, min(10, round(basis + random.gauss(0, 1.2))))
            abgeben(code, fall, level,
                    max(1, min(10, round(random.gauss(6.5, 1.7)))),
                    0.0 if i == 1 else 0.9)

    abgeben(codes[0], pack["faelle"][0], 7, 8, 0.8)
    abgeben(codes[0], pack["faelle"][3], 5, 6, 0.8)

    voll = ruf("/api/pack", code=codes[1])
    daten = {
        "anmelden": ruf("/api/anmelden", {"code": codes[0]}),
        "pack": ruf("/api/pack", code=codes[0]),
        "profil": ruf("/api/profil", code=codes[0]),
        "leaderboard": ruf("/api/leaderboard", code=codes[0]),
        "uebersicht": ruf("/api/admin/uebersicht", admin=a.token),
        "kalibrierung": ruf("/api/admin/kalibrierung", admin=a.token),
        "fragebogen": ruf("/api/fragebogen"),
        "csv": ruf("/api/admin/export.csv", admin=a.token, roh=True),
        # Modelle und Feldschnitte aller Faelle, gesehen von einem Scout, der
        # alles abgegeben hat - die Attrappe braucht sie fuer die Rueckmeldung
        # auf Faelle, die in der Vorschau erst noch abgegeben werden.
        "modelle": {str(f["id"]): f["modell"] for f in voll["faelle"]},
        "kohorten": {str(f["id"]): f["rueckmeldung"]["kohorte"]
                     for f in voll["faelle"]},
    }
    with open(a.ziel, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False)

    offen = sum(1 for f in daten["pack"]["faelle"]
                if not f["eigene_bewertung"]["abgegeben"])
    print(f"{a.ziel}: {len(daten['pack']['faelle'])} Faelle "
          f"({offen} offen), {len(daten['leaderboard']['zeilen'])} Scouts, "
          f"{daten['kalibrierung']['n_bewertungen']} Bewertungen im Report.")


if __name__ == "__main__":
    main()
