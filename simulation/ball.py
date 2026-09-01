"""Ballphysik: Flug, Rollen, Aufprall, Drall.

Der Ball ist ein eigener Koerper mit dreidimensionalem Zustand. Das ist kein
Selbstzweck: erst durch die Hoehe wird ein hoher Ball etwas anderes als ein
flacher Pass gleicher Laenge - er ist langsamer am Ziel, laesst dem Gegner
Zeit und ist nur mit dem Kopf zu verarbeiten. Genau diese Unterschiede
entscheiden im Modell darueber, ob eine hohe Abwehrlinie ueberspielt wird.

Modelliert:
  - Schwerkraft
  - quadratischer Luftwiderstand (a = -k |v| v)
  - Magnus-Effekt als Querbeschleunigung proportional zu Drall mal Tempo
  - Rollreibung am Boden
  - Aufprall mit getrennter Daempfung senkrecht und waagerecht

Nicht modelliert (bewusst): Widerstandskrise bei sehr hohen Geschwindigkeiten,
Nahtorientierung ("Knuckleball"), Windfeld, unebener Rasen.
"""
import math

import konfig as K


class Ball:
    __slots__ = ("pos", "v", "drall", "traeger", "letzter_traeger",
                 "letztes_team", "in_der_luft", "start_pos", "start_zeit")

    def __init__(self):
        self.pos = (0.0, 0.0, 0.0)      # x, y, z
        self.v = (0.0, 0.0, 0.0)
        self.drall = 0.0                # rad/s um die Hochachse, + = links herum
        self.traeger = None             # Spieler mit Ballkontrolle oder None
        self.letzter_traeger = None
        self.letztes_team = None
        self.in_der_luft = False
        self.start_pos = (0.0, 0.0)     # Ausgangspunkt der laufenden Aktion
        self.start_zeit = 0.0

    # ------------------------------------------------------------- Ableitungen
    @property
    def xy(self):
        return (self.pos[0], self.pos[1])

    @property
    def vxy(self):
        return (self.v[0], self.v[1])

    @property
    def tempo(self):
        return math.hypot(self.v[0], self.v[1])

    @property
    def liegt(self):
        return (not self.in_der_luft
                and self.tempo < K.BALL_RUHE_V
                and abs(self.v[2]) < K.BALL_RUHE_V)

    # -------------------------------------------------------------- Steuerung
    def setzen(self, xy, z=0.0):
        self.pos = (xy[0], xy[1], z)
        self.v = (0.0, 0.0, 0.0)
        self.drall = 0.0
        self.in_der_luft = z > 0.02

    def loesen(self, richtung_xy, tempo, steigung=0.0, drall=0.0,
               traeger=None, zeit=0.0):
        """Ball spielen: Richtung in der Ebene, Tempo, Abflugwinkel (rad).

        `steigung` = 0 ist ein Flachpass, 0.3 rad rund 17 Grad - die uebliche
        Groessenordnung fuer einen scharfen Chip ueber die Kette.
        """
        nx, ny = richtung_xy
        n = math.hypot(nx, ny)
        if n < 1e-9:
            nx, ny, n = 1.0, 0.0, 1.0
        nx /= n
        ny /= n
        vh = tempo * math.cos(steigung)
        vz = tempo * math.sin(steigung)
        self.v = (nx * vh, ny * vh, vz)
        self.drall = drall
        self.in_der_luft = vz > 0.05 or self.pos[2] > 0.05
        self.traeger = None
        if traeger is not None:
            self.letzter_traeger = traeger
            self.letztes_team = traeger.team
        self.start_pos = (self.pos[0], self.pos[1])
        self.start_zeit = zeit

    # ------------------------------------------------------------------ Physik
    def schritt(self, dt):
        x, y, z = self.pos
        vx, vy, vz = self.v
        tempo3 = math.sqrt(vx * vx + vy * vy + vz * vz)

        if z > 0.02 or vz > 0.02:
            # ---- Flugphase
            k = K.K_LUFT * tempo3
            ax = -k * vx
            ay = -k * vy
            az = -k * vz - K.G
            # Magnus: Querkraft senkrecht zur waagerechten Flugrichtung
            vh = math.hypot(vx, vy)
            if vh > 0.3 and abs(self.drall) > 0.05:
                m = K.K_MAGNUS * self.drall * vh
                ax += -vy / vh * m
                ay += vx / vh * m
            vx += ax * dt
            vy += ay * dt
            vz += az * dt
            x += vx * dt
            y += vy * dt
            z += vz * dt
            if z <= 0.0:
                # ---- Aufprall
                z = 0.0
                if vz < 0.0:
                    vz = -vz * K.AUFPRALL_Z
                    vx *= K.AUFPRALL_XY
                    vy *= K.AUFPRALL_XY
                    self.drall *= 0.6
                    if vz < 0.35:
                        vz = 0.0
            self.in_der_luft = z > 0.02 or vz > 0.02
        else:
            # ---- Rollphase
            z = 0.0
            vz = 0.0
            vh = math.hypot(vx, vy)
            if vh > 1e-6:
                # Rollreibung plus Luftwiderstand
                verz = K.ROLLREIBUNG * K.G + K.K_LUFT * vh * vh
                dv = verz * dt
                if dv >= vh:
                    vx = vy = 0.0
                else:
                    f = (vh - dv) / vh
                    vx *= f
                    vy *= f
                    # Drall zieht den rollenden Ball leicht seitwaerts
                    if abs(self.drall) > 0.05:
                        m = 0.35 * K.K_MAGNUS * self.drall * vh * dt
                        qx, qy = -vy / vh, vx / vh
                        vx += qx * m
                        vy += qy * m
            x += vx * dt
            y += vy * dt
            self.in_der_luft = False

        self.drall *= math.exp(-K.DRALL_ABKLINGEN * dt)
        self.pos = (x, y, z)
        self.v = (vx, vy, vz)

    # ------------------------------------------------ Vorhersage der Flugbahn
    def bahn(self, dauer, dt=None, kopie_von=None):
        """Positionen der naechsten `dauer` Sekunden vorausrechnen.

        Wird von der Entscheidungsschicht gebraucht: ein Verteidiger muss
        abschaetzen, wo der Ball sein wird, nicht wo er ist. Gibt Liste von
        (t, x, y, z) zurueck.
        """
        dt = dt or (K.DT * 2.0)
        schatten = Ball()
        schatten.pos = self.pos
        schatten.v = self.v
        schatten.drall = self.drall
        schatten.in_der_luft = self.in_der_luft
        out = []
        t = 0.0
        while t < dauer:
            schatten.schritt(dt)
            t += dt
            p = schatten.pos
            out.append((t, p[0], p[1], p[2]))
        return out


def flugbahn_vorschau(start_xy, richtung_xy, tempo, steigung, drall, dauer,
                      dt=None):
    """Bahn eines noch nicht gespielten Balls - fuer die Passbewertung.

    Erlaubt es, eine Passidee vollstaendig durchzurechnen, bevor der Ball
    ueberhaupt losgeht. Genau das macht ein Spieler beim Aufschauen auch.
    """
    b = Ball()
    b.setzen(start_xy, 0.06)
    b.loesen(richtung_xy, tempo, steigung, drall)
    return b.bahn(dauer, dt)


def ankunftszeit(strecke, tempo, flach=True):
    """Grobe Laufzeit eines Balls ueber eine Strecke, inkl. Abbremsen.

    Analytische Naeherung fuer den Flachpass (konstante Verzoegerung durch
    Rollreibung), damit die Passbewertung nicht fuer jede Option eine volle
    Integration braucht.
    """
    if tempo <= 0.05:
        return float("inf")
    if not flach:
        return strecke / max(tempo * 0.86, 0.05)
    # Effektive mittlere Verzoegerung: die Rollreibung ist konstant, der
    # Luftwiderstand faellt mit dem Tempo. Der Faktor 0.70 bildet den
    # Mittelwert ueber die Strecke ab; Abweichung zur vollen Integration
    # unter 5 % im ueblichen Passbereich (geprueft in tests.py).
    a = K.ROLLREIBUNG * K.G + 0.70 * K.K_LUFT * tempo * tempo
    # s = v t - 0.5 a t^2  ->  t = (v - sqrt(v^2 - 2 a s)) / a
    disk = tempo * tempo - 2.0 * a * strecke
    if disk <= 0.0:
        return float("inf")            # Ball bleibt vorher liegen
    return (tempo - math.sqrt(disk)) / a


def tempo_fuer_strecke(strecke, wunschzeit, flach=True):
    """Umkehrung: welches Abspieltempo braucht es fuer diese Ankunftszeit."""
    if wunschzeit <= 0.05:
        return K.PASS_MAX_V
    if not flach:
        return min(strecke / (wunschzeit * 0.86), K.PASS_MAX_V)
    # Iterativ, weil a von v abhaengt
    v = strecke / wunschzeit
    for _ in range(4):
        a = K.ROLLREIBUNG * K.G + 0.70 * K.K_LUFT * v * v
        v = strecke / wunschzeit + 0.5 * a * wunschzeit
        if v > K.PASS_MAX_V:
            return K.PASS_MAX_V
    return v
