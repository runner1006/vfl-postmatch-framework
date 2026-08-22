"""Selbsttest der Report-Engine: python3 skripte/test_report.py

Prueft, dass jedes Profil rendert, dass die drei Ebenen rechnerisch zu ihren
Quellen passen und dass die Trennung der Ebenen eingehalten wird. Laeuft ohne
Fremdpakete und ohne die providerlizenzierten Rohdaten.
"""
import csv
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import befund as bf                                                   # noqa: E402
import klubprofil as kp                                               # noqa: E402
import report as rp                                                   # noqa: E402

DS = bf.Datensatz()
PROFILE = kp.alle()


class Profile(unittest.TestCase):
    def test_profile_vorhanden(self):
        self.assertTrue(PROFILE, "keine Klubprofile in klubs/")

    def test_quelle_existiert(self):
        for p in PROFILE:
            with self.subTest(klub=p["slug"]):
                self.assertTrue(DS.spiele(p), f'{p["slug"]}: keine Spiele')

    def test_pflichtfelder(self):
        for p in PROFILE:
            for feld in kp.PFLICHT:
                self.assertTrue(p.get(feld), f'{p["slug"]}: {feld} fehlt')

    def test_unbekannter_slug_meldet_sich(self):
        with self.assertRaises(kp.ProfilFehler):
            kp.lade("gibt-es-nicht")


class EbeneA(unittest.TestCase):
    def test_score_im_bereich(self):
        for p in PROFILE:
            for s in DS.spiele(p):
                a = bf.ebene_a(DS, s)
                if a["score"] is not None:
                    self.assertGreaterEqual(a["score"], 0)
                    self.assertLessEqual(a["score"], 100)
                for ph in a["phasen"]:
                    if ph["score"] is not None:
                        self.assertGreaterEqual(ph["score"], 0)
                        self.assertLessEqual(ph["score"], 100)

    def test_stark_und_schwach_sind_sortiert(self):
        for p in PROFILE:
            for s in DS.spiele(p)[:5]:
                a = bf.ebene_a(DS, s)
                if len(a["kpis"]) < 6:
                    continue
                self.assertGreaterEqual(a["stark"][0]["score"], a["stark"][-1]["score"])
                self.assertLessEqual(a["schwach"][0]["score"], a["stark"][-1]["score"])

    def test_phasenfrage_nennt_keinen_fremden_klub(self):
        for ph in bf.ebene_a(DS, DS.spiele(PROFILE[0])[0])["phasen"]:
            self.assertNotIn("VfL", ph["frage"])


class EbeneB(unittest.TestCase):
    def test_nur_mit_passender_liga(self):
        for p in PROFILE:
            gilt = (p.get("ziel") or {}).get("gilt_fuer_liga")
            for s in DS.spiele(p):
                e = bf.ebene_b(DS, s, p)
                if not gilt or not s["ls"].startswith(gilt):
                    self.assertIsNone(e, f'{p["slug"]} {s["ls"]}: Ebene B darf nicht greifen')

    def test_ziel_folgt_der_gegnerstaerke(self):
        """Gegen einen schwaecheren Gegner muss die Zielmarke hoeher liegen."""
        p = kp.lade("vfl-bochum")
        werte = []
        for s in DS.spiele(p):
            e = bf.ebene_b(DS, s, p)
            if e:
                werte.append((e["gegner_off"] - e["gegner_def"], e["ziel_diff"]))
        self.assertGreater(len(werte), 20)
        for staerke, ziel in werte:
            # ziel_diff = b_off - b_def - (gegner_off - gegner_def)
            b = DS.benchmark
            erwartet = b["npxg_erzeugt"] - b["npxg_zugelassen"] - staerke
            self.assertAlmostEqual(ziel, erwartet, places=6)

    def test_ist_diff_passt_zur_gerechneten_csv(self):
        """Kreuzprobe gegen ergebnisse/bochum_2526_scored.csv."""
        pfad = os.path.join(kp.ERGEBNISSE, "bochum_2526_scored.csv")
        if not os.path.exists(pfad):
            self.skipTest("bochum_2526_scored.csv fehlt")
        with open(pfad, encoding="utf-8") as f:
            csv_zeilen = {int(r["match_id"]): r for r in csv.DictReader(f)}
        p = kp.lade("vfl-bochum")
        geprueft = 0
        for s in DS.spiele(p):
            r = csv_zeilen.get(s["id"])
            if not r:
                continue
            e = bf.ebene_b(DS, s, p)
            self.assertIsNotNone(e)
            erwartet = float(r["CC1_npxg"]) - float(r["CC1d_npxg_gegen"])
            self.assertAlmostEqual(e["ist_diff"], erwartet, places=2)
            geprueft += 1
        self.assertEqual(geprueft, 34)


class EbeneC(unittest.TestCase):
    def test_delta_punkte_ist_punkte_minus_xpoints(self):
        for p in PROFILE:
            for s in DS.spiele(p):
                c = bf.ebene_c(s)
                if c["xp"] is None or c["dpkt"] is None:
                    continue
                self.assertAlmostEqual(c["dpkt"], c["punkte"] - c["xp"], places=1)

    def test_wahrscheinlichkeiten_summieren_auf_eins(self):
        for p in PROFILE:
            for s in DS.spiele(p):
                c = bf.ebene_c(s)
                teile = [c["psieg"], c["premis"], c["pnied"]]
                if any(t is None for t in teile):
                    continue
                self.assertAlmostEqual(sum(teile), 1.0, places=2)

    def test_xpoints_passt_zur_gerechneten_csv(self):
        pfad = os.path.join(kp.ERGEBNISSE, "bochum_2526_scored.csv")
        if not os.path.exists(pfad):
            self.skipTest("bochum_2526_scored.csv fehlt")
        with open(pfad, encoding="utf-8") as f:
            csv_zeilen = {int(r["match_id"]): r for r in csv.DictReader(f)}
        for s in DS.spiele(kp.lade("vfl-bochum")):
            r = csv_zeilen[s["id"]]
            self.assertAlmostEqual(s["xp"], float(r["xpoints"]), places=2)
            self.assertEqual(s["pkt"], int(float(r["punkte"])))


class Saisonlage(unittest.TestCase):
    def test_punkte_summieren_sich(self):
        p = kp.lade("vfl-bochum")
        spiele = DS.spiele(p)
        lage = bf.saisonlage(DS, spiele, len(spiele) - 1, p)
        self.assertEqual(lage["punkte"], sum(s["pkt"] for s in spiele))
        self.assertEqual(lage["spiele"], len(spiele))
        self.assertLessEqual(lage["ueber_ziel"], lage["ueber_ziel_von"])

    def test_nur_bis_zum_aktuellen_spiel(self):
        p = kp.lade("vfl-bochum")
        spiele = DS.spiele(p)
        lage = bf.saisonlage(DS, spiele, 4, p)
        self.assertEqual(lage["spiele"], 5)
        self.assertEqual(lage["punkte"], sum(s["pkt"] for s in spiele[:5]))

    def test_verlauf_markiert_genau_ein_spiel(self):
        p = kp.lade("sturm-graz")
        spiele = DS.spiele(p)
        lage = bf.saisonlage(DS, spiele, 60, p)
        self.assertEqual(sum(1 for v in lage["verlauf"] if v["aktuell"]), 1)
        self.assertEqual(len({s["ls"] for s in spiele[:1]}), 1)


class Rendern(unittest.TestCase):
    def test_jedes_spiel_jedes_profils_rendert(self):
        for p in PROFILE:
            spiele = DS.spiele(p)
            for i in range(len(spiele)):
                doc = rp.dokument(bf.befund(DS, p, i))
                with self.subTest(klub=p["slug"], spiel=i):
                    self.assertIn(p["name"], doc)
                    self.assertIn("Post-Match-Report", doc)
                    self.assertIn("Seite 2 von 2", doc)
                    self.assertNotIn("None", doc)
                    self.assertGreater(len(doc), 12000)

    def test_kein_offener_platzhalter(self):
        doc = rp.dokument(bf.befund(DS, PROFILE[0], 0))
        self.assertNotIn("{esc(", doc)
        self.assertNotIn("{zahl(", doc)

    def test_sonderzeichen_werden_maskiert(self):
        p = dict(kp.lade("vfl-bochum"), name='<script>alarm()</script>')
        doc = rp.dokument(bf.befund(DS, p, 0))
        self.assertNotIn("<script>alarm()", doc)
        self.assertIn("&lt;script&gt;alarm()", doc)

    def test_zahlen_in_deutscher_schreibweise(self):
        self.assertEqual(rp.zahl(1.25, 2), "1,25")
        self.assertEqual(rp.zahl(-0.5, 1, plus=True), "−0,5")
        self.assertEqual(rp.zahl(2.0, 2, plus=True), "+2,00")
        self.assertEqual(rp.zahl(None), "—")

    def test_dateiname_ist_stabil(self):
        s = {"gw": 7, "datum": "2025-09-20", "geg": "Borussia M'gladbach"}
        self.assertEqual(rp.dateiname(s), "07-2025-09-20-borussia-m-gladbach.html")


class Auswahl(unittest.TestCase):
    def test_finde_nach_spieltag_und_gegner(self):
        spiele = DS.spiele(kp.lade("vfl-bochum"))
        i = bf.finde(spiele, spieltag=spiele[3]["gw"])
        self.assertIn(3, i)
        j = bf.finde(spiele, gegner=spiele[3]["geg"][:5].lower())
        self.assertIn(3, j)
        self.assertEqual(bf.finde(spiele, gegner="gibt es nicht"), [])

    def test_index_ausserhalb_meldet_sich(self):
        with self.assertRaises(bf.Datenfehler):
            bf.befund(DS, PROFILE[0], 10_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
