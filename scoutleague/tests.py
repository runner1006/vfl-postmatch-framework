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
import modell    # noqa: E402

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

    # ---- Audit-Block
    z = metriken.zentraltendenz([3, 3, 3, 3, 3, 3, 4, 5])
    pruefe(z["modalwert"] == 3 and nah(z["anteil"], 0.75),
           "Zentraltendenz findet Modalwert und Anteil")
    pruefe(z["genutzte_stufen"] == 3, "Zentraltendenz zaehlt genutzte Stufen")
    pruefe(metriken.zentraltendenz([]) is None, "Zentraltendenz ohne Werte")

    st = metriken.rater_strenge({"streng": [2, 3, 2, 3], "mild": [4, 5, 4, 5]})
    pruefe(nah(st["spanne"], 2.0), "Rater-Strenge misst die Spanne")
    pruefe(st["strengster"] == "streng" and st["mildester"] == "mild",
           "Rater-Strenge benennt strengsten und mildesten Scout")
    pruefe(metriken.rater_strenge({"nur_einer": [3, 4]})["spanne"] is None,
           "Rater-Strenge braucht zwei Scouts")

    pruefe(nah(metriken.pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0),
           "Pearson = 1 bei linearem Zusammenhang")
    pruefe(metriken.pearson([3, 3, 3, 3], [1, 2, 3, 4]) is None,
           "Pearson = None bei konstanter Seite")
    pruefe(nah(metriken.halo([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1.0),
           "Halo = 1, wenn das Urteil das Attribut-Mittel spiegelt")

    zs = metriken.z_werte([2, 4, 6])
    pruefe(zs is not None and nah(sum(zs), 0.0, 1e-9),
           "z-Werte mitteln sich zu null")
    pruefe(metriken.z_werte([3, 3, 3]) is None,
           "z-Werte ohne Streuung nicht definiert")

    at = metriken.attribut_trennschaerfe(
        {"lebendig": [1, 3, 5, 2, 4], "tot": [3, 3, 3, 3, 3]}, 0.4)
    pruefe(at["tot"]["tot"] is True and at["lebendig"]["tot"] is False,
           "tote Attribute werden erkannt")

    pruefe(metriken.konflikt(8, 5, 2)["richtung"] == "scout_hoeher",
           "Konflikt: Scout hoeher")
    pruefe(metriken.konflikt(4, 7, 2)["richtung"] == "modell_hoeher",
           "Konflikt: Modell hoeher")
    pruefe(metriken.konflikt(6, 5, 2) is None,
           "kein Konflikt unter dem Schwellenabstand")

    # Bruecke Perzentil -> Level (Audit, Kapitel 9)
    pruefe(metriken.perzentil_zu_level(95, 6) == 7.0,
           "Perzentil 95 hebt das Liga-Niveau um eine Stufe")
    pruefe(metriken.perzentil_zu_level(60, 6) == 6.0,
           "Perzentil im Mittelfeld laesst das Niveau stehen")
    pruefe(metriken.perzentil_zu_level(5, 6) == 5.0,
           "Perzentil 5 senkt das Niveau um eine Stufe")
    pruefe(metriken.perzentil_zu_level(99, 10) == 10.0,
           "Bruecke bleibt in der Skala")

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


def test_modell():
    """Die Ableitung aus dem Export. Geprueft wird vor allem, wo sie sich
    weigert - eine erfundene Modellerwartung ist schlimmer als eine leere."""
    print("\nModellableitung")

    # Robustes Einlesen
    pruefe(modell.zahl("61,40") == 61.4, "deutsche Kommazahl")
    pruefe(modell.zahl("1.234,5") == 1234.5, "Tausenderpunkt und Komma")
    pruefe(modell.zahl("72%") == 72.0, "Prozentzeichen")
    pruefe(modell.zahl("") is None and modell.zahl("-") is None,
           "leere Zellen ergeben None, nicht 0")

    # Spalten finden, egal wie sie geschrieben sind
    kopf = ["Player", "Position", "Team", "Competition", "Season",
            "Minutes played", "Birthday", "Default Index", "xG Assist",
            "Smart passes per 90"]
    sp, fehlt = modell.spalten_finden(kopf)
    pruefe(sp["spieler"] == "Player" and sp["minuten"] == "Minutes played",
           "Spalten werden ueber Schreibweisen hinweg gefunden")
    pruefe(sp["index"] == "Default Index", "Default Index wird als Index erkannt")
    pruefe("alter" in fehlt, "fehlende Spalten werden gemeldet, nicht geraten")
    sp2, _ = modell.spalten_finden(["spieler", "minuten_gespielt", "wettbewerb"])
    pruefe(sp2.get("spieler") == "spieler" and sp2.get("liga") == "wettbewerb",
           "auch deutsche Spaltennamen")

    # Perzentil
    pool = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    pruefe(nah(modell.perzentil(10, pool), 95.0), "hoechster Wert -> Perzentil 95")
    pruefe(nah(modell.perzentil(1, pool), 5.0), "niedrigster Wert -> Perzentil 5")
    pruefe(modell.perzentil(5, [3]) is None, "Perzentil braucht mehr als einen Wert")
    pruefe(nah(modell.perzentil(5, [5, 5, 5, 5]), 50.0),
           "bei lauter gleichen Werten liegt jeder in der Mitte")

    # Perzentil -> Note, mit Spreizung an den Raendern
    noten = [modell.perzentil_zu_note(p) for p in (2, 20, 50, 80, 97)]
    pruefe(noten == [1, 2, 3, 4, 5], f"Perzentilbaender treffen 1-5 (hat {noten})")
    pruefe(modell.perzentil_zu_note(None) is None, "ohne Perzentil keine Note")

    # Liga-Register
    name, stufe, _e = modell.liga_aufloesen("Germany. 2. Bundesliga")
    pruefe(name == "2. Bundesliga" and stufe == 7, "Alias trifft die Audit-Stufe")
    name, stufe, eintrag = modell.liga_aufloesen("Primera RFEF")
    pruefe(name == "Primera Federación" and stufe is None,
           "nicht eingeordnete Liga liefert None statt einer geratenen Zahl")
    pruefe(eintrag and eintrag.get("offen"),
           "und nennt, was zur Einordnung fehlt")
    _n, stufe, _e = modell.liga_aufloesen("Gibt Es Nicht FC Liga")
    pruefe(stufe is None, "unbekannte Liga bricht nicht, sie bleibt leer")

    # Level heute
    pruefe(modell.level_heute(7, 95) == 8.0,
           "Spitzenperzentil hebt um eine Stufe")
    pruefe(modell.level_heute(7, 55) == 7.0, "Mittelfeld laesst die Stufe stehen")
    pruefe(modell.level_heute(None, 95) is None,
           "ohne Liga-Niveau kein Level - das ist der Kern")

    # Ceiling
    pruefe(modell.ceiling(6, 18) > modell.ceiling(6, 28),
           "junger Spieler bekommt mehr Spielraum als ein alter")
    pruefe(modell.ceiling(6, 32) < 6, "jenseits der Peakjahre kippt es")
    pruefe(modell.ceiling(6, 20, trend=0.2) > modell.ceiling(6, 20, trend=-0.2),
           "steigender Verlauf hebt, fallender senkt")
    pruefe(modell.ceiling(10, 18) == 10.0, "das Ceiling bleibt in der Skala")
    pruefe(modell.ceiling(4, 17, trend=0.9) - 4 <= modell.MAX_ZUWACHS,
           "der Zuwachs ist gedeckelt - ein optimistisches Modell liesse das "
           "ganze Feld pessimistisch aussehen")
    pruefe(modell.ceiling(6, 24) == 6.0,
           "im Peakalter ohne Verlauf bleibt das Ceiling auf dem Niveau")
    pruefe(modell.ceiling(None, 20) is None and modell.ceiling(6, None) is None,
           "ohne Level oder ohne Alter kein Ceiling")

    # Poolpruefung: der wichtigste Teil - wann verweigert sie?
    def pool_zeilen(n, minuten=900, liga="Germany. 3. Liga"):
        return [{"Player": f"S{i}", "Minutes played": str(minuten),
                 "Competition": liga, "Default Index": str(0.5 + i / 100)}
                for i in range(n)]
    sp, _ = modell.spalten_finden(["Player", "Minutes played", "Competition",
                                   "Default Index"])

    gut = modell.pool_pruefen(pool_zeilen(60), sp)
    pruefe(gut["brauchbar"] and gut["zeilen_im_pool"] == 60,
           "voller Ligapool gilt als brauchbar")

    klein = modell.pool_pruefen(pool_zeilen(8), sp)
    pruefe(not klein["brauchbar"], "acht Zeilen sind kein Pool")

    kuratiert = modell.pool_pruefen(
        pool_zeilen(40) + pool_zeilen(3, minuten=25), sp)
    pruefe(not kuratiert["brauchbar"]
           and any("handverlesen" in g for g in kuratiert["gruende"]),
           "Zeilen unter 60 Minuten verraten einen handverlesenen Export")

    gemischt = modell.pool_pruefen(
        sum([pool_zeilen(12, liga=f"Liga {i}") for i in range(4)], []), sp)
    pruefe(any("Wettbewerbe" in g for g in gemischt["gruende"]),
           "Perzentil ueber vier Ligen hinweg wird abgelehnt")

    ohne_minuten, _ = modell.spalten_finden(["Player", "Competition"])
    blind = modell.pool_pruefen(pool_zeilen(60), ohne_minuten)
    pruefe(any("Minutenspalte" in g for g in blind["gruende"]),
           "ohne Minutenspalte greift der 400-Minuten-Filter nicht, und das "
           "wird gesagt")

    # Spielermodell: Attribute ohne Datenzuordnung bleiben leer
    pool_werte = {"xG Assist": [0.1 * i for i in range(20)]}
    m = modell.spieler_modell(
        [{"xG Assist": "1.5"}], pool_werte, 7,
        {"letzter_pass": "xG Assist", "mentalitaet": "Gibt Es Nicht"},
        gesamt_perzentil=92.0, alter=20)
    # 1.5 liegt im Pool 0.0-1.9 auf Perzentil 77.5, also im Band 65-90 -> 4
    pruefe(m["bewertung"].get("letzter_pass") == 4,
           f"Attribut mit Daten bekommt eine Note "
           f"(hat {m['bewertung'].get('letzter_pass')}, "
           f"P{m['attribut_perzentile'].get('letzter_pass')})")
    pruefe("mentalitaet" not in m["bewertung"]
           and "mentalitaet" in m["attribute_ohne_daten"],
           "Attribut ohne Kennzahl bleibt leer und wird als Luecke gefuehrt")
    pruefe(m["level_heute"] == 8.0 and m["level_ceiling"] == 9.0,
           f"spieler_modell liefert Level und Ceiling "
           f"(hat {m['level_heute']}/{m['level_ceiling']})")
    ohne_p = modell.spieler_modell([{"xG Assist": "1.5"}], pool_werte, 7,
                                   {"letzter_pass": "xG Assist"})
    pruefe(ohne_p["level_heute"] is None,
           "ohne Gesamtperzentil kein Level - nicht aus einem Attribut geraten")

    # Ganzer Export von Platte
    tmp = tempfile.mkdtemp(prefix="scoutleague-export-")
    pfad = os.path.join(tmp, "export-99.csv")
    with open(pfad, "w", encoding="utf-8-sig", newline="") as f:
        f.write("Player;Position;Competition;Minutes played;Default Index\n")
        for i in range(40):
            f.write(f"Spieler {i};CF;Germany. 2. Bundesliga;{900 + i};"
                    f"{0.40 + i / 200:.3f}\n")
    gelesen = modell.export_lesen(pfad)
    pruefe(len(gelesen) == 40 and gelesen[0]["Player"] == "Spieler 0",
           "semikolongetrennter utf-8-sig-Export wird korrekt gelesen")
    sp3, _ = modell.spalten_finden(list(gelesen[0]))
    werte = [modell.zahl(z[sp3["index"]]) for z in gelesen]
    p_letzter = modell.perzentil(werte[-1], werte)
    pruefe(p_letzter > 95, "der beste Spieler des Pools liegt oben")
    pruefe(modell.level_heute(7, p_letzter) == 8.0,
           "und landet damit eine Stufe ueber dem Liganiveau")

    # Methodenblatt
    text = modell.bericht(klein, {"MLS"}, {"mentalitaet"}, {"top5_12m"})
    for pflicht in ("Pool nicht belastbar", "Liga-Niveau", "Ceiling",
                    "MLS", "mentalitaet", "top5_12m"):
        pruefe(pflicht in text, f"Methodenblatt nennt {pflicht}")


def test_kleine_stichprobe():
    """Unter der Mindestzahl darf der Report nichts diagnostizieren - ein Scout
    mit einer Bewertung hat per Konstruktion 100 % auf einer Stufe, und das
    als Zentraltendenz zu melden waere Rauschen als Befund verkauft."""
    print("\nKleine Stichprobe")
    tmp = tempfile.mkdtemp(prefix="scoutleague-klein-")
    umgebung = dict(os.environ, SCOUTLEAGUE_DB=os.path.join(tmp, "k.db"),
                    SCOUTLEAGUE_ADMIN_TOKEN="t")
    cli = [sys.executable, os.path.join(HIER, "cli.py")]
    subprocess.run(cli + ["pack", "--datei", os.path.join(HIER, "pakete", "demo.json")],
                   env=umgebung, check=True, capture_output=True)
    aus = subprocess.run(cli + ["scouts", "--namen", "Solo"],
                         env=umgebung, check=True, capture_output=True, text=True)
    code = aus.stdout.split()[0]

    port = 8932
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
        _st, pack = k.hole("/api/pack", code=code)
        lk = [q["key"] for q in pack["fragebogen"]["level"]["fragen"]]
        prognosen = [p["key"] for p in pack["fragebogen"]["prognosen"]]
        f0 = pack["faelle"][0]
        k.sende("/api/bewertung", {
            "fall_id": f0["id"], "level": {lk[0]: 7, lk[1]: 8},
            "antworten": {a["key"]: 3 for a in f0["attribute"]},
            "prognosen": {p: 0.5 for p in prognosen}, "abgeben": True}, code=code)

        _st, kr = k.hole("/api/admin/kalibrierung", admin="t")
        pruefe(kr["n_bewertungen"] == 1, "eine Bewertung im Report")
        pruefe(any("Momentaufnahme" in w for w in kr["warnungen"]),
               "Report weist die duenne Datenlage aus")
        pruefe(len(kr["warnungen"]) == 1,
               "und diagnostiziert sonst nichts (100 % auf einer Stufe waere "
               "hier kein Befund)")

        _st, prof = k.hole("/api/profil", code=code)
        pruefe(prof["zentraltendenz"]["anteil"] == 1.0,
               "die Rohzahl steht trotzdem da")
        pruefe(prof["halo"] is None and prof["entkopplung"] is None,
               "Halo und Entkopplung bleiben leer statt geraten")
        pruefe(prof["schwellen"]["mindest_faelle_diagnose"] >= 3,
               "das Frontend bekommt die Mindestzahl mitgeliefert")
    finally:
        server.terminate()
        server.wait(timeout=5)


def test_ende_zu_ende():
    print("\nEnde zu Ende")
    tmp = tempfile.mkdtemp(prefix="scoutleague-test-")
    dbpfad = os.path.join(tmp, "test.db")
    umgebung = dict(os.environ, SCOUTLEAGUE_DB=dbpfad,
                    SCOUTLEAGUE_ADMIN_TOKEN="testtoken")

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

        # ---------------------------------------------------------- Anmeldung
        pruefe(k.sende("/api/anmelden", {"code": "GIBTSNICHT"})[0] == 401,
               "unbekannter Code wird abgewiesen")
        st, a = k.sende("/api/anmelden", {"code": codes[0]})
        pruefe(st == 200 and a["name"] == "Anna", "gueltiger Code meldet an")
        pruefe(k.hole("/api/pack")[0] == 401, "Pack ohne Code gesperrt")

        st, pack = k.hole("/api/pack", code=codes[0])
        pruefe(st == 200 and len(pack["faelle"]) == 6, "Pack liefert sechs Faelle")
        pruefe(all("modell" not in f for f in pack["faelle"]),
               "Modell bleibt vor der Abgabe verborgen")

        # ------------------------------------------------- Positions-Sets
        gruppen = {f["positionsgruppe"] for f in pack["faelle"]}
        pruefe(gruppen == {"CB", "WB", "CM", "WF", "AM", "CF"},
               f"alle sechs Positionsgruppen im Pack (hat {sorted(gruppen)})")
        cb = next(f for f in pack["faelle"] if f["positionsgruppe"] == "CB")
        cf = next(f for f in pack["faelle"] if f["positionsgruppe"] == "CF")
        cb_keys = {a["key"] for a in cb["attribute"]}
        cf_keys = {a["key"] for a in cf["attribute"]}
        pruefe(len(cb["attribute"]) == 8 and len(cf["attribute"]) == 8,
               "jede Position bekommt acht Attribute")
        pruefe("kopfball" in cb_keys and "kopfball" not in cf_keys,
               "Positions-Set trennt: kopfball nur beim Innenverteidiger")
        pruefe({"technik", "spielintelligenz", "athletik", "mentalitaet"}
               <= cb_keys & cf_keys, "Kern-Set gilt fuer alle Positionen")

        # ------------------------------------------------------ Level-Skala
        stufen = pack["fragebogen"]["level"]["stufen"]
        pruefe(len(stufen) == 10, "Level-Skala hat zehn Stufen")
        pruefe(all(s_.get("ligen") and s_.get("marktwert") for s_ in stufen),
               "jede Level-Stufe traegt Liga-Anker und Marktwertband")
        pruefe(len(pack["fragebogen"]["level"]["fragen"]) == 2,
               "zwei getrennte Level-Fragen")

        level_keys = [q["key"] for q in pack["fragebogen"]["level"]["fragen"]]
        prognosen = [p["key"] for p in pack["fragebogen"]["prognosen"]]
        fall = pack["faelle"][0]
        fall_keys = [a["key"] for a in fall["attribute"]]

        # ------------------------------------------------------ Validierung
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "level": {level_keys[0]: 11}},
                        code=codes[0])
        pruefe(st == 400 and "Skala" in a["fehler"], "Level ausserhalb 1-10")
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "antworten": {fall_keys[0]: 9}},
                        code=codes[0])
        pruefe(st == 400 and "Skala" in a["fehler"], "Attribut ausserhalb 1-5")
        fremd = "kopfball" if fall["positionsgruppe"] != "CB" else "abschluss"
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "antworten": {fremd: 3}},
                        code=codes[0])
        pruefe(st == 400 and "Position" in a["fehler"],
               "Attribut fremder Position wird abgelehnt")
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "prognosen": {prognosen[0]: 1.4}},
                        code=codes[0])
        pruefe(st == 400, "Prognose ausserhalb 0-1")
        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "level": {level_keys[0]: 6},
                         "abgeben": True}, code=codes[0])
        pruefe(st == 400 and "fehlen" in a["fehler"],
               "unvollstaendige Abgabe wird abgelehnt")

        st, a = k.sende("/api/bewertung",
                        {"fall_id": fall["id"], "level": {level_keys[0]: 6}},
                        code=codes[0])
        pruefe(st == 200 and a["abgegeben"] is False, "Zwischenstand wird gesichert")
        st, pack2 = k.hole("/api/pack", code=codes[0])
        pruefe(pack2["faelle"][0]["eigene_bewertung"]["level"][level_keys[0]] == 6,
               "Zwischenstand kommt zurueck")

        # --------------------------------------------------------- Abgaben
        # Anna spreizt und trifft, Bela klumpt auf Level 5, Cem liegt daneben,
        # Dora liegt dazwischen. Das erzeugt genau die Muster, die der Audit
        # diagnostiziert.
        levels = {codes[0]: [8, 4, 7, 3, 6, 5],
                  codes[1]: [5, 5, 5, 5, 5, 5],
                  codes[2]: [3, 8, 2, 9, 4, 7],
                  codes[3]: [6, 5, 7, 4, 6, 5]}
        attr = {codes[0]: [5, 2, 4, 1, 3, 3],
                codes[1]: [3, 3, 3, 3, 3, 3],
                codes[2]: [2, 5, 1, 5, 2, 4],
                codes[3]: [4, 3, 4, 2, 3, 3]}
        wahrsch = {codes[0]: [0.9, 0.8, 0.2, 0.1, 0.7, 0.6],
                   codes[1]: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
                   codes[2]: [0.1, 0.2, 0.8, 0.9, 0.3, 0.4],
                   codes[3]: [0.6, 0.6, 0.4, 0.4, 0.6, 0.5]}
        for code in levels:
            for i, f_ in enumerate(pack["faelle"]):
                keys = [a["key"] for a in f_["attribute"]]
                st, a = k.sende("/api/bewertung", {
                    "fall_id": f_["id"],
                    "level": {level_keys[0]: levels[code][i],
                              level_keys[1]: min(10, levels[code][i] + 1)},
                    "antworten": {q: attr[code][i] for q in keys},
                    "prognosen": {p: wahrsch[code][i] for p in prognosen},
                    "notiz": "Test", "sekunden": 42, "abgeben": True,
                }, code=code)
                if st != 200:
                    pruefe(False, f"Abgabe {code}/{f_['id']}: {a}")
                    break
        else:
            pruefe(True, "alle 24 Abgaben angenommen")

        st, a = k.sende("/api/bewertung", {
            "fall_id": pack["faelle"][0]["id"],
            "level": {q: 5 for q in level_keys},
            "antworten": {q: 2 for q in fall_keys},
            "prognosen": {p: 0.5 for p in prognosen}, "abgeben": True},
            code=codes[0])
        pruefe(st == 409, "abgegebener Fall bleibt gesperrt")

        # ------------------------------------------------- Sofort-Rueckmeldung
        st, pack3 = k.hole("/api/pack", code=codes[0])
        f0 = pack3["faelle"][0]
        r = f0["rueckmeldung"]
        pruefe("modell" in f0, "nach Abgabe wird das Modell sichtbar")
        pruefe(r["modell_naehe"] is not None, "Rueckmeldung traegt die Modell-Naehe")
        pruefe(r["attribut_mittel"] is not None, "Rueckmeldung traegt das Attribut-Mittel")
        pruefe(r["level_abstand"] is not None, "Rueckmeldung traegt den Level-Abstand")
        pruefe(r["kohorte"]["n"] == 4, "Feldvergleich zaehlt alle vier Abgaben")
        pruefe("mittel_bereinigt" in r["kohorte"],
               "Feldvergleich weist den rater-bereinigten Schnitt aus")

        # Anna sagt Level 8, das Modell 6.5 -> Abstand 1.5, kein Konflikt.
        # Cem sagt 3 -> Abstand -3.5, das ist einer.
        st, packc = k.hole("/api/pack", code=codes[2])
        kf = packc["faelle"][0]["rueckmeldung"]["konflikt"]
        pruefe(kf is not None and kf["richtung"] == "modell_hoeher",
               "Konfliktfall wird im Frontend markiert")

        # -------------------------------------------------------- Profil
        st, prof_flach = k.hole("/api/profil", code=codes[1])
        pruefe(prof_flach["spreizung"] == 0.0, "flacher Scout hat Spreizung 0")
        pruefe(prof_flach["zentraltendenz"]["anteil"] == 1.0,
               "flacher Scout: 100 % auf einer Stufe")
        pruefe(prof_flach["verteilung"]["5"] == 6,
               "Verteilung laeuft ueber die Level-Skala")
        st, prof_anna = k.hole("/api/profil", code=codes[0])
        pruefe(prof_anna["spreizung"] > 1.5, "gespreizter Scout hat hohe Spreizung")
        pruefe(prof_anna["halo"] is not None, "Profil weist den Halo aus")
        pruefe(prof_anna["entkopplung"] is not None,
               "Profil weist die Entkopplung aus")
        pruefe(prof_anna["zentraltendenz"]["genutzte_stufen"] == 6,
               "gespreizter Scout nutzt sechs Stufen")

        # Annas Attribute laufen mit ihren Leveln -> hoher Halo.
        pruefe(prof_anna["halo"] > 0.9,
               f"Halo entlarvt das Echo-Urteil (r={prof_anna['halo']})")

        # ------------------------------------------------------ Leaderboard
        st, lb = k.hole("/api/leaderboard", code=codes[0])
        pruefe(lb["aufgeloest"] is False, "vor Aufloesung: vorlaeufige Rangfolge")
        pruefe(len(lb["zeilen"]) == 4, "Leaderboard listet vier Scouts")
        pruefe(all("halo" in z for z in lb["zeilen"]),
               "Leaderboard traegt den Halo je Scout")
        flach = next(z for z in lb["zeilen"] if z["name"] == "Bela")
        pruefe(flach["rang"] == 4, "der flache Scout steht hinten")

        # ----------------------------------------------------------- Admin
        pruefe(k.hole("/api/admin/uebersicht")[0] == 401, "Admin ohne Token gesperrt")
        st, u = k.hole("/api/admin/uebersicht", admin="testtoken")
        pruefe(st == 200 and all(s_["abgegeben"] == 6 for s_ in u["scouts"]),
               "Admin sieht sechs Abgaben je Scout")

        # -------------------------------------------------- Kalibrier-Report
        pruefe(k.hole("/api/admin/kalibrierung")[0] == 401,
               "Kalibrier-Report ohne Token gesperrt")
        st, kr = k.hole("/api/admin/kalibrierung", admin="testtoken")
        pruefe(st == 200 and kr["n_bewertungen"] == 24,
               "Kalibrier-Report rechnet auf allen 24 Bewertungen")
        pruefe(kr["n_scouts"] == 4, "Kalibrier-Report kennt vier Scouts")

        zt = kr["zentraltendenz"][level_keys[0]]
        pruefe(zt["n"] == 24 and 0 < zt["anteil"] <= 1,
               "Zentraltendenz im Report ist plausibel")
        pruefe(kr["rater_strenge"]["spanne"] is not None,
               "Rater-Strenge im Report hat eine Spanne")
        pruefe(kr["halo"]["gesamt"] is not None
               and len(kr["halo"]["je_scout"]) == 4,
               "Halo gesamt und je Scout")
        pruefe(kr["entkopplung"]["gesamt"] is not None,
               "Entkopplung wird gerechnet")
        pruefe(set(kr["attribute"]) == {"CB", "WB", "CM", "WF", "AM", "CF"},
               "Attribut-Trennschaerfe je Positionsgruppe")
        pruefe(all(v["n"] == 4 for g in kr["attribute"].values()
                   for v in g.values()),
               "jedes Attribut traegt vier Bewertungen")
        svm = kr["scout_vs_modell"]
        pruefe(svm["gesamt"] is not None, "Scout gegen Modell wird gerechnet")
        pruefe(all(v == 1 for v in svm["n_faelle_je_gruppe"].values()),
               "Report weist die Fallzahl je Gruppe aus")
        pruefe(all(r is None for r in svm["je_gruppe"].values()),
               "bei einem Fall je Gruppe bleibt die Korrelation leer statt zu "
               "raten")
        pruefe(len(kr["konflikte"]) > 0, "Konfliktliste ist gefuellt")
        pruefe(all(abs(c["differenz"]) >= 2 for c in kr["konflikte"]),
               "jeder Konflikt liegt ueber dem Schwellenabstand")
        pruefe(abs(kr["konflikte"][0]["differenz"])
               >= abs(kr["konflikte"][-1]["differenz"]),
               "Konflikte sind nach Abstand sortiert")
        pruefe(isinstance(kr["warnungen"], list) and len(kr["warnungen"]) > 0,
               "Report formuliert Warnungen im Klartext")
        pruefe(not any("Momentaufnahme" in w for w in kr["warnungen"]),
               "bei 24 Bewertungen keine Momentaufnahme-Warnung")

        # Bela klumpt auf eine Stufe -> muss als Zentraltendenz auffallen
        pruefe(kr["rater_strenge"]["je_scout"]["Bela"] == 5.0,
               "Rater-Strenge weist Belas Klumpen bei 5 aus")

        # -------------------------------------------------------- Aufloesen
        for i, erg in enumerate([1, 1, 0, 0, 1, 1]):
            for p in prognosen:
                st, _ = k.sende("/api/admin/aufloesen",
                                {"fall_id": pack["faelle"][i]["id"], "frage": p,
                                 "ergebnis": erg, "quelle": "test"},
                                admin="testtoken")
                if st != 200:
                    pruefe(False, f"Aufloesung {i}/{p} fehlgeschlagen")
        pruefe(True, "alle 18 Aufloesungen angenommen")

        st, lb2 = k.hole("/api/leaderboard", code=codes[0])
        pruefe(lb2["aufgeloest"] is True, "nach Aufloesung: endgueltige Rangfolge")
        pruefe(lb2["zeilen"][0]["name"] == "Anna",
               f"der treffsichere Scout fuehrt "
               f"({[z['name'] for z in lb2['zeilen']]})")
        anna = lb2["zeilen"][0]
        cem = next(z for z in lb2["zeilen"] if z["name"] == "Cem")
        pruefe(anna["brier"] < cem["brier"],
               "wer richtig lag, hat den kleineren Brier")
        pruefe(anna["brier_skill"] > 0 > cem["brier_skill"],
               "Skill trennt besser-als-Basisrate von schlechter")

        # ---------------------------------------------------------- Export
        st, csv = k.hole("/api/admin/export.csv", admin="testtoken", roh=True)
        zeilen = csv.strip().split("\n")
        pruefe(st == 200 and len(zeilen) == 1 + 4 * 6 * 3,
               f"CSV hat Kopf + 72 Zeilen (hat {len(zeilen) - 1})")
        kopf = zeilen[0].split(";")
        for spalte in ("level_heute", "level_ceiling", "modell_level",
                       "positionsgruppe", "ergebnis"):
            pruefe(spalte in kopf, f"CSV traegt die Spalte {spalte}")
        i_erg = kopf.index("ergebnis")
        i_lvl = kopf.index("level_heute")
        pruefe(all(z.split(";")[i_erg] in ("0", "1") for z in zeilen[1:]),
               "jede CSV-Zeile traegt ein Outcome-Label")
        pruefe(all(1 <= int(z.split(";")[i_lvl]) <= 10 for z in zeilen[1:]),
               "jede CSV-Zeile traegt ein Level in der Skala")

        # ------------------------------------------------------- Pack zu
        k.sende("/api/admin/pack_status", {"slug": "demo", "status": "geschlossen"},
                admin="testtoken")
        st, a = k.sende("/api/bewertung", {"fall_id": pack["faelle"][0]["id"]},
                        code=codes[2])
        pruefe(st == 409, "geschlossenes Pack nimmt nichts mehr an")

        st, _ = k.hole("/", roh=True)
        pruefe(st == 200, "Startseite wird ausgeliefert")
        pruefe(k.hole("/../db.py", roh=True)[0] == 404,
               "Pfadausbruch aus /static wird geblockt")

    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    test_metriken()
    test_modell()
    test_ende_zu_ende()
    test_kleine_stichprobe()
    print(f"\n{GEPRUEFT[0]} Pruefungen, {len(FEHLER)} Fehler")
    if FEHLER:
        for f in FEHLER:
            print("  - " + f)
        sys.exit(1)
