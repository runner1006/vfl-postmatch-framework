"""Raumkontrolle, Abschlusswert und Gefahrenflaeche.

Drei Bewertungsfunktionen, auf die die gesamte Entscheidungsschicht
zurueckgreift:

`kontrolle`      Wer kaeme zuerst an einen Punkt? Aus Ankunftszeiten, nicht
                 aus Luftlinien - deshalb zaehlt hier auch, wer schon in die
                 richtige Richtung laeuft.
`xg`             Wie gross ist die Torwahrscheinlichkeit eines Abschlusses?
`gefahr`         Was ist Ballbesitz an diesem Ort wert?

Kalibrierung und Grenzen
------------------------
`xg` ist an sechs zentrale Stuetzstellen gelegt (5.5 m: 0.45, 11 m: 0.29,
16.5 m: 0.12, 20 m: 0.075, 25 m: 0.035, 30 m: 0.018) und in der Winkelachse
ueber das Verhaeltnis zum maximal moeglichen Torwinkel derselben Entfernung
geformt. `gefahr` ist eine **heuristische Ersatzflaeche** fuer xT: eine Summe
zweier Exponentiale, deren Stuetzstellen (Strafraum 0.26, Strafraumkante
0.063, Mittellinie 0.010, eigener Strafraum 0.001) den Groessenordnungen
veroeffentlichter xT-Gitter entsprechen. Sie ist **nicht** aus Ereignisdaten
geschaetzt. Wer ein eigenes xT-Gitter hat, ersetzt `gefahr` - alles andere
bleibt unberuehrt. Diese Grenze steht ausdruecklich auch in der README.
"""
import math

import konfig as K
import mathe as M

# ------------------------------------------------------------------ Abschluss
XG_A = 0.652          # Achsenabschnitt der zentralen Entfernungskurve
XG_B = -0.155         # je Meter
XG_WINKEL_EXP = 1.2   # Schaerfe der Winkelabwertung


def tor_mitte(richtung):
    """Mittelpunkt des Tores, auf das `richtung` spielt."""
    return (richtung * K.HALB_L, 0.0)


def tor_pfosten(richtung):
    x = richtung * K.HALB_L
    return (x, -K.TOR_HALB_BREITE), (x, K.TOR_HALB_BREITE)


def torwinkel(pos, richtung):
    """Sichtbarer Torwinkel in rad (ohne Verdeckung)."""
    a, b = tor_pfosten(richtung)
    return M.dreieck_winkel(pos, a, b)


def xg_roh(pos, richtung):
    """Abschlusswert ohne Gegnerdruck und ohne Faehigkeiten."""
    d = M.abstand(pos, tor_mitte(richtung))
    if d < 0.5:
        d = 0.5
    basis = M.logistisch(XG_A + XG_B * d, 0.0, 1.0)
    zentral = 2.0 * math.atan(K.TOR_HALB_BREITE / d)
    w = torwinkel(pos, richtung)
    rel = M.klemme(w / zentral, 0.0, 1.0)
    return basis * (rel ** XG_WINKEL_EXP)


def xg(pos, richtung, gegner=None, torwart=None, abschluss=0.5,
       kopfball=False, unter_druck=0.0, ball_hoehe=0.0):
    """Torwahrscheinlichkeit eines Abschlusses aus `pos`.

    Beruecksichtigt neben Ort und Winkel:
      - Verdeckung: Gegner im Schusskorridor nehmen Winkel weg
      - Torwartstellung: ein weit herausgeruecktes Tor ist kleiner
      - Druck: ein Verteidiger im Nahbereich kostet Ausfuehrungsqualitaet
      - Kopfball und hohe Baelle sind deutlich schlechter zu verwerten
    """
    wert = xg_roh(pos, richtung)
    if wert <= 0.0:
        return 0.0
    w_sicht = torwinkel(pos, richtung)

    if gegner:
        # Verdeckung geometrisch: jeder Koerper zwischen Schuetze und Tor
        # verdeckt einen Winkelbereich. Aufsummiert wird der ueberdeckte Anteil
        # des sichtbaren Torwinkels, gedeckelt bei 90 Prozent. Das ist der
        # Grund, warum Distanzschuesse durch die Menge selten sind - ohne
        # diesen Term schiesst die Simulation aus 25 m, sobald der Wert eines
        # Abschlusses den Wert des Ballbesitzes knapp uebersteigt.
        d_tor = M.abstand(pos, tor_mitte(richtung))
        belegt = 0.0
        for g in gegner:
            dg = M.abstand(pos, g.pos)
            if dg < 0.5 or dg > d_tor:
                continue
            naeh, t = M.punkt_auf_strecke(pos, tor_mitte(richtung), g.pos)
            if t <= 0.0 or t >= 1.0:
                continue
            quer = M.abstand(naeh, g.pos)
            # Wirksame Koerperbreite rund 0.6 m, plus ein gestreckter Fuss
            halbbreite = 0.55
            if quer > halbbreite + 1.7:
                continue
            # Ein Verteidiger muss nicht exakt auf der Linie stehen, um den
            # Abschluss zu stoeren - er muss nur nah genug sein, um im
            # entscheidenden Moment das Bein hinzubekommen.
            wirksam = M.klemme(1.0 - (quer - halbbreite) / 1.7, 0.0, 1.0) \
                if quer > halbbreite else 1.0
            # Winkel, den der Koerper aus Sicht des Schuetzen einnimmt
            anteil = 2.0 * math.atan(halbbreite / dg) / max(w_sicht, 1e-3)
            belegt += anteil * wirksam
        wert *= max(0.10, 1.0 - M.klemme(belegt, 0.0, 0.90))

    if torwart is not None:
        # Wie weit steht der Torwart auf der Winkelhalbierenden heraus?
        tm = tor_mitte(richtung)
        naeh, t = M.punkt_auf_strecke(pos, tm, torwart.pos)
        quer = M.abstand(naeh, torwart.pos)
        heraus = M.klemme(1.0 - t, 0.0, 1.0)
        deckung = heraus * M.abklingend(quer, 2.2)
        wert *= (1.0 - 0.42 * deckung)

    # Unter Druck wird der Abschluss ueberhastet: weniger Zeit fuer
    # Standbein, Koerperstellung und Zielpunkt.
    wert *= (1.0 - 0.60 * M.klemme(unter_druck, 0.0, 1.0))
    if kopfball:
        wert *= 0.62
    elif ball_hoehe > 0.5:
        wert *= (1.0 - 0.25 * M.klemme((ball_hoehe - 0.5) / 0.8, 0.0, 1.0))
    # Abschlussqualitaet: 0.0 -> 0.72x, 0.5 -> 1.0x, 1.0 -> 1.34x
    wert *= (0.72 + 0.62 * abschluss)
    return M.klemme(wert, 0.0, 0.97)


# ------------------------------------------------------------------- Gefahr
GEFAHR_A1, GEFAHR_D1 = 0.52, 7.5
GEFAHR_A2, GEFAHR_D2 = 0.030, 28.0


def gefahr(pos, richtung):
    """Wert des Ballbesitzes an einem Ort (xT-Ersatzflaeche, siehe Modulkopf)."""
    d = M.abstand(pos, tor_mitte(richtung))
    radial = (GEFAHR_A1 * math.exp(-d / GEFAHR_D1)
              + GEFAHR_A2 * math.exp(-d / GEFAHR_D2))
    y = pos[1] / 22.0
    quer = 0.45 + 0.55 * math.exp(-y * y)
    return radial * quer


def gefahr_gitter(richtung, nx=42, ny=27):
    """Gefahrenflaeche als Gitter - fuer die Visualisierung."""
    zellen = []
    for j in range(ny):
        y = -K.HALB_B + (j + 0.5) * K.FELD_BREITE / ny
        reihe = []
        for i in range(nx):
            x = -K.HALB_L + (i + 0.5) * K.FELD_LAENGE / nx
            reihe.append(gefahr((x, y), richtung))
        zellen.append(reihe)
    return zellen


# ------------------------------------------------------------- Raumkontrolle
KONTROLL_SCHAERFE = 0.42     # s; kleinere Werte = haertere Zuordnung


def zeiten_zu_punkt(punkt, spieler, mit_reaktion=True):
    return [(s, s.zeit_zu_punkt(punkt, mit_reaktion)) for s in spieler]


def kontrolle(punkt, heim, gast, mit_reaktion=True):
    """Wahrscheinlichkeit, dass das Heimteam an diesem Punkt zuerst ist."""
    th = min((s.zeit_zu_punkt(punkt, mit_reaktion) for s in heim),
             default=float("inf"))
    tg = min((s.zeit_zu_punkt(punkt, mit_reaktion) for s in gast),
             default=float("inf"))
    if th == float("inf") and tg == float("inf"):
        return 0.5
    return M.logistisch(tg - th, 0.0, KONTROLL_SCHAERFE)


def kontrollfeld(heim, gast, nx=42, ny=27, mit_reaktion=True):
    """Kontrollwahrscheinlichkeit des Heimteams als Gitter.

    Teuer (nx*ny*22 Ankunftszeiten). Wird nur fuer Analyse und Anzeige
    gerufen, nie in der Spielschleife.
    """
    feld = []
    for j in range(ny):
        y = -K.HALB_B + (j + 0.5) * K.FELD_BREITE / ny
        reihe = []
        for i in range(nx):
            x = -K.HALB_L + (i + 0.5) * K.FELD_LAENGE / nx
            reihe.append(kontrolle((x, y), heim, gast, mit_reaktion))
        feld.append(reihe)
    return feld


def kontrollierte_flaeche(heim, gast, richtung_heim, nx=42, ny=27,
                          nur_gefaehrlich=False):
    """Kontrollierte Flaeche in m^2, wahlweise mit Gefahr gewichtet.

    `nur_gefaehrlich=True` gewichtet jede Zelle mit ihrer Gefahr - das
    unterscheidet Raumgewinn im Niemandsland von Raumgewinn vor dem Tor.
    Wichtig: jede Mannschaft wird mit **ihrer eigenen** Angriffsrichtung
    gewichtet. Wer beide mit derselben Richtung gewichtet, misst nicht die
    Kontrolle beider Teams, sondern zweimal dieselbe Feldhaelfte.
    """
    zelle = (K.FELD_LAENGE / nx) * (K.FELD_BREITE / ny)
    summe_h = summe_g = 0.0
    for j in range(ny):
        y = -K.HALB_B + (j + 0.5) * K.FELD_BREITE / ny
        for i in range(nx):
            x = -K.HALB_L + (i + 0.5) * K.FELD_LAENGE / nx
            p = kontrolle((x, y), heim, gast)
            if nur_gefaehrlich:
                gh = gefahr((x, y), richtung_heim)
                gg = gefahr((x, y), -richtung_heim)
            else:
                gh = gg = 1.0
            summe_h += p * zelle * gh
            summe_g += (1.0 - p) * zelle * gg
    return summe_h, summe_g



# --------------------------------------------------------- Passunterbrechung
def abfangwahrscheinlichkeit(bahn, gegner, start_zeit=0.0, empfaenger=None):
    """Wie wahrscheinlich faengt die Gegenseite diesen Ball ab?

    Fuer jeden Bahnpunkt (t, x, y, z) wird geprueft, ob ein Gegner rechtzeitig
    dort sein kann. Hoehe zaehlt: ueber Kopfhoehe ist nichts abzufangen,
    zwischen Fuss- und Kopfhoehe wird es schwerer. Aggregiert wird ueber das
    Gegenereignis, damit viele knappe Chancen sich nicht kuenstlich addieren.
    """
    # Je Gegner das Maximum ueber die Bahn, dann das Produkt ueber die Gegner -
    # sonst zaehlt derselbe Verteidiger an jeder Stuetzstelle erneut.
    p_durch = 1.0
    for g in gegner:
        if g is empfaenger:
            continue
        vorsprung = 0.10 + 0.30 * g.attribute.antizipation
        best = 0.0
        for (t, x, y, z) in bahn:
            if z > K.KOPFBALL_HOEHE:
                continue
            hoehen_faktor = 1.0 if z < K.KONTROLL_HOEHE else 0.55
            marge = (start_zeit + t) - (g.zeit_zu_punkt((x, y)) - vorsprung)
            if marge < -0.55:
                continue
            p = M.logistisch(marge, 0.10, 0.22) * hoehen_faktor
            if p > best:
                best = p
        p_durch *= (1.0 - best * 0.88)
    return M.klemme(1.0 - p_durch, 0.0, 0.985)


def druck_auf(spieler, gegner, radius=6.0):
    """Gegnerdruck auf 0..1: Naehe plus Anlaufrichtung.

    Ein Gegner, der auf den Ballfuehrenden zulaeuft, erzeugt mehr Druck als
    einer, der gleich weit weg steht und sich wegbewegt.
    """
    summe = 0.0
    for g in gegner:
        d = M.abstand(spieler.pos, g.pos)
        if d > radius:
            continue
        naehe = 1.0 - d / radius
        richtung = M.normiert(M.sub(spieler.pos, g.pos))
        anlauf = M.punkt(g.v, richtung)
        summe += naehe * naehe * (1.0 + 0.10 * max(0.0, anlauf))
    return M.klemme(summe, 0.0, 1.0)


def druck_auf_punkt(punkt, gegner, radius=6.0):
    """Wie `druck_auf`, aber fuer einen gedachten Ort statt einen Spieler.

    Wird in der Passbewertung gebraucht: wie eng waere es dort, wenn der Ball
    ankommt.
    """
    summe = 0.0
    for g in gegner:
        d = M.abstand(punkt, g.pos)
        if d > radius:
            continue
        naehe = 1.0 - d / radius
        summe += naehe * naehe
    return M.klemme(summe, 0.0, 1.0)
