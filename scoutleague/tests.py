#!/usr/bin/env python3
"""Pruefungen fuer die Scout League.

    python3 scoutleague/tests.py

Zwei Bloecke: die Metrik-Mathematik gegen von Hand gerechnete Werte, und ein
End-to-End-Lauf gegen einen echt gestarteten Server auf einer Wegwerf-Datenbank.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import metriken  # noqa: E402

FEHLER = []
GEPRUEFT = [0]


def pruefe(bedingung, text):
    GEPRUEFT[0] += 1
    if bedingung:
        print(f"  ok    {text}")
    else:
        print(f"  FEHL  {text}")
        FEHLER.append(text)


def nah(a, b, eps=1e-6):
    return a is not None and abs(a - b) < eps


# ------------------------------------------------------------------- Metriken
def test_metriken():
    print("\nMetriken")

    pruefe(nah(metriken.mittel([1, 2, 3]), 2.0), "Mittel")
    pruefe(nah(metriken.stdabw([2, 4, 4, 4, 5, 5, 7, 9]), 2.13808993529939, 1e-9),
           "Stichproben-Standardabweichung")
    pruefe(metriken.stdabw([3]) is None, "Standardabweichung braucht zwei Werte")

    # Brier: (0.8-1)^2 + (0.3-0)^2 = 0.04 + 0.09 = 0.13, /2 = 0.065
    pruefe(nah(metriken.brier([(0.8, 1), (0.3, 0)]), 0.065),
           "Brier gegen Handrechnung")
    pruefe(nah(metriken.brier([(1.0, 1), (0.0, 0)]), 0.0), "Brier: perfekt = 0")
    pruefe(nah(metriken.brier([(0.5, 1), (0.5, 0)]), 0.25), "Brier: Muenzwurf = 0.25")
    pruefe(metriken.brier([]) is None, "Brier ohne Paare = None")

    # Skill: Basisrate 0.5, Basis-Brier 0.25, eigener 0.065 -> 1 - 0.26 = 0.74
    pruefe(nah(metriken.brier_skill([(0.8, 1), (0.3, 0)], 0.5), 0.74, 1e-3),
           "Brier-Skill gegen Basisrate")
    pruefe(metriken.brier_skill([(0.5, 1), (0.5, 0)], 0.5) == 0.0,
           "Skill = 0, wenn genau die Basisrate gesagt wurde")

    # Kalibrierung: wer 100% sagt und recht hat, hat Fehler 0
    pruefe(nah(metriken.kalibrierungsfehler([(1.0, 1), (1.0, 1)]), 0.0),
           "Kalibrierungsfehler 0 bei perfekter Sicherheit")
    pruefe(nah(metriken.kalibrierungsfehler([(1.0, 0), (1.0, 0)]), 1.0),
           "Kalibrierungsfehler 1 bei maximaler Fehlsicherheit")
    kurve = metriken.kalibrierungskurve([(0.1, 0), (0.9, 1)])
    pruefe(sum(b["n"] for b in kurve) == 2, "Kalibrierungskurve zaehlt alle Paare")

    # Spearman
    pruefe(nah(metriken.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0),
           "Spearman = 1 bei gleicher Reihenfolge")
    pruefe(nah(metriken.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0),
           "Spearman = -1 bei umgekehrter Reihenfolge")
    pruefe(metriken.spearman([3, 3, 3, 3], [1, 2, 3, 4]) is None,
           "Spearman = None, wenn eine Seite konstant ist")
    pruefe(metriken.spearman([1, 2], [1, 2]) is None,
           "Spearman braucht mindestens drei Punkte")

    # Modell-Naehe
    pruefe(nah(metriken.modell_naehe({"a": 3}, {"a": 3}), 100.0),
           "Modell-Naehe 100 bei Treffer")
    pruefe(nah(metriken.modell_naehe({"a": 1}, {"a": 5}), 0.0),
           "Modell-Naehe 0 bei maximalem Abstand")
    pruefe(metriken.modell_naehe({"a": 3}, {}) is None,
           "Modell-Naehe None ohne Modellerwartung")
    pruefe(nah(metriken.prognose_naehe({"p": 0.7}, {"p": 0.7}), 100.0),
           "Prognose-Naehe 100 bei Treffer")

    # Spreizung
    pruefe(nah(metriken.spreizung([3, 3, 3, 3]), 0.0),
           "Spreizung 0, wenn alles dieselbe Note ist")
    pruefe(metriken.spreizung([1, 5]) > 2.8, "Spreizung gross bei Extremen")
    pruefe(nah(metriken.spreizungs_index(1.0, 2.0), 0.5),
           "Spreizungs-Index gegen Kohorte")

    # Basisraten
    raten = metriken.basisraten({(1, "x"): 1, (2, "x"): 0, (3, "x"): 1})
    pruefe(nah(raten["x"], 2 / 3), "Basisrate je Frage")

    # Gesamtbild eines Scouts
    abgaben = [
        {"fall_id": 1, "antworten": {"gesamt": 4}, "prognosen": {"p": 0.9},
         "modell": {"bewertung": {"gesamt": 4}, "prognose": {"p": 0.5}}},
        {"fall_id": 2, "antworten": {"gesamt": 2}, "prognosen": {"p": 0.1},
         "modell": {"bewertung": {"gesamt": 3}, "prognose": {"p": 0.5}}},
        {"fall_id": 3, "antworten": {"gesamt": 5}, "prognosen": {"p": 0.8},
         "modell": {"bewertung": {"gesamt": 5}, "prognose": {"p": 0.5}}},
    ]
    aufl = {(1, "p"): 1, (2, "p"): 0, (3, "p"): 1}
    m = metriken.scout_metriken(abgaben, {}, aufl)
    pruefe(m["n_faelle"] == 3, "scout_metriken zaehlt Faelle")
    pruefe(m["n_aufgeloest"] == 3, "scout_metriken zaehlt aufgeloeste Prognosen")
    pruefe(nah(m["trennschaerfe"], 1.0), "Trennschaerfe 1 bei gleicher Rangfolge")
    pruefe(m["brier"] < 0.03, "guter Prognostiker hat kleinen Brier")
    skill = metriken.skill_gesamt(m["_paare_je_frage"], metriken.basisraten(aufl))
    pruefe(skill > 0.8, "guter Prognostiker hat hohen Skill")

    # Der Scout, der ueberall die 3 vergibt
    flach = [{"fall_id": i, "antworten": {"gesamt": 3}, "prognosen": {},
              "modell": {"bewertung": {"gesamt": i}, "prognose": {}}}
             for i in range(1, 5)]
    mf = metriken.scout_metriken(flach, {}, {})
    pruefe(nah(mf["spreizung"], 0.0), "flacher Scout: Spreizung 0")
    pruefe(mf["trennschaerfe"] is None,
           "flacher Scout: keine Trennschaerfe messbar")


# ---------------------------------------------------------------- End to End
class Klient:
    def __init__(self, basis):
        self.basis = basis

    def hole(self, pfad, code=None, admin=None, roh=False):
        return self._ruf("GET", pfad, None, code, admin, roh)

    def sende(self, pfad, koerper, code=None, admin=None):
        return self._ruf("POST", pfad, koerper, code, admin, False)

    def _ruf(self, methode, pfad, koerper, code, admin, roh):
        daten = json.dumps(koerper).encode() if koerper is not None else None
        r = urllib.request.Request(self.basis + pfad, data=daten, method=methode)
        r.add_header("Content-Type", "application/json")
        if code:
            r.add_header("X-Scout-Code", code)
        if admin:
            r.add_header("X-Admin-Token", admin)
        try:
            with urllib.request.urlopen(r, timeout=10) as a:
                text = a.read().decode()
                return a.status, (text if roh else json.loads(text))
        except urllib.error.HTTPError as e:
            text = e.read().decode()
            try:
                return e.code, json.loads(text)
            except ValueError:
                return e.code, text


def test_ende_zu_ende():
    print("\nEnde zu Ende")
    tmp = tempfile.mkdtemp(prefix="scoutleague-test-")
    dbpfad = os.path.join(tmp, "test.db")
    umgebung = dict(os.environ, SCOUTLEAGUE_DB=dbpfad,
                    SCOUTLEAGUE_ADMIN_TOKEN="testtoken")

    # Scouts und Pack ueber die CLI - derselbe Weg wie im Betrieb
    cli = [sys.executable, os.path.join(HIER, "cli.py")]
    subprocess.run(cli + ["pack", "--datei", os.path.join(HIER, "pakete", "demo.json")],
                   env=umgebung, check=True, capture_output=True)
    aus = subprocess.run(cli + ["scouts", "--namen", "Anna,Bela,Cem,Dora"],
                         env=umgebung, check=True, capture_output=True, text=True)
    codes = [z.split()[0] for z in aus.stdout.strip().splitlines()]
    pruefe(len(codes) == 4 and len(set(codes)) == 4, "CLI legt vier eigene Codes an")

    port = 8931
    server = subprocess.Popen(
        [sys.executable, os.path.join(HIER, "serve.py"), "--port", str(port),
         "--host", "127.0.0.1"],
        env=umgebung, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    k = Klient(f"http://127.0.0.1:{port}")
    try:
        for _ in range(60):
            try:
                if k.hole("/api/fragebogen")[0] == 200:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("Server ist nicht hochgekommen")

        # Anmeldung
        pruefe(k.sende("/api/anmelden", {"code": "GIBTSNICHT"})[0] == 401,
               "unbekannter Code wird abgewiesen")
        st, a = k.sende("/api/anmelden", {"code": codes[0]})
        pruefe(st == 200 and a["name"] == "Anna", "gueltiger Code meldet an")
        pruefe(k.hole("/api/pack")[0] == 401, "Pack ohne Code gesperrt")

        st, pack = k.hole("/api/pack", code=codes[0])
        pruefe(st == 200 and len(pack["faelle"]) == 5, "Pack liefert fuenf Faelle")
        pruefe(all("modell" not in f for f in pack["faelle"]),
               "Modell bleibt vor der Abgabe verborgen")
        pruefe(len(pack["fragebogen"]["bewertung"]["fragen"]) == 8,
               "Fragebogen kommt mit")

        fall = pack["faelle"][0]
        fragen = [q["key"] for q in pack["fragebogen"]["bewertung"]["fragen"]]
        prognosen = [p["key"] for p in pack["fragebogen"]["prognosen"]]

        # Validierung
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "antworten": {fragen[0]: 9},
                         "prognosen": {}}, code=codes[0])
        pruefe(st == 400 and "Skala" in a["fehler"], "Bewertung ausserhalb der Skala")
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "antworten": {},
                         "prognosen": {prognosen[0]: 1.4}}, code=codes[0])
        pruefe(st == 400, "Prognose ausserhalb 0-1")
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "antworten": {fragen[0]: 3},
                         "prognosen": {}, "abgeben": True}, code=codes[0])
        pruefe(st == 400 and "fehlen" in a["fehler"],
               "unvollstaendige Abgabe wird abgelehnt")

        # Zwischenstand
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "antworten": {fragen[0]: 3},
                         "prognosen": {}}, code=codes[0])
        pruefe(st == 200 and a["abgegeben"] is False, "Zwischenstand wird gesichert")
        st, pack2 = k.hole("/api/pack", code=codes[0])
        pruefe(pack2["faelle"][0]["eigene_bewertung"]["antworten"][fragen[0]] == 3,
               "Zwischenstand kommt zurueck")

        # Vollstaendige Abgaben: vier Scouts, jeder mit eigenem Muster
        muster = {
            codes[0]: [5, 4, 3, 2, 1],   # gut gespreizt
            codes[1]: [3, 3, 3, 3, 3],   # der flache Scout
            codes[2]: [1, 2, 3, 4, 5],   # gespreizt, andere Reihenfolge
            codes[3]: [4, 4, 2, 5, 3],
        }
        wahrscheinlichkeiten = {
            codes[0]: [0.9, 0.8, 0.2, 0.1, 0.7],
            codes[1]: [0.5, 0.5, 0.5, 0.5, 0.5],
            codes[2]: [0.1, 0.2, 0.8, 0.9, 0.3],
            codes[3]: [0.6, 0.6, 0.4, 0.4, 0.6],
        }
        for code, noten in muster.items():
            for i, fall_ in enumerate(pack["faelle"]):
                st, a = k.sende("/api/bewertung", {
                    "fall_id": fall_["id"],
                    "antworten": {q: noten[i] for q in fragen},
                    "prognosen": {p: wahrscheinlichkeiten[code][i] for p in prognosen},
                    "notiz": "Test", "sekunden": 42, "abgeben": True,
                }, code=code)
                if st != 200:
                    pruefe(False, f"Abgabe {code}/{fall_['id']}: {a}")
                    break
        else:
            pruefe(True, "alle 20 Abgaben angenommen")

        st, a = k.sende("/api/bewertung", {
            "fall_id": pack["faelle"][0]["id"],
            "antworten": {q: 2 for q in fragen},
            "prognosen": {p: 0.5 for p in prognosen}, "abgeben": True},
            code=codes[0])
        pruefe(st == 409, "abgegebener Fall bleibt gesperrt")

        st, pack3 = k.hole("/api/pack", code=codes[0])
        f0 = pack3["faelle"][0]
        pruefe("modell" in f0, "nach Abgabe wird das Modell sichtbar")
        pruefe(f0["rueckmeldung"]["modell_naehe"] is not None,
               "Sofort-Rueckmeldung enthaelt die Modell-Naehe")
        pruefe(f0["rueckmeldung"]["kohorte"]["n"] == 4,
               "Feldvergleich zaehlt alle vier Abgaben")

        # Profil
        st, prof = k.hole("/api/profil", code=codes[1])
        pruefe(prof["spreizung"] == 0.0, "flacher Scout hat Spreizung 0")
        pruefe(prof["verteilung"]["3"] == 5, "Verteilung zaehlt fuenf Dreier")
        st, prof0 = k.hole("/api/profil", code=codes[0])
        pruefe(prof0["spreizung"] > 1.0, "gespreizter Scout hat Spreizung > 1")
        pruefe(prof0["bias"] is not None, "Bias gegen das Feld wird gerechnet")

        # Leaderboard vor der Aufloesung
        st, lb = k.hole("/api/leaderboard", code=codes[0])
        pruefe(lb["aufgeloest"] is False, "vor Aufloesung: vorlaeufige Rangfolge")
        pruefe(len(lb["zeilen"]) == 4, "Leaderboard listet vier Scouts")
        pruefe([z["rang"] for z in lb["zeilen"]] == [1, 2, 3, 4], "Raenge sind gesetzt")
        flach_zeile = next(z for z in lb["zeilen"] if z["name"] == "Bela")
        pruefe(flach_zeile["rang"] == 4, "der flache Scout steht hinten")

        # Admin
        pruefe(k.hole("/api/admin/uebersicht")[0] == 401, "Admin ohne Token gesperrt")
        st, u = k.hole("/api/admin/uebersicht", admin="testtoken")
        pruefe(st == 200 and len(u["scouts"]) == 4, "Admin-Uebersicht listet Scouts")
        pruefe(all(s["abgegeben"] == 5 for s in u["scouts"]),
               "Admin sieht fuenf Abgaben je Scout")

        # Aufloesen: Faelle 1, 2, 5 treten ein, 3 und 4 nicht
        for i, erg in enumerate([1, 1, 0, 0, 1]):
            for p in prognosen:
                st, _ = k.sende("/api/admin/aufloesen",
                                {"fall_id": pack["faelle"][i]["id"], "frage": p,
                                 "ergebnis": erg, "quelle": "test"},
                                admin="testtoken")
                if st != 200:
                    pruefe(False, f"Aufloesung {i}/{p} fehlgeschlagen")
        pruefe(True, "alle 15 Aufloesungen angenommen")

        st, lb2 = k.hole("/api/leaderboard", code=codes[0])
        pruefe(lb2["aufgeloest"] is True, "nach Aufloesung: endgueltige Rangfolge")
        namen = [z["name"] for z in lb2["zeilen"]]
        pruefe(namen[0] == "Anna",
               f"der treffsichere Scout fuehrt (Reihenfolge: {namen})")
        anna = lb2["zeilen"][0]
        cem = next(z for z in lb2["zeilen"] if z["name"] == "Cem")
        pruefe(anna["brier"] < cem["brier"],
               "wer richtig lag, hat den kleineren Brier")
        pruefe(anna["brier_skill"] > 0 > cem["brier_skill"],
               "Skill trennt besser-als-Basisrate von schlechter")
        pruefe(lb2["basisraten"][prognosen[0]] == 0.6,
               "Basisrate = 3 von 5 Faellen")

        # Export
        st, csv = k.hole("/api/admin/export.csv", admin="testtoken", roh=True)
        zeilen = csv.strip().split("\n")
        pruefe(st == 200 and len(zeilen) == 1 + 4 * 5 * 3,
               f"CSV hat Kopf + 60 Zeilen (hat {len(zeilen) - 1})")
        pruefe("prognose_wahrscheinlichkeit" in zeilen[0] and "ergebnis" in zeilen[0],
               "CSV enthaelt Prognose und Ergebnis")
        pruefe(all(z.split(";")[15] in ("0", "1") for z in zeilen[1:]),
               "jede CSV-Zeile traegt ein Outcome-Label")

        # Pack schliessen sperrt weitere Abgaben
        k.sende("/api/admin/pack_status", {"slug": "demo", "status": "geschlossen"},
                admin="testtoken")
        st, a = k.sende("/api/bewertung", {
            "fall_id": pack["faelle"][0]["id"], "antworten": {}, "prognosen": {}},
            code=codes[2])
        pruefe(st == 409, "geschlossenes Pack nimmt nichts mehr an")

        # Statische Auslieferung
        st, _ = k.hole("/", roh=True)
        pruefe(st == 200, "Startseite wird ausgeliefert")
        pruefe(k.hole("/../db.py", roh=True)[0] == 404,
               "Pfadausbruch aus /static wird geblockt")

    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    test_metriken()
    test_ende_zu_ende()
    print(f"\n{GEPRUEFT[0]} Pruefungen, {len(FEHLER)} Fehler")
    if FEHLER:
        for f in FEHLER:
            print("  - " + f)
        sys.exit(1)
