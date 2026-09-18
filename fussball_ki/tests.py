#!/usr/bin/env python3
"""Pruefungen der Fussball-KI. Aufruf: python3 -m fussball_ki.tests

Reine Standardbibliothek, kein Netz: der Claude-Forscher wird mit einem
Attrappen-Client geprueft, der die SDK-Antwort nachstellt.
"""
import json
import os
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))

from fussball_ki import bewertung, daten, forscher, gedaechtnis, hypothese, modelle  # noqa: E402
from fussball_ki.bericht import bericht_markdown, status_text  # noqa: E402
from fussball_ki.schleife import Schleife  # noqa: E402


class Formeln(unittest.TestCase):
    def test_erlaubte_arithmetik(self):
        self.assertEqual(daten.formel_pruefen("a - b * 2 + sqrt(abs(c))", {"a", "b", "c"}), {"a", "b", "c"})
        self.assertAlmostEqual(daten.formel_auswerten("a - b * 2", {"a": 5, "b": 1}), 3.0)
        self.assertAlmostEqual(daten.formel_auswerten("max(a, b) / (abs(b) + 0.5)", {"a": 1, "b": -1}), 1 / 1.5)

    def test_verbotenes(self):
        for f in ("__import__('os')", "a.b", "a[0]", "lambda: 1", "open('x')", "a if a else b",
                  "print(a)", "a = 1", "x", "a ** b ** c ** d if 1 else 2"):
            with self.assertRaises(daten.FormelFehler, msg=f):
                daten.formel_pruefen(f, {"a", "b", "c", "d"})

    def test_rechenfehler_werden_none(self):
        self.assertIsNone(daten.formel_auswerten("a / b", {"a": 1, "b": 0}))
        self.assertIsNone(daten.formel_auswerten("log(a)", {"a": -1}))
        self.assertIsNone(daten.formel_auswerten("a + b", {"a": 1, "b": None}))


class Modelle(unittest.TestCase):
    def test_logit_lernt_bekannte_gewichte(self):
        import math
        import random
        rnd = random.Random(3)
        X = [[rnd.gauss(0, 1), rnd.gauss(0, 1)] for _ in range(5000)]
        y = []
        for a, b in X:
            p = 1 / (1 + math.exp(-(0.5 + 1.5 * a - 1.0 * b)))
            y.append(1 if rnd.random() < p else 0)
        m = modelle.Logit(l2=0.01).fit(X, y, 2)
        # B[0] beschreibt Klasse 0 gegen Referenz 1 -> Vorzeichen gedreht
        self.assertAlmostEqual(-m.B[0][1], 1.5, delta=0.2)
        self.assertAlmostEqual(-m.B[0][2], -1.0, delta=0.2)
        p = m.predict_proba(X)
        self.assertTrue(all(abs(sum(pi) - 1) < 1e-9 for pi in p))

    def test_multinomial_und_json_roundtrip(self):
        import random
        rnd = random.Random(5)
        X = [[rnd.gauss(0, 1) for _ in range(3)] for _ in range(200)]
        y = [0 if x[0] > 0.5 else (1 if x[1] > 0 else 2) for x in X]
        m = modelle.Logit(l2=0.5).fit(X, y, 3)
        m2 = modelle.modell_aus_dict(json.loads(json.dumps(m.als_dict())))
        self.assertEqual(m.predict_proba(X[:5]), m2.predict_proba(X[:5]))
        self.assertGreater(modelles_treffer(y, m.predict_proba(X)), 0.8)

    def test_mlp_lernt_xor(self):
        X = [[0, 0], [0, 1], [1, 0], [1, 1]] * 25
        y = [0, 1, 1, 0] * 25
        m = modelle.MLP(versteckt=6, l2=0.0, lernrate=0.05, epochen=300, seed=1).fit(X, y, 2)
        self.assertGreater(modelles_treffer(y, m.predict_proba(X)), 0.95)
        m2 = modelle.modell_aus_dict(json.loads(json.dumps(m.als_dict())))
        self.assertEqual(m.predict_proba(X[:4]), m2.predict_proba(X[:4]))

    def test_metriken(self):
        self.assertAlmostEqual(modelle.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]), 0.75)
        self.assertAlmostEqual(modelle.auc([0, 1, 0, 1], [0.5] * 4), 0.5)
        self.assertIsNone(modelle.auc([0, 0], [0.1, 0.2]))
        self.assertAlmostEqual(modelle.log_loss([0, 1], [[0.5, 0.5], [0.5, 0.5]]), 0.6931, places=3)
        self.assertAlmostEqual(modelle.brier([1], [[0.2, 0.8]]), 0.08)

    def test_standardisierer_imputiert(self):
        s = modelle.Standardisierer().fit([[1.0, None], [3.0, 4.0], [None, 6.0]])
        z = s.transform([[2.0, None]])[0]
        self.assertAlmostEqual(z[0], 0.0)
        self.assertAlmostEqual(z[1], 0.0)


def modelles_treffer(y, p):
    return modelle.trefferquote(y, p)


class Daten(unittest.TestCase):
    def test_spiele(self):
        t = daten.lade("spiel")
        self.assertEqual(len(t), 298)
        self.assertEqual(sorted(set(t.labels())), [0, 1, 2])
        self.assertNotIn("tore", t.merkmale)
        self.assertNotIn("psieg", t.merkmale)
        self.assertIn("geg_off", t.merkmale)
        self.assertIn("logloss", t.benchmark)
        # zeitlich sortiert
        zeiten = [z["zeit"] for z in t.zeilen]
        self.assertEqual(zeiten, sorted(zeiten))

    def test_saisons(self):
        t = daten.lade("aufstieg")
        self.assertEqual(len(t), 162)
        self.assertEqual(sum(t.labels()), 27)
        self.assertNotIn("punkte", t.merkmale)
        self.assertIn("auc_mittel", t.benchmark)


class Hypothesen(unittest.TestCase):
    def setUp(self):
        self.t = daten.lade("spiel")

    def test_startpaket_ist_gueltig(self):
        for aufgabe in daten.AUFGABEN:
            t = daten.lade(aufgabe)
            for v in hypothese.startpaket(aufgabe):
                h, fehler = hypothese.pruefen(v, t)
                self.assertEqual(fehler, [], v["name"])
                self.assertEqual(len(h["kennung"]), 10)

    def test_ablehnung(self):
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": ["tore"], "modell": {"typ": "logit"}}, self.t)
        self.assertIsNone(h)
        self.assertTrue(any("tore" in f for f in fehler))
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": ["npxg"],
                                       "abgeleitet": [{"name": "npxg", "formel": "npxg*2"}]}, self.t)
        self.assertTrue(any("kollidiert" in f for f in fehler))
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": [],
                                       "abgeleitet": [{"name": "boese", "formel": "__import__('os')"}]}, self.t)
        self.assertIsNone(h)
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": ["npxg"], "modell": {"typ": "svm"}}, self.t)
        self.assertTrue(any("Modelltyp" in f for f in fehler))

    def test_klemmen_und_kennung(self):
        h, fehler = hypothese.pruefen({"name": "x", "merkmale": ["npxg"], "modell": {"typ": "mlp", "l2": -5,
                                       "versteckt": 999, "epochen": 1, "lernrate": 9}}, self.t)
        self.assertEqual(fehler, [])
        self.assertEqual(h["modell"]["versteckt"], 32)
        self.assertEqual(h["modell"]["epochen"], 20)
        h2, _ = hypothese.pruefen({"name": "anders", "merkmale": ["npxg"], "modell": {"typ": "mlp", "l2": -5,
                                   "versteckt": 999, "epochen": 1, "lernrate": 9}}, self.t)
        self.assertEqual(h["kennung"], h2["kennung"])  # Name zaehlt nicht


class Bewertung(unittest.TestCase):
    def test_falten_fest_und_disjunkt(self):
        t = daten.lade("spiel")
        lern, pruef = bewertung.lern_und_pruefmenge(t)
        self.assertEqual(len(lern) + len(pruef), 298)
        self.assertLess(max(lern), min(pruef))
        f1, f2 = bewertung.falten(t, lern), bewertung.falten(t, lern)
        self.assertEqual(f1, f2)
        for train, test in f1:
            self.assertFalse(set(train) & set(test))
            self.assertFalse(set(test) & set(pruef))
        t2 = daten.lade("aufstieg")
        lern2, pruef2 = bewertung.lern_und_pruefmenge(t2)
        self.assertEqual({t2.zeilen[i]["gruppe"] for i in pruef2}, {"2025/26"})
        self.assertEqual(len(bewertung.falten(t2, lern2)), 8)

    def test_bewertung_schlaegt_basisrate(self):
        t = daten.lade("spiel")
        h, _ = hypothese.pruefen(hypothese.startpaket("spiel")[0], t)
        e = bewertung.bewerten(t, h)
        self.assertLess(e["metriken"]["logloss"], e["metriken"]["logloss_basis"])
        self.assertIn("logloss_framework", e["metriken"])
        self.assertEqual(e["n_lern"], 238)
        endm = bewertung.endmodell(t, h)
        p = bewertung.vorhersagen(endm, t.zeilen[0]["merkmale"], t.zeilen[0]["gruppe"])
        self.assertAlmostEqual(sum(p.values()), 1.0, places=3)
        self.assertIn("koeffizienten", endm)

    def test_aufstieg_metriken(self):
        t = daten.lade("aufstieg")
        h, _ = hypothese.pruefen(hypothese.startpaket("aufstieg")[0], t)
        e = bewertung.bewerten(t, h)
        self.assertGreater(e["metriken"]["auc_mittel"], 0.8)
        self.assertEqual(e["metriken"]["top3_von"], 24)
        self.assertEqual(e["pruef"]["top3_von"], 3)


class Schleifen(unittest.TestCase):
    def test_offline_schleife(self):
        with tempfile.TemporaryDirectory() as d:
            ged = gedaechtnis.Gedaechtnis(d)
            s = Schleife(forscher.OfflineForscher(seed=0), ged, aufgaben=("aufstieg",), vorschlaege=2,
                         ausgabe=lambda *a: None)
            verlauf = s.lernen(2)
            self.assertEqual([v["runde"] for v in verlauf], [1, 2])
            self.assertTrue(ged.bestes("aufstieg"))
            self.assertGreaterEqual(len(ged.experimente("aufstieg", nur_ok=True)), 3)
            self.assertIn("Aufgabe aufstieg", ged.erkenntnisse())
            # Fortsetzung zaehlt weiter
            s.lernen(1)
            self.assertEqual(ged.naechste_runde(), 4)
            self.assertIn("Runden gelernt: 3", status_text(ged))
            self.assertIn("## Aufgabe `aufstieg`", bericht_markdown(ged))
            # keine Wiederholung derselben Kennung als "ok"
            kenn = [e["hypothese"]["kennung"] for e in ged.experimente("aufstieg", nur_ok=True)]
            self.assertEqual(len(kenn), len(set(kenn)))

    def test_claude_forscher_mit_attrappe(self):
        antworten = []

        class Block:
            type = "text"
            def __init__(self, text):
                self.text = text

        class Antwort:
            def __init__(self, text, stop="end_turn"):
                self.content = [Block(text)]
                self.stop_reason = stop
                self.usage = None

        class Messages:
            def create(self, **kw):
                antworten.append(kw)
                if kw.get("output_config", {}).get("format"):
                    hyps = {"hypothesen": [
                        {"name": "Test", "begruendung": "b", "merkmale": ["xpoints", "npxg_diff"],
                         "abgeleitet": [{"name": "q", "formel": "xpoints * npxg_diff"}],
                         "modell": {"typ": "logit", "l2": 2.0, "versteckt": 8, "epochen": 100, "lernrate": 0.02},
                         "standardisierung": "gruppe", "erwartung": "e"},
                        {"name": "Kaputt", "begruendung": "b", "merkmale": ["tore"], "abgeleitet": [],
                         "modell": {"typ": "logit", "l2": 1, "versteckt": 8, "epochen": 100, "lernrate": 0.02},
                         "standardisierung": "global", "erwartung": "e"}]}
                    return Antwort(json.dumps(hyps))
                return Antwort("# Erkenntnisse\n\n## Aufgabe aufstieg\n\n### Was traegt\n- xpoints\n")

        class Beta:
            messages = Messages()

        class Client:
            beta = Beta()

        f = forscher.ClaudeForscher(modell="claude-opus-5", client=Client())
        with tempfile.TemporaryDirectory() as d:
            ged = gedaechtnis.Gedaechtnis(d)
            s = Schleife(f, ged, aufgaben=("aufstieg",), vorschlaege=2, ausgabe=lambda *a: None)
            s.lernen(1)
            exps = ged.experimente("aufstieg")
            self.assertEqual([e["status"] for e in exps], ["ok", "abgelehnt"])
            self.assertEqual(exps[0]["forscher"], "claude:claude-opus-5")
            self.assertTrue(ged.erkenntnisse().startswith("<!-- geschrieben von claude:claude-opus-5"))
        # Anfrageform: Schema, Fallbacks, Cache-Markierung
        erste = antworten[0]
        self.assertEqual(erste["model"], "claude-opus-5")
        self.assertEqual(erste["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", erste["betas"])
        self.assertEqual(erste["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(erste["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertIn("Rangliste", erste["messages"][0]["content"])

    def test_claude_ausfall_faengt_ersatz(self):
        class Kaputt:
            name = "claude:kaputt"
            def vorschlagen(self, k):
                raise forscher.ForscherFehler("kein Netz")
            def reflektieren(self, k):
                raise forscher.ForscherFehler("kein Netz")
        with tempfile.TemporaryDirectory() as d:
            ged = gedaechtnis.Gedaechtnis(d)
            s = Schleife(Kaputt(), ged, aufgaben=("aufstieg",), vorschlaege=1, ausgabe=lambda *a: None)
            s.lernen(1)
            e = ged.experimente("aufstieg")
            self.assertEqual(len(e), 1)
            self.assertIn("Ersatz", e[0]["forscher"])
            self.assertIn("offline", ged.erkenntnisse().splitlines()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
