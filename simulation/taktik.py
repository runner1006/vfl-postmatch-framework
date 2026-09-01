"""Taktische Schicht: Formationen, Rollen, Anweisungen, Positionsfindung.

Diese Schicht beantwortet fuer jeden Spieler ohne Ball die Frage "wo will ich
in diesem Moment stehen?". Sie schreibt ausschliesslich Zielpunkte; wie
schnell ein Spieler dort ankommt, entscheidet allein seine Physik. Genau
darum wirkt sich ein schnellerer Innenverteidiger auf die moegliche
Abwehrhoehe aus, ohne dass irgendwo eine Regel "schnell -> hoch" stuende: die
Anweisung setzt die Linie, die Physik entscheidet, ob sie zu halten ist.

Arbeitsrahmen
-------------
Alle Berechnungen laufen im **Angriffsrahmen** des jeweiligen Teams: x = +52.5
ist immer das gegnerische Tor, y ist ballseitig vorzeichenrichtig. Der Wechsel
ins Weltsystem ist eine Multiplikation mit `richtung`. Dadurch braucht keine
Regel eine Fallunterscheidung nach Spielrichtung oder Halbzeit.
"""
import math

import konfig as K
import mathe as M
import raumkontrolle as R

# --------------------------------------------------------------- Rollentypen
# linie: 1 = Abwehrkette, 2 = Mittelfeld, 3 = Angriff, 0 = Torwart
ROLLEN = {
    "TW":  dict(linie=0, fluegel=0, defensiv=1.0),
    "IV":  dict(linie=1, fluegel=0, defensiv=0.95),
    "LV":  dict(linie=1, fluegel=-1, defensiv=0.70),
    "RV":  dict(linie=1, fluegel=+1, defensiv=0.70),
    "DM":  dict(linie=2, fluegel=0, defensiv=0.80),
    "ZM":  dict(linie=2, fluegel=0, defensiv=0.55),
    "LM":  dict(linie=2, fluegel=-1, defensiv=0.55),
    "RM":  dict(linie=2, fluegel=+1, defensiv=0.55),
    "OM":  dict(linie=3, fluegel=0, defensiv=0.30),
    "LA":  dict(linie=3, fluegel=-1, defensiv=0.28),
    "RA":  dict(linie=3, fluegel=+1, defensiv=0.28),
    "ST":  dict(linie=3, fluegel=0, defensiv=0.18),
}

# Formationen als Grundpositionen im Angriffsrahmen.
# x: Anteil der Feldlaenge vom eigenen Tor (0.0) zum gegnerischen (1.0)
# y: Meter von der Mittelachse, negativ = links aus Sicht der Angriffsrichtung
FORMATIONEN = {
    "4-2-3-1": [
        ("TW", 0.030, 0.0), ("IV", 0.160, -8.0), ("IV", 0.160, 8.0),
        ("LV", 0.200, -22.0), ("RV", 0.200, 22.0),
        ("DM", 0.330, -7.0), ("DM", 0.330, 7.0),
        ("LM", 0.520, -21.0), ("OM", 0.520, 0.0), ("RM", 0.520, 21.0),
        ("ST", 0.680, 0.0),
    ],
    "4-3-3": [
        ("TW", 0.030, 0.0), ("IV", 0.160, -8.0), ("IV", 0.160, 8.0),
        ("LV", 0.205, -22.0), ("RV", 0.205, 22.0),
        ("DM", 0.320, 0.0), ("ZM", 0.450, -10.0), ("ZM", 0.450, 10.0),
        ("LA", 0.620, -24.0), ("ST", 0.700, 0.0), ("RA", 0.620, 24.0),
    ],
    "3-4-3": [
        ("TW", 0.030, 0.0),
        ("IV", 0.170, -13.0), ("IV", 0.150, 0.0), ("IV", 0.170, 13.0),
        ("LM", 0.390, -27.0), ("DM", 0.330, -6.0), ("DM", 0.330, 6.0),
        ("RM", 0.390, 27.0),
        ("LA", 0.620, -19.0), ("ST", 0.700, 0.0), ("RA", 0.620, 19.0),
    ],
    "4-4-2": [
        ("TW", 0.030, 0.0), ("IV", 0.160, -8.0), ("IV", 0.160, 8.0),
        ("LV", 0.200, -22.0), ("RV", 0.200, 22.0),
        ("LM", 0.450, -22.0), ("ZM", 0.400, -7.0), ("ZM", 0.400, 7.0),
        ("RM", 0.450, 22.0),
        ("ST", 0.660, -7.0), ("ST", 0.660, 7.0),
    ],
    "5-3-2": [
        ("TW", 0.030, 0.0),
        ("IV", 0.150, -12.0), ("IV", 0.140, 0.0), ("IV", 0.150, 12.0),
        ("LV", 0.260, -25.0), ("RV", 0.260, 25.0),
        ("DM", 0.350, 0.0), ("ZM", 0.470, -10.0), ("ZM", 0.470, 10.0),
        ("ST", 0.660, -7.0), ("ST", 0.660, 7.0),
    ],
    "4-2-2-2": [
        ("TW", 0.030, 0.0), ("IV", 0.160, -8.0), ("IV", 0.160, 8.0),
        ("LV", 0.205, -22.0), ("RV", 0.205, 22.0),
        ("DM", 0.330, -8.0), ("DM", 0.330, 8.0),
        ("LM", 0.530, -17.0), ("RM", 0.530, 17.0),
        ("ST", 0.680, -7.0), ("ST", 0.680, 7.0),
    ],
}


class Teamanweisung:
    """Die taktischen Stellschrauben einer Mannschaft.

    Alles hier ist im Kontrafaktischen einzeln verstellbar. Die Einheiten sind
    absichtlich physisch: `abwehrhoehe` steht in Metern von der eigenen
    Torlinie, nicht auf einer Skala von 1 bis 10.
    """
    __slots__ = ("formation", "abwehrhoehe", "kompaktheit", "pressing",
                 "pressing_ausloeser", "breite", "tempo", "risiko",
                 "manndeckung", "abseitsfalle", "gegenpressing", "lenken",
                 "aufruecken_aussen")

    def __init__(self, formation="4-2-3-1", abwehrhoehe=38.0, kompaktheit=0.6,
                 pressing=0.6, pressing_ausloeser=26.0, breite=25.0,
                 tempo=0.5, risiko=0.5, manndeckung=0.25, abseitsfalle=0.4,
                 gegenpressing=0.6, lenken=0.4, aufruecken_aussen=0.6):
        self.formation = formation
        self.abwehrhoehe = abwehrhoehe          # m von eigener Torlinie
        self.kompaktheit = kompaktheit          # 0 = weit, 1 = eng
        self.pressing = pressing                # 0 = abwarten, 1 = Vollangriff
        self.pressing_ausloeser = pressing_ausloeser  # m Ballentfernung
        self.breite = breite                    # m Halbbreite im Ballbesitz
        self.tempo = tempo                      # 0 = kontrolliert, 1 = direkt
        self.risiko = risiko                    # Gewicht des Ballverlusts
        self.manndeckung = manndeckung          # Anteil Mann- statt Raumdeckung
        self.abseitsfalle = abseitsfalle        # Bereitschaft, die Linie zu halten
        self.gegenpressing = gegenpressing      # Intensitaet in den ersten 5 s
        self.lenken = lenken                    # 0 = zentral stellen, 1 = nach aussen
        self.aufruecken_aussen = aufruecken_aussen  # wie hoch die Aussenverteidiger gehen

    def kopie(self, **aenderungen):
        werte = {n: getattr(self, n) for n in self.__slots__}
        unbekannt = set(aenderungen) - set(self.__slots__)
        if unbekannt:
            raise KeyError("unbekannte Anweisungen: %s" % sorted(unbekannt))
        werte.update(aenderungen)
        return Teamanweisung(**werte)

    def als_dict(self):
        return {n: getattr(self, n) for n in self.__slots__}


VORLAGEN = {
    "hoch_pressend": Teamanweisung(abwehrhoehe=46.0, kompaktheit=0.75,
                                   pressing=0.85, pressing_ausloeser=32.0,
                                   tempo=0.62, risiko=0.6, gegenpressing=0.85,
                                   abseitsfalle=0.65),
    "ausgeglichen": Teamanweisung(),
    "tiefer_block": Teamanweisung(abwehrhoehe=26.0, kompaktheit=0.85,
                                  pressing=0.30, pressing_ausloeser=16.0,
                                  tempo=0.65, risiko=0.35, gegenpressing=0.30,
                                  abseitsfalle=0.2, aufruecken_aussen=0.35),
    "ballbesitz": Teamanweisung(abwehrhoehe=42.0, kompaktheit=0.5,
                                pressing=0.7, pressing_ausloeser=28.0,
                                breite=28.0, tempo=0.30, risiko=0.35,
                                gegenpressing=0.8),
}


# --------------------------------------------------------------- Hilfsrahmen
def in_weltrahmen(p, richtung):
    """Angriffsrahmen -> Weltsystem. Die Umkehrung ist dieselbe Operation."""
    return (p[0] * richtung, p[1] * richtung)


def formation_bauen(schluessel):
    if schluessel not in FORMATIONEN:
        raise KeyError("unbekannte Formation %r, bekannt: %s"
                       % (schluessel, sorted(FORMATIONEN)))
    return FORMATIONEN[schluessel]


# ---------------------------------------------------------- Linienberechnung
def abwehrlinie(lage, team):
    """x-Koordinate der Abwehrkette im Angriffsrahmen des Teams.

    Zwei Faelle:
      - eigener Ballbesitz: die Kette rueckt auf, begrenzt durch die
        Anweisung und durch den Abstand zum Ball (Spiel nicht auseinanderreissen)
      - gegnerischer Ballbesitz: die Kette orientiert sich am Ball und an der
        angewiesenen Hoehe, geht aber nie tiefer als kurz vor den eigenen Fuenfer
    """
    a = lage.anweisung[team]
    richtung = lage.richtung[team]
    bx = lage.ball.pos[0] * richtung
    hoehe = -K.HALB_L + a.abwehrhoehe

    if lage.phasenbesitz == team:
        linie = min(bx - 11.0, hoehe + 9.0)
    else:
        linie = min(bx - 5.0, hoehe)
    return M.klemme(linie, -K.HALB_L + 5.0, K.HALB_L - 12.0)


def abseitslinie(lage, team):
    """x der Abseitslinie fuer angreifendes `team`, im Angriffsrahmen.

    Zweitletzter Verteidiger der Gegenseite bzw. Mittellinie, je nachdem was
    weiter hinten liegt.
    """
    richtung = lage.richtung[team]
    gegner = lage.mannschaft[1 - team]
    xs = sorted((s.pos[0] * richtung for s in gegner), reverse=True)
    if len(xs) < 2:
        return K.HALB_L
    return max(xs[1], 0.0)


# ----------------------------------------------------- Zielpunkt ohne Ball
def zielposition(sp, lage):
    """Wunschposition eines Spielers ohne Ball, im Weltsystem.

    Aufbau: Grundposition aus der Formation, dann drei Verschiebungen
    (Ballbezug, Linienbindung, Rollenauftrag) und zuletzt eine Abstossung von
    zu nahen Mitspielern. Die Reihenfolge ist wichtig - der Rollenauftrag darf
    die Linienbindung ueberschreiben, die Abstossung aber niemals so stark,
    dass die Kette zerfaellt.
    """
    team = sp.team
    richtung = lage.richtung[team]
    a = lage.anweisung[team]
    rolle = ROLLEN[sp.rolle]
    basis = lage.grundposition[sp.nummer, team]        # im Angriffsrahmen
    bx = lage.ball.pos[0] * richtung
    by = lage.ball.pos[1] * richtung

    if sp.ist_torwart:
        return _torwartposition(sp, lage)

    besitz = lage.phasenbesitz
    zx, zy = basis

    if besitz == team:
        # ------------------------------------------------ eigener Ballbesitz
        zx += 0.30 * bx
        zy += 0.22 * by
        if rolle["fluegel"] != 0:
            # Breite halten, ballfern etwas einruecken
            ziel_y = rolle["fluegel"] * a.breite
            ballfern = (by * rolle["fluegel"]) < -8.0
            if ballfern:
                ziel_y *= 0.72
            zy = M.lerp(zy, ziel_y, 0.65 if rolle["linie"] >= 2 else 0.45)
        if rolle["linie"] == 1:
            zx = abwehrlinie(lage, team)
            if rolle["fluegel"] != 0:
                # Aussenverteidiger schieben mit, ballseitig deutlich hoeher
                ballseitig = (by * rolle["fluegel"]) > 0.0
                schub = a.aufruecken_aussen * (16.0 if ballseitig else 7.0)
                zx += schub
        elif rolle["linie"] == 3:
            # Angreifer binden die letzte Linie
            linie = abseitslinie(lage, team)
            # Kein Spieler haelt die Linie perfekt. Der Sicherheitsabstand
            # haengt am Positionsspiel: ein schwacher Timer steht dreieinhalb
            # Meter zu tief, ein sehr guter knapp davor.
            puffer = 0.4 + 3.2 * (1.0 - sp.attribute.positionsspiel)
            if rolle["fluegel"] == 0:
                zx = max(zx, min(linie - puffer, bx + 24.0))
            else:
                zx = max(zx, min(linie - puffer - 1.8, bx + 18.0))
        zx = min(zx, K.HALB_L - 1.5)

    elif besitz == 1 - team:
        # -------------------------------------------- gegnerischer Ballbesitz
        linie = abwehrlinie(lage, team)
        tiefe = M.lerp(30.0, 17.0, a.kompaktheit)      # Blocktiefe in m
        rel = {1: 0.0, 2: 0.55, 3: 1.0}[rolle["linie"]]
        zx = linie + rel * tiefe
        # Ballseitiges Verschieben ist eine **Verschiebung des Blocks**, keine
        # Stauchung auf den Ball. Der Unterschied ist gross: bei einer
        # Stauchung stehen alle zehn Feldspieler in einem Schlauch von zwanzig
        # Metern Breite, jeder Ballfuehrende hat drei Gegner im Nahbereich und
        # keine Passquote der Welt haelt das aus. Der Block behaelt seine
        # Breite (leicht gestaucht nach Kompaktheit) und wandert zum Ball.
        stauchung = 0.22 * a.kompaktheit
        verschiebung = 0.42 * by
        zy = basis[1] * (1.0 - stauchung) + verschiebung
        zy = M.klemme(zy, -K.HALB_B + 2.0, K.HALB_B - 2.0)
        zx = max(zx, -K.HALB_L + 3.0)

    else:
        # ------------------------------------------------------ loser Ball
        zx = M.lerp(basis[0], bx, 0.35)
        zy = M.lerp(basis[1], by, 0.45)

    ziel = in_weltrahmen((zx, zy), richtung)
    ziel = _abstossung(sp, ziel, lage)
    return (M.klemme(ziel[0], -K.HALB_L + 0.6, K.HALB_L - 0.6),
            M.klemme(ziel[1], -K.HALB_B + 0.6, K.HALB_B - 0.6))


def _abstossung(sp, ziel, lage, radius=7.0, staerke=0.45):
    """Mitspieler nicht auf einen Haufen laufen lassen."""
    dx = dy = 0.0
    for m in lage.mannschaft[sp.team]:
        if m is sp or m.ist_torwart:
            continue
        d = M.abstand(ziel, m.pos)
        if d < radius and d > 1e-3:
            f = (1.0 - d / radius) ** 2 * staerke * radius
            dx += (ziel[0] - m.pos[0]) / d * f
            dy += (ziel[1] - m.pos[1]) / d * f
    # Positionsspiel daempft das Umherirren
    d = 0.55 + 0.45 * (1.0 - sp.attribute.positionsspiel)
    return (ziel[0] + dx * d, ziel[1] + dy * d)


def _torwartposition(sp, lage):
    """Torwart auf der Winkelhalbierenden, Tiefe nach Ballentfernung.

    Steht die Abwehr hoch und der Ball weit vorne, ruecken die Fuesse mit
    heraus - der Torwart wird zum letzten Verteidiger. Das ist die zweite
    Haelfte der Frage nach der moeglichen Abwehrhoehe.
    """
    richtung = lage.richtung[sp.team]
    tor = (-K.HALB_L * richtung, 0.0)
    b = lage.ball.xy
    d = M.abstand(b, tor)
    richtung_zum_ball = M.normiert(M.sub(b, tor))

    tiefe = K.TW_LINIE_TIEFE + M.klemme((d - 16.0) / 34.0, 0.0, 1.0) * 5.5
    if lage.ballbesitz != sp.team and d > 30.0:
        linie = abwehrlinie(lage, sp.team) + K.HALB_L      # m vom eigenen Tor
        tiefe += M.klemme((linie - 30.0) / 18.0, 0.0, 1.0) * 9.0
    tiefe = min(tiefe, K.TW_MAX_AUSFLUG)

    ziel = (tor[0] + richtung_zum_ball[0] * tiefe,
            tor[1] + richtung_zum_ball[1] * tiefe)
    # nicht weiter seitlich als der Pfosten plus etwas
    grenze = K.TOR_HALB_BREITE + 2.5 + 0.25 * tiefe
    return (ziel[0], M.klemme(ziel[1], -grenze, grenze))


# ------------------------------------------------------------------ Pressing
def presser_bestimmen(lage, team):
    """Wer geht zum Ball? Nach Ankunftszeit, Anzahl nach Pressingintensitaet.

    Gibt eine Menge von Spielern zurueck. Der erste Presser attackiert den
    Ballfuehrenden, die weiteren sichern die naechsten Anspielstationen.
    """
    a = lage.anweisung[team]
    ball = lage.ball.xy
    kandidaten = []
    for s in lage.mannschaft[team]:
        if s.ist_torwart:
            continue
        d = M.abstand(s.pos, ball)
        if d > a.pressing_ausloeser + 12.0:
            continue
        t = s.zeit_zu_punkt(ball)
        # aggressive Spieler gehen eher raus
        t -= 0.25 * s.attribute.aggressivitaet
        kandidaten.append((t, s.nummer, s))
    kandidaten.sort()
    if not kandidaten:
        return []

    # Wie viele gehen raus? Die Anweisung muss hier deutlich durchschlagen,
    # sonst unterscheidet sich ein Vollangriff kaum vom Abwarten und die
    # Pressingintensitaet bleibt eine Zahl ohne Wirkung.
    anzahl = 1 + int(round(a.pressing * 2.6))
    if lage.gegenpress_bis[team] > lage.zeit:
        anzahl += int(round(a.gegenpressing * 1.8))
    # nur Spieler, die ueberhaupt in Reichweite sind
    auswahl = []
    for t, _, s in kandidaten[:anzahl]:
        if M.abstand(s.pos, ball) <= a.pressing_ausloeser + 8.0:
            auswahl.append(s)
    return auswahl          # geordnet: Index 0 attackiert den Ball


def pressziel(sp, lage, rang=0):
    """Anlaufpunkt eines Pressers.

    Gestaffelt nach Rang, weil sich sonst alle auf denselben Quadratmeter
    stellen: **Rang 0** attackiert den Ballfuehrenden und bleibt dabei rund
    anderthalb Meter vor ihm stehen, statt in ihn hineinzulaufen - Stellen
    statt Durchrauschen. Der Anlauf erfolgt leicht von innen, damit der
    Ballfuehrende zur Seitenlinie gedraengt wird; das steuert `lenken`.
    **Rang 1 und hoeher** gehen nicht zum Ball, sondern in die naechstbeste
    Anspielstation. Ohne diese Staffelung erstickt die Simulation jeden
    Spielaufbau und die Passquote faellt auf die Haelfte des Realen.
    """
    a = lage.anweisung[sp.team]
    richtung = lage.richtung[sp.team]
    traeger = lage.ball.traeger
    if traeger is None:
        return abfangpunkt(sp, lage)

    if rang > 0:
        gegner = _naechste_anspielstation(sp, traeger, lage, rang)
        if gegner is not None:
            return deckungsziel(sp, gegner, lage, tiefe=1.6)

    ziel = traeger.pos
    t = sp.zeit_zu_punkt(ziel)
    ziel = (ziel[0] + traeger.v[0] * t * 0.45,
            ziel[1] + traeger.v[1] * t * 0.45)

    tor = (-K.HALB_L * richtung, 0.0)
    zum_tor = M.normiert(M.sub(tor, ziel))
    quer = (-zum_tor[1], zum_tor[0])
    innen = 1.0 if (ziel[1] * richtung) < 0.0 else -1.0
    versatz = a.lenken * 1.6 * innen
    # Abstand halten: der Presser stellt, er rennt nicht hinein. Dieser Wert
    # muss unter `konfig.ZWEIKAMPF_RADIUS` bleiben, sonst stellt der Presser
    # sich ausser Reichweite und der Ballfuehrende dribbelt ungestoert durch.
    abstand = M.lerp(1.7, 0.9, a.pressing)
    return (ziel[0] + zum_tor[0] * abstand + quer[0] * versatz,
            ziel[1] + zum_tor[1] * abstand + quer[1] * versatz)


def _naechste_anspielstation(sp, traeger, lage, rang):
    """Der Gegenspieler, den dieser Presser zustellen soll.

    Sortiert nach Gefaehrlichkeit der Anspielstation (Wert des Ortes mal
    Naehe zum Ballfuehrenden), damit sich Rang 1 und Rang 2 nicht denselben
    Gegner teilen.
    """
    richtung_gegner = lage.richtung[1 - sp.team]
    kandidaten = []
    for g in lage.mannschaft[1 - sp.team]:
        if g is traeger or g.ist_torwart:
            continue
        d_ball = M.abstand(g.pos, traeger.pos)
        if d_ball > 32.0:
            continue
        wert = R.gefahr(g.pos, richtung_gegner) * M.abklingend(d_ball, 18.0)
        wert -= 0.0009 * M.abstand(sp.pos, g.pos)
        kandidaten.append((-wert, g.nummer, g))
    if not kandidaten:
        return None
    kandidaten.sort()
    return kandidaten[min(rang - 1, len(kandidaten) - 1)][2]


def abfangpunkt(sp, lage, horizont=2.6):
    """Fruehester Punkt der Ballbahn, den dieser Spieler erreichen kann."""
    bahn = lage.ballbahn or lage.ball.bahn(horizont)
    for (t, x, y, z) in bahn:
        if z > K.KOPFBALL_HOEHE:
            continue
        if sp.zeit_zu_punkt((x, y)) <= t + 0.05:
            return (x, y)
    if bahn:
        t, x, y, z = bahn[-1]
        return (x, y)
    return lage.ball.xy


def durchbrueche(lage, team):
    """Gegenspieler, die hinter die eigene Kette gelaufen sind - mit Bewacher.

    Ohne diese Zuordnung verteidigt die Simulation eine Linie statt Menschen:
    die Kette steht ordentlich auf ihrer Hoehe, waehrend der Stuermer bereits
    dahinter laeuft und ungestoert zum Abschluss kommt. In der Rohfassung war
    bei mehr als neun von zehn Abschluessen kein Feldspieler mehr torseitig -
    genau dieser Fehler.

    Zugeordnet wird nach Ankunftszeit am Abfangpunkt, nicht nach Entfernung:
    ein schneller Innenverteidiger holt einen Lauf ein, den ein langsamer
    aufgeben muss. Damit haengt die verteidigbare Abwehrhoehe direkt an den
    physischen Attributen - ohne dass irgendwo eine Regel dazu stuende.
    """
    r = lage.richtung[team]
    feld = [s for s in lage.mannschaft[team] if not s.ist_torwart]
    if not feld:
        return {}
    letzter = min(s.pos[0] * r for s in feld)

    laeufer = []
    for g in lage.mannschaft[1 - team]:
        if g.ist_torwart:
            continue
        gx = g.pos[0] * r
        if gx > letzter + 1.0 or gx > 0.0:
            continue                     # nicht hinter der Kette bzw. zu weit weg
        # Wohin laeuft er? Vorhalten auf zwei Sekunden
        ziel = (g.pos[0] + g.v[0] * 1.2, g.pos[1] + g.v[1] * 1.2)
        laeufer.append((gx, g, ziel))
    if not laeufer:
        return {}
    laeufer.sort()                       # der tiefste zuerst

    zuordnung = {}
    vergeben = set()
    for gx, g, ziel in laeufer[:3]:
        best, bt = None, 1e9
        for s in feld:
            if s in vergeben:
                continue
            tt = s.zeit_zu_punkt(ziel)
            # Verteidiger, die ohnehin tiefer stehen, sind zustaendiger
            tt += 0.15 * max(0.0, (s.pos[0] * r) - gx) / 10.0
            if tt < bt:
                bt, best = tt, s
        if best is not None:
            vergeben.add(best)
            zuordnung[best] = ziel
    return zuordnung


def deckungsziel(sp, gegner, lage, tiefe=1.8):
    """Manndeckung: torseitig und ballseitig zum zugeordneten Gegner."""
    richtung = lage.richtung[sp.team]
    tor = (-K.HALB_L * richtung, 0.0)
    zum_tor = M.normiert(M.sub(tor, gegner.pos))
    zum_ball = M.normiert(M.sub(lage.ball.xy, gegner.pos))
    mix = M.normiert((zum_tor[0] * 0.65 + zum_ball[0] * 0.35,
                      zum_tor[1] * 0.65 + zum_ball[1] * 0.35))
    return (gegner.pos[0] + mix[0] * tiefe, gegner.pos[1] + mix[1] * tiefe)
