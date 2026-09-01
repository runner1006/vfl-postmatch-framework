"""Feldmasse, Physikkonstanten und Simulationsparameter.

Koordinatensystem
-----------------
Ursprung im Mittelpunkt. x laeuft entlang der Laengsachse in [-52.5, +52.5],
y entlang der Querachse in [-34, +34], z ist die Hoehe. Heimteam
(`richtung = +1`) greift Richtung +x an, Gastteam (`richtung = -1`) Richtung
-x. Seitenwechsel zur Halbzeit ist damit ein Vorzeichenwechsel, kein Umbau.

Alle Groessen in SI: Meter, Sekunden, Kilogramm, Radiant.

Kalibrierung
------------
Die Werte hier sind Modellparameter, keine Messwerte. Physikalische
Konstanten (Schwerkraft, Luftdichte, Ballmasse) sind gesetzt; alles was
Verhalten steuert, ist auf plausible Aggregatgroessen eines Profispiels
justiert (Passzahl, Schussrate, Laufdistanz, Spitzengeschwindigkeit) und in
`tests.py` gegen Erwartungsbaender geprueft. Wer die Engine an eigene
Tracking-Daten anpasst, aendert hier - nicht in der Logik.
"""
import math

# ------------------------------------------------------------------ Spielfeld
FELD_LAENGE = 105.0
FELD_BREITE = 68.0
HALB_L = FELD_LAENGE / 2.0          # 52.5
HALB_B = FELD_BREITE / 2.0          # 34.0

TOR_HALB_BREITE = 3.66              # 7.32 m Torbreite
TOR_HOEHE = 2.44
STRAFRAUM_TIEFE = 16.5
STRAFRAUM_HALB_BREITE = 20.16
TORRAUM_TIEFE = 5.5
TORRAUM_HALB_BREITE = 9.16
ELFMETER_ABSTAND = 11.0
ANSTOSSKREIS = 9.15                 # zugleich Mindestabstand bei Standards

# ---------------------------------------------------------------- Zeitschritt
DT = 0.04                           # 25 Hz, entspricht der Rate ueblicher
                                    # optischer Tracking-Systeme
HALBZEIT_SEKUNDEN = 45.0 * 60.0

# ------------------------------------------------------------------ Ballphysik
G = 9.81
BALL_MASSE = 0.43
BALL_RADIUS = 0.11
LUFTDICHTE = 1.225
CW = 0.25                           # Widerstandsbeiwert im ueblichen
                                    # Geschwindigkeitsbereich; die
                                    # Widerstandskrise wird nicht modelliert
BALL_QUERSCHNITT = math.pi * BALL_RADIUS ** 2
# a_luft = -K_LUFT * |v| * v  ->  bei 30 m/s rund 12 m/s^2 Verzoegerung
K_LUFT = 0.5 * LUFTDICHTE * CW * BALL_QUERSCHNITT / BALL_MASSE
ROLLREIBUNG = 0.052                 # -> rund 0.51 m/s^2 auf Rasen
K_MAGNUS = 0.0033                   # a_quer = K_MAGNUS * drall * |v|
DRALL_ABKLINGEN = 0.22              # 1/s, exponentiell
AUFPRALL_Z = 0.55                   # Restitution senkrecht
AUFPRALL_XY = 0.78                  # Daempfung waagerecht je Aufprall
BALL_RUHE_V = 0.12                  # darunter gilt der Ball als liegend

# -------------------------------------------------------------- Spielerphysik
# Grundwerte eines "durchschnittlichen" Profis. Die Attribute je Spieler
# skalieren diese Werte (siehe spieler.Attribute).
BASIS_VMAX = 8.4                     # m/s Spitzengeschwindigkeit
BASIS_AMAX = 10.0                   # m/s^2 Antritt aus dem Stand
BASIS_BREMS = 8.6                   # m/s^2 Verzoegerung
BASIS_QUER = 7.2                    # m/s^2 Querbeschleunigung (Richtungswechsel)
BASIS_REAKTION = 0.22               # s Wahrnehmungs- und Reaktionslatenz
BASIS_DREHRATE = 8.0                # rad/s Koerperdrehung im Stand

# Kraft-Geschwindigkeits-Beziehung: bei v = vmax bleibt keine
# Laengsbeschleunigung mehr uebrig.
def antrieb_bei_tempo(a_max, tempo, v_max):
    """Verfuegbare Laengsbeschleunigung bei aktuellem Tempo."""
    if v_max <= 0.0:
        return 0.0
    rest = 1.0 - tempo / v_max
    return a_max * rest if rest > 0.0 else 0.0


# Querbeschleunigung faellt mit dem Tempo: enge Richtungswechsel gehen im
# Sprint nicht mehr.
def querlimit_bei_tempo(a_quer, tempo, v_max):
    if v_max <= 0.0:
        return 0.0
    f = 1.0 - 0.55 * (tempo / v_max) ** 2
    return a_quer * (f if f > 0.15 else 0.15)


# --------------------------------------------------------------- Ausdauer
# Energiehaushalt auf [0,1]. Der Verbrauch waechst ueberproportional mit dem
# Tempo (Sprints kosten deutlich mehr als Traben) und zusaetzlich mit
# Beschleunigungsarbeit. Kalibriert auf: rund 10-11 km Laufdistanz und ein
# Endstand um 0.6 bei mittlerer Ausdauer.
ENERGIE_TEMPO_K = 0.00195           # je s bei tempo = vmax
ENERGIE_BESCHL_K = 0.00042          # je s bei |a| = amax
ENERGIE_ERHOLUNG = 0.00060          # je s in Ruhe
ENERGIE_MIN = 0.45
# Auswirkung: bei leerer Energie bleiben 80 % von vmax und 72 % von amax.
MUEDIGKEIT_VMAX = 0.20
MUEDIGKEIT_AMAX = 0.28

# ------------------------------------------------------------ Ballkontrolle
KONTROLL_RADIUS = 0.85              # Ballradius, in dem ein Spieler den Ball
                                    # annehmen/fuehren kann
KONTROLL_HOEHE = 1.05               # darueber nur Kopfball
KOPFBALL_HOEHE = 2.35
DRIBBEL_ABSTAND = 1.05              # Fuehrungsabstand vor dem Fuss
BERUEHRUNG_TAKT = 0.42              # s zwischen zwei Ballfuehrungskontakten
ZWEIKAMPF_RADIUS = 2.00              # Reichweite eines Tacklings inkl. Ausfallschritt
                                    # MUSS groesser sein als der Stellabstand des
                                    # Pressers in taktik.pressziel - sonst kann ein
                                    # Presser den Ball grundsaetzlich nicht erobern
SCHUSS_MAX_V = 32.0                 # m/s bei maximalem Abschlusswert
PASS_MAX_V = 26.0

# ------------------------------------------------------------ Entscheidungen
ENTSCHEIDUNGSTAKT = 0.18            # s zwischen zwei Neubewertungen am Ball
LAUFTAKT = 0.24                     # s zwischen zwei Zielneuberechnungen ohne Ball
TAKT_JITTER = 0.06                  # Streuung darauf, damit nicht alle Agenten
                                    # im selben Frame denken

# -------------------------------------------------------------------- Regeln
ABSEITS_TOLERANZ = 0.20             # m Unschaerfe der Abseitslinie
FOUL_BASIS = 0.026                  # Grundwahrscheinlichkeit je verlorenem
                                    # Zweikampf, dass er als Foul endet
FOUL_STRAFRAUM = 0.40               # Im eigenen Strafraum wird deutlich
                                    # vorsichtiger verteidigt - ohne diesen
                                    # Faktor faellt in jedem Spiel ein
                                    # gutes Dutzend Elfmeter
PENALTY_XG = 0.76                   # identisch zum Analyse-Framework
STANDARD_ABSTAND = ANSTOSSKREIS

# ---------------------------------------------------------------- Torhueter
TW_LINIE_TIEFE = 1.2                # Ruheposition vor der Torlinie
TW_MAX_AUSFLUG = 30.0               # m vom Tor beim Herauslaufen
TW_REAKTION = 0.18
TW_REICHWEITE = 2.55                # m Spannweite beim Hechten
TW_ABSTOSS_V = 24.0
