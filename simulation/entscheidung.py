"""Entscheidungen am Ball: Optionen erzeugen, bewerten, ausfuehren.

Kein Wuerfeln auf einer Ergebnistabelle. Der Ballfuehrende erzeugt konkrete
raeumliche Optionen (dieser Pass zu diesem Punkt mit diesem Tempo), bewertet
jede davon mit demselben Nutzenmass und fuehrt genau eine aus - mit
Ausfuehrungsfehler. Ob ein Pass ankommt, entscheidet danach die Physik und
nicht die Bewertung.

Nutzenmass
----------
Alle Werte stehen in derselben Einheit: Torwahrscheinlichkeit. Ein Tor ist
1.0, `raumkontrolle.gefahr` ist der Wert des Ballbesitzes an einem Ort, `xg`
der Wert eines Abschlusses. Dadurch sind Schuss, Pass und Dribbling direkt
vergleichbar, ohne Gewichtungsakrobatik.

    nutzen = p_erfolg * wert_danach - risiko * (1 - p_erfolg) * wert_fuer_gegner

`risiko` kommt aus der Mannschaftsanweisung, die Streuung der Auswahl aus dem
Attribut `entscheidung`. Ein schwacher Entscheider waehlt nicht zufaellig,
sondern haeufiger die zweitbeste Option - das ist der Unterschied.
"""
import math

import ball as B
import konfig as K
import mathe as M
import raumkontrolle as R
import taktik as T


class Option:
    __slots__ = ("art", "ziel", "tempo", "steigung", "drall", "empfaenger",
                 "p", "nutzen", "notiz")

    def __init__(self, art, ziel, tempo=0.0, steigung=0.0, drall=0.0,
                 empfaenger=None, p=1.0, nutzen=0.0, notiz=""):
        self.art = art               # schuss | pass | dribbling | klaerung | halten
        self.ziel = ziel
        self.tempo = tempo
        self.steigung = steigung
        self.drall = drall
        self.empfaenger = empfaenger
        self.p = p
        self.nutzen = nutzen
        self.notiz = notiz

    def __repr__(self):
        return "<%s -> (%.1f, %.1f) p=%.2f u=%.4f %s>" % (
            self.art, self.ziel[0], self.ziel[1], self.p, self.nutzen, self.notiz)


# ------------------------------------------------------------ Passunterbrechung
def _abfangen_gerade(start, ziel, v_pass, gegner, empfaenger, hoch=False):
    """Unterbrechungswahrscheinlichkeit fuer einen geradlinigen Pass.

    Bewusst schlanker als `raumkontrolle.abfangwahrscheinlichkeit`: die Bahn
    wird als Strecke behandelt und nur an acht Stuetzstellen geprueft, und
    Gegner ausserhalb eines Korridors um die Strecke fallen vorab heraus. Das
    ist die einzige Stelle, an der die Engine Genauigkeit gegen Rechenzeit
    tauscht - die volle Integration laeuft danach ohnehin.

    Geprueft wird bis zum 1.25-fachen der Passlaenge. Der Grund ist physisch:
    ein Pass bleibt nicht am Zielpunkt liegen, sondern rollt darueber hinaus.
    Wer nur bis zum Ziel prueft, haelt Paesse fuer sicher, die in Wahrheit dem
    dahinterstehenden Gegner in den Fuss laufen.
    """
    d = M.abstand(start, ziel)
    if d < 0.5:
        return 0.0
    t_ges = B.ankunftszeit(d, v_pass, flach=not hoch)
    if t_ges == float("inf"):
        t_ges = d / max(v_pass * 0.6, 1.0)

    ueberlauf = 1.25
    ende = (start[0] + (ziel[0] - start[0]) * ueberlauf,
            start[1] + (ziel[1] - start[1]) * ueberlauf)

    nah = []
    for g in gegner:
        naeh, _ = M.punkt_auf_strecke(start, ende, g.pos)
        if M.abstand(naeh, g.pos) < 16.0:
            nah.append(g)
    if not nah:
        return 0.0

    # Wichtig: je Gegner **einmal** zaehlen, nicht je Stuetzstelle. Ein
    # Verteidiger nahe der Passlinie taucht in mehreren Stuetzstellen auf; wer
    # die Stuetzstellen multipliziert, haelt jeden zweiten Pass fuer
    # abgefangen. Deshalb erst je Gegner das Maximum ueber die Bahn, dann das
    # Produkt ueber die Gegner.
    schritte = 8
    stuetz = []
    for i in range(1, schritte + 1):
        f = ueberlauf * i / float(schritte)
        px = start[0] + (ziel[0] - start[0]) * f
        py = start[1] + (ziel[1] - start[1]) * f
        t = t_ges * (f ** 0.86 if not hoch else f)
        if hoch:
            z = 4.0 * (f / ueberlauf) * (1.0 - f / ueberlauf) * (0.14 * d)
            if z > K.KOPFBALL_HOEHE:
                continue
            hoehen_faktor = 0.5 if z > K.KONTROLL_HOEHE else 1.0
        else:
            hoehen_faktor = 1.0
        gewicht = 1.0 if f <= 1.0 else 0.45
        stuetz.append((px, py, t, hoehen_faktor * gewicht))

    p_durch = 1.0
    for g in nah:
        if g is empfaenger:
            continue
        vorsprung = 0.05 + 0.20 * g.attribute.antizipation
        best = 0.0
        for (px, py, t, faktor) in stuetz:
            marge = t - (g.zeit_zu_punkt((px, py)) - vorsprung)
            if marge < -0.45:
                continue
            # Schaerfe der Kurve: bei Gleichstand rund 27 Prozent, eine
            # Drittelsekunde zu spaet nur noch fuenf. Eine flachere Kurve macht
            # jeden Pass durch das Mittelfeld zum Gluecksspiel.
            p = M.logistisch(marge, 0.15, 0.15) * faktor
            if p > best:
                best = p
        p_durch *= (1.0 - best * 0.88)
    return M.klemme(1.0 - p_durch, 0.0, 0.97)


def _empfaenger_kommt_hin(sp, empfaenger, ziel, t_ball, gegner):
    """Wahrscheinlichkeit, dass der vorgesehene Empfaenger den Ball erlaeuft.

    Ohne diesen Faktor bewertet die Engine Paesse in einen Raum, den der
    Mitspieler gar nicht erreicht, als gelungen - der haeufigste Fehler
    einfacher Passmodelle.
    """
    t_e = empfaenger.zeit_zu_punkt(ziel)
    t_g = min((g.zeit_zu_punkt(ziel) for g in gegner), default=99.0)
    # gegen den Ball: der Empfaenger darf spaeter kommen, aber nicht viel
    p_zeit = M.logistisch(t_ball + 0.55 - t_e, 0.0, 0.28)
    p_duell = M.logistisch(t_g - t_e, -0.15, 0.30)
    return p_zeit * (0.42 + 0.58 * p_duell)


def _ausfuehrungsguete(sp, d, druck, ziel):
    """Wahrscheinlichkeit, den Pass technisch sauber zu spielen.

    Faellt mit Entfernung, Gegnerdruck und Koerperstellung. Ein Pass gegen die
    eigene Laufrichtung ist schwerer als einer in Blickrichtung.
    """
    a = sp.attribute
    w = math.atan2(ziel[1] - sp.pos[1], ziel[0] - sp.pos[0])
    dreh = abs(M.winkel_diff(w, sp.blick)) / math.pi          # 0 .. 1
    # Dies ist nur die Ausfuehrung. Ob der Pass ankommt, entscheidet zusaetzlich
    # das Abfangmodell und die Frage, ob der Empfaenger hinkommt - die drei
    # Faktoren werden multipliziert. Deshalb liegt dieser Wert hoeher als eine
    # gemessene Passquote.
    basis = 0.99 - 0.0022 * d
    basis -= 0.13 * druck
    basis -= 0.10 * dreh
    basis += 0.09 * (a.passgenauigkeit - 0.5) * 2.0
    return M.klemme(basis, 0.25, 0.997)


def _passtempo(sp, d):
    v_kappe = K.PASS_MAX_V * (0.74 + 0.36 * sp.attribute.passtempo)
    # Passhaerte nach Laenge: ein 10-m-Pass mit 9 m/s, ein 30-m-Pass mit rund
    # 18 m/s. Haerter gespielte Baelle kommen frueher an, sind aber schwerer
    # zu verarbeiten - beides steckt bereits im Modell, deshalb keine Extraregel.
    return M.klemme(5.0 + 0.42 * d, 6.5, v_kappe)


# Fortsetzungsfaktor des Ballbesitzes.
#
# `raumkontrolle.gefahr` ist der Wert einer Zelle. Der Wert, den ein Team
# aufgibt, wenn es den Ball verliert, ist groesser: Ballbesitz enthaelt die
# Option, die Lage noch zu verbessern. Ohne diesen Faktor steht ein Abschluss
# mit zwei Prozent Torwahrscheinlichkeit rechnerisch gleichauf mit dem Halten
# des Balls in einer aussichtsreichen Lage - und die Simulation schiesst aus
# jeder Entfernung, sobald sie freie Sicht hat.
#
# Der Faktor wirkt auf alle Optionen, die den Ballbesitz fortsetzen (Pass,
# Dribbling, Halten) und auf die Kosten eines Ballverlusts - nicht auf den
# Abschluss. Er verschiebt damit genau das Verhaeltnis, um das es geht.
FORTSETZUNG = 2.0


def wert_position(pos, richtung, druck=0.0):
    """Wert des Ballbesitzes an einem Ort, bedingt auf Behaupten.

    Der Druckabschlag bildet ab, dass ein Ball, der zwischen zwei Gegnern
    ankommt, weniger wert ist als derselbe Ball im freien Raum. Ein staerkerer
    Abschlag (0.70 statt 0.45) wurde geprueft und wieder verworfen: er
    verschiebt die Auswahl zwar zur sicheren Verlagerung, verschlechtert aber
    alle Aggregate, weil die Mannschaft dann im eigenen Drittel zirkuliert und
    der Gegner dort presst.
    """
    return (R.gefahr(pos, richtung) * FORTSETZUNG
            * (1.0 - 0.45 * M.klemme(druck, 0.0, 1.0)))


# ------------------------------------------------------------ Optionsgenerierung
def optionen(sp, lage):
    """Alle Handlungsoptionen des Ballfuehrenden, bewertet."""
    team = sp.team
    richtung = lage.richtung[team]
    a = lage.anweisung[team]
    eigene = lage.mannschaft[team]
    gegner = lage.mannschaft[1 - team]
    pos = sp.pos
    druck = R.druck_auf(sp, gegner)
    wert_jetzt = wert_position(pos, richtung, druck)
    gegen_richtung = -richtung
    abseits_x = T.abseitslinie(lage, team)

    out = []

    # ------------------------------------------------------------------ Schuss
    d_tor = M.abstand(pos, R.tor_mitte(richtung))
    if d_tor < 34.0 and not sp.ist_torwart:
        tw = lage.torwart[1 - team]
        # Fuer den Abschluss zaehlt zusaetzlich die Koerperstellung: wer sich
        # erst noch zum Tor drehen muss, schiesst schlechter.
        w_tor = math.atan2(-pos[1], richtung * K.HALB_L - pos[0])
        dreh = abs(M.winkel_diff(w_tor, sp.blick)) / math.pi
        p_tor = R.xg(pos, richtung, gegner=gegner, torwart=tw,
                     abschluss=sp.attribute.abschluss, unter_druck=druck,
                     ball_hoehe=lage.ball.pos[2]) * (1.0 - 0.30 * dreh)
        # Ein Abschluss beendet den Angriff. Trifft er nicht, bleibt ein kleiner
        # Restwert (Abpraller, Ecke) und der Ballbesitz ist weg. Ohne diesen
        # Verzicht auf den Fortsetzungswert waere jeder Distanzschuss
        # rechnerisch besser als der Ballbesitz, aus dem er entsteht.
        restwert = 0.09 * wert_jetzt
        nutzen = p_tor + (1.0 - p_tor) * restwert
        nutzen += 0.015 * (sp.attribute.risikofreude - 0.5) * p_tor
        out.append(Option("schuss", R.tor_mitte(richtung), p=p_tor,
                          nutzen=nutzen, notiz="d=%.0f" % d_tor))

    # -------------------------------------------------------------------- Pass
    sicht = 26.0 + 22.0 * sp.attribute.uebersicht
    for m in eigene:
        if m is sp:
            continue
        d0 = M.abstand(pos, m.pos)
        if d0 > sicht or d0 < 1.2:
            continue
        if m.ist_torwart and (pos[0] * richtung) > 0.0:
            continue                                  # kein Rueckpass ueber das
                                                      # halbe Feld aus der Haelfte
        for variante in ("fuss", "raum"):
            ziel = _passziel(sp, m, lage, variante)
            if ziel is None:
                continue
            d = M.abstand(pos, ziel)
            if d < 1.0 or d > 62.0:
                continue
            hoch = variante == "raum" and d > 22.0
            v = _passtempo(sp, d)
            p_abgefangen = _abfangen_gerade(pos, ziel, v, gegner, m, hoch)
            p_technik = _ausfuehrungsguete(sp, d, druck, ziel)
            t_ball = B.ankunftszeit(d, v, flach=not hoch)
            if t_ball == float("inf"):
                t_ball = d / max(v * 0.6, 1.0)
            p_hin = _empfaenger_kommt_hin(sp, m, ziel, t_ball, gegner)
            p_annahme = 0.72 + 0.26 * m.attribute.erste_beruehrung
            p = (1.0 - p_abgefangen) * p_technik * p_hin * p_annahme

            druck_m = R.druck_auf(m, gegner, radius=5.0)
            wert_neu = wert_position(ziel, richtung, druck_m)
            # Direktheit: die Anweisung `tempo` bevorzugt vertikalen Raumgewinn
            vorwaerts = (ziel[0] - pos[0]) * richtung
            wert_neu += a.tempo * 0.00025 * max(0.0, vorwaerts)
            wert_gegen = R.gefahr(ziel, gegen_richtung) * FORTSETZUNG
            # Ballverlust kostet den Wert der eigenen Situation mit,
            # nicht nur den Raumgewinn des Gegners.
            # Ein Ballverlust kostet mehr als die Zelle, auf der man steht: er
            # beendet den ganzen Angriff. Der Faktor 2.5 bildet den
            # Fortsetzungswert des Ballbesitzes ab. Ohne ihn waehlt die Engine
            # systematisch den unwahrscheinlichen Steilpass vor dem sicheren
            # Querpass - und die Passquote bleibt bei 45 Prozent.
            verlustkosten = wert_gegen + 2.5 * wert_jetzt
            nutzen = p * wert_neu - a.risiko * (1.0 - p) * verlustkosten

            # Abseits: der Passgeber sieht es, aber nicht perfekt
            if (ziel[0] * richtung) > abseits_x + K.ABSEITS_TOLERANZ and \
               (m.pos[0] * richtung) > abseits_x:
                nutzen *= 0.10 + 0.20 * (1.0 - m.attribute.positionsspiel)

            out.append(Option("pass", ziel, tempo=v,
                              steigung=(0.30 if hoch else 0.0),
                              empfaenger=m, p=p, nutzen=nutzen,
                              notiz="%s %.0fm" % (variante, d)))

    # --------------------------------------------------------------- Dribbling
    if not sp.ist_torwart:
        v_dribbel = sp.v_max_akt() * (0.52 + 0.30 * sp.attribute.dribbling)
        for grad in (-55, -25, 0, 25, 55):
            w = math.radians(grad)
            basis = (math.cos(w) * richtung, math.sin(w) * richtung)
            weite = 3.2 + 2.6 * sp.attribute.dribbling
            ziel = (pos[0] + basis[0] * weite, pos[1] + basis[1] * weite)
            if abs(ziel[1]) > K.HALB_B - 0.5 or abs(ziel[0]) > K.HALB_L - 0.5:
                continue
            p = _dribbel_erfolg(sp, ziel, gegner, v_dribbel)
            dauer = weite / max(v_dribbel, 0.5)
            wert_neu = wert_position(ziel, richtung,
                                     R.druck_auf_punkt(ziel, gegner))
            wert_gegen = R.gefahr(ziel, gegen_richtung) * FORTSETZUNG
            # Zeitabschlag: waehrend des Dribblings ordnet sich der Gegner neu
            wert_neu *= math.exp(-0.10 * dauer)
            nutzen = p * wert_neu - a.risiko * (1.0 - p) * (wert_gegen + 2.0 * wert_jetzt)
            nutzen += 0.0006 * (sp.attribute.dribbling - 0.5)
            out.append(Option("dribbling", ziel, tempo=v_dribbel, p=p,
                              nutzen=nutzen, notiz="%d Grad" % grad))

    # --------------------------------------------------------------- Klaerung
    eigene_haelfte = (pos[0] * richtung) < -12.0
    if eigene_haelfte and druck > 0.45:
        for seite in (-1.0, 1.0):
            ziel = ((pos[0] * richtung + 42.0) * richtung,
                    seite * 19.0 * richtung)
            ziel = (M.klemme(ziel[0], -K.HALB_L + 2, K.HALB_L - 2),
                    M.klemme(ziel[1], -K.HALB_B + 2, K.HALB_B - 2))
            p_eigen = R.kontrolle(ziel, eigene, gegner)
            nutzen = (p_eigen * R.gefahr(ziel, richtung)
                      - a.risiko * (1.0 - p_eigen) * R.gefahr(ziel, gegen_richtung)
                      + 0.004 * druck)     # Entlastungswert
            out.append(Option("klaerung", ziel, tempo=K.PASS_MAX_V,
                              steigung=0.55, p=p_eigen, nutzen=nutzen,
                              notiz="Entlastung"))

    # ----------------------------------------------------------------- Halten
    out.append(Option("halten", pos, p=M.klemme(0.95 - 0.55 * druck, 0.25, 0.97),
                      nutzen=wert_jetzt * (0.95 - 0.55 * druck) - 0.0004,
                      notiz="abschirmen"))
    return out


def _passziel(sp, m, lage, variante):
    """Zielpunkt eines Passes auf einen Mitspieler."""
    richtung = lage.richtung[sp.team]
    d0 = M.abstand(sp.pos, m.pos)
    if variante == "fuss":
        # Vorhalten auf die aktuelle Bewegung
        t = B.ankunftszeit(d0, _passtempo(sp, d0))
        if t == float("inf"):
            t = d0 / 14.0
        return (m.pos[0] + m.v[0] * t * 0.85, m.pos[1] + m.v[1] * t * 0.85)
    # in den Raum: vor den Mitspieler, in Angriffsrichtung
    if T.ROLLEN[m.rolle]["linie"] < 2:
        return None
    weite = 7.0 + 9.0 * m.attribute.v_max / K.BASIS_VMAX
    lauf = M.normiert((richtung * 1.0, m.v[1] * 0.25))
    ziel = (m.pos[0] + lauf[0] * weite, m.pos[1] + lauf[1] * weite)
    if abs(ziel[1]) > K.HALB_B - 1.5 or abs(ziel[0]) > K.HALB_L - 1.0:
        return None
    return ziel


def _dribbel_erfolg(sp, ziel, gegner, v_dribbel):
    """Wahrscheinlichkeit, den Ball ueber diesen Weg zu behaupten.

    Geprueft wird der **Weg**, nicht der Zielpunkt. Das ist der entscheidende
    Unterschied: ein Verteidiger, der dem Ballfuehrenden auf den Fersen sitzt,
    ist vom Zielpunkt weit entfernt und taucht in einer reinen Zielpunktpruefung
    gar nicht auf. In der Rohfassung fuehrte genau das dazu, dass ein einzelner
    Spieler mit Wahrscheinlichkeit 0.85 je Ballkontakt siebenunddreissig Meter
    durch eine komplette Mannschaft dribbelte.

    Je Gegner wird der beste Zugriffspunkt auf dem Weg gesucht und daraus ein
    Zweikampf mit dem ueblichen Kraefteverhaeltnis; die Gegenwahrscheinlichkeiten
    werden ueber die Gegner multipliziert.
    """
    staerke_t = 0.62 * sp.attribute.dribbling + 0.38 * sp.attribute.zweikampf
    p_durch = 1.0
    schritte = 4
    for g in gegner:
        if g.ist_torwart:
            continue
        if M.abstand(g.pos, sp.pos) > 14.0:
            continue
        best = 0.0
        for i in range(1, schritte + 1):
            f = i / float(schritte)
            px = sp.pos[0] + (ziel[0] - sp.pos[0]) * f
            py = sp.pos[1] + (ziel[1] - sp.pos[1]) * f
            t_sp = M.abstand(sp.pos, (px, py)) / max(v_dribbel, 0.5)
            t_g = g.zeit_zu_punkt((px, py)) - 0.10 * g.attribute.antizipation
            # Ein Verteidiger muss nicht vor dem Ball am Punkt sein, um zu
            # stoeren - er muss nur nah genug herankommen, um in den Zweikampf
            # zu gehen. Deshalb liegt der Wendepunkt bei -0.35 s: auch wer
            # eine Drittelsekunde spaeter kommt, ist noch eine Gefahr.
            zugriff = M.logistisch(t_sp - t_g, -0.35, 0.35)
            if zugriff > best:
                best = zugriff
        if best < 0.02:
            continue
        staerke_g = 0.70 * g.attribute.zweikampf + 0.30 * g.attribute.antizipation
        p_verlust = M.klemme(0.30 + 0.80 * (staerke_g - staerke_t), 0.06, 0.80)
        p_durch *= (1.0 - best * p_verlust)
    return M.klemme(p_durch, 0.03, 0.97)


def _naechster_gegner(punkt, gegner):
    best = None
    bd = 1e9
    for g in gegner:
        d = M.abstand(punkt, g.pos)
        if d < bd:
            bd = d
            best = g
    return best, bd


# ----------------------------------------------------------------- Auswahl
def waehlen(sp, lage, rng):
    """Beste Option unter Entscheidungsrauschen.

    Das Rauschen ist Gumbel-verteilt, seine Skala ist **relativ zur Spannweite
    der Nutzenwerte** dieser Situation. Das ist keine Feinheit, sondern der
    Unterschied zwischen einem Spieler und einem Wuerfel: Nutzenunterschiede
    zwischen Handlungsoptionen sind im Mittelfeld winzig (Tausendstel einer
    Torwahrscheinlichkeit) und im Strafraum gross. Eine feste Rauschskala ist
    im ersten Fall groesser als jedes Signal - die Simulation waehlt dann
    gleichverteilt aus dreizehn Optionen und spielt Paesse mit elf Prozent
    Erfolgsaussicht, obwohl Optionen mit dreiundsechzig Prozent bereitliegen.

    Mit relativer Skala waehlt ein perfekter Entscheider praktisch immer das
    Maximum, ein schwacher regelmaessig die zweit- oder drittbeste Option -
    und das ist genau die Eigenschaft, die ein Spielertausch im
    Kontrafaktischen sichtbar machen soll.
    """
    opts = optionen(sp, lage)
    if not opts:
        return None
    werte = [o.nutzen for o in opts]
    spanne = max(werte) - min(werte)
    if spanne <= 1e-9:
        return opts[0]
    sigma = 0.16 * spanne * (1.30 - sp.attribute.entscheidung)
    best = None
    bw = -1e18
    for o in opts:
        u = rng.random()
        if u <= 1e-12:
            u = 1e-12
        g = -math.log(-math.log(u))
        w = o.nutzen + sigma * g
        if w > bw:
            bw = w
            best = o
    return best


# -------------------------------------------------------------- Ausfuehrung
def ausfuehren(sp, opt, lage, rng):
    """Option in Ballbewegung uebersetzen - mit Ausfuehrungsfehler.

    Der Fehler ist der zweite Ort, an dem Faehigkeiten wirken: die Bewertung
    entscheidet, *was* versucht wird, die Streuung hier, *wie genau* es
    gelingt.
    """
    ballobj = lage.ball
    gegner = lage.mannschaft[1 - sp.team]
    druck = R.druck_auf(sp, gegner)
    richtung = lage.richtung[sp.team]

    if opt.art == "halten":
        return None

    if opt.art == "schuss":
        a = sp.attribute
        # Zielpunkt im Tor: Ecken sind wertvoller, aber schwerer
        ziel_y = rng.uniform(-1.0, 1.0) * K.TOR_HALB_BREITE * (0.45 + 0.45 * a.abschluss)
        ziel_z = abs(rng.gauss(0.0, 0.55)) + 0.25
        ziel_z = min(ziel_z, K.TOR_HOEHE * 0.92)
        tor = (richtung * K.HALB_L, ziel_y)
        d = M.abstand(sp.pos, tor)
        # Zielfehler waechst deutlich mit der Entfernung. Kalibriert gegen die
        # Trefferquote der Engine selbst (siehe tests.py, Schussdrill): rund
        # 60 Prozent aufs Tor aus 6 m, rund ein Viertel aus 28 m.
        streu = (0.045 + 0.0060 * d) * (1.45 - a.abschluss) * (1.0 + 0.9 * druck)
        w = math.atan2(tor[1] - sp.pos[1], tor[0] - sp.pos[0]) + rng.gauss(0.0, streu)
        v = K.SCHUSS_MAX_V * (0.68 + 0.32 * a.abschluss) * (1.0 - 0.15 * druck)
        steig = math.atan2(max(ziel_z - 0.2, 0.0), max(d, 1.0)) + rng.gauss(0.0, streu * 0.35)
        ballobj.loesen(M.aus_winkel(w), v, steigung=max(steig, -0.02),
                       drall=rng.gauss(0.0, 12.0), traeger=sp, zeit=lage.zeit)
        sp.blick = w
        return "schuss"

    if opt.art in ("pass", "klaerung"):
        a = sp.attribute
        d = M.abstand(sp.pos, opt.ziel)
        guete = _ausfuehrungsguete(sp, d, druck, opt.ziel)
        # Streuung quer zur Passrichtung, in Metern am Ziel
        # Streuung am Ziel. Kalibriert auf rund 0.85 m Standardabweichung bei
        # einem 20-m-Pass ohne Druck fuer einen durchschnittlichen Spieler.
        streu_m = (0.20 + 0.030 * d) * (1.4 - a.passgenauigkeit) * (1.0 + 0.9 * druck)
        if opt.art == "klaerung":
            streu_m *= 1.7
        fehler_quer = rng.gauss(0.0, streu_m)
        fehler_laengs = rng.gauss(0.0, streu_m * 0.7)
        richtung_v = M.normiert(M.sub(opt.ziel, sp.pos))
        quer = (-richtung_v[1], richtung_v[0])
        ziel = (opt.ziel[0] + quer[0] * fehler_quer + richtung_v[0] * fehler_laengs,
                opt.ziel[1] + quer[1] * fehler_quer + richtung_v[1] * fehler_laengs)
        d2 = max(M.abstand(sp.pos, ziel), 0.5)
        v = opt.tempo * (1.0 + rng.gauss(0.0, 0.07))
        if opt.steigung > 0.01:
            # Hoher Ball: Abflugwinkel so, dass er ungefaehr am Ziel aufkommt
            steig = M.klemme(0.5 * math.asin(M.klemme(K.G * d2 / max(v * v, 1.0),
                                                      -1.0, 1.0)), 0.12, 0.9)
        else:
            steig = 0.0
        ballobj.loesen(M.normiert(M.sub(ziel, sp.pos)), v, steigung=steig,
                       drall=rng.gauss(0.0, 6.0), traeger=sp, zeit=lage.zeit)
        sp.blick = M.winkel(M.sub(ziel, sp.pos))
        return "pass" if opt.art == "pass" else "klaerung"

    if opt.art == "dribbling":
        # Kein Loesen: der Ball bleibt in Fuehrung, das Ziel steuert den Lauf
        # Mit Ball ist ein Spieler langsamer als ohne - der Wert steckt in
        # `opt.tempo` und stammt aus derselben Rechnung wie die Bewertung.
        sp.steuere(opt.ziel, wunschtempo=opt.tempo)
        return "dribbling"
    return None
