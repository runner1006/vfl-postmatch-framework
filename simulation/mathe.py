"""Leichtgewichtige Vektor- und Hilfsmathematik.

Bewusst ohne numpy: die Engine laeuft im Kern auf einigen Millionen sehr
kleinen Operationen je Spiel. Fuer 2- und 3-Vektoren ist der numpy-Overhead
je Operation groesser als der Rechenweg selbst. Vektoren sind schlichte
Tupel `(x, y)` bzw. `(x, y, z)`, die Funktionen hier sind bewusst flach
gehalten und werden in den heissen Schleifen lokal gebunden.
"""
import math

# ------------------------------------------------------------------ 2D-Basis


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def skal(a, s):
    return (a[0] * s, a[1] * s)


def punkt(a, b):
    """Skalarprodukt."""
    return a[0] * b[0] + a[1] * b[1]


def kreuz(a, b):
    """Z-Komponente des Kreuzprodukts zweier 2-Vektoren."""
    return a[0] * b[1] - a[1] * b[0]


def betrag(a):
    return math.hypot(a[0], a[1])


def betrag2(a):
    """Quadrierter Betrag - spart die Wurzel in Distanzvergleichen."""
    return a[0] * a[0] + a[1] * a[1]


def abstand(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def abstand2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def normiert(a):
    m = math.hypot(a[0], a[1])
    if m < 1e-9:
        return (0.0, 0.0)
    return (a[0] / m, a[1] / m)


def begrenzt(a, maximum):
    """Vektor auf eine Maximallaenge stutzen, Richtung bleibt erhalten."""
    m = math.hypot(a[0], a[1])
    if m <= maximum or m < 1e-9:
        return a
    f = maximum / m
    return (a[0] * f, a[1] * f)


def winkel(a):
    return math.atan2(a[1], a[0])


def aus_winkel(w, laenge=1.0):
    return (math.cos(w) * laenge, math.sin(w) * laenge)


def winkel_diff(a, b):
    """Kleinste vorzeichenbehaftete Differenz zweier Winkel, in (-pi, pi]."""
    d = (a - b + math.pi) % (2.0 * math.pi) - math.pi
    return d


def klemme(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------- Kurvenformen

def logistisch(x, mitte=0.0, breite=1.0):
    """Logistik mit Wendepunkt `mitte`; `breite` ist die Skala in x-Einheiten."""
    z = (x - mitte) / breite
    if z > 40.0:
        return 1.0
    if z < -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def abklingend(d, skala):
    """Exponentieller Abfall auf [0,1], 1 bei d=0."""
    if skala <= 0.0:
        return 0.0
    return math.exp(-d / skala)


# ------------------------------------------------------- Geometrie am Feld

def punkt_auf_strecke(a, b, p):
    """Naechster Punkt auf der Strecke a-b zu p, samt Parameter t in [0,1]."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 < 1e-9:
        return a, 0.0
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return (a[0] + dx * t, a[1] + dy * t), t


def dreieck_winkel(p, a, b):
    """Winkel, unter dem die Strecke a-b von p aus erscheint (rad).

    Fuer den Torwinkel beim Abschluss: a und b sind die Pfosten.
    """
    va = (a[0] - p[0], a[1] - p[1])
    vb = (b[0] - p[0], b[1] - p[1])
    na = math.hypot(*va)
    nb = math.hypot(*vb)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    c = (va[0] * vb[0] + va[1] * vb[1]) / (na * nb)
    return math.acos(klemme(c, -1.0, 1.0))
