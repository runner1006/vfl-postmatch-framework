#!/usr/bin/env python3
"""Pruefungen der Fussball-KI. Aufruf: python3 -m fussballki.tests

Kein Netz: der Claude-Forscher wird mit einem Attrappen-Client geprueft, der
die SDK-Antwort nachstellt. Die echten Spieldaten aus daten/ werden gelesen.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))

from fussballki import aufgaben, bewertung, daten, forscher, formeln, gedaechtnis, hypothese, merkmale, modelle  # noqa: E402
from fussballki.bericht import bericht_markdown, status_text  # noqa: E402
from fussballki.schleife import Schleife  # noqa: E402

BEISPIEL_A = """= Deutsche Bundesliga 2024/25

# Date       Fri Aug 23 2024 - Sat May 17 2025 (267d)

▪ Matchday 1
  Fri Aug 23 2024
    20:30  Borussia Mönchengladbach v Bayer 04 Leverkusen      2-3 (0-2)
  Sat Aug 24
    15:30  RB Leipzig              v VfL Bochum 1848          1-0 (0-0)
           1. FC Union Berlin      v VfL Bochum 1848          0-2    [awarded]
▪ Matchday 17
  Sat Jan 11
    15:30  VfL Bochum 1848         v RB Leipzig
"""

BEISPIEL_B = """= Deutsche Bundesliga 2020/21\r
\r
▪ Matchday 1\r
Fri Sep 18\r
  20:30  FC Bayern München        8-0 (3-0)  FC Schalke 04\r
Sat Sep 19\r
  15:30  1. FC Köln               2-3 (1-2)  TSG 1899 Hoffenheim\r
                  (Tor 12', Tor 44')\r
Wed Mar 11\r
  18:30  Werder Bremen            1-1 (0-0)  Hertha BSC\r
Sat Feb 27\r
  15:30  SC Freiburg              0-1 (0-1)  VfB Stuttgart\r
"""


class Parser(unittest.TestCase):
    def _lese(self, text, liga, saison):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, saison, "x.txt")
            os.makedirs(os.path.dirname(p))
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            return daten.lese_datei(p, liga, saison)

    def test_format_a_mit_awarded_und_offen(self):
        sp = self._lese(BEISPIEL_A, 1, "2024-25")
        self.assertEqual(len(sp), 4)
        self.assertEqual((sp[0].heim, sp[0].gast, sp[0].tore_heim, sp[0].tore_gast), ("mönchengladbach", "bayer leverkusen", 2, 3))
        self.assertEqual(sp[0].datum, dt.date(2024, 8, 23))
        self.assertEqual(sp[1].datum, dt.date(2024, 8, 24))
        self.assertEqual((sp[2].heim, sp[2].gast, sp[2].hinweis), ("union berlin", "bochum", "awarded"))
        self.assertEqual(sp[3].datum, dt.date(2025, 1, 11))
        self.assertFalse(sp[3].gespielt)
        self.assertIsNone(sp[3].ergebnis)
        self.assertEqual([s.ergebnis for s in sp[:3]], [2, 0, 2])

    def test_format_b_mit_crlf_und_nachholspiel(self):
        sp = self._lese(BEISPIEL_B, 1, "2020-21")
        self.assertEqual(len(sp), 4)
        self.assertEqual((sp[0].heim, sp[0].gast, sp[0].tore_heim), ("bayern münchen", "schalke", 8))
        self.assertEqual(sp[2].datum, dt.date(2021, 3, 11))
        self.assertEqual(sp[3].datum, dt.date(2021, 2, 27))
        self.assertEqual((sp[3].heim, sp[3].gast, sp[3].ergebnis), ("freiburg", "stuttgart", 2))

    def test_schluessel(self):
        for a, b in [("FC Bayern München", "Bayern München"), ("TSG 1899 Hoffenheim", "1899 Hoffenheim"),
                     ("Borussia M'gladbach", "Bor. Mönchengladbach"), ("FC St. Pauli 1910", "St. Pauli"),
                     ("1. FC Heidenheim 1846", "Heidenheim"), ("SpVgg Greuther Fürth 1903", "SpVgg Greuther Fürth")]:
            self.assertEqual(daten.schluessel(a), daten.schluessel(b), (a, b))
        self.assertNotEqual(daten.schluessel("TSV 1860 München"), daten.schluessel("Bayern München"))
        self.assertNotEqual(daten.schluessel("Eintracht Frankfurt"), daten.schluessel("FSV Frankfurt"))

    def test_schnappschuss(self):
        sp = daten.lade_spiele()
        self.assertGreater(len(sp), 9000)
        self.assertEqual(daten.pruefe_konsistenz(sp), [])
        self.assertEqual([s.id for s in sp[:3]], [1, 2, 3])
        self.assertTrue(all(sp[i].datum <= sp[i + 1].datum for i in range(len(sp) - 1)))
        self.assertTrue(any(not s.gespielt for s in sp))


class Formeln(unittest.TestCase):
    def test_erlaubt(self):
        self.assertEqual(formeln.pruefen("a - b * 2 + sqrt(abs(c))", {"a", "b", "c"}), {"a", "b", "c"})
        self.assertAlmostEqual(formeln.auswerten("max(a, b) / (abs(b) + 0.5)", {"a": 1, "b": -1}), 1 / 1.5)

    def test_verboten(self):
        for f in ("__import__('os')", "a.b", "a[0]", "lambda: 1", "open('x')", "a if a else b",
                  "print(a)", "x", "True"):
            with self.assertRaises(formeln.FormelFehler, msg=f):
                formeln.pruefen(f, {"a", "b"})

    def test_rechenfehler(self):
        self.assertIsNone(formeln.auswerten("a / b", {"a": 1, "b": 0}))
        self.assertIsNone(formeln.auswerten("log(a)", {"a": -1}))
        self.assertIsNone(formeln.auswerten("a + b", {"a": 1, "b": None}))


class Modelle(unittest.TestCase):
    def test_logit_findet_gewichte(self):
        rnd = np.random.RandomState(3)
        X = rnd.normal(size=(6000, 2))
        p = 1 / (1 + np.exp(-(0.5 + 1.5 * X[:, 0] - 1.0 * X[:, 1])))
        y = (rnd.uniform(size=6000) < p).astype(int)
        m = modelle.Logit(l2=0.01).fit(X, y, 2)
        self.assertAlmostEqual(-m.B[0][1], 1.5, delta=0.15)
        self.assertAlmostEqual(-m.B[0][2], -1.0, delta=0.15)
        self.assertTrue(np.allclose(m.predict_proba(X).sum(axis=1), 1.0))

    def test_poisson_findet_raten(self):
        rnd = np.random.RandomState(4)
        X = rnd.normal(size=(6000, 2))
        tore = np.stack([rnd.poisson(np.exp(0.4 + 0.3 * X[:, 0])), rnd.poisson(np.exp(0.1 - 0.2 * X[:, 1]))], axis=1)
        m = modelle.Poisson(l2=0.01).fit(X, K=3, tore=tore)
        self.assertAlmostEqual(m.beta_heim[1], 0.3, delta=0.05)
        self.assertAlmostEqual(m.beta_gast[2], -0.2, delta=0.05)
        P = m.predict_proba(X)
        self.assertTrue(np.allclose(P.sum(axis=1), 1.0))
        erg = np.where(tore[:, 0] > tore[:, 1], 0, np.where(tore[:, 0] == tore[:, 1], 1, 2))
        self.assertLess(modelle.log_loss(erg, P), modelle.log_loss(erg, np.tile(np.bincount(erg) / len(erg), (len(erg), 1))))
        m2 = modelle.Poisson(l2=0.01).fit(X, K=2, tore=tore)
        self.assertAlmostEqual(float(m2.predict_proba(X)[:, 1].mean()), float((tore.sum(1) >= 3).mean()), delta=0.02)

    def test_mlp_lernt_xor(self):
        X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]] * 25, dtype=float)
        y = np.array([0, 1, 1, 0] * 25)
        m = modelle.MLP(versteckt=6, l2=0.0, lernrate=0.05, epochen=300, seed=1).fit(X, y, 2)
        self.assertGreater(modelle.trefferquote(y, m.predict_proba(X)), 0.95)

    def test_json_roundtrip(self):
        rnd = np.random.RandomState(5)
        X = rnd.normal(size=(300, 3))
        y = np.where(X[:, 0] > 0.5, 0, np.where(X[:, 1] > 0, 1, 2))
        tore = rnd.poisson(1.5, size=(300, 2))
        for m in (modelle.Logit(l2=0.5).fit(X, y, 3), modelle.MLP(epochen=20).fit(X, y, 3),
                  modelle.Poisson().fit(X, K=3, tore=tore)):
            r = modelle.modell_aus_dict(json.loads(json.dumps(m.als_dict())))
            self.assertTrue(np.allclose(r.predict_proba(X[:5]), m.predict_proba(X[:5])))

    def test_metriken(self):
        self.assertAlmostEqual(modelle.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]), 0.75)
        self.assertAlmostEqual(modelle.auc([0, 1, 0, 1], [0.5] * 4), 0.5)
        self.assertIsNone(modelle.auc([0, 0], [0.1, 0.2]))
        self.assertAlmostEqual(modelle.log_loss([0, 1], [[0.5, 0.5], [0.5, 0.5]]), 0.6931, places=3)
        self.assertAlmostEqual(modelle.brier([1], [[0.2, 0.8]]), 0.08)
        s = modelle.Standardisierer().fit(np.array([[1.0, np.nan], [3.0, 4.0], [np.nan, 6.0]]))
        self.assertTrue(np.allclose(s.transform(np.array([[2.0, np.nan]])), [[0.0, 0.0]]))


class Merkmale(unittest.TestCase):
    def test_leckfrei_und_symmetrisch(self):
        sp = daten.lade_spiele()
        M = merkmale.berechne(sp)
        self.assertEqual(len(M), len(sp))
        self.assertEqual(set(M[0]), set(merkmale.MERKMALE))
        # Merkmale eines Spiels aendern sich nicht, wenn spaetere Spiele fehlen
        n = 4000
        M2 = merkmale.berechne(sp[:n])
        self.assertEqual(M[n - 1], M2[n - 1])
        self.assertEqual(M[100], M2[100])
        # erstes Spiel: kein Verlauf
        self.assertIsNone(M[0]["form5_punkte_heim"])
        self.assertIsNone(M[0]["ruhetage_heim"])
        self.assertEqual(M[0]["elo_diff"], 0.0)
        # Elo-Erwartung zwischen 0 und 1, Elo-Summe erhalten
        self.assertTrue(all(0 < m["elo_erwartung"] < 1 for m in M))
        elo = merkmale.elo_stand(sp)
        self.assertEqual(max(elo, key=elo.get), "bayern münchen")

    def test_paarungsmerkmale(self):
        sp = [s for s in daten.lade_spiele() if s.gespielt]
        k = daten.Spiel(id=0, saison=sp[-1].saison, liga=1, spieltag=5, datum=sp[-1].datum + dt.timedelta(days=3),
                        heim="bochum", gast="schalke", heim_name="Bochum", gast_name="Schalke")
        m = merkmale.berechne(sp + [k])[-1]
        self.assertGreater(m["spiele_gesamt_heim"], 300)
        self.assertGreaterEqual(m["ruhetage_heim"], 3.0)
        self.assertEqual(m["liga"], 1.0)


class Aufgaben(unittest.TestCase):
    def test_tabellen(self):
        t = aufgaben.lade("ergebnis")
        self.assertEqual(sorted(set(t.labels())), [0, 1, 2])
        self.assertGreater(len(t.offen), 0)
        self.assertTrue(all(z["label"] is None for z in t.offen))
        t2 = aufgaben.lade("tore")
        self.assertEqual(sorted(set(t2.labels())), [0, 1])
        self.assertEqual(len(t2), len(t))
        self.assertIn("elo_diff", aufgaben.katalog(t))
        n = aufgaben.naechste_spiele(t, limit=5)
        self.assertEqual(len(n), 5)
        self.assertTrue(all(z["extra"]["datum"] >= max(x["extra"]["datum"] for x in t.zeilen) for z in n))


class Bewertung(unittest.TestCase):
    def test_saisonplan_und_falten(self):
        t = aufgaben.lade("ergebnis")
        tests, pruef, laufend = bewertung.saisonplan(t)
        self.assertEqual(tests[0], "2015-16")
        self.assertLess(tests[-1], pruef)
        self.assertTrue(laufend is None or laufend > pruef)
        for train, test, saison in bewertung.falten(t):
            self.assertTrue(all(t.zeilen[i]["gruppe"] < saison for i in train))
            self.assertTrue(all(t.zeilen[i]["gruppe"] == saison for i in test))

    def test_startpaket_schlaegt_basisrate(self):
        for aufgabe in aufgaben.AUFGABEN:
            t = aufgaben.lade(aufgabe)
            bewertung.benchmarks(t)
            self.assertLess(t.benchmark["logloss_elo"], t.benchmark["logloss_basis"])
            for v in hypothese.startpaket(aufgabe):
                h, fehler = hypothese.pruefen(v, t)
                self.assertEqual(fehler, [], v["name"])
                e = bewertung.bewerten(t, h)
                self.assertLess(e["metriken"]["logloss"], e["metriken"]["logloss_basis"])
                self.assertIn("logloss_elo", e["metriken"])
                self.assertEqual(e["pruefsaison"], t.benchmark["pruefsaison"])
            endm = bewertung.endmodell(t, h)
            z = t.zeilen[-1]
            p = bewertung.vorhersagen(endm, z["merkmale"], z["gruppe"])
            self.assertAlmostEqual(sum(v for k, v in p.items() if not k.startswith("_")), 1.0, places=3)
            self.assertIn("koeffizienten", endm)

    def test_hypothesen_pruefung(self):
        t = aufgaben.lade("ergebnis")
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": ["tore_heim"]}, t)
        self.assertIsNone(h)
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": ["elo_diff"], "modell": {"typ": "poisson", "l2": 0.5}}, t)
        self.assertEqual(fehler, [])
        self.assertEqual(h["modell"], {"typ": "poisson", "l2": 0.5})
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": [], "abgeleitet": [{"name": "b", "formel": "__import__('os')"}]}, t)
        self.assertIsNone(h)


class Schleifen(unittest.TestCase):
    def test_offline_schleife(self):
        with tempfile.TemporaryDirectory() as d:
            ged = gedaechtnis.Gedaechtnis(d)
            s = Schleife(forscher.OfflineForscher(seed=0), ged, aufgaben=("tore",), vorschlaege=2,
                         ausgabe=lambda *a: None)
            verlauf = s.lernen(2)
            self.assertEqual([v["runde"] for v in verlauf], [1, 2])
            self.assertTrue(ged.bestes("tore"))
            self.assertGreaterEqual(len(ged.experimente("tore", nur_ok=True)), 3)
            self.assertIn("Aufgabe tore", ged.erkenntnisse())
            self.assertEqual(ged.naechste_runde(), 3)
            self.assertIn("Runden gelernt: 2", status_text(ged))
            self.assertIn("## Aufgabe `tore`", bericht_markdown(ged))
            kenn = [e["hypothese"]["kennung"] for e in ged.experimente("tore", nur_ok=True)]
            self.assertEqual(len(kenn), len(set(kenn)))

    def test_claude_forscher_mit_attrappe(self):
        anfragen = []

        class Block:
            type = "text"
            def __init__(self, text):
                self.text = text

        class Antwort:
            def __init__(self, text):
                self.content = [Block(text)]
                self.stop_reason = "end_turn"
                self.usage = None

        class Messages:
            def create(self, **kw):
                anfragen.append(kw)
                if kw.get("output_config", {}).get("format"):
                    return Antwort(json.dumps({"hypothesen": [
                        {"name": "Test", "begruendung": "b", "merkmale": ["elo_diff", "form5_punkte_diff"],
                         "abgeleitet": [{"name": "q", "formel": "elo_diff * form5_punkte_diff"}],
                         "modell": {"typ": "poisson", "l2": 2.0, "versteckt": 8, "epochen": 100, "lernrate": 0.02},
                         "standardisierung": "gruppe", "erwartung": "e"},
                        {"name": "Kaputt", "begruendung": "b", "merkmale": ["tore_heim"], "abgeleitet": [],
                         "modell": {"typ": "logit", "l2": 1, "versteckt": 8, "epochen": 100, "lernrate": 0.02},
                         "standardisierung": "global", "erwartung": "e"}]}))
                return Antwort("# Erkenntnisse\n\n## Aufgabe ergebnis\n\n### Was traegt\n- elo_diff\n")

        class Beta:
            messages = Messages()

        class Client:
            beta = Beta()

        f = forscher.ClaudeForscher(modell="claude-opus-5", client=Client())
        with tempfile.TemporaryDirectory() as d:
            ged = gedaechtnis.Gedaechtnis(d)
            Schleife(f, ged, aufgaben=("ergebnis",), vorschlaege=2, ausgabe=lambda *a: None).lernen(1)
            exps = ged.experimente("ergebnis")
            self.assertEqual([e["status"] for e in exps], ["ok", "abgelehnt"])
            self.assertEqual(exps[0]["hypothese"]["modell"]["typ"], "poisson")
            self.assertTrue(ged.erkenntnisse().startswith("<!-- geschrieben von claude:claude-opus-5"))
        erste = anfragen[0]
        self.assertEqual(erste["model"], "claude-opus-5")
        self.assertEqual(erste["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", erste["betas"])
        self.assertEqual(erste["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(erste["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertIn("Elo-Logit", erste["messages"][0]["content"])

    def test_ausfall_faengt_ersatz(self):
        class Kaputt:
            name = "claude:kaputt"
            def vorschlagen(self, k):
                raise forscher.ForscherFehler("kein Netz")
            def reflektieren(self, k):
                raise forscher.ForscherFehler("kein Netz")
        with tempfile.TemporaryDirectory() as d:
            ged = gedaechtnis.Gedaechtnis(d)
            Schleife(Kaputt(), ged, aufgaben=("tore",), vorschlaege=1, ausgabe=lambda *a: None).lernen(1)
            e = ged.experimente("tore")
            self.assertEqual(len(e), 1)
            self.assertIn("Ersatz", e[0]["forscher"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
