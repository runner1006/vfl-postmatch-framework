"""Spielt Daten, Klubprofile, Texte und das Report-Aussehen in app.html ein.

Wie das Dashboard ist die App eine einzelne, in sich geschlossene Datei: kein
Server, kein Netzzugriff, Doppelklick genuegt. Dieses Skript ersetzt genau die
drei Datenzeilen und den Stilblock und laesst alles andere in Ruhe.

Aufruf:  python3 skripte/build_app.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import befund as bf                                                   # noqa: E402
import klubprofil as kp                                               # noqa: E402
import report as rp                                                   # noqa: E402

HTML = os.path.join(kp.WURZEL, "app.html")
CSS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.css")


def js_json(daten):
    """Kompakt und sicher im Script-Tag: '</' wuerde den Block sonst schliessen."""
    return json.dumps(daten, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def texte():
    """Beschriftungen kommen aus dem Python-Code, nicht aus einer JS-Kopie."""
    return {
        "flag": bf.FLAG_TEXT,
        "kontext_kurz": bf.KONTEXT_KURZ,
        "nachkomma": bf.NACHKOMMA,
        "frage_ersatz": [list(paar) for paar in bf.FRAGE_NEUTRAL],
        "urteil_kurz": rp.URTEIL_KURZ,
    }


def ersetze(text, muster, neu, was, flags=re.M):
    text, n = re.subn(muster, lambda _m: neu, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"FEHLER: {was} nicht gefunden")
    return text


def main():
    with open(bf.STANDARD_DATEI, encoding="utf-8") as f:
        md = json.load(f)
    profile = kp.alle()
    if not profile:
        raise SystemExit("FEHLER: keine Klubprofile in klubs/")
    for p in profile:
        bf.Datensatz().team(p["quelle"]["team_key"])          # Profil gegen Daten pruefen

    text = open(HTML, encoding="utf-8").read()
    for name, wert in (("MD", md), ("KLUBS", profile), ("TEXTE", texte())):
        neu = f"const {name} = {js_json(wert)};"
        text = ersetze(text, rf"^const {name} = .*;$", neu,
                       f"Zeile 'const {name} = ...'")
        print(f"  {name:6s} {len(neu) / 1024:7.0f} KB")

    css = open(CSS, encoding="utf-8").read()
    text = ersetze(text, r'<style id="report-css">.*?</style>',
                   f'<style id="report-css">\n{css}</style>', "Stilblock report-css",
                   flags=re.S)
    print(f"  CSS    {len(css) / 1024:7.0f} KB  <- skripte/report.css")

    open(HTML, "w", encoding="utf-8").write(text)
    print(f"app.html geschrieben ({os.path.getsize(HTML) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
