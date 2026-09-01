"""Die Simulationsschleife: 22 Agenten, ein Ball, ein Regelwerk.

Ablauf je Zeitschritt (Standard 25 Hz):

  1. Lage aktualisieren (Ballbahn, Ballbesitz, Gegenpressing-Fenster)
  2. Entscheidungen - gestaffelt, nicht alle Agenten im selben Frame
  3. Physik - erst die Spieler, dann der Ball
  4. Kontakte - Ballannahme, Zweikaempfe, Torwartaktionen
  5. Regeln - Aus, Tor, Abseits, Foul
  6. Aufzeichnung

Der Spielstand entsteht ausschliesslich aus dieser Schleife. Es gibt keine
Stelle, an der ein Ergebnis, ein Torschuss oder ein Ballbesitzwert direkt
gezogen wird - jede Zahl im Bericht ist ein gezaehltes Ereignis aus der
raeumlich-zeitlichen Entwicklung.
"""
import math
import random

import ball as B
import entscheidung as E
import konfig as K
import mathe as M
import raumkontrolle as R
import spieler as SP
import taktik as T


class Lage:
    """Gemeinsamer Zustand, den alle Schichten lesen (und keine schreibt)."""
    __slots__ = ("ball", "mannschaft", "torwart", "anweisung", "richtung",
                 "ballbesitz", "phasenbesitz", "letzter_besitz", "zeit",
                 "ballbahn", "gegenpress_bis", "grundposition", "halbzeit",
                 "spielt", "lose_seit")

    def __init__(self):
        self.ball = None
        self.mannschaft = [[], []]
        self.torwart = [None, None]
        self.anweisung = [None, None]
        self.richtung = [1, -1]
        self.ballbesitz = None       # Spieler hat den Ball am Fuss
        self.phasenbesitz = None     # wessen Spielphase laeuft gerade
        self.letzter_besitz = None
        self.lose_seit = None
        self.zeit = 0.0
        self.ballbahn = None
        self.gegenpress_bis = [-99.0, -99.0]
        self.grundposition = {}
        self.halbzeit = 1
        self.spielt = True


class Ereignis:
    __slots__ = ("zeit", "art", "team", "spieler", "pos", "wert", "notiz")

    def __init__(self, zeit, art, team=None, spieler=None, pos=None,
                 wert=None, notiz=""):
        self.zeit = zeit
        self.art = art
        self.team = team
        self.spieler = spieler
        self.pos = pos
        self.wert = wert
        self.notiz = notiz

    def als_dict(self):
        return dict(zeit=round(self.zeit, 2), art=self.art, team=self.team,
                    spieler=self.spieler, pos=(None if self.pos is None else
                                               [round(self.pos[0], 2),
                                                round(self.pos[1], 2)]),
                    wert=(None if self.wert is None else round(self.wert, 4)),
                    notiz=self.notiz)


class Standard:
    """Ruhende Spielsituation samt Aufbauphase."""
    __slots__ = ("art", "team", "punkt", "bereit_ab", "schuetze")

    def __init__(self, art, team, punkt, bereit_ab, schuetze=None):
        self.art = art
        self.team = team
        self.punkt = punkt
        self.bereit_ab = bereit_ab
        self.schuetze = schuetze


class Spiel:
    """Eine 11-gegen-11-Simulation."""

    def __init__(self, heim, gast, anweisung_heim=None, anweisung_gast=None,
                 seed=0, dt=K.DT, aufzeichnen=True, aufzeichnungsrate=5):
        """`heim`/`gast` sind Listen von `spieler.Spieler` (11 je Team).

        `aufzeichnungsrate` gibt an, jeder wievielte Frame in die
        Bahnaufzeichnung geht. 5 bei 25 Hz ergibt 5 Hz - genug fuer die
        Darstellung, ein Fuenftel der Datenmenge.
        """
        if len(heim) != 11 or len(gast) != 11:
            raise ValueError("beide Mannschaften brauchen genau 11 Spieler")
        self.rng = random.Random(seed)
        self.dt = dt
        self.lage = Lage()
        self.lage.ball = B.Ball()
        self.lage.mannschaft = [list(heim), list(gast)]
        self.lage.anweisung = [anweisung_heim or T.Teamanweisung(),
                               anweisung_gast or T.Teamanweisung()]
        self.lage.richtung = [1, -1]

        for team, elf in enumerate(self.lage.mannschaft):
            for s in elf:
                s.team = team
                s.rng_offset = self.rng.random()
            tw = [s for s in elf if s.ist_torwart]
            if len(tw) != 1:
                raise ValueError("Team %d braucht genau einen Torwart" % team)
            self.lage.torwart[team] = tw[0]

        self._grundpositionen_setzen()

        self.tore = [0, 0]
        self.ereignisse = []
        self.standard = None
        self.abseits_marke = {}       # spieler -> True, gesetzt beim Abspiel
        self.bahn = []                # Aufzeichnung
        self.aufzeichnen = aufzeichnen
        self.rate = max(1, int(aufzeichnungsrate))
        self._frame = 0
        self.statistik = _leere_statistik()
        self._letzter_schuss_zeit = -99.0
        self._besitz_frames = [0, 0]
        self._anlaeufer = {}          # Spieler -> Abfangpunkt am losen Ball
        self._anlauf_marge = {}       # Spieler -> Zeitvorsprung dorthin
        self._taktik = _leere_taktikzaehler()
        self._im_strafraum = [False, False]
        self._pass_start = None       # (spieler, zeit) fuer Abseits/Statistik

    # ------------------------------------------------------------- Aufstellung
    def _grundpositionen_setzen(self):
        for team, elf in enumerate(self.lage.mannschaft):
            form = T.formation_bauen(self.lage.anweisung[team].formation)
            if len(form) != 11:
                raise ValueError("Formation hat nicht 11 Positionen")
            # Rollen aus der Formation uebernehmen, Reihenfolge = Aufstellung
            for s, (rolle, bx, by) in zip(elf, form):
                s.rolle = rolle
                s.ist_torwart = (rolle == "TW")
                ax = bx * K.FELD_LAENGE - K.HALB_L
                self.lage.grundposition[(s.nummer, team)] = (ax, by)
            self.lage.torwart[team] = [s for s in elf if s.ist_torwart][0]

    def aufstellen(self, anstoss_team=0):
        """Spieler auf ihre Grundpositionen, Ball auf den Anstosspunkt."""
        for team, elf in enumerate(self.lage.mannschaft):
            r = self.lage.richtung[team]
            for s in elf:
                ax, ay = self.lage.grundposition[(s.nummer, team)]
                if team != anstoss_team:
                    ax = min(ax, -2.5)          # eigene Haelfte beim Anstoss
                else:
                    ax = min(ax, -1.0)
                s.pos = (ax * r, ay * r)
                s.v = (0.0, 0.0)
                s.blick = 0.0 if r > 0 else math.pi
                s.am_ball = False
        self.lage.ball.setzen((0.0, 0.0))
        self.lage.ball.traeger = None
        self.lage.ballbesitz = None
        feld = [p for p in self.lage.mannschaft[anstoss_team] if not p.ist_torwart]
        schuetze = min(feld, key=lambda p: M.abstand(p.pos, (0.0, 0.0)))
        self.standard = Standard("anstoss", anstoss_team, (0.0, 0.0),
                                 self.lage.zeit + 1.5, schuetze)

    # ----------------------------------------------------------------- Ablauf
    def laufen(self, dauer, fortschritt=None):
        """`dauer` Sekunden Spielzeit simulieren."""
        ende = self.lage.zeit + dauer
        naechster_bericht = self.lage.zeit + 300.0
        while self.lage.zeit < ende:
            self.schritt()
            if fortschritt and self.lage.zeit >= naechster_bericht:
                fortschritt(self.lage.zeit, self.tore)
                naechster_bericht += 300.0
        return self

    def spielen(self, minuten=90.0, fortschritt=None):
        """Volles Spiel inklusive Halbzeit und Seitenwechsel."""
        self.aufstellen(anstoss_team=0)
        self.laufen(minuten * 30.0, fortschritt)
        self.seiten_wechseln()
        self.aufstellen(anstoss_team=1)
        self.laufen(minuten * 30.0, fortschritt)
        return self

    def seiten_wechseln(self):
        self.lage.richtung = [-self.lage.richtung[0], -self.lage.richtung[1]]
        self.lage.halbzeit = 2
        for elf in self.lage.mannschaft:
            for s in elf:
                s.energie = min(1.0, s.energie + 0.10)   # Halbzeitpause

    # ------------------------------------------------------------ Zeitschritt
    def schritt(self):
        lage = self.lage
        dt = self.dt
        lage.zeit += dt
        self._frame += 1

        # 1 - Lage
        traeger = lage.ball.traeger
        neuer_besitz = traeger.team if traeger is not None else None
        if neuer_besitz is not None:
            if lage.letzter_besitz is not None and neuer_besitz != lage.letzter_besitz:
                verlierer = lage.letzter_besitz
                lage.gegenpress_bis[verlierer] = lage.zeit + 5.0
                self._taktik["ballverluste"][verlierer] += 1
                self._taktik["verlust_zeit"][verlierer] = lage.zeit
            elif neuer_besitz is not None:
                verlust = self._taktik["verlust_zeit"][neuer_besitz]
                if verlust is not None and lage.zeit - verlust <= 5.0:
                    self._taktik["rueckeroberung_5s"][neuer_besitz] += 1
                    self._taktik["verlust_zeit"][neuer_besitz] = None
            lage.letzter_besitz = neuer_besitz
            self._besitz_frames[neuer_besitz] += 1
        lage.ballbesitz = neuer_besitz
        # Spielphase und Ballfuehrung sind zweierlei. Waehrend ein Pass
        # fliegt, hat niemand den Ball am Fuss - die verteidigende Mannschaft
        # verteidigt aber weiter. Wer beides gleichsetzt, laesst bei jedem
        # Pass die Ordnung zerfallen; in der Rohfassung stand danach nur noch
        # der Torwart zwischen Stuermer und Tor.
        if neuer_besitz is not None:
            lage.phasenbesitz = neuer_besitz
            lage.lose_seit = None
        else:
            if lage.lose_seit is None:
                lage.lose_seit = lage.zeit
            if lage.zeit - lage.lose_seit > 1.8:
                lage.phasenbesitz = None      # echter Kampf um den zweiten Ball
            else:
                lage.phasenbesitz = lage.letzter_besitz
        if traeger is None:
            if self._frame % 3 == 0 or not lage.ballbahn:
                lage.ballbahn = lage.ball.bahn(2.8, dt * 3.0)
                self._anlaeufer_bestimmen()
        else:
            lage.ballbahn = None
            self._anlaeufer = {}
            self._anlauf_marge = {}

        # 2 - Entscheidungen und Zielpunkte
        if self.standard is not None:
            self._standard_schritt()
        else:
            self._agenten_schritt()

        # 3 - Physik
        for elf in lage.mannschaft:
            for s in elf:
                s.schritt(dt)
        vorher = lage.ball.pos
        if lage.ball.traeger is not None:
            self._ball_fuehren(lage.ball.traeger)
        else:
            lage.ball.schritt(dt)

        # 4 - Kontakte
        if self.standard is None:
            self._kontakte(vorher)
            self._torwart_aktion()

        # 5 - Regeln
        if self.standard is None:
            self._regeln()

        # 6 - Aufzeichnung und taktische Erfassung
        self._taktik_erfassen()
        if self.aufzeichnen and self._frame % self.rate == 0:
            self._aufzeichnen()

    # ---------------------------------------------------------- Agentenschritt
    def _agenten_schritt(self):
        lage = self.lage
        t = lage.zeit
        traeger = lage.ball.traeger

        for team in (0, 1):
            verteidigt = lage.phasenbesitz != team
            presser = T.presser_bestimmen(lage, team) if verteidigt else []
            press_rang = {p: i for i, p in enumerate(presser)}
            laeufer = T.durchbrueche(lage, team) if verteidigt else {}
            for s in lage.mannschaft[team]:
                if t < s.naechste_entscheidung:
                    continue
                s.naechste_entscheidung = t + K.LAUFTAKT + \
                    (s.rng_offset - 0.5) * 2.0 * K.TAKT_JITTER

                if s is traeger:
                    s.naechste_entscheidung = t + K.ENTSCHEIDUNGSTAKT + \
                        (s.rng_offset - 0.5) * 2.0 * K.TAKT_JITTER
                    self._am_ball(s)
                    continue

                if s.ist_torwart:
                    ztw = T._torwartposition(s, lage)
                    s.steuere(ztw,
                              wunschtempo=M.klemme(
                                  1.2 + 0.6 * M.abstand(s.pos, ztw), 0.8,
                                  s.v_max_akt()),
                              blickziel=lage.ball.xy)
                    continue

                anlauf = self._anlaeufer.get(s)
                if anlauf is not None:
                    # Vollgas nur, wenn es knapp ist - sonst kontrolliert hin
                    d = M.abstand(s.pos, anlauf)
                    knapp = self._anlauf_marge.get(s, 0.0) < 0.6
                    tempo = s.v_max_akt() if knapp else \
                        M.klemme(1.2 + 0.55 * d, 1.5, s.v_max_akt())
                    s.steuere(anlauf, wunschtempo=tempo, blickziel=lage.ball.xy)
                    continue

                verfolgung = laeufer.get(s)
                if verfolgung is not None:
                    # Lauf hinter die Kette: nachsetzen, so schnell es geht
                    s.steuere(verfolgung, wunschtempo=s.v_max_akt(),
                              blickziel=lage.ball.xy)
                    continue

                if s in press_rang:
                    ziel = T.pressziel(s, lage, press_rang[s])
                    d = M.abstand(s.pos, ziel)
                    tempo = M.klemme(1.8 + 0.55 * d, 1.2, s.v_max_akt()) \
                        * (0.80 + 0.20 * lage.anweisung[team].pressing)
                    s.steuere(ziel, wunschtempo=tempo, blickziel=lage.ball.xy)
                    continue

                if verteidigt and lage.anweisung[team].manndeckung > 0.05:
                    gegner = self._zuordnung(s)
                    if gegner is not None and \
                       self.rng.random() < lage.anweisung[team].manndeckung:
                        zd = T.deckungsziel(s, gegner, lage)
                        s.steuere(zd, wunschtempo=M.klemme(
                            1.6 + 0.45 * M.abstand(s.pos, zd), 1.2, s.v_max_akt()),
                            blickziel=lage.ball.xy)
                        continue

                ziel = T.zielposition(s, lage)
                d = M.abstand(s.pos, ziel)
                # Tempo aus der Entfernung zum Ziel, nicht pauschal. Ohne diese
                # Kopplung laeuft die Mannschaft dauerhaft im Grenzbereich und
                # die Laufdistanz landet beim Doppelten des Realen.
                if d < 3.5:
                    tempo = 0.0
                else:
                    tempo = M.klemme(0.8 + 0.30 * (d - 3.5), 1.0, s.v_max_akt())
                blick = lage.ball.xy if verteidigt else None
                s.steuere(ziel, wunschtempo=tempo, blickziel=blick)

    def _anlaeufer_bestimmen(self):
        """Wer laeuft dem losen oder fliegenden Ball entgegen?

        Fuer jeden Spieler in Ballnaehe wird der frueheste Punkt der Ballbahn
        gesucht, den er vor dem Ball erreicht. Je Mannschaft laufen die zwei
        Bestplatzierten an; der vorgesehene Passempfaenger ist immer dabei,
        weil er als einziger weiss, wohin der Ball gespielt wurde.

        Ohne diesen Schritt spielt die Simulation Paesse in leere Raeume: der
        Empfaenger bliebe auf seiner taktischen Position stehen und der Ball
        rollte an ihm vorbei. Das war in der Rohfassung die Hauptursache fuer
        eine Passquote um 30 statt um 80 Prozent.
        """
        lage = self.lage
        bahn = lage.ballbahn
        self._anlauf_marge = {}
        if not bahn:
            self._anlaeufer = {}
            return
        bp = lage.ball.xy
        empfaenger = None
        if self._pass_start is not None:
            empfaenger = self._pass_start[2].empfaenger

        zuordnung = {}
        for team in (0, 1):
            bewertet = []
            for s in lage.mannschaft[team]:
                if lage.zeit < s.sperre_bis:
                    continue
                if M.abstand(s.pos, bp) > 32.0 and s is not empfaenger:
                    continue
                punkt, marge = self._abfangpunkt_und_marge(s, bahn)
                if punkt is None:
                    continue
                bewertet.append((marge, s.nummer, s, punkt))
            bewertet.sort(key=lambda e: -e[0])
            anzahl = 2
            for marge, _, s, punkt in bewertet[:anzahl]:
                zuordnung[s] = punkt
                self._anlauf_marge[s] = marge
            if empfaenger is not None and empfaenger.team == team \
                    and empfaenger not in zuordnung:
                punkt, _ = self._abfangpunkt_und_marge(empfaenger, bahn)
                zuordnung[empfaenger] = punkt or (bahn[-1][1], bahn[-1][2])
        self._anlaeufer = zuordnung

    def _abfangpunkt_und_marge(self, s, bahn):
        """Fruehester erreichbarer Bahnpunkt und der Zeitvorsprung dorthin."""
        beste = None
        best_marge = -1e9
        for i in range(0, len(bahn), 2):
            t, x, y, z = bahn[i]
            if z > K.KOPFBALL_HOEHE:
                continue
            marge = t - s.zeit_zu_punkt((x, y))
            if marge >= 0.0:
                return (x, y), marge
            if marge > best_marge:
                best_marge = marge
                beste = (x, y)
        return beste, best_marge

    def _zuordnung(self, s):
        """Naechster ungedeckter Gegner in der eigenen Zone."""
        lage = self.lage
        best = None
        bd = 12.0
        for g in lage.mannschaft[1 - s.team]:
            if g.ist_torwart:
                continue
            d = M.abstand(s.pos, g.pos)
            if d < bd:
                bd = d
                best = g
        return best

    def _am_ball(self, s):
        opt = E.waehlen(s, self.lage, self.rng)
        if opt is None:
            return
        art = E.ausfuehren(s, opt, self.lage, self.rng)
        if art in ("pass", "klaerung", "schuss"):
            s.am_ball = False
            s.letzte_beruehrung = self.lage.zeit
            self.lage.ball.traeger = None
            self._pass_start = (s, self.lage.zeit, opt)
            if opt.empfaenger is not None:
                # Der Empfaenger reagiert im naechsten Frame - seine
                # Reaktionszeit steckt in `zeit_zu_punkt`, nicht hier.
                opt.empfaenger.naechste_entscheidung = self.lage.zeit
            self._abseits_marken_setzen(s.team)
            self.statistik["paesse"][s.team] += 1 if art == "pass" else 0
            if art == "pass":
                self._ppda_buchen(1 - s.team, "gegnerpaesse")
            if art == "schuss":
                self._schuss_buchen(s, opt)
            elif art == "klaerung":
                self.statistik["klaerungen"][s.team] += 1
        elif art == "dribbling":
            self.statistik["dribblings"][s.team] += 1
            # Ein Dribbling ist eine Folge von Ballkontakten, keine Entscheidung
            # je Frame. Ohne diese Bindung entstehen Passzahlen jenseits des
            # Realen, weil der Ballfuehrende funfmal je Sekunde neu abwaegt.
            s.naechste_entscheidung = self.lage.zeit + 0.45 + \
                (s.rng_offset - 0.5) * 0.2

    def _schuss_buchen(self, s, opt):
        lage = self.lage
        self.statistik["schuesse"][s.team] += 1
        self.statistik["xg"][s.team] += opt.p
        self.ereignisse.append(Ereignis(lage.zeit, "schuss", s.team, s.name,
                                        s.pos, opt.p, opt.notiz))
        self._letzter_schuss_zeit = lage.zeit

    def _abseits_marken_setzen(self, team):
        """Abseitsstellung im Moment des Abspiels festhalten."""
        lage = self.lage
        linie = T.abseitslinie(lage, team)
        r = lage.richtung[team]
        self.abseits_marke = {}
        bx = lage.ball.pos[0] * r
        for m in lage.mannschaft[team]:
            x = m.pos[0] * r
            if x > linie + K.ABSEITS_TOLERANZ and x > bx and x > 0.0:
                self.abseits_marke[m] = True

    # ------------------------------------------------------------ Ballfuehrung
    def _ball_fuehren(self, s):
        """Der gefuehrte Ball liegt vor dem Fuss, nicht im Koerper."""
        vor = M.aus_winkel(s.blick, K.DRIBBEL_ABSTAND)
        self.lage.ball.pos = (s.pos[0] + vor[0], s.pos[1] + vor[1], 0.06)
        self.lage.ball.v = (s.v[0], s.v[1], 0.0)

    # ---------------------------------------------------------------- Kontakte
    def _kontakte(self, vorher):
        """Ballkontakte im zurueckgelegten Streckenabschnitt.

        Geprueft wird die **Strecke** vom vorigen zum aktuellen Ballort, nicht
        der aktuelle Punkt. Bei 30 m/s legt der Ball je Frame 1.2 m zurueck und
        wuerde sonst durch Spieler hindurchtunneln: geblockte Schuesse und
        abgefangene scharfe Paesse gaebe es praktisch nicht, und die
        tatsaechliche Torausbeute laege deutlich ueber dem eigenen xG-Modell.
        """
        lage = self.lage
        t = lage.zeit
        bp = lage.ball.xy
        bz = lage.ball.pos[2]

        traeger = lage.ball.traeger
        if traeger is not None:
            self._zweikampf_am_ball(traeger)
            return

        vor_xy = (vorher[0], vorher[1])
        if min(vorher[2], bz) > K.KOPFBALL_HOEHE:
            return

        # Wer ist am Ball? Naechster Punkt auf der Strecke, Hoehe interpoliert.
        kandidaten = []
        beruehrpunkt = {}
        for elf in lage.mannschaft:
            for s in elf:
                if t < s.sperre_bis or t - s.letzte_beruehrung < 0.30:
                    continue
                radius = K.KONTROLL_RADIUS + (0.35 if s.ist_torwart else 0.0)
                naeh, f = M.punkt_auf_strecke(vor_xy, bp, s.pos)
                if M.abstand(naeh, s.pos) > radius:
                    continue
                z = vorher[2] + (bz - vorher[2]) * f
                if z > K.KOPFBALL_HOEHE:
                    continue
                kandidaten.append(s)
                beruehrpunkt[s] = naeh
        if not kandidaten:
            return

        # Torwart im eigenen Strafraum greift zuerst
        for s in kandidaten:
            if s.ist_torwart and self._im_eigenen_strafraum(s, bp):
                self._ball_annehmen(s, sicher=True)
                return

        if len(kandidaten) == 1:
            self._ball_annehmen(kandidaten[0])
            return

        # Als umkaempft gilt nur, was wirklich umkaempft ist: mindestens ein
        # Bewerber der Gegenseite in aehnlicher Entfernung. Zwei Mitspieler am
        # selben Ball sind kein Zweikampf.
        gegner_dabei = any(a.team != b.team for a in kandidaten for b in kandidaten)
        # Umkaempfter Ball: wer naeher dran ist, gewinnt meistens. Attribute und
        # Koerperstellung entscheiden nur die knappen Faelle - ohne den
        # Naeheterm verliert der ordentlich angespielte Empfaenger jeden
        # zweiten Ball an einen anderthalb Meter entfernten Gegner.
        bester, bw = None, -1e9
        for s in kandidaten:
            d = M.abstand(s.pos, beruehrpunkt[s])
            w = 1.4 * (1.0 - d / (K.KONTROLL_RADIUS + 0.4))
            w += (0.6 * s.attribute.zweikampf + 0.4 * s.attribute.erste_beruehrung)
            bpt = beruehrpunkt[s]
            w += 0.25 * (1.0 - abs(M.winkel_diff(
                math.atan2(bpt[1] - s.pos[1], bpt[0] - s.pos[0]), s.blick)) / math.pi)
            w += self.rng.gauss(0.0, 0.22)
            if w > bw:
                bw, bester = w, s
        for s in kandidaten:
            if s is not bester:
                s.sperre_bis = t + 0.25
        self._ball_annehmen(bester, umkaempft=gegner_dabei)

    def _ball_annehmen(self, s, sicher=False, umkaempft=False):
        """Annahmeversuch. Misslingt er, springt der Ball weg."""
        lage = self.lage
        rel = M.betrag(M.sub(lage.ball.vxy, s.v))
        hoch = lage.ball.pos[2] > K.KONTROLL_HOEHE
        druck = R.druck_auf(s, lage.mannschaft[1 - s.team], radius=4.0)
        if sicher:
            p = 0.97
        else:
            # Kalibriert auf: unbedraengte Annahme gelingt fast immer, unter
            # vollem Druck rund zwei von drei Mal. Das Balltempo zaehlt erst
            # oberhalb von 10 m/s - ein sauber gespielter Pass ist auch scharf
            # zu verarbeiten.
            p = (0.96 + 0.14 * (s.attribute.erste_beruehrung - 0.5)
                 - 0.008 * max(0.0, rel - 12.0) - 0.28 * druck)
            if hoch:
                p = p * 0.70 + 0.16 * s.attribute.kopfball
            if umkaempft:
                p -= 0.12
        if self.rng.random() < M.klemme(p, 0.05, 0.98):
            lage.ball.traeger = s
            lage.ball.letzter_traeger = s
            lage.ball.letztes_team = s.team
            s.am_ball = True
            s.letzte_beruehrung = lage.zeit
            self._abseits_pruefen(s)
            if self._pass_start is not None:
                geber, zeit0, opt = self._pass_start
                if geber.team == s.team and opt.art == "pass":
                    self.statistik["paesse_an"][s.team] += 1
                self._pass_start = None
            # Ballan- und -mitnahme kostet Zeit. Ohne diese Pause spielt die
            # Simulation Direktpassketten im Viertelsekundentakt und landet bei
            # der dreifachen realen Passzahl.
            s.naechste_entscheidung = lage.zeit + \
                M.klemme(0.75 - 0.35 * s.attribute.erste_beruehrung, 0.30, 0.80)
        else:
            # abgeprallt
            w = self.rng.uniform(0, 2 * math.pi)
            tempo = max(1.5, rel * 0.35)
            lage.ball.loesen(M.aus_winkel(w), tempo,
                             steigung=self.rng.uniform(0.0, 0.35), traeger=s,
                             zeit=lage.zeit)
            s.letzte_beruehrung = lage.zeit
            s.sperre_bis = lage.zeit + 0.18

    def _zweikampf_am_ball(self, traeger):
        """Verteidiger versucht, dem Ballfuehrenden den Ball abzunehmen."""
        lage = self.lage
        t = lage.zeit
        for g in lage.mannschaft[1 - traeger.team]:
            if M.abstand(g.pos, traeger.pos) > K.ZWEIKAMPF_RADIUS:
                continue
            if t < g.sperre_bis or t - g.letzte_beruehrung < 1.0:
                continue
            # Versuchsrate: aggressive Spieler greifen haeufiger an. Kalibriert
            # auf rund einen Zweikampfversuch je 1.5 s Bedraengnis - hoehere
            # Raten erzeugen Zweikampfzahlen jenseits jeder Statistik.
            # Auch die Mannschaftsanweisung wirkt: wer hoch presst, geht
            # haeufiger in den Zweikampf statt zu begleiten.
            rate = ((0.65 + 0.80 * g.attribute.aggressivitaet)
                    * (0.72 + 0.56 * lage.anweisung[g.team].pressing) * self.dt)
            if self.rng.random() > rate:
                continue
            g.letzte_beruehrung = t
            staerke_g = 0.7 * g.attribute.zweikampf + 0.3 * g.attribute.antizipation
            staerke_t = (0.55 * traeger.attribute.dribbling
                         + 0.45 * traeger.attribute.zweikampf)
            # Wer von hinten kommt, hat es schwerer
            w = math.atan2(traeger.pos[1] - g.pos[1], traeger.pos[0] - g.pos[0])
            von_vorn = 1.0 - abs(M.winkel_diff(w, traeger.blick)) / math.pi
            p_gewinn = M.klemme(0.42 + 0.85 * (staerke_g - staerke_t)
                                - 0.12 * von_vorn, 0.08, 0.88)
            # Ein Zweikampf wird je *Sequenz* gezaehlt, nicht je Versuch: ein
            # Verteidiger, der drei Sekunden am Mann klebt, geht als ein
            # Zweikampf in die Statistik ein, nicht als drei. Sonst laegen die
            # Zweikampfzahlen beim Dreifachen jeder realen Erhebung.
            self._ppda_buchen(g.team, "defensivaktionen")
            if t - g.aktion_bis > 3.0:
                self.statistik["zweikaempfe"][g.team] += 1
                g.aktion = "zweikampf"
            g.aktion_bis = t
            if self.rng.random() < p_gewinn:
                if g.aktion == "zweikampf":
                    self.statistik["zweikaempfe_gew"][g.team] += 1
                    g.aktion = None
                if self.rng.random() < 0.55:
                    lage.ball.traeger = g
                    g.am_ball = True
                    traeger.am_ball = False
                    lage.ball.letztes_team = g.team
                    g.naechste_entscheidung = t + 0.20
                else:
                    # abgegraetscht: loser Ball
                    w2 = self.rng.uniform(0, 2 * math.pi)
                    lage.ball.traeger = None
                    traeger.am_ball = False
                    lage.ball.loesen(M.aus_winkel(w2), self.rng.uniform(3.0, 9.0),
                                     steigung=self.rng.uniform(0.0, 0.4),
                                     traeger=g, zeit=t)
                traeger.sperre_bis = t + 0.25
                return
            # verloren -> Foulgefahr
            p_foul = K.FOUL_BASIS * (0.6 + 1.4 * g.attribute.aggressivitaet)
            if self._im_eigenen_strafraum(g, traeger.pos):
                p_foul *= K.FOUL_STRAFRAUM
            if self.rng.random() < p_foul:
                self._foul(g, traeger)
                return
            g.sperre_bis = t + 0.35

    # --------------------------------------------------------------- Torwart
    def _torwart_aktion(self):
        lage = self.lage
        ball = lage.ball
        if ball.traeger is not None:
            return
        for team in (0, 1):
            tw = lage.torwart[team]
            r = lage.richtung[team]
            tor = (-K.HALB_L * r, 0.0)
            if M.abstand(ball.xy, tor) > 22.0:
                continue
            # Kommt der Ball aufs Tor?
            if ball.v[0] * (-r) <= 0.5:
                continue
            kreuzung = self._torlinien_kreuzung(ball, r)
            if kreuzung is None:
                continue
            t, y, z, tempo = kreuzung
            if abs(y) > K.TOR_HALB_BREITE or z > K.TOR_HOEHE:
                continue                        # geht ohnehin daneben
            if t > 1.0:
                continue                        # noch nicht festlegen
            # Genau ein Paradeversuch je Ballfreigabe. Ohne diese Sperre
            # bekommt der Torwart in jedem Frame eine neue Chance und haelt
            # rechnerisch alles - in der Rohfassung fiel aus 22 m kein
            # einziges Tor mehr.
            if tw.aktion == ball.start_zeit:
                continue
            tw.aktion = ball.start_zeit

            # Parade. Massgeblich ist der Weg, den der Torwart bis zum
            # Kreuzungspunkt zuruecklegen muss: Sprungreichweite plus die
            # Schritte, die nach seiner Reaktionszeit noch bleiben. Die Hoehe
            # zaehlt staerker als die Breite - ein Ball in den Winkel ist
            # schwerer als einer flach daneben.
            quer = abs(y - tw.pos[1])
            hoch = max(0.0, z - 0.55)
            weg = math.hypot(quer, hoch * 1.25)
            reaktion = tw.attribute.reaktion * 0.85
            erreichbar = K.TW_REICHWEITE + tw.v_max_akt() * max(0.0, t - reaktion)
            # Zwei getrennte Groessen: **erreichbar** ist Geometrie (Spannweite
            # plus die Schritte nach der Reaktionszeit), **zeitfaktor** ist die
            # Guete der Aktion. Aus kurzer Distanz erreicht der Torwart den Ball
            # zwar, kann ihn aber kaum noch kontrolliert abwehren - deshalb
            # faellt der Zeitfaktor unter einer halben Sekunde deutlich ab.
            # Kalibriert gegen den Schussdrill in tests.py.
            verhaeltnis = weg / erreichbar
            if verhaeltnis >= 1.0:
                continue
            zeitfaktor = M.klemme(0.62 + 0.38 * (t - 0.18) / 0.5, 0.75, 1.0)
            guete = 0.90 + 0.20 * tw.attribute.zweikampf
            p = M.klemme(0.97 * math.exp(-1.1 * verhaeltnis * verhaeltnis)
                         * zeitfaktor * guete
                         - 0.006 * max(0.0, tempo - 22.0), 0.02, 0.96)
            if self.rng.random() >= p:
                continue
            self.statistik["paraden"][team] += 1
            x_linie = -r * K.HALB_L
            if self.rng.random() < 0.55:
                ball.setzen((x_linie + r * 1.0, y), 0.2)
                ball.traeger = tw
                tw.am_ball = True
                self.ereignisse.append(Ereignis(lage.zeit, "parade", team,
                                                tw.name, tw.pos))
            else:
                w = math.atan2(y, x_linie + r * K.HALB_L) if abs(y) > 0.1 else \
                    (math.pi if r > 0 else 0.0)
                ball.setzen((x_linie + r * 1.2, y), max(z * 0.6, 0.1))
                ball.loesen(M.aus_winkel(w + self.rng.gauss(0, 0.6)),
                            self.rng.uniform(4.0, 12.0), steigung=0.3,
                            traeger=tw, zeit=lage.zeit)
                self.ereignisse.append(Ereignis(lage.zeit, "parade", team,
                                                tw.name, tw.pos, notiz="abgewehrt"))
            tw.letzte_beruehrung = lage.zeit

    def _torlinien_kreuzung(self, ball, r):
        """Wo und wann kreuzt der Ball die eigene Torlinie?

        Zwischen den Stuetzstellen der Bahn wird linear interpoliert. Ohne die
        Interpolation wird die Parade an einem Punkt bis zu zweieinhalb Meter
        *hinter* der Linie bewertet - der Ball ist dort seitlich schon
        abgedriftet, der Torwart scheint zu weit weg, und aus kurzer Distanz
        faellt fast jeder Schuss.
        """
        x_linie = -r * K.HALB_L
        bahn = ball.bahn(1.6, self.dt * 2.0)
        vorher_x = ball.pos[0]
        vorher = (0.0, ball.pos[0], ball.pos[1], ball.pos[2])
        for (t, x, y, z) in bahn:
            drueber = (x <= x_linie) if r > 0 else (x >= x_linie)
            if drueber:
                t0, x0, y0, z0 = vorher
                d = x - x0
                f = 0.0 if abs(d) < 1e-9 else (x_linie - x0) / d
                f = M.klemme(f, 0.0, 1.0)
                return (t0 + (t - t0) * f, y0 + (y - y0) * f,
                        z0 + (z - z0) * f, ball.tempo)
            vorher = (t, x, y, z)
        return None

    # ----------------------------------------------------------------- Regeln    # ----------------------------------------------------------------- Regeln
    def _regeln(self):
        lage = self.lage
        b = lage.ball
        x, y, z = b.pos

        # --- Tor
        if abs(x) >= K.HALB_L and abs(y) <= K.TOR_HALB_BREITE and z <= K.TOR_HOEHE:
            # Wer spielt auf dieses Tor?
            treffer_team = 0 if (x > 0) == (lage.richtung[0] > 0) else 1
            self._tor(treffer_team)
            return

        # --- Seitenaus
        if abs(y) > K.HALB_B:
            letzte = b.letztes_team
            team = 1 - letzte if letzte is not None else 0
            punkt = (M.klemme(x, -K.HALB_L + 0.5, K.HALB_L - 0.5),
                     math.copysign(K.HALB_B - 0.1, y))
            self._standard_setzen("einwurf", team, punkt)
            return

        # --- Torlinie ohne Tor
        if abs(x) > K.HALB_L:
            letzte = b.letztes_team
            if letzte is None:
                letzte = 0
            # Auf welches Tor? Verteidigendes Team bestimmt Ecke oder Abstoss
            verteidiger = 0 if (x > 0) != (lage.richtung[0] > 0) else 1
            if letzte == verteidiger:
                self._standard_setzen(
                    "ecke", 1 - verteidiger,
                    (math.copysign(K.HALB_L - 0.3, x),
                     math.copysign(K.HALB_B - 0.3, y if y != 0 else 1.0)))
            else:
                r = lage.richtung[verteidiger]
                self._standard_setzen(
                    "abstoss", verteidiger,
                    (-r * (K.HALB_L - K.TORRAUM_TIEFE - 0.5),
                     math.copysign(6.0, y if y != 0 else 1.0)))
            return

    def _abseits_pruefen(self, s):
        if self.abseits_marke.get(s):
            self.abseits_marke = {}
            self.statistik["abseits"][s.team] += 1
            self.ereignisse.append(Ereignis(self.lage.zeit, "abseits", s.team,
                                            s.name, s.pos))
            self._standard_setzen("freistoss", 1 - s.team, s.pos)

    def _foul(self, taeter, opfer):
        lage = self.lage
        self.statistik["fouls"][taeter.team] += 1
        self.ereignisse.append(Ereignis(lage.zeit, "foul", taeter.team,
                                        taeter.name, opfer.pos))
        r = lage.richtung[taeter.team]
        eigenes_tor = (-r * K.HALB_L, 0.0)
        im_strafraum = (M.abstand(opfer.pos, eigenes_tor) < 20.0
                        and abs(opfer.pos[0]) > K.HALB_L - K.STRAFRAUM_TIEFE
                        and abs(opfer.pos[1]) < K.STRAFRAUM_HALB_BREITE
                        and (opfer.pos[0] * r) < 0)
        if im_strafraum:
            self._elfmeter(1 - taeter.team, opfer)
        else:
            self._standard_setzen("freistoss", 1 - taeter.team, opfer.pos)

    def _elfmeter(self, team, schuetze):
        lage = self.lage
        r = lage.richtung[team]
        punkt = (r * (K.HALB_L - K.ELFMETER_ABSTAND), 0.0)
        self.ereignisse.append(Ereignis(lage.zeit, "elfmeter", team,
                                        schuetze.name, punkt))
        tw = lage.torwart[1 - team]
        p = K.PENALTY_XG * (0.86 + 0.28 * schuetze.attribute.abschluss) \
            * (1.0 - 0.10 * (tw.attribute.zweikampf - 0.5))
        self.statistik["schuesse"][team] += 1
        self.statistik["xg"][team] += p
        if self.rng.random() < M.klemme(p, 0.05, 0.97):
            self._tor(team, notiz="Elfmeter", schuetze=schuetze.name, pos=punkt)
        else:
            self._standard_setzen("abstoss", 1 - team,
                                  (-r * (K.HALB_L - K.TORRAUM_TIEFE - 0.5), 6.0))

    def _tor(self, team, notiz="", schuetze=None, pos=None):
        lage = self.lage
        self.tore[team] += 1
        name = schuetze or (lage.ball.letzter_traeger.name
                            if lage.ball.letzter_traeger else "?")
        self.ereignisse.append(Ereignis(lage.zeit, "tor", team, name,
                                        pos or lage.ball.xy, notiz=notiz))
        for elf in lage.mannschaft:
            for s in elf:
                s.am_ball = False
        lage.ball.traeger = None
        self.aufstellen(anstoss_team=1 - team)

    # ------------------------------------------------------------- Standards
    def _standard_setzen(self, art, team, punkt):
        lage = self.lage
        punkt = (M.klemme(punkt[0], -K.HALB_L + 0.3, K.HALB_L - 0.3),
                 M.klemme(punkt[1], -K.HALB_B + 0.1, K.HALB_B - 0.1))
        lage.ball.setzen(punkt)
        lage.ball.traeger = None
        for elf in lage.mannschaft:
            for s in elf:
                s.am_ball = False
        # Ausfuehrender: naechster passender Spieler
        if art == "abstoss":
            schuetze = lage.torwart[team]
        else:
            feld = [s for s in lage.mannschaft[team] if not s.ist_torwart]
            schuetze = min(feld, key=lambda s: M.abstand(s.pos, punkt))
        verzoegerung = {"einwurf": 3.0, "abstoss": 6.0, "ecke": 9.0,
                        "freistoss": 5.0, "anstoss": 2.0}.get(art, 4.0)
        self.standard = Standard(art, team, punkt,
                                 lage.zeit + verzoegerung, schuetze)
        self.statistik["standards"][team] += 1
        self.ereignisse.append(Ereignis(lage.zeit, art, team, schuetze.name, punkt))

    def _standard_schritt(self):
        lage = self.lage
        st = self.standard
        punkt = st.punkt
        for team in (0, 1):
            for s in lage.mannschaft[team]:
                if s is st.schuetze:
                    ziel = (punkt[0] - 0.9 * _richtung_zum_feld(punkt)[0],
                            punkt[1] - 0.9 * _richtung_zum_feld(punkt)[1])
                    s.steuere(ziel, wunschtempo=s.v_max_akt() * 0.55,
                              blickziel=punkt)
                    continue
                ziel = self._standard_ziel(s, st)
                if team != st.team and st.art in ("einwurf", "freistoss", "ecke"):
                    d = M.abstand(ziel, punkt)
                    if d < K.STANDARD_ABSTAND:
                        weg = M.normiert(M.sub(ziel, punkt)) if d > 0.1 else (0.0, 1.0)
                        ziel = (punkt[0] + weg[0] * K.STANDARD_ABSTAND,
                                punkt[1] + weg[1] * K.STANDARD_ABSTAND)
                s.steuere(ziel, wunschtempo=s.v_max_akt() * 0.60,
                          blickziel=punkt)

        if lage.zeit < st.bereit_ab:
            return
        if M.abstand(st.schuetze.pos, punkt) > 2.2:
            return

        # Ausfuehren
        lage.ball.setzen(punkt)
        st.schuetze.blick = M.winkel(M.sub(
            (lage.richtung[st.team] * K.HALB_L, 0.0), punkt))
        lage.ball.traeger = st.schuetze
        st.schuetze.am_ball = True
        st.schuetze.naechste_entscheidung = lage.zeit
        st.schuetze.letzte_beruehrung = lage.zeit
        lage.ball.letztes_team = st.team
        self.standard = None
        self.abseits_marke = {}

    def _standard_ziel(self, s, st):
        lage = self.lage
        if st.art == "ecke":
            r = lage.richtung[st.team]
            tor = (r * K.HALB_L, 0.0)
            if s.team == st.team and not s.ist_torwart:
                if T.ROLLEN[s.rolle]["linie"] >= 2:
                    return (tor[0] - r * self.rng.uniform(5.0, 13.0),
                            self.rng.uniform(-8.0, 8.0))
                return (tor[0] - r * 26.0, s.pos[1] * 0.6)
            if s.team != st.team and not s.ist_torwart:
                return (tor[0] - r * self.rng.uniform(4.0, 11.0),
                        self.rng.uniform(-7.0, 7.0))
        if st.art == "anstoss":
            ax, ay = lage.grundposition[(s.nummer, s.team)]
            r = lage.richtung[s.team]
            if s.team != st.team:
                ax = min(ax, -2.5)
            else:
                ax = min(ax, -1.0)
            return (ax * r, ay * r)
        return T.zielposition(s, lage)

    def _im_eigenen_strafraum(self, s, punkt):
        r = self.lage.richtung[s.team]
        return (punkt[0] * r) < -(K.HALB_L - K.STRAFRAUM_TIEFE) and \
               abs(punkt[1]) < K.STRAFRAUM_HALB_BREITE

    # ------------------------------------------------ Taktische Erfassung
    def _taktik_erfassen(self):
        """Laufende taktische Kennzahlen mitschreiben.

        Alles hier ist gezaehlt, nicht geschaetzt: die Abwehrhoehe ist der
        gemittelte Ort der Viererkette, PPDA sind gezaehlte gegnerische Paesse
        je eigener Defensivaktion, Strafraumeintritte sind Flankenwechsel eines
        Zustands. Die gefahrgewichtete Flaeche ist die einzige teure Groesse und
        wird deshalb nur alle fuenf Sekunden abgetastet.
        """
        lage = self.lage
        z = self._taktik
        for team in (0, 1):
            r = lage.richtung[team]
            kette = [s.pos[0] * r for s in lage.mannschaft[team]
                     if T.ROLLEN[s.rolle]["linie"] == 1]
            if kette:
                z["linie_summe"][team] += (sum(kette) / len(kette)) + K.HALB_L
                z["linie_n"][team] += 1
            # Strafraumeintritt: Zustandswechsel des Balls
            drin = ((lage.ball.pos[0] * r) > (K.HALB_L - K.STRAFRAUM_TIEFE)
                    and abs(lage.ball.pos[1]) < K.STRAFRAUM_HALB_BREITE)
            if drin and not self._im_strafraum[team]:
                z["strafraumeintritte"][team] += 1
            self._im_strafraum[team] = drin

        if self._frame % 125 == 0:      # alle 5 s bei 25 Hz
            h, g = R.kontrollierte_flaeche(lage.mannschaft[0], lage.mannschaft[1],
                                           lage.richtung[0], nx=22, ny=14,
                                           nur_gefaehrlich=True)
            z["gefahrflaeche"][0] += h
            z["gefahrflaeche"][1] += g
            z["gefahr_n"] += 1

    def _ppda_buchen(self, team, art):
        """PPDA-Bausteine: gegnerische Paesse und eigene Defensivaktionen.

        Gezaehlt wird nur im vorderen Feldbereich (ab 40 % der Feldlaenge aus
        Sicht des pressenden Teams) - so ist PPDA ueblich definiert.
        """
        lage = self.lage
        r = lage.richtung[team]
        x = lage.ball.pos[0] * r
        if x < -K.HALB_L + 0.40 * K.FELD_LAENGE:
            return
        self._taktik[art][team] += 1

    def raumauswertung(self):
        """Taktische Kennzahlen des Laufs, teamweise als (heim, gast)."""
        z = self._taktik
        hoehe = tuple(round(z["linie_summe"][i] / max(1, z["linie_n"][i]), 2)
                      for i in (0, 1))
        ppda = tuple(round(z["gegnerpaesse"][i] / max(1, z["defensivaktionen"][i]), 2)
                     for i in (0, 1))
        flaeche = tuple(round(z["gefahrflaeche"][i] / max(1, z["gefahr_n"]), 3)
                        for i in (0, 1))
        rueck = tuple(round(z["rueckeroberung_5s"][i] / max(1, z["ballverluste"][i]), 3)
                      for i in (0, 1))
        return {
            "abwehrhoehe_m": hoehe,
            "ppda": ppda,
            "gefahrflaeche": flaeche,
            "strafraumeintritte": tuple(z["strafraumeintritte"]),
            "rueckeroberung_5s": rueck,
        }

    # ------------------------------------------------------------ Aufzeichnung
    def _aufzeichnen(self):
        lage = self.lage
        rahmen = [round(lage.zeit, 2)]
        for elf in lage.mannschaft:
            for s in elf:
                rahmen.append(round(s.pos[0], 2))
                rahmen.append(round(s.pos[1], 2))
        b = lage.ball.pos
        rahmen.extend((round(b[0], 2), round(b[1], 2), round(b[2], 2)))
        rahmen.append(-1 if lage.ballbesitz is None else lage.ballbesitz)
        self.bahn.append(rahmen)

    # -------------------------------------------------------------- Auswertung
    def bericht(self):
        lage = self.lage
        gesamt = max(1, sum(self._besitz_frames))
        st = self.statistik
        aus = {
            "tore": list(self.tore),
            "xg": [round(v, 3) for v in st["xg"]],
            "schuesse": list(st["schuesse"]),
            "paesse": list(st["paesse"]),
            "paesse_an": list(st["paesse_an"]),
            "passquote": [round(st["paesse_an"][i] / max(1, st["paesse"][i]), 3)
                          for i in (0, 1)],
            "ballbesitz": [round(self._besitz_frames[i] / gesamt, 3) for i in (0, 1)],
            "zweikaempfe": list(st["zweikaempfe"]),
            "zweikampfquote": [round(st["zweikaempfe_gew"][i]
                                     / max(1, st["zweikaempfe"][i]), 3)
                               for i in (0, 1)],
            "fouls": list(st["fouls"]),
            "abseits": list(st["abseits"]),
            "standards": list(st["standards"]),
            "paraden": list(st["paraden"]),
            "spielzeit": round(lage.zeit, 1),
        }
        for team in (0, 1):
            elf = lage.mannschaft[team]
            aus.setdefault("laufdistanz", []).append(
                round(sum(s.laufdistanz for s in elf) / 1000.0, 2))
            aus.setdefault("sprintdistanz", []).append(
                round(sum(s.sprintdistanz for s in elf), 0))
            aus.setdefault("spitzentempo", []).append(
                round(max(s.spitzentempo for s in elf), 2))
            aus.setdefault("energie_ende", []).append(
                round(sum(s.energie for s in elf) / len(elf), 3))
        return aus

    def spielerbericht(self):
        zeilen = []
        for team, elf in enumerate(self.lage.mannschaft):
            for s in elf:
                zeilen.append(dict(
                    team=team, nummer=s.nummer, name=s.name, rolle=s.rolle,
                    laufdistanz_km=round(s.laufdistanz / 1000.0, 2),
                    sprint_m=round(s.sprintdistanz, 0),
                    hi_m=round(s.hi_distanz, 0),
                    spitzentempo=round(s.spitzentempo, 2),
                    energie=round(s.energie, 3)))
        return zeilen


def _richtung_zum_feld(punkt):
    """Einheitsvektor vom Feldrand ins Feld - fuer die Aufstellung am Ball."""
    v = (-punkt[0], -punkt[1])
    return M.normiert(v)


def _leere_taktikzaehler():
    return {
        "linie_summe": [0.0, 0.0], "linie_n": [0, 0],
        "gegnerpaesse": [0, 0], "defensivaktionen": [0, 0],
        "gefahrflaeche": [0.0, 0.0], "gefahr_n": 0,
        "strafraumeintritte": [0, 0],
        "ballverluste": [0, 0], "rueckeroberung_5s": [0, 0],
        "verlust_zeit": [None, None],
    }


def _leere_statistik():
    z = {k: [0, 0] for k in (
        "schuesse", "paesse", "paesse_an", "zweikaempfe", "zweikaempfe_gew",
        "fouls", "abseits", "standards", "paraden", "klaerungen", "dribblings",
    )}
    z["xg"] = [0.0, 0.0]
    return z
