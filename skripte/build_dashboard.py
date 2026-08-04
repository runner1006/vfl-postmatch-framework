"""Spielt die gerechneten JSON-Daten in dashboard.html ein.

Das Dashboard ist bewusst eine einzelne, in sich geschlossene Datei - es soll ohne
Server und ohne Netzzugriff aufgehen. Die Daten liegen deshalb als zwei Konstanten
inline. Dieses Skript ersetzt genau diese beiden Zeilen und laesst alles andere in
Ruhe, damit nach jedem Rechenlauf nicht von Hand kopiert werden muss.

Aufruf:  python3 build_dashboard.py
"""
import json
import re
from pathlib import Path

from config import OUT

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "dashboard.html"

QUELLEN = [("DATA", "dashboard_data.json"), ("MD", "dashboard_matches.json")]


def main():
    text = HTML.read_text(encoding="utf-8")
    for konstante, datei in QUELLEN:
        pfad = Path(OUT) / datei
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        # separators ohne Leerzeichen: die Datei ist knapp 1 MB gross, jedes
        # gesparte Zeichen zaehlt beim Oeffnen im Browser.
        neu = (f"const {konstante} = "
               + json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + ";")
        muster = re.compile(rf"^const {konstante} = \{{.*\}};$", re.M)
        text, n = muster.subn(lambda _m: neu, text, count=1)
        if n != 1:
            raise SystemExit(f"FEHLER: Zeile 'const {konstante} = {{...}};' nicht gefunden")
        print(f"  {konstante:5s} <- {datei}  ({len(neu) / 1024:.0f} KB)")

    HTML.write_text(text, encoding="utf-8")
    print(f"dashboard.html geschrieben ({HTML.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
