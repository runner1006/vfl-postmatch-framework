"""Kommandozeile der Fussball-KI.

    python3 -m fussballki lernen --runden 3              Selbstlern-Schleife
    python3 -m fussballki status --erkenntnisse          was sie bisher weiss
    python3 -m fussballki vorhersage --naechste          naechste offene Spiele
    python3 -m fussballki vorhersage --heim Bochum --gast Schalke
    python3 -m fussballki bericht                        wissen/bericht.md
    python3 -m fussballki daten                          Merkmalskatalog
    python3 -m fussballki quellen                        Spieldaten aktualisieren
"""
import argparse
import datetime as dt
import json
import os
import sys

from . import aufgaben, merkmale
from .bericht import bericht_schreiben, status_text
from .bewertung import benchmarks, vorhersagen
from .daten import Spiel, lade_spiele, schluessel
from .forscher import ClaudeForscher, OfflineForscher, forscher_waehlen
from .gedaechtnis import Gedaechtnis
from .schleife import Schleife


def _aufgaben(arg):
    return list(aufgaben.AUFGABEN) if arg in (None, "alle") else [arg]


def _ged(a):
    return Gedaechtnis(a.wissen) if a.wissen else Gedaechtnis()


def cmd_lernen(a):
    ged = _ged(a)
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
    print()
    print("Bericht: %s" % bericht_schreiben(ged))


def cmd_status(a):
    ged = _ged(a)
    print(status_text(ged))
    if a.erkenntnisse:
        print()
        print(ged.erkenntnisse())
    if a.elo:
        spiele = lade_spiele()
        namen = {}
        for s in spiele:
            namen[s.heim], namen[s.gast] = s.heim_name, s.gast_name
        elo = merkmale.elo_stand(spiele)
        print()
        print("Elo-Rangliste (nach dem letzten gespielten Spiel):")
        for i, (k, v) in enumerate(sorted(elo.items(), key=lambda kv: -kv[1])[:a.elo], 1):
            print("  %2d. %-28s %5.0f" % (i, namen[k], v))


def cmd_bericht(a):
    print("geschrieben: %s" % bericht_schreiben(_ged(a), a.ziel))


def cmd_daten(a):
    for aufgabe in _aufgaben(a.aufgabe):
        t = aufgaben.lade(aufgabe)
        print("== %s: %d gespielte Spiele, %d offene, Klassen %s" % (aufgabe, len(t), len(t.offen), ", ".join(t.klassen)))
        print("Frage: %s" % t.frage)
        if a.benchmark:
            b = benchmarks(t)
            print("Benchmarks: %s" % json.dumps({k: v for k, v in b.items() if k != "elo_logloss_je_saison"}, ensure_ascii=False))
        print(aufgaben.katalog(t))
        print()


def cmd_quellen(a):
    from .quellen import holen
    geholt, fehlend = holen(a.saisons)
    print("%d Dateien geholt, %d nicht vorhanden%s" % (len(geholt), len(fehlend), (": " + ", ".join(fehlend)) if fehlend else ""))


def _verein(name, namen):
    """Teilstring-Suche ueber Anzeigenamen und Schluessel."""
    k = schluessel(name)
    if k in namen:
        return k
    treffer = [key for key, anzeige in namen.items() if name.lower() in anzeige.lower() or k in key]
    if len(treffer) == 1:
        return treffer[0]
    if not treffer:
        sys.exit("Verein %r nicht gefunden." % name)
    sys.exit("Verein %r ist mehrdeutig: %s" % (name, ", ".join(namen[t] for t in treffer)))


def _zeige(p, klassen):
    for k in klassen:
        print("  %-14s %5.1f %%" % (k, 100 * p[k]))
    if "_tore_erwartet" in p:
        print("  erwartete Tore %.2f : %.2f" % p["_tore_erwartet"])


def cmd_vorhersage(a):
    ged = _ged(a)
    best = ged.bestes(a.aufgabe)
    if not best:
        sys.exit("Noch kein Modell fuer %s - erst `lernen` ausfuehren." % a.aufgabe)
    endm = best["endmodell"]
    t = aufgaben.lade(a.aufgabe)
    print("Modell: %s (Runde %s, Datenstand %s)" % (endm["hypothese"]["name"], best.get("runde"), endm.get("stand")))
    if a.naechste:
        for z in aufgaben.naechste_spiele(t, limit=a.limit):
            ex = z["extra"]
            p = vorhersagen(endm, z["merkmale"], z["gruppe"])
            print("%s  %s - %s" % (ex["datum"], ex["heim"], ex["gast"]))
            _zeige(p, endm["klassen"])
        return
    if a.id:
        z = next((z for z in t.zeilen + t.offen if str(z["id"]) == str(a.id)), None)
        if not z:
            sys.exit("Keine Zeile mit ID %s." % a.id)
        ex = z["extra"]
        print("Spiel: %s  %s - %s%s" % (ex["datum"], ex["heim"], ex["gast"],
                                        (" (%d:%d)" % ex["tore"]) if ex["tore"] else ""))
        _zeige(vorhersagen(endm, z["merkmale"], z["gruppe"]), endm["klassen"])
        return
    if not (a.heim and a.gast):
        sys.exit("--naechste, --id oder --heim und --gast angeben.")
    spiele = lade_spiele()
    heim, gast = _verein(a.heim, t.namen), _verein(a.gast, t.namen)
    datum = dt.date.fromisoformat(a.datum) if a.datum else max(s.datum for s in spiele if s.gespielt) + dt.timedelta(days=1)
    letzte = max((s for s in spiele if s.gespielt and heim in (s.heim, s.gast)), key=lambda s: s.datum, default=None)
    liga = a.liga or (letzte.liga if letzte else 1)
    saison = letzte.saison if letzte else spiele[-1].saison
    kuenstlich = Spiel(id=0, saison=saison, liga=liga, spieltag=a.spieltag, datum=datum, heim=heim, gast=gast,
                       heim_name=t.namen[heim], gast_name=t.namen[gast])
    reihe = [s for s in spiele if s.gespielt and s.datum < datum] + [kuenstlich]
    m = merkmale.berechne(reihe)[-1]
    print("Paarung: %s - %s am %s (Liga %d)" % (t.namen[heim], t.namen[gast], datum.isoformat(), liga))
    _zeige(vorhersagen(endm, m, saison), endm["klassen"])
    if a.merkmale:
        print("Merkmale: %s" % json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}, ensure_ascii=False))


def main(argv=None):
    p = argparse.ArgumentParser(prog="fussballki", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wissen", help="anderes Gedaechtnis-Verzeichnis (Standard: wissen/ im Projekt)")
    sub = p.add_subparsers(dest="befehl", required=True)

    l = sub.add_parser("lernen", help="Selbstlern-Schleife laufen lassen")
    l.add_argument("--runden", type=int, default=3)
    l.add_argument("--aufgabe", choices=list(aufgaben.AUFGABEN) + ["alle"], default="alle")
    l.add_argument("--vorschlaege", type=int, default=3, help="Hypothesen je Runde und Aufgabe")
    l.add_argument("--offline", action="store_true", help="ohne Sprachmodell (evolutionaere Suche)")
    l.add_argument("--modell", help="Claude-Modell-ID (Standard: claude-opus-5)")
    l.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    l.add_argument("--seed", type=int, default=0)
    l.set_defaults(fn=cmd_lernen)

    s = sub.add_parser("status", help="Stand des Gedaechtnisses")
    s.add_argument("--erkenntnisse", action="store_true", help="auch die Erkenntnisse zeigen")
    s.add_argument("--elo", type=int, nargs="?", const=20, help="Elo-Rangliste (Standard: Top 20)")
    s.set_defaults(fn=cmd_status)

    b = sub.add_parser("bericht", help="Markdown-Bericht schreiben")
    b.add_argument("--ziel")
    b.set_defaults(fn=cmd_bericht)

    d = sub.add_parser("daten", help="Merkmalskatalog zeigen")
    d.add_argument("--aufgabe", choices=list(aufgaben.AUFGABEN) + ["alle"], default="alle")
    d.add_argument("--benchmark", action="store_true", help="Benchmarks mitrechnen")
    d.set_defaults(fn=cmd_daten)

    q = sub.add_parser("quellen", help="Spieldaten von openfootball aktualisieren")
    q.add_argument("--saisons", nargs="*", help="z.B. 2025-26 2026-27 (Standard: alle ab 2010-11)")
    q.set_defaults(fn=cmd_quellen)

    v = sub.add_parser("vorhersage", help="mit dem besten Modell vorhersagen")
    v.add_argument("--aufgabe", choices=list(aufgaben.AUFGABEN), default="ergebnis")
    v.add_argument("--naechste", action="store_true", help="alle offenen Spiele ab dem letzten Spieltag")
    v.add_argument("--limit", type=int, help="hoechstens so viele offene Spiele")
    v.add_argument("--id", help="Spiel-ID aus den Daten")
    v.add_argument("--heim", help="Heimverein (Teilstring)")
    v.add_argument("--gast", help="Gastverein (Teilstring)")
    v.add_argument("--datum", help="Spieldatum JJJJ-MM-TT (Standard: Tag nach dem letzten Spiel)")
    v.add_argument("--liga", type=int, choices=[1, 2])
    v.add_argument("--spieltag", type=int)
    v.add_argument("--merkmale", action="store_true", help="berechnete Merkmale mit ausgeben")
    v.set_defaults(fn=cmd_vorhersage)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
