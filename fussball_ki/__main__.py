"""Kommandozeile der Fussball-KI.

    python3 -m fussball_ki lernen --runden 3          # Selbstlern-Schleife
    python3 -m fussball_ki status                     # was sie bisher weiss
    python3 -m fussball_ki vorhersage --aufgabe spiel --id 5717436
    python3 -m fussball_ki vorhersage --aufgabe aufstieg --team Bochum --saison 2025/26
    python3 -m fussball_ki bericht                    # wissen/bericht.md
    python3 -m fussball_ki daten --aufgabe spiel      # Merkmalskatalog
"""
import argparse
import json
import os
import sys

from .bericht import bericht_schreiben, status_text
from .bewertung import vorhersagen
from .daten import AUFGABEN, katalog, lade
from .forscher import ClaudeForscher, OfflineForscher, forscher_waehlen
from .gedaechtnis import Gedaechtnis
from .schleife import Schleife


def _aufgaben(arg):
    return list(AUFGABEN) if arg in (None, "alle") else [arg]


def cmd_lernen(a):
    ged = Gedaechtnis(a.wissen) if a.wissen else Gedaechtnis()
    if a.offline:
        forscher = OfflineForscher(seed=a.seed)
    elif a.modell:
        forscher = ClaudeForscher(modell=a.modell, effort=a.effort)
    else:
        forscher = forscher_waehlen(seed=a.seed)
        if isinstance(forscher, ClaudeForscher):
            forscher.effort = a.effort
    print("Forscher: %s · Aufgaben: %s · Runden: %d · Vorschlaege je Runde: %d" % (
        forscher.name, ", ".join(_aufgaben(a.aufgabe)), a.runden, a.vorschlaege))
    if isinstance(forscher, OfflineForscher) and not a.offline:
        print("(kein ANTHROPIC_API_KEY gesetzt - Offline-Forscher; fuer den Claude-Forscher Schluessel exportieren)")
    s = Schleife(forscher, ged, aufgaben=_aufgaben(a.aufgabe), vorschlaege=a.vorschlaege,
                 ersatz=OfflineForscher(seed=a.seed + 1))
    s.lernen(a.runden)
    print()
    print(status_text(ged))
    pfad = bericht_schreiben(ged)
    print()
    print("Bericht: %s" % pfad)


def cmd_status(a):
    ged = Gedaechtnis(a.wissen) if a.wissen else Gedaechtnis()
    print(status_text(ged))
    if a.erkenntnisse:
        print()
        print(ged.erkenntnisse())


def cmd_bericht(a):
    ged = Gedaechtnis(a.wissen) if a.wissen else Gedaechtnis()
    pfad = bericht_schreiben(ged, a.ziel)
    print("geschrieben: %s" % pfad)


def cmd_daten(a):
    for aufgabe in _aufgaben(a.aufgabe):
        t = lade(aufgabe)
        print("== %s: %d Zeilen, Klassen %s" % (aufgabe, len(t), ", ".join(t.klassen)))
        print("Frage: %s" % t.frage)
        print("Benchmark: %s" % json.dumps(t.benchmark, ensure_ascii=False))
        print(katalog(t))
        print()


def cmd_vorhersage(a):
    ged = Gedaechtnis(a.wissen) if a.wissen else Gedaechtnis()
    best = ged.bestes(a.aufgabe)
    if not best:
        sys.exit("Noch kein Modell fuer %s - erst `lernen` ausfuehren." % a.aufgabe)
    endm = best["endmodell"]
    t = lade(a.aufgabe)
    zeile = None
    if a.json:
        werte = json.loads(a.json)
        gruppe = a.gruppe
        beschreibung = "eigene Eingabe"
    else:
        for z in t.zeilen:
            ex = z["extra"]
            if a.id and str(z["id"]) == str(a.id):
                zeile = z
            elif a.team and a.team.lower() in ex["team"].lower() and (
                    not a.saison or a.saison in (ex.get("saison") or ex.get("liga_saison") or "")):
                zeile = z
            if zeile:
                break
        if not zeile:
            sys.exit("Keine Zeile gefunden (--id, --team/--saison oder --json angeben).")
        werte, gruppe = zeile["merkmale"], zeile["gruppe"]
        ex = zeile["extra"]
        if a.aufgabe == "spiel":
            beschreibung = "%s gegen %s am %s (%s), Ergebnis %s" % (
                ex["team"], ex["gegner"], ex["datum"], "heim" if werte.get("heim") else "auswaerts", ex["ergebnis"])
        else:
            beschreibung = "%s %s, Platz %d" % (ex["team"], ex["saison"], ex["platz"])
    p = vorhersagen(endm, werte, gruppe)
    print("Modell: %s (Runde %s)" % (endm["hypothese"]["name"], best.get("runde")))
    print("Eingabe: %s" % beschreibung)
    for k, v in p.items():
        print("  %-12s %5.1f %%" % (k, 100 * v))
    if zeile is not None and a.aufgabe == "spiel":
        pf = zeile["extra"].get("p_framework")
        if pf and all(v is not None for v in pf):
            print("Framework-Poisson zum Vergleich: " + ", ".join(
                "%s %.1f %%" % (k, 100 * v) for k, v in zip(t.klassen, pf)))


def main(argv=None):
    p = argparse.ArgumentParser(prog="fussball_ki", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wissen", help="anderes Gedaechtnis-Verzeichnis (Standard: fussball_ki/wissen)")
    sub = p.add_subparsers(dest="befehl", required=True)

    l = sub.add_parser("lernen", help="Selbstlern-Schleife laufen lassen")
    l.add_argument("--runden", type=int, default=3)
    l.add_argument("--aufgabe", choices=list(AUFGABEN) + ["alle"], default="alle")
    l.add_argument("--vorschlaege", type=int, default=3, help="Hypothesen je Runde und Aufgabe")
    l.add_argument("--offline", action="store_true", help="ohne Sprachmodell (evolutionaere Suche)")
    l.add_argument("--modell", help="Claude-Modell-ID (Standard: claude-opus-5)")
    l.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    l.add_argument("--seed", type=int, default=0)
    l.set_defaults(fn=cmd_lernen)

    s = sub.add_parser("status", help="Stand des Gedaechtnisses")
    s.add_argument("--erkenntnisse", action="store_true", help="auch die Erkenntnisse zeigen")
    s.set_defaults(fn=cmd_status)

    b = sub.add_parser("bericht", help="Markdown-Bericht schreiben")
    b.add_argument("--ziel")
    b.set_defaults(fn=cmd_bericht)

    d = sub.add_parser("daten", help="Merkmalskatalog zeigen")
    d.add_argument("--aufgabe", choices=list(AUFGABEN) + ["alle"], default="alle")
    d.set_defaults(fn=cmd_daten)

    v = sub.add_parser("vorhersage", help="mit dem besten Modell vorhersagen")
    v.add_argument("--aufgabe", choices=list(AUFGABEN), required=True)
    v.add_argument("--id", help="Spiel-ID bzw. 'Saison-TeamID'")
    v.add_argument("--team", help="Teamname (Teilstring)")
    v.add_argument("--saison", help="z.B. 2025/26 oder '2BL 2025/26'")
    v.add_argument("--json", help="Merkmalsdict als JSON")
    v.add_argument("--gruppe", help="Gruppe fuer Standardisierung je Gruppe (Saison / Teamschluessel)")
    v.set_defaults(fn=cmd_vorhersage)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
