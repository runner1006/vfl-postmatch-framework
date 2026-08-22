"""Kreuzprobe App gegen Druckreport: python3 skripte/test_frontend.py

Die Arithmetik der drei Ebenen steht zweimal — in `befund.py` fuer den Druck und
in `app.html` fuer die Oberflaeche. Dieser Test laesst die App in einem lokalen
Chromium ueber *jedes* Spiel *jedes* Profils rechnen und vergleicht Zahl fuer
Zahl mit Python. Laeuft die App auseinander, faellt es hier auf und nicht beim
Kunden.

Ohne Chromium ueberspringt der Test sich selbst, statt rot zu werden.
"""
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import befund as bf                                                   # noqa: E402
import klubprofil as kp                                               # noqa: E402

APP = os.path.join(kp.WURZEL, "app.html")
BROWSER = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
]
TOLERANZ = 1e-9

HARNESS = """
<script>
window.addEventListener("load", function(){
  var raus = [];
  for(const profil of window.APP.profile()){
    const spiele = window.APP.spieleVon(profil);
    for(let i = 0; i < spiele.length; i++){
      const b = window.APP.befund(profil, i);
      raus.push({
        klub: profil.slug, i: i, id: b.spiel.id,
        a_score: b.a.score, a_conf: b.a.conf,
        phasen: b.a.phasen.map(p => [p.key, p.score, p.unsicher]),
        stark: b.a.stark.map(k => k.key), schwach: b.a.schwach.map(k => k.key),
        ohne_daten: b.a.ohne_daten,
        b: b.b === null ? null : [b.b.ziel_off, b.b.ziel_def, b.b.ist_diff,
                                  b.b.ziel_diff, b.b.delta, b.b.erreicht],
        c: [b.c.dpkt, b.c.verwertung, b.c.verwertung_geg, b.c.tw_effekt],
        saison: [b.saison.spiele, b.saison.punkte, b.saison.xp, b.saison.score_median,
                 b.saison.score_rang, b.saison.form, b.saison.ueber_ziel,
                 b.saison.ueber_ziel_von],
        kontext: b.kontext.map(z => [z.label, z.wert, z.nachkomma, z.perzentil]),
        flags: b.flags.map(f => f.text)
      });
    }
  }
  document.body.innerHTML = '<pre id="js"></pre>';
  document.getElementById("js").textContent = JSON.stringify(raus);
});
</script>
"""


def browser():
    return next((b for b in BROWSER if os.path.exists(b)), None) \
        or shutil.which("chromium") or shutil.which("google-chrome")


def js_befunde(binaer):
    """Laesst die App rechnen und holt das Ergebnis aus dem gerenderten DOM."""
    with open(APP, encoding="utf-8") as f:
        seite = f.read().replace("</body>", HARNESS + "</body>")
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "harness.html")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(seite)
        roh = subprocess.run(
            [binaer, "--headless", "--disable-gpu", "--no-sandbox",
             "--virtual-time-budget=20000", "--dump-dom", "file://" + pfad],
            capture_output=True, text=True, timeout=300).stdout
    if '<pre id="js">' not in roh:
        raise AssertionError("Die App hat nichts ausgegeben — Fehler beim Laden?")
    inhalt = roh.split('<pre id="js">', 1)[1].split("</pre>", 1)[0]
    return json.loads(html.unescape(inhalt))


def py_befund(profil, i):
    b = bf.befund(bf.Datensatz(), profil, i)
    return {
        "klub": profil["slug"], "i": i, "id": b["spiel"]["id"],
        "a_score": b["a"]["score"], "a_conf": b["a"]["conf"],
        "phasen": [[p["key"], p["score"], p["unsicher"]] for p in b["a"]["phasen"]],
        "stark": [k["key"] for k in b["a"]["stark"]],
        "schwach": [k["key"] for k in b["a"]["schwach"]],
        "ohne_daten": b["a"]["ohne_daten"],
        "b": None if b["b"] is None else [
            b["b"]["ziel_off"], b["b"]["ziel_def"], b["b"]["ist_diff"],
            b["b"]["ziel_diff"], b["b"]["delta"], b["b"]["erreicht"]],
        "c": [b["c"]["dpkt"], b["c"]["verwertung"], b["c"]["verwertung_geg"],
              b["c"]["tw_effekt"]],
        "saison": [b["saison"]["spiele"], b["saison"]["punkte"], b["saison"]["xp"],
                   b["saison"]["score_median"], b["saison"]["score_rang"],
                   b["saison"]["form"], b["saison"]["ueber_ziel"],
                   b["saison"]["ueber_ziel_von"]],
        "kontext": [[z["label"], z["wert"], z["nachkomma"], z["perzentil"]]
                    for z in b["kontext"]],
        "flags": [f["text"] for f in b["flags"]],
    }


def gleich(a, b, pfad=""):
    """Vergleicht verschachtelte Werte und meldet die erste Abweichung im Klartext."""
    if isinstance(a, bool) or isinstance(b, bool):
        return None if a == b else f"{pfad}: {a} != {b}"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return None if abs(a - b) <= TOLERANZ else f"{pfad}: {a} != {b}"
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{pfad}: Laenge {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            fehler = gleich(x, y, f"{pfad}[{i}]")
            if fehler:
                return fehler
        return None
    return None if a == b else f"{pfad}: {a!r} != {b!r}"


class AppRechnetWiePython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binaer = browser()
        if not cls.binaer:
            raise unittest.SkipTest("kein Chromium gefunden")
        if not os.path.exists(APP):
            raise unittest.SkipTest("app.html fehlt")
        cls.js = js_befunde(cls.binaer)

    def test_gleich_viele_spiele(self):
        erwartet = sum(len(bf.Datensatz().spiele(p)) for p in kp.alle())
        self.assertEqual(len(self.js), erwartet)
        self.assertGreater(erwartet, 250)

    def test_jede_zahl_stimmt(self):
        nach_klub = {}
        for zeile in self.js:
            nach_klub.setdefault(zeile["klub"], []).append(zeile)
        for profil in kp.alle():
            zeilen = nach_klub.get(profil["slug"], [])
            self.assertTrue(zeilen, f'{profil["slug"]}: die App kennt das Profil nicht')
            for zeile in zeilen:
                py = py_befund(profil, zeile["i"])
                for feld in py:
                    fehler = gleich(py[feld], zeile.get(feld), f'{profil["slug"]}/{zeile["i"]}.{feld}')
                    self.assertIsNone(fehler, fehler)


class AppIstGebaut(unittest.TestCase):
    @staticmethod
    def _app():
        with open(APP, encoding="utf-8") as f:
            return f.read()

    def test_daten_sind_eingespielt(self):
        text = self._app()
        self.assertNotIn("const MD = {};", text, "app.html ist ungebaut — build_app.py laufen lassen")
        self.assertNotIn("const KLUBS = [];", text)
        self.assertNotIn("/* REPORT-CSS */", text)

    def test_jedes_profil_steckt_in_der_app(self):
        text = self._app()
        for p in kp.alle():
            self.assertIn(f'"slug":"{p["slug"]}"', text)

    def test_stil_stammt_aus_report_css(self):
        with open(os.path.join(kp.WURZEL, "skripte", "report.css"), encoding="utf-8") as f:
            css = f.read()
        text = self._app()
        marker = ".kennzahl .wert{font-size:26pt"
        self.assertIn(marker, css)
        self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
