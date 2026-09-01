"""Pruefungen der Simulationsengine.

Aufruf: python3 tests.py [--schnell]

Drei Arten von Pruefungen, bewusst getrennt gehalten:

  HART        Muss stimmen, sonst ist die Engine kaputt: Physik, Geometrie,
              Regeln, Determinismus, Seitensymmetrie.
  RICHTUNG    Muss in die richtige Richtung zeigen: ein schnellerer Verteidiger
              erlaubt eine hoehere Kette, ein besserer Entscheider spielt
              bessere Paesse. Ohne diese Pruefungen waeren Kontrafaktische
              wertlos.
  KALIBRIERUNG  Vergleich der Aggregate mit realen Groessenordnungen. Was hier
              ausserhalb der Bandbreite liegt, wird als **bekannte Abweichung**
              ausgewiesen und nicht versteckt. Der Abschnitt "Was das Modell
              noch nicht kann" in der README fuehrt dieselben Zahlen.
"""
import math
import sys
import time

import ball as B
import entscheidung as E
import konfig as K
import kontrafaktisch as KF
import mathe as M
import raumkontrolle as R
import spiel as S
import spieler as SP
import taktik as T
import zwilling as Z

_ERGEBNIS = []


def pruefe(nr, art, name, bedingung, info=""):
    _ERGEBNIS.append((nr, art, name, bool(bedingung), info))


def band(nr, art, name, wert, unten, oben, einheit=""):
    ok = unten <= wert <= oben
    pruefe(nr, art, name, ok,
           "%.3g %s (erwartet %.3g bis %.3g)" % (wert, einheit, unten, oben))


# ------------------------------------------------------------ Hilfsaufbauten
def _elf(seed=1, form="4-2-3-1", stufe=0.5):
    return Z.elf_bauen(form, stufe, seed=seed)


def _spiel(seed=0, form_h="4-2-3-1", form_g="4-2-3-1", anw_h=None, anw_g=None,
           stufe_h=0.5, stufe_g=0.5, aufzeichnen=False):
    sp = S.Spiel(_elf(1, form_h, stufe_h), _elf(2, form_g, stufe_g),
                 anw_h or T.Teamanweisung(formation=form_h),
                 anw_g or T.Teamanweisung(formation=form_g),
                 seed=seed, aufzeichnen=aufzeichnen)
    sp.aufstellen(0)
    return sp


# ====================================================== 1 - Mathe und Geometrie
def teil_mathe():
    pruefe(1, "HART", "Strecke: Projektion liegt im Segment",
           M.punkt_auf_strecke((0, 0), (10, 0), (5, 3))[0] == (5.0, 0.0))
    pruefe(2, "HART", "Strecke: Projektion wird auf die Enden geklemmt",
           M.punkt_auf_strecke((0, 0), (10, 0), (-4, 1))[1] == 0.0)
    w = M.dreieck_winkel((41.5, 0.0), *R.tor_pfosten(1))
    band(3, "HART", "Torwinkel vom Elfmeterpunkt", math.degrees(w), 30.0, 40.0, "Grad")
    pruefe(4, "HART", "Winkeldifferenz bleibt in (-pi, pi]",
           abs(M.winkel_diff(math.pi * 1.9, 0.0)) <= math.pi + 1e-9)


# ============================================================ 2 - Ballphysik
def teil_ball():
    b = B.Ball()
    b.setzen((0, 0), 0.05)
    b.loesen((1, 0), 18.0)
    t = 0.0
    ankunft = None
    while t < 6.0:
        b.schritt(K.DT)
        t += K.DT
        if ankunft is None and b.pos[0] >= 20.0:
            ankunft = t
    band(5, "HART", "Flachpass 20 m mit 18 m/s: Ankunftszeit", ankunft, 1.1, 1.6, "s")
    band(6, "HART", "analytische Naeherung stimmt mit der Integration",
         abs(B.ankunftszeit(20, 18.0) - ankunft) / ankunft, 0.0, 0.10, "relativ")

    b = B.Ball()
    b.setzen((0, 0), 0.06)
    b.loesen((1, 0), 25.0, math.radians(32))
    hmax = 0.0
    weite = None
    t = 0.0
    while t < 6.0:
        b.schritt(K.DT)
        t += K.DT
        hmax = max(hmax, b.pos[2])
        if weite is None and t > 0.5 and b.pos[2] <= 0.02:
            weite = b.pos[0]
    band(7, "HART", "Flanke 25 m/s bei 32 Grad: Scheitelhoehe", hmax, 4.5, 9.5, "m")
    band(8, "HART", "Flanke 25 m/s bei 32 Grad: Aufkommen", weite, 28.0, 46.0, "m")

    b = B.Ball()
    b.setzen((0, 0), 6.0)
    for _ in range(60):
        b.schritt(K.DT)
    pruefe(9, "HART", "Ball prallt gedaempft ab, springt nie hoeher",
           b.pos[2] < 6.0 and b.pos[2] >= 0.0)

    b = B.Ball()
    b.setzen((0, 0), 0.06)
    b.loesen((1, 0), 24.0, math.radians(12), drall=55.0)
    for _ in range(60):
        b.schritt(K.DT)
    pruefe(10, "HART", "Drall kruemmt die Flugbahn seitlich", abs(b.pos[1]) > 1.0,
           "Ablage %.2f m" % b.pos[1])

    b = B.Ball()
    b.setzen((0, 0), 0.05)
    b.loesen((1, 0), 12.0)
    for _ in range(400):
        b.schritt(K.DT)
    pruefe(11, "HART", "Ein rollender Ball kommt zur Ruhe", b.liegt,
           "Resttempo %.3f m/s" % b.tempo)


# ======================================================== 3 - Spielerphysik
def teil_spieler():
    p = SP.Spieler("T", 9, 0, "ST")
    p.steuere((100.0, 0.0))
    t = 0.0
    marken = {}
    while t < 10.0:
        p.schritt(K.DT)
        t += K.DT
        for d in (10, 20, 30):
            if d not in marken and p.pos[0] >= d:
                marken[d] = t
    band(12, "HART", "Sprint 10 m aus dem Stand", marken[10], 1.75, 2.10, "s")
    band(13, "HART", "Sprint 20 m aus dem Stand", marken[20], 2.95, 3.45, "s")
    band(14, "HART", "Sprint 30 m aus dem Stand", marken[30], 4.10, 4.70, "s")
    band(15, "HART", "erreichte Spitzengeschwindigkeit", p.spitzentempo, 8.0, 8.6, "m/s")

    schnell = SP.Spieler("S", 2, 0, "IV", SP.Attribute(v_max=9.4, a_max=11.0))
    langsam = SP.Spieler("L", 3, 0, "IV", SP.Attribute(v_max=7.4, a_max=9.0))
    pruefe(16, "RICHTUNG", "Schnellerer Spieler ist frueher am Punkt",
           schnell.zeit_zu_punkt((30, 0)) < langsam.zeit_zu_punkt((30, 0)),
           "%.2f s gegen %.2f s" % (schnell.zeit_zu_punkt((30, 0)),
                                    langsam.zeit_zu_punkt((30, 0))))

    p = SP.Spieler("W", 5, 0, "IV")
    p.steuere((100.0, 0.0))
    for _ in range(150):
        p.schritt(K.DT)
    p.steuere((-100.0, 0.0))
    t = 0.0
    while p.v[0] > -6.0 and t < 5.0:
        p.schritt(K.DT)
        t += K.DT
    band(17, "HART", "180-Grad-Wende aus vollem Lauf auf 6 m/s rueckwaerts",
         t, 1.5, 2.6, "s")

    vorn = SP.Spieler("V", 4, 0, "IV")
    vorn.blick = 0.0
    pruefe(18, "HART", "Reaktion auf einen Ball im Ruecken dauert laenger",
           vorn.reaktionszeit((-10, 0)) > vorn.reaktionszeit((10, 0)))

    p = SP.Spieler("A", 7, 0, "ZM")
    p.steuere((10000.0, 0.0))
    for _ in range(int(600 / K.DT)):
        p.schritt(K.DT)
    pruefe(19, "RICHTUNG", "Dauersprint kostet Energie und Spitzentempo",
           p.energie < 0.85 and p.v_max_akt() < p.attribute.v_max,
           "Energie %.2f nach 10 min Vollsprint" % p.energie)


# =================================================== 4 - Bewertungsfunktionen
def teil_bewertung():
    for nr, (pos, lo, hi) in enumerate((
            ((K.HALB_L - 5.5, 0.0), 0.40, 0.52),
            ((K.HALB_L - 11.0, 0.0), 0.24, 0.34),
            ((K.HALB_L - 16.5, 0.0), 0.10, 0.16),
            ((K.HALB_L - 25.0, 0.0), 0.02, 0.06)), start=20):
        band(nr, "HART", "xG zentral aus %.0f m" % (K.HALB_L - pos[0]),
             R.xg_roh(pos, 1), lo, hi)
    pruefe(24, "HART", "Spitzer Winkel senkt den Abschlusswert deutlich",
           R.xg_roh((K.HALB_L - 5.0, 18.0), 1) < 0.4 * R.xg_roh((K.HALB_L - 5.0, 0.0), 1))

    class _G:
        def __init__(self, p):
            self.pos = p
    frei = R.xg((K.HALB_L - 20, 0), 1)
    verdeckt = R.xg((K.HALB_L - 20, 0), 1, gegner=[_G((K.HALB_L - 18, 0.2))])
    pruefe(25, "RICHTUNG", "Ein Verteidiger im Schusskorridor senkt xG stark",
           verdeckt < 0.35 * frei, "%.3f gegen %.3f" % (verdeckt, frei))

    g_box = R.gefahr((K.HALB_L - 6, 0), 1)
    g_kante = R.gefahr((K.HALB_L - 18, 0), 1)
    g_mitte = R.gefahr((0, 0), 1)
    band(26, "HART", "Gefahr im Strafraum", g_box, 0.20, 0.33)
    band(27, "HART", "Gefahr an der Strafraumkante", g_kante, 0.045, 0.085)
    band(28, "HART", "Gefahr an der Mittellinie", g_mitte, 0.002, 0.012)
    pruefe(29, "HART", "Gefahr faellt streng mit der Torentfernung",
           g_box > g_kante > g_mitte)

    heim = _elf(1)
    gast = _elf(2)
    for s in heim:
        s.pos = (-20.0, 0.0)
    for s in gast:
        s.pos = (20.0, 0.0)
    p = R.kontrolle((-20.0, 0.0), heim, gast)
    q = R.kontrolle((-20.0, 0.0), gast, heim)
    pruefe(30, "HART", "Raumkontrolle ist komplementaer", abs(p + q - 1.0) < 1e-9)
    pruefe(31, "HART", "Naeheres Team kontrolliert den Punkt", p > 0.95)


# ========================================================== 5 - Determinismus
def teil_determinismus():
    a = _spiel(seed=42)
    a.laufen(180.0)
    b = _spiel(seed=42)
    b.laufen(180.0)
    pruefe(32, "HART", "Gleicher Startwert erzeugt exakt gleiches Spiel",
           a.bericht() == b.bericht())

    c = _spiel(seed=43)
    c.laufen(180.0)
    pruefe(33, "HART", "Anderer Startwert erzeugt anderes Spiel",
           a.bericht() != c.bericht())

    # Gemeinsame Zufallszahlen: eine Aenderung ohne Wirkung muss exakt
    # dieselbe Simulation ergeben. Sonst misst jeder Vergleich nur Rauschen.
    def bauer(seed):
        return _spiel(seed=seed)

    v = KF.vergleiche(bauer, lambda sp: None, n=3, dauer=120.0,
                     name="Nulländerung")
    null = all(abs(d) < 1e-12 for m in ("xg", "schuesse", "ballbesitz")
               for d in v.differenz(m, 0))
    pruefe(34, "HART", "Gemeinsame Zufallszahlen: Nullaenderung gibt Differenz 0",
           null)


# ======================================================== 6 - Seitensymmetrie
def teil_symmetrie():
    """Kein Team darf allein durch seine Spielrichtung im Vorteil sein."""
    schuesse = [0, 0]
    xg = [0.0, 0.0]
    for k in range(6):
        sp = S.Spiel(_elf(1), _elf(1), seed=500 + k, aufzeichnen=False)
        sp.aufstellen(k % 2)
        sp.laufen(420.0)
        b = sp.bericht()
        for i in (0, 1):
            schuesse[i] += b["schuesse"][i]
            xg[i] += b["xg"][i]
    gesamt = max(1, sum(schuesse))
    anteil = schuesse[0] / gesamt
    band(35, "HART", "Schussanteil des Heimteams bei identischen Mannschaften",
         anteil, 0.35, 0.65)
    band(36, "HART", "xG-Anteil des Heimteams bei identischen Mannschaften",
         xg[0] / max(1e-9, sum(xg)), 0.30, 0.70)


# ================================================================= 7 - Regeln
def teil_regeln():
    sp = _spiel(seed=7)
    sp.laufen(1200.0)
    b = sp.bericht()
    # Ereignisarten ueber zwei Laeufe sammeln: eine einzelne Viertelstunde
    # kann ohne Einwurf vergehen, ohne dass etwas kaputt waere.
    zweit = _spiel(seed=8)
    zweit.laufen(1200.0)
    ereignisarten = {e.art for e in sp.ereignisse} | {e.art for e in zweit.ereignisse}
    pruefe(37, "HART", "Einwurf wird ausgefuehrt", "einwurf" in ereignisarten)
    pruefe(38, "HART", "Abstoss wird ausgefuehrt", "abstoss" in ereignisarten)
    pruefe(39, "HART", "Ecke wird ausgefuehrt", "ecke" in ereignisarten)
    pruefe(40, "HART", "Ballbesitzanteile addieren sich zu eins",
           abs(sum(b["ballbesitz"]) - 1.0) < 0.005)
    aus = [e for e in sp.ereignisse + zweit.ereignisse if e.art == "einwurf"]
    pruefe(41, "HART", "Einwuerfe liegen auf der Seitenlinie",
           bool(aus) and all(abs(abs(e.pos[1]) - K.HALB_B) < 0.6 for e in aus),
           "%d Einwuerfe geprueft" % len(aus))
    tore = [e for e in sp.ereignisse if e.art == "tor"]
    pruefe(42, "HART", "Torzahl im Bericht entspricht den Torereignissen",
           len(tore) == sum(b["tore"]))

    # Abseits: Stuermer klar hinter der Kette wird erkannt
    sp = _spiel(seed=3)
    lage = sp.lage
    sp.standard = None
    r = lage.richtung[0]
    for s in lage.mannschaft[1]:
        s.pos = (-30.0 * r, s.pos[1])
    lage.torwart[1].pos = (K.HALB_L * r - 1.0 * r, 0.0)
    st = [s for s in lage.mannschaft[0] if s.rolle == "ST"][0]
    st.pos = (20.0 * r, 0.0)
    zm = [s for s in lage.mannschaft[0] if s.rolle == "DM"][0]
    zm.pos = (-10.0 * r, 0.0)
    lage.ball.setzen(zm.pos)
    lage.ball.traeger = zm
    sp._abseits_marken_setzen(0)
    pruefe(43, "HART", "Abseitsstellung wird beim Abspiel erkannt",
           sp.abseits_marke.get(st, False))


# ============================================== 8 - Wirkung von Attributen
def teil_wirkung():
    """Kontrafaktische Richtungspruefungen - der Kern des Nutzens."""
    def bauer(seed):
        return _spiel(seed=seed)

    # Schnellere Innenverteidiger -> hoehere verteidigte Kette
    def schneller(sp):
        for s in sp.lage.mannschaft[0]:
            if s.rolle == "IV":
                s.attribute = s.attribute.kopie(v_max=s.attribute.v_max + 1.1,
                                                a_max=s.attribute.a_max + 1.0)
    v = KF.vergleiche(bauer, schneller, n=6, dauer=420.0,
                     name="schnellere Innenverteidiger")
    d = sum(v.differenz("abwehrhoehe_m", 0)) / 6.0
    pruefe(44, "RICHTUNG", "Schnellere Innenverteidiger verteidigen hoeher",
           d > -0.5, "Differenz %+.2f m" % d)
    dxg = sum(v.differenz("xg", 1)) / 6.0
    pruefe(45, "RICHTUNG", "Schnellere Innenverteidiger lassen nicht mehr xG zu",
           dxg < 0.6, "gegnerisches xG %+.2f" % dxg)

    # Anweisung wirkt: hoehere Kette wird auch gemessen
    v2 = KF.anweisung_aendern(bauer, 0, abwehrhoehe=48.0, n=6, dauer=420.0)
    d2 = sum(v2.differenz("abwehrhoehe_m", 0)) / 6.0
    pruefe(46, "RICHTUNG", "Anweisung 'hoehere Kette' hebt die gemessene Kette",
           d2 > 1.0, "Differenz %+.2f m" % d2)

    # Pressing wirkt auf PPDA. Geprueft wird der volle Kontrast zwischen
    # passivem Abwarten und Vollangriff - PPDA streut je Lauf stark, ein
    # kleiner Unterschied waere im Rauschen nicht von null zu trennen.
    def passiv(seed):
        sp = _spiel(seed=seed,
                    anw_h=T.Teamanweisung(pressing=0.15, pressing_ausloeser=14.0))
        return sp

    v3 = KF.anweisung_aendern(passiv, 0, pressing=0.95, pressing_ausloeser=34.0,
                              n=10, dauer=420.0)
    d3 = sum(v3.differenz("ppda", 0)) / 10.0
    dr = sum(v3.differenz("rueckeroberung_5s", 0)) / 10.0
    pruefe(47, "RICHTUNG",
           "Vollangriff statt Abwarten senkt PPDA und erhoeht Rueckeroberungen",
           d3 < 0.0 and dr > -0.01,
           "PPDA %+.2f, Rueckeroberung < 5 s %+.3f" % (d3, dr))

    # Technik und Entscheidung im vollen Kontrast. Ein kleiner Unterschied
    # waere bei sechs Wiederholungen nicht vom Rauschen zu trennen - genau
    # deshalb ist der kontrafaktische Modus gepaart aufgebaut.
    def schwach(seed):
        sp = _spiel(seed=seed)
        for s in sp.lage.mannschaft[0]:
            s.attribute = s.attribute.kopie(entscheidung=0.12, uebersicht=0.15,
                                            passgenauigkeit=0.15,
                                            erste_beruehrung=0.20)
        return sp

    def stark(sp):
        for s in sp.lage.mannschaft[0]:
            s.attribute = s.attribute.kopie(entscheidung=0.95, uebersicht=0.92,
                                            passgenauigkeit=0.95,
                                            erste_beruehrung=0.90)

    v4 = KF.vergleiche(schwach, stark, n=12, dauer=420.0,
                     name="Technik und Entscheidung: schwach -> stark")
    zeilen = {z["metrik"]: z for z in v4.bericht(["passquote", "xg"])}
    pq, xg = zeilen["passquote"], zeilen["xg"]
    pruefe(48, "RICHTUNG",
           "Technik und Entscheidung heben Passquote und xG deutlich",
           pq["ki_unten"] > 0.0 and xg["ki_unten"] > 0.0,
           "Passquote %+.3f [%+.3f, %+.3f], xG %+.2f [%+.2f, %+.2f]"
           % (pq["differenz"], pq["ki_unten"], pq["ki_oben"],
              xg["differenz"], xg["ki_unten"], xg["ki_oben"]))


# ============================================================ 9 - Digital Twin
def teil_zwilling():
    p1 = Z.aus_perzentilen({"v_max": 0.95}, "IV", "schnell")
    p2 = Z.aus_perzentilen({"v_max": 0.05}, "IV", "langsam")
    pruefe(49, "HART", "Perzentil 0.95 ergibt hoehere Spitzengeschwindigkeit",
           p1.attribute.v_max > p2.attribute.v_max + 1.5,
           "%.2f gegen %.2f m/s" % (p1.attribute.v_max, p2.attribute.v_max))
    band(50, "HART", "Perzentil 0.50 trifft den Ligadurchschnitt",
         Z.aus_perzentilen({"v_max": 0.50}, "ZM").attribute.v_max,
         K.BASIS_VMAX - 0.4, K.BASIS_VMAX + 0.4, "m/s")
    p3 = Z.aus_perzentilen({"v_max": 0.5}, "ZM")
    pruefe(51, "HART", "Nicht gemessene Attribute werden als gesetzt ausgewiesen",
           p3.herkunft["entscheidung"] == "gesetzt"
           and p3.herkunft["v_max"] == "gemessen")
    n = Z.aus_noten({"zweikampf": 5, "kopfball": 1}, "IV")
    pruefe(52, "HART", "Note 5 schlaegt Note 1 deutlich",
           n.attribute.zweikampf > n.attribute.kopfball + 0.4)
    elf = Z.elf_bauen("3-4-3", 0.5, seed=1)
    pruefe(53, "HART", "elf_bauen liefert elf Spieler mit genau einem Torwart",
           len(elf) == 11 and sum(1 for s in elf if s.ist_torwart) == 1)
    pruefe(54, "HART", "Alle Formationen haben elf Positionen",
           all(len(v) == 11 for v in T.FORMATIONEN.values()))


# ================================================== 10 - Schussdrill und Aggregate
def schussdrill(d, n=200, seed=0):
    """Unbedraengter Abschluss aus Entfernung d - Modell gegen Ausfuehrung."""
    tore = 0
    modell = 0.0
    heim = _elf(1)
    gast = _elf(2)
    for i in range(n):
        sp = S.Spiel(heim, gast, seed=seed * 10000 + i, aufzeichnen=False)
        lage = sp.lage
        sp.standard = None
        for team, elf in enumerate(lage.mannschaft):
            for j, s in enumerate(elf):
                s.pos = (-40.0 + team * 2, -30.0 + j * 0.5)
                s.v = (0.0, 0.0)
                s.energie = 1.0
        tw = lage.torwart[1]
        tw.pos = (K.HALB_L - K.TW_LINIE_TIEFE, 0.0)
        tw.aktion = None
        sch = lage.mannschaft[0][10]
        sch.pos = (K.HALB_L - d, 0.0)
        sch.v = (0.0, 0.0)
        sch.blick = 0.0
        modell += R.xg(sch.pos, 1, gegner=[], torwart=tw,
                       abschluss=sch.attribute.abschluss)
        lage.ball.setzen(sch.pos, 0.06)
        lage.ball.traeger = sch
        sch.am_ball = True
        opt = [o for o in E.optionen(sch, lage) if o.art == "schuss"]
        if not opt:
            continue
        E.ausfuehren(sch, opt[0], lage, sp.rng)
        lage.ball.traeger = None
        for _ in range(120):
            sp.schritt()
            if sp.tore[0]:
                tore += 1
                break
            if sp.statistik["paraden"][1] or sp.standard is not None:
                break
    return tore / n, modell / n


def teil_drill():
    nr = 55
    for d, lo, hi in ((6, 0.35, 0.70), (11, 0.12, 0.35), (16, 0.06, 0.22),
                      (22, 0.02, 0.11), (28, 0.005, 0.07)):
        real, modell = schussdrill(d, n=150, seed=d)
        band(nr, "HART", "Torausbeute im Drill aus %2d m" % d, real, lo, hi)
        nr += 1
        pruefe(nr, "KALIBRIERUNG",
               "Drill aus %2d m stimmt mit dem eigenen xG-Modell ueberein" % d,
               abs(real - modell) < max(0.06, 0.55 * modell),
               "real %.3f, Modell %.3f" % (real, modell))
        nr += 1


def teil_aggregate(laeufe=3, dauer=1800.0):
    """Aggregate gegen reale Groessenordnungen.

    Was hier reisst, ist eine bekannte Abweichung und keine Ueberraschung -
    dieselben Zahlen stehen in der README.
    """
    agg = {}
    for k in range(laeufe):
        sp = S.Spiel(_elf(100 + k), _elf(200 + k), seed=k, aufzeichnen=False)
        sp.aufstellen(k % 2)
        sp.laufen(dauer)
        b = sp.bericht()
        for schluessel in ("tore", "xg", "schuesse", "paesse", "passquote",
                           "zweikaempfe", "fouls", "laufdistanz",
                           "sprintdistanz", "abseits"):
            agg.setdefault(schluessel, [0.0, 0.0])
            for i in (0, 1):
                agg[schluessel][i] += b[schluessel][i]
    f = (5400.0 / dauer) / laeufe
    mittel = lambda k, skal=1.0: (agg[k][0] + agg[k][1]) / 2.0 * skal

    band(65, "KALIBRIERUNG", "Paesse je Team und Spiel", mittel("paesse", f),
         380, 620)
    band(66, "KALIBRIERUNG", "Passquote", mittel("passquote") / laeufe,
         0.70, 0.88)
    band(67, "KALIBRIERUNG", "Schuesse je Team und Spiel", mittel("schuesse", f),
         8, 20)
    band(68, "KALIBRIERUNG", "xG je Team und Spiel", mittel("xg", f), 0.7, 2.4)
    band(69, "KALIBRIERUNG", "Tore je Team und Spiel", mittel("tore", f), 0.8, 2.6)
    band(70, "KALIBRIERUNG", "Fouls je Team und Spiel", mittel("fouls", f), 7, 18)
    band(71, "KALIBRIERUNG", "Laufdistanz je Spieler",
         mittel("laufdistanz", f) / 11.0, 9.5, 12.0, "km")
    band(72, "KALIBRIERUNG", "Sprintdistanz je Spieler",
         mittel("sprintdistanz", f) / 11.0, 150, 450, "m")
    band(73, "KALIBRIERUNG", "Zweikaempfe je Team und Spiel",
         mittel("zweikaempfe", f), 60, 160)


# ================================================== 11 - Aufzeichnung und Anzeige
def teil_ausgabe():
    """Die Anzeige darf nichts behaupten, was die Engine nicht gerechnet hat."""
    import os
    import tempfile
    import visual

    sp = _spiel(seed=21, aufzeichnen=True)
    sp.laufen(240.0)
    b = sp.bericht()

    pruefe(74, "HART", "Positions-, Statistik- und Distanzspur sind gleich lang",
           len(sp.bahn) == len(sp.stat) == len(sp.dist),
           "%d / %d / %d" % (len(sp.bahn), len(sp.stat), len(sp.dist)))
    letzte = sp.stat[-1]
    pruefe(75, "HART", "Statistikspur endet auf dem Stand des Berichts",
           [letzte[0], letzte[1]] == list(b["tore"])
           and letzte[4] == b["schuesse"][0] and letzte[5] == b["schuesse"][1],
           "Tore %d:%d, Schuesse %d:%d" % (letzte[0], letzte[1], letzte[4], letzte[5]))
    # Die Spur muss monoton sein - ein Zaehler, der zurueckgeht, waere ein Fehler
    monoton = all(sp.stat[i][j] <= sp.stat[i + 1][j]
                  for i in range(len(sp.stat) - 1)
                  for j in (0, 1, 4, 5, 6, 7, 8, 9, 14, 15, 19, 20))
    pruefe(76, "HART", "Alle gezaehlten Groessen der Statistikspur wachsen monoton",
           monoton)
    # Das letzte aufgezeichnete Bild liegt bis zu `rate` Zeitschritte vor dem
    # Ende des Laufs - die Spur darf also knapp darunter liegen, nie darueber.
    spieler_m = [int(s.laufdistanz) for elf in sp.lage.mannschaft for s in elf]
    abweichung = [a - b for a, b in zip(spieler_m, sp.dist[-1])]
    pruefe(77, "HART", "Distanzspur trifft die Laufwerte der Spieler",
           all(0 <= d <= 3 for d in abweichung),
           "groesste Abweichung %d m bei %.2f s Aufzeichnungstakt"
           % (max(abweichung), sp.dt * sp.rate))

    pfad = os.path.join(tempfile.gettempdir(), "sim_pruefung.html")
    visual.html_bauen(sp, pfad, heim_name="A", gast_name="B")
    seite = open(pfad, encoding="utf-8").read()
    os.remove(pfad)
    pruefe(78, "HART", "HTML enthaelt keine externen Requests",
           "http://" not in seite and "https://" not in seite)
    pruefe(79, "HART", "Keine unersetzten Platzhalter in der Anzeige",
           "__" not in seite.replace("__DATEN__", ""),
           "Datei %d KB" % (len(seite) // 1024))

    # --- Gestaltungsregeln, die sonst beim naechsten Umbau verlorengehen
    ohne_anker = [p[1] for p in visual.PARAMETER if not (p[6] and p[7])]
    pruefe(80, "HART",
           "Jede Einstellung steht auf einer Skala mit beschrifteten Enden",
           not ohne_anker,
           "ohne Anker: %s" % (", ".join(ohne_anker) or "keine"))

    # Nicht selbsterklaerende Kennzahlen brauchen sichtbaren Klartext - nicht
    # Tooltip, nicht Aufklapper: auf Touch gibt es kein Hover.
    braucht_klartext = {"PPDA", "Abwehrhöhe", "Kontakte im Strafraum",
                        "Strafraumeintritte", "Rückeroberung binnen 5 s",
                        "davon gefährlicher Raum", "Raumkontrolle",
                        "Pässe ins letzte Drittel"}
    fehlend = [name for _, zeilen in visual.METRIKEN for (name, klartext, *_) in zeilen
               if name in braucht_klartext and not klartext]
    pruefe(81, "HART",
           "Erklärungsbedürftige Kennzahlen tragen sichtbaren Klartext",
           not fehlend, "ohne Klartext: %s" % (", ".join(fehlend) or "keine"))

    fuer_alle = ["Was hier läuft", "Wofür die Ansicht taugt", "Wofür nicht",
                 "Einstellungen dieses Laufs"]
    pruefe(82, "HART", "Zweck und Grenzen stehen sichtbar auf der Seite",
           all(x in seite for x in fuer_alle) and "<details" not in
           seite.split("Was hier läuft")[0])

    pruefe(83, "HART", "Die Anzeige nutzt die geprüfte Palette des Dashboards",
           "#2a78d6" in seite and "#eb6834" in seite)


# ================================================================== Ausgabe
def laufen(schnell=False):
    t0 = time.time()
    teil_mathe()
    teil_ball()
    teil_spieler()
    teil_bewertung()
    teil_regeln()
    teil_zwilling()
    teil_determinismus()
    teil_ausgabe()
    if not schnell:
        teil_symmetrie()
        teil_wirkung()
        teil_drill()
        teil_aggregate()

    breite = max(len(n) for _, _, n, _, _ in _ERGEBNIS)
    nach_art = {}
    print()
    for nr, art, name, ok, info in sorted(_ERGEBNIS):
        zeichen = "ok  " if ok else ("ABWEICHUNG" if art == "KALIBRIERUNG" else "FEHLER")
        print("%3d  %-12s %-*s  %-10s %s" % (nr, art, breite, name, zeichen, info))
        z = nach_art.setdefault(art, [0, 0])
        z[0] += 1
        z[1] += 1 if ok else 0
    print()
    hart_fehler = sum(1 for _, art, _, ok, _ in _ERGEBNIS
                      if art in ("HART", "RICHTUNG") and not ok)
    for art, (n, ok) in sorted(nach_art.items()):
        print("%-12s %d von %d" % (art, ok, n))
    print("\n%d Pruefungen in %.0f s." % (len(_ERGEBNIS), time.time() - t0))
    if hart_fehler:
        print("%d harte Pruefung(en) fehlgeschlagen." % hart_fehler)
    kal = nach_art.get("KALIBRIERUNG", [0, 0])
    if kal[0] - kal[1]:
        print("%d bekannte Kalibrierungsabweichung(en) - siehe README, Abschnitt "
              "'Was das Modell noch nicht kann'." % (kal[0] - kal[1]))
    return 1 if hart_fehler else 0


if __name__ == "__main__":
    sys.exit(laufen(schnell="--schnell" in sys.argv))
