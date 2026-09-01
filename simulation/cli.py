"""Kommandozeile der Simulation.

    python3 cli.py spiel            --minuten 90 --html spiel.html
    python3 cli.py kontrafaktisch   --frage abwehrhoehe --n 20
    python3 cli.py situation        --sekunden 10 --n 60
    python3 cli.py drill
    python3 cli.py tests
"""
import argparse
import json
import sys
import time

import konfig as K
import kontrafaktisch as KF
import spiel as S
import spieler as SP
import taktik as T
import visual
import zwilling as Z


def _elf(seed, formation, stufe):
    return Z.elf_bauen(formation, stufe, seed=seed)


def _spiel_bauen(args, seed):
    heim = _elf(1, args.heim_formation, args.heim_stufe)
    gast = _elf(2, args.gast_formation, args.gast_stufe)
    anw_h = T.VORLAGEN[args.heim_stil].kopie(formation=args.heim_formation)
    anw_g = T.VORLAGEN[args.gast_stil].kopie(formation=args.gast_formation)
    sp = S.Spiel(heim, gast, anw_h, anw_g, seed=seed,
                 aufzeichnen=args.aufzeichnen,
                 aufzeichnungsrate=args.aufzeichnungsrate)
    sp.aufstellen(0)
    return sp


def _gemeinsame_argumente(p, aufzeichnen=False):
    p.add_argument("--heim-formation", default="4-2-3-1",
                   choices=sorted(T.FORMATIONEN))
    p.add_argument("--gast-formation", default="4-2-3-1",
                   choices=sorted(T.FORMATIONEN))
    p.add_argument("--heim-stil", default="ausgeglichen", choices=sorted(T.VORLAGEN))
    p.add_argument("--gast-stil", default="ausgeglichen", choices=sorted(T.VORLAGEN))
    p.add_argument("--heim-stufe", type=float, default=0.50,
                   help="Niveau der Heimelf, 0.5 = Ligadurchschnitt")
    p.add_argument("--gast-stufe", type=float, default=0.50)
    p.add_argument("--heim-name", default="Heim")
    p.add_argument("--gast-name", default="Gast")
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(aufzeichnen=aufzeichnen, aufzeichnungsrate=5)


# ------------------------------------------------------------------- Spiel
def befehl_spiel(args):
    args.aufzeichnen = bool(args.html or args.bahn)
    sp = _spiel_bauen(args, args.seed)
    t0 = time.time()

    def fortschritt(zeit, tore):
        print("   %2d. Minute   %d:%d" % (zeit / 60, tore[0], tore[1]),
              file=sys.stderr)

    if args.minuten >= 89:
        sp.spielen(90.0, fortschritt if args.ausfuehrlich else None)
    else:
        sp.laufen(args.minuten * 60.0, fortschritt if args.ausfuehrlich else None)

    b = sp.bericht()
    r = sp.raumauswertung()
    print("\nEndstand  %d : %d      (%.0f s Rechenzeit fuer %.0f min Spielzeit)"
          % (b["tore"][0], b["tore"][1], time.time() - t0, b["spielzeit"] / 60))
    print("\n%-24s %10s %10s" % ("", "Heim", "Gast"))
    print("-" * 46)
    zeilen = [
        ("xG", b["xg"]), ("Schuesse", b["schuesse"]),
        ("Paesse", b["paesse"]), ("Passquote", b["passquote"]),
        ("Ballbesitz", b["ballbesitz"]), ("Zweikaempfe", b["zweikaempfe"]),
        ("Fouls", b["fouls"]), ("Abseits", b["abseits"]),
        ("Paraden", b["paraden"]),
        ("Abwehrhoehe (m)", r["abwehrhoehe_m"]), ("PPDA", r["ppda"]),
        ("Strafraumeintritte", r["strafraumeintritte"]),
        ("Rueckeroberung < 5 s", r["rueckeroberung_5s"]),
        ("Laufdistanz (km)", b["laufdistanz"]),
        ("Sprintdistanz (m)", b["sprintdistanz"]),
        ("Energie am Ende", b["energie_ende"]),
    ]
    for name, werte in zeilen:
        print("%-24s %10s %10s" % (name, werte[0], werte[1]))

    if args.spieler:
        print("\n%-4s %-6s %-4s %8s %8s %8s %8s" % (
            "Nr", "Team", "Rolle", "km", "Sprint", "Vmax", "Energie"))
        for z in sp.spielerbericht():
            print("%-4d %-6s %-4s %8.2f %8.0f %8.2f %8.2f" % (
                z["nummer"], "Heim" if z["team"] == 0 else "Gast", z["rolle"],
                z["laufdistanz_km"], z["sprint_m"], z["spitzentempo"], z["energie"]))

    if args.html:
        visual.html_bauen(sp, args.html, heim_name=args.heim_name,
                          gast_name=args.gast_name)
        print("\nAnimation geschrieben: %s" % args.html)
    if args.bahn:
        visual.bahn_schreiben(sp, args.bahn)
        print("Bahnaufzeichnung geschrieben: %s" % args.bahn)


# --------------------------------------------------------- Kontrafaktisch
FRAGEN = {
    "abwehrhoehe": "Was aendert eine hoehere Abwehrkette?",
    "pressing": "Was aendert aggressiveres Pressing?",
    "schneller_iv": "Was aendert ein schnellerer Innenverteidiger?",
    "besserer_stuermer": "Was aendert ein besserer Abschlussspieler?",
    "formation": "Was aendert 3-4-3 statt der Grundformation?",
    "tiefer_block": "Was aendert ein tiefer Block?",
}


def befehl_kontrafaktisch(args):
    def bauer(seed):
        return _spiel_bauen(args, seed)

    frage = args.frage
    t0 = time.time()
    fort = (lambda i, n: print("   Wiederholung %d von %d" % (i, n),
                               file=sys.stderr)) if args.ausfuehrlich else None
    gem = dict(n=args.n, dauer=args.minuten * 60.0, fortschritt=fort)

    if frage == "abwehrhoehe":
        v = KF.anweisung_aendern(bauer, 0, abwehrhoehe=args.wert or 48.0, **gem)
    elif frage == "pressing":
        v = KF.anweisung_aendern(bauer, 0, pressing=args.wert or 0.92,
                                 pressing_ausloeser=34.0, **gem)
    elif frage == "tiefer_block":
        v = KF.anweisung_aendern(bauer, 0, abwehrhoehe=26.0, pressing=0.3,
                                 kompaktheit=0.85, pressing_ausloeser=16.0, **gem)
    elif frage == "formation":
        v = KF.formationswechsel(bauer, 0, args.formation or "3-4-3", **gem)
    elif frage == "schneller_iv":
        v = KF.spielertausch(bauer, 0, 2,
                             {"v_max": 9.5, "a_max": 11.2, "brems": 9.6},
                             name="Innenverteidiger #2: Spitzentempo 9.5 statt "
                                  "%.1f m/s" % K.BASIS_VMAX, **gem)
    elif frage == "besserer_stuermer":
        v = KF.spielertausch(bauer, 0, 11,
                             {"abschluss": 0.92, "erste_beruehrung": 0.88,
                              "positionsspiel": 0.85},
                             name="Stuermer #11: Abschluss und Timing auf Topniveau",
                             **gem)
    else:
        raise SystemExit("unbekannte Frage %r" % frage)

    print("\n" + v.tabelle())
    print("\n%s" % FRAGEN[frage])
    print("Rechenzeit %.0f s. Positive Differenz = die Variante liefert mehr."
          % (time.time() - t0))
    print("Das Intervall beschreibt die Unsicherheit im Modell, nicht in der "
          "Wirklichkeit.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(v.bericht(), f, indent=1, ensure_ascii=False)
        print("Ergebnis geschrieben: %s" % args.json)


# ------------------------------------------------------------- Situation
def befehl_situation(args):
    sp = _spiel_bauen(args, args.seed)
    sp.laufen(args.ab * 60.0)
    marken = tuple(float(x) for x in args.marken.split(","))
    print("Ausgangslage bei %.1f min, Ball bei (%.1f, %.1f), Ballbesitz %s"
          % (sp.lage.zeit / 60, sp.lage.ball.pos[0], sp.lage.ball.pos[1],
             {0: "Heim", 1: "Gast", None: "offen"}[sp.lage.phasenbesitz]))
    aus = KF.situation_fortschreiben(sp, wiederholungen=args.n, marken=marken,
                                     startseed=args.seed * 1000)
    for marke in sorted(aus):
        d = aus[marke]
        print("\nNach %.0f Sekunden (%d Wiederholungen):" % (marke, d["n"]))
        print("  Ball x   Median %+7.1f m   [%+.1f, %+.1f]  (aus Sicht Heim)"
              % (d["ball_x"]["median"], d["ball_x"]["p10"], d["ball_x"]["p90"]))
        print("  Ball y   Median %+7.1f m   [%+.1f, %+.1f]"
              % (d["ball_y"]["median"], d["ball_y"]["p10"], d["ball_y"]["p90"]))
        print("  gefaehrliche Flaeche Heim  %7.1f   Gast %7.1f"
              % (d["gefahr_heim"]["median"], d["gefahr_gast"]["median"]))
        print("  Ballbesitz Heim  %.0f %%" % (d["ballbesitz_heim"] * 100))


# ----------------------------------------------------------------- Sonstiges
def befehl_drill(args):
    import tests
    print("Unbedraengter Abschluss, Torwart auf der Linie:\n")
    print(" %5s %12s %12s" % ("m", "Modell-xG", "tatsaechlich"))
    for d in (6, 11, 16, 22, 28):
        real, modell = tests.schussdrill(d, n=args.n, seed=d)
        print(" %5d %12.3f %12.3f" % (d, modell, real))


def befehl_tests(args):
    import tests
    raise SystemExit(tests.laufen(schnell=args.schnell))


# --------------------------------------------------------------------- main
def main(argv=None):
    p = argparse.ArgumentParser(
        description="Agentenbasierte 11-gegen-11-Fussballsimulation")
    p.add_argument("--ausfuehrlich", action="store_true")
    unter = p.add_subparsers(dest="befehl", required=True)

    a = unter.add_parser("spiel", help="ein Spiel simulieren")
    _gemeinsame_argumente(a)
    a.add_argument("--minuten", type=float, default=90.0)
    a.add_argument("--html", help="Animation als eigenstaendige HTML-Datei")
    a.add_argument("--bahn", help="Bahnaufzeichnung als JSON")
    a.add_argument("--spieler", action="store_true", help="Spielerwerte ausgeben")
    a.add_argument("--aufzeichnungsrate", type=int, default=5)
    a.set_defaults(fn=befehl_spiel)

    b = unter.add_parser("kontrafaktisch", help="zwei Varianten gepaart vergleichen")
    _gemeinsame_argumente(b)
    b.add_argument("--frage", default="abwehrhoehe", choices=sorted(FRAGEN))
    b.add_argument("--n", type=int, default=20, help="gepaarte Wiederholungen")
    b.add_argument("--minuten", type=float, default=10.0)
    b.add_argument("--wert", type=float, default=None)
    b.add_argument("--formation", default=None, choices=sorted(T.FORMATIONEN))
    b.add_argument("--json", default=None)
    b.set_defaults(fn=befehl_kontrafaktisch)

    c = unter.add_parser("situation", help="eine Spielsituation fortschreiben")
    _gemeinsame_argumente(c)
    c.add_argument("--ab", type=float, default=5.0, help="Minute der Ausgangslage")
    c.add_argument("--n", type=int, default=60)
    c.add_argument("--marken", default="5,10")
    c.set_defaults(fn=befehl_situation)

    d = unter.add_parser("drill", help="Schusskalibrierung pruefen")
    d.add_argument("--n", type=int, default=200)
    d.set_defaults(fn=befehl_drill)

    e = unter.add_parser("tests", help="Pruefungen laufen lassen")
    e.add_argument("--schnell", action="store_true")
    e.set_defaults(fn=befehl_tests)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
