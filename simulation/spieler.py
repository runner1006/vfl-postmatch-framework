"""Der Spieler als dynamischer Agent: Physik, Ausdauer, Wahrnehmung.

Ein Agent hat drei Schichten, die hier strikt getrennt bleiben:

1. **Attribute** - was der Spieler kann. Zeitkonstant innerhalb eines Spiels
   (bis auf Ermuedung). Das ist die Schnittstelle zum Digital Twin: reale
   Messwerte gehen hier hinein, sonst nirgends.
2. **Zustand** - wo er ist, wie schnell, wohin gedreht, wie frisch.
3. **Steuerung** - was er gerade will. Die taktische und die
   Entscheidungsschicht schreiben nur `ziel`, `wunschtempo` und `blickziel`;
   wie daraus Bewegung wird, entscheidet allein die Physik hier.

Diese Trennung ist der Grund, warum ein Spielertausch im Kontrafaktischen
sauber ist: es aendert sich Schicht 1, nicht die Regeln.
"""
import math

import konfig as K
import mathe as M


class Attribute:
    """Faehigkeitsprofil eines Spielers.

    Physische Werte stehen in SI-Einheiten, weil sie messbar sind und aus
    Tracking-Daten direkt uebernommen werden koennen. Technische und
    kognitive Werte stehen auf [0, 1], wobei 0.5 dem Ligadurchschnitt
    entspricht; sie sind nicht direkt messbar und werden im Digital Twin aus
    Perzentilen abgebildet (siehe `zwilling.py`).
    """
    __slots__ = (
        "v_max", "a_max", "brems", "quer", "reaktion", "drehrate", "ausdauer",
        "passgenauigkeit", "passtempo", "erste_beruehrung", "dribbling",
        "abschluss", "zweikampf", "kopfball",
        "entscheidung", "uebersicht", "antizipation", "positionsspiel",
        "aggressivitaet", "risikofreude",
    )

    def __init__(self, v_max=K.BASIS_VMAX, a_max=K.BASIS_AMAX,
                 brems=K.BASIS_BREMS, quer=K.BASIS_QUER,
                 reaktion=K.BASIS_REAKTION, drehrate=K.BASIS_DREHRATE,
                 ausdauer=0.5, passgenauigkeit=0.5, passtempo=0.5,
                 erste_beruehrung=0.5, dribbling=0.5, abschluss=0.5,
                 zweikampf=0.5, kopfball=0.5, entscheidung=0.5,
                 uebersicht=0.5, antizipation=0.5, positionsspiel=0.5,
                 aggressivitaet=0.5, risikofreude=0.5):
        self.v_max = v_max
        self.a_max = a_max
        self.brems = brems
        self.quer = quer
        self.reaktion = reaktion
        self.drehrate = drehrate
        self.ausdauer = ausdauer
        self.passgenauigkeit = passgenauigkeit
        self.passtempo = passtempo
        self.erste_beruehrung = erste_beruehrung
        self.dribbling = dribbling
        self.abschluss = abschluss
        self.zweikampf = zweikampf
        self.kopfball = kopfball
        self.entscheidung = entscheidung
        self.uebersicht = uebersicht
        self.antizipation = antizipation
        self.positionsspiel = positionsspiel
        self.aggressivitaet = aggressivitaet
        self.risikofreude = risikofreude

    def kopie(self, **aenderungen):
        """Neues Profil mit einzelnen ueberschriebenen Werten.

        Das ist die Grundoperation jedes Kontrafaktischen: ein Attribut
        aendern, alles andere gleich lassen.
        """
        werte = {n: getattr(self, n) for n in self.__slots__}
        unbekannt = set(aenderungen) - set(self.__slots__)
        if unbekannt:
            raise KeyError("unbekannte Attribute: %s" % sorted(unbekannt))
        werte.update(aenderungen)
        return Attribute(**werte)

    def als_dict(self):
        return {n: getattr(self, n) for n in self.__slots__}


DURCHSCHNITT = Attribute()


class Spieler:
    """Ein Agent auf dem Platz."""
    __slots__ = (
        "name", "nummer", "team", "rolle", "attribute", "ist_torwart",
        "pos", "v", "blick", "energie",
        "ziel", "wunschtempo", "blickziel",
        "letzte_beruehrung", "sperre_bis", "naechste_entscheidung",
        "laufdistanz", "sprintdistanz", "hi_distanz", "spitzentempo",
        "am_ball", "aktion", "aktion_bis", "rng_offset",
    )

    def __init__(self, name, nummer, team, rolle, attribute=None,
                 ist_torwart=False):
        self.name = name
        self.nummer = nummer
        self.team = team              # 0 = Heim, 1 = Gast
        self.rolle = rolle            # Rollenschluessel, siehe taktik.py
        self.attribute = attribute or Attribute()
        self.ist_torwart = ist_torwart

        self.pos = (0.0, 0.0)
        self.v = (0.0, 0.0)
        self.blick = 0.0              # Koerperorientierung in rad
        self.energie = 1.0

        self.ziel = (0.0, 0.0)
        self.wunschtempo = 0.0
        self.blickziel = None         # Punkt, zu dem der Koerper zeigen soll

        self.letzte_beruehrung = -99.0
        self.sperre_bis = -99.0       # z.B. nach Fehlversuch kurz handlungsunfaehig
        self.naechste_entscheidung = 0.0
        self.rng_offset = 0.0

        self.laufdistanz = 0.0
        self.sprintdistanz = 0.0      # > 7.0 m/s
        self.hi_distanz = 0.0         # > 5.5 m/s
        self.spitzentempo = 0.0

        self.am_ball = False
        self.aktion = None            # laufende Aktion (Schuss, Pass, Grtsche)
        self.aktion_bis = -99.0

    # ------------------------------------------------------------- Ableitungen
    @property
    def tempo(self):
        return math.hypot(self.v[0], self.v[1])

    def v_max_akt(self):
        """Spitzengeschwindigkeit unter aktueller Ermuedung."""
        a = self.attribute
        return a.v_max * (1.0 - K.MUEDIGKEIT_VMAX * (1.0 - self.energie))

    def a_max_akt(self):
        a = self.attribute
        return a.a_max * (1.0 - K.MUEDIGKEIT_AMAX * (1.0 - self.energie))

    def brems_akt(self):
        a = self.attribute
        return a.brems * (1.0 - 0.5 * K.MUEDIGKEIT_AMAX * (1.0 - self.energie))

    # ---------------------------------------------------------------- Steuerung
    def steuere(self, ziel, wunschtempo=None, blickziel=None):
        """Zielpunkt setzen. Die Physik im naechsten `schritt` folgt daraus."""
        self.ziel = ziel
        self.wunschtempo = self.v_max_akt() if wunschtempo is None else wunschtempo
        self.blickziel = blickziel

    def halte(self, blickziel=None):
        self.ziel = self.pos
        self.wunschtempo = 0.0
        self.blickziel = blickziel

    # ------------------------------------------------------------------ Physik
    def schritt(self, dt):
        """Ein Integrationsschritt: Wunschgeschwindigkeit -> Kraft -> Bewegung.

        Beschleunigung wird in eine Laengs- und eine Querkomponente relativ
        zur aktuellen Laufrichtung zerlegt. Das ist der Punkt, an dem
        Richtungswechsel teuer werden: quer steht deutlich weniger
        Beschleunigung zur Verfuegung als geradeaus, und dieser Anteil sinkt
        zusaetzlich mit dem Tempo. Ein 180-Grad-Wechsel im Sprint kostet
        dadurch von selbst rund eine Sekunde - ohne Sonderregel.
        """
        px, py = self.pos
        vx, vy = self.v
        tempo = math.hypot(vx, vy)
        v_max = self.v_max_akt()

        # Wunschgeschwindigkeit
        zx = self.ziel[0] - px
        zy = self.ziel[1] - py
        d = math.hypot(zx, zy)
        soll = min(self.wunschtempo, v_max)
        if d < 1e-6:
            sx = sy = 0.0
        else:
            # kurz vor dem Ziel abbremsen, statt darueber hinauszuschiessen
            brems_weg = tempo * tempo / (2.0 * max(self.brems_akt(), 0.1))
            if d < brems_weg:
                soll = min(soll, math.sqrt(2.0 * self.brems_akt() * d))
            sx = zx / d * soll
            sy = zy / d * soll

        dvx = sx - vx
        dvy = sy - vy

        if tempo > 0.15:
            ex, ey = vx / tempo, vy / tempo
        else:
            n = math.hypot(dvx, dvy)
            ex, ey = (dvx / n, dvy / n) if n > 1e-9 else (math.cos(self.blick),
                                                          math.sin(self.blick))

        dv_l = dvx * ex + dvy * ey
        dv_qx = dvx - dv_l * ex
        dv_qy = dvy - dv_l * ey

        a_l_max = (K.antrieb_bei_tempo(self.a_max_akt(), tempo, v_max)
                   if dv_l > 0.0 else self.brems_akt())
        a_q_max = K.querlimit_bei_tempo(self.attribute.quer, tempo, v_max)

        tau = 0.12                     # Regelhorizont
        a_l = M.klemme(dv_l / tau, -a_l_max, a_l_max)
        a_qx, a_qy = M.begrenzt((dv_qx / tau, dv_qy / tau), a_q_max)

        ax = a_l * ex + a_qx
        ay = a_l * ey + a_qy

        vx += ax * dt
        vy += ay * dt
        neu_tempo = math.hypot(vx, vy)
        if neu_tempo > v_max:
            f = v_max / neu_tempo
            vx *= f
            vy *= f
            neu_tempo = v_max

        px += vx * dt
        py += vy * dt
        # Spieler duerfen kurz ueber die Linie, aber nicht ins Nirgendwo
        px = M.klemme(px, -K.HALB_L - 3.0, K.HALB_L + 3.0)
        py = M.klemme(py, -K.HALB_B - 3.0, K.HALB_B + 3.0)

        self.pos = (px, py)
        self.v = (vx, vy)

        # Koerperorientierung
        if self.blickziel is not None:
            soll_w = math.atan2(self.blickziel[1] - py, self.blickziel[0] - px)
        elif neu_tempo > 0.4:
            soll_w = math.atan2(vy, vx)
        else:
            soll_w = self.blick
        max_dreh = self.attribute.drehrate * (1.0 - 0.5 * neu_tempo / max(v_max, 0.1)) * dt
        diff = M.winkel_diff(soll_w, self.blick)
        if abs(diff) <= max_dreh:
            self.blick = soll_w
        else:
            self.blick += math.copysign(max_dreh, diff)

        # Laufdaten
        s = neu_tempo * dt
        self.laufdistanz += s
        if neu_tempo > 5.5:
            self.hi_distanz += s
            if neu_tempo > 7.0:
                self.sprintdistanz += s
        if neu_tempo > self.spitzentempo:
            self.spitzentempo = neu_tempo

        # Energiehaushalt
        rel_v = neu_tempo / max(self.attribute.v_max, 0.1)
        rel_a = math.hypot(ax, ay) / max(self.attribute.a_max, 0.1)
        kapazitaet = 0.72 + 0.56 * self.attribute.ausdauer   # 0.72 .. 1.28
        verbrauch = (K.ENERGIE_TEMPO_K * rel_v ** 3
                     + K.ENERGIE_BESCHL_K * rel_a) / kapazitaet
        erholung = K.ENERGIE_ERHOLUNG * max(0.0, 1.0 - rel_v * 2.2)
        self.energie = M.klemme(self.energie + (erholung - verbrauch) * dt,
                                K.ENERGIE_MIN, 1.0)

    # ------------------------------------------------------- Wahrnehmungsmodell
    def reaktionszeit(self, ziel=None):
        """Latenz bis zur Handlung, erhoeht wenn das Ziel im Ruecken liegt.

        Koerperorientierung ist damit keine Kosmetik: ein Spieler, der zur
        eigenen Torlinie schaut, reagiert auf einen Ball hinter sich messbar
        spaeter - genau der Effekt, der hohe Abwehrlinien angreifbar macht.
        """
        t = self.attribute.reaktion * (1.0 + 0.35 * (1.0 - self.energie))
        if ziel is None:
            return t
        w = math.atan2(ziel[1] - self.pos[1], ziel[0] - self.pos[0])
        ab = abs(M.winkel_diff(w, self.blick))
        # 0 rad -> Faktor 1.0, pi rad -> Faktor 1.55
        return t * (1.0 + 0.55 * (ab / math.pi))

    def zeit_zu_punkt(self, ziel, mit_reaktion=True):
        """Ankunftszeit an einem Punkt unter Beruecksichtigung von Traegheit.

        Zweiphasenmodell: beschleunigen bis v_max, dann konstant. Dazu ein
        Aufschlag fuer den noetigen Richtungswechsel aus der aktuellen
        Laufrichtung. Das ist der Kern des Raumkontroll-Modells - wer schon
        in die richtige Richtung laeuft, ist naeher als die Luftlinie sagt.
        """
        dx = ziel[0] - self.pos[0]
        dy = ziel[1] - self.pos[1]
        d = math.hypot(dx, dy)
        t = self.reaktionszeit(ziel) if mit_reaktion else 0.0
        if d < 1e-6:
            return t

        v_max = self.v_max_akt()
        a = self.a_max_akt()
        tempo = math.hypot(self.v[0], self.v[1])

        # Anteil des aktuellen Tempos, der in die Zielrichtung zeigt
        if tempo > 0.15:
            proj = (self.v[0] * dx + self.v[1] * dy) / (tempo * d)
        else:
            proj = 0.0
        v0 = M.klemme(tempo * proj, -v_max, v_max)
        if v0 < 0.0:
            # zuerst abbremsen
            t += -v0 / max(self.brems_akt(), 0.1)
            v0 = 0.0

        # Strecke bis v_max
        d_beschl = (v_max * v_max - v0 * v0) / (2.0 * a)
        if d <= d_beschl:
            t += (-v0 + math.sqrt(v0 * v0 + 2.0 * a * d)) / a
        else:
            t += (v_max - v0) / a + (d - d_beschl) / v_max
        return t

    def kann_erreichen(self, ziel, zeit, mit_reaktion=True):
        return self.zeit_zu_punkt(ziel, mit_reaktion) <= zeit

    # ----------------------------------------------------------------- Sonstiges
    def zuruecksetzen_statistik(self):
        self.laufdistanz = 0.0
        self.sprintdistanz = 0.0
        self.hi_distanz = 0.0
        self.spitzentempo = 0.0

    def __repr__(self):
        return "<Spieler %s #%d %s>" % (self.name, self.nummer, self.rolle)
