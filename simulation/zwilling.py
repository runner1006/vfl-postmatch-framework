"""Digital Twin: von realen Messwerten zum Agentenprofil.

Das ist die Nahtstelle zwischen dem Analyseteil des Repositorys und der
Simulation. Sie hat genau eine Aufgabe: aus dem, was ueber einen Spieler
messbar ist, ein `spieler.Attribute` zu machen - und dabei sichtbar zu lassen,
welcher Teil des Profils gemessen und welcher gesetzt ist.

Drei Wege hinein:

`aus_perzentilen`  fuer Ligaperzentile (0..1) je Messgroesse
`aus_noten`        fuer Scoutingnoten 1-5, wie sie das Scout-League-Modul
                   dieses Repositorys erzeugt
`aus_messwerten`   fuer direkt gemessene physische Groessen (Tracking)

Was hier ehrlich bleiben muss
-----------------------------
Vier Attribute - Entscheidung, Uebersicht, Positionsspiel und mit Abstrichen
Antizipation - sind aus aggregierten Ereignisdaten **nicht identifizierbar**.
Ein Spieler mit vielen Fehlpaessen kann schlecht entscheiden oder in einer
Mannschaft spielen, die ihm keine Anspielstationen gibt. Diese Attribute
bleiben deshalb ohne Scoutingurteil auf 0.5, und jedes erzeugte Profil traegt
in `herkunft` mit, welche Werte gemessen und welche gesetzt sind. Wer diese
Unterscheidung wegwirft, bekommt eine Simulation, die Praezision vortaeuscht.
"""
import json
import os
import random

import mathe as M
import spieler as SP
import taktik as T

_PFAD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "kalibrierung.json")
with open(_PFAD, encoding="utf-8") as _f:
    KALIBRIERUNG = json.load(_f)

PHYSISCH = KALIBRIERUNG["physisch"]
PROFILE = KALIBRIERUNG["positionsprofile"]
KOGNITIV_UNBESTIMMT = ("entscheidung", "uebersicht", "positionsspiel")


def _perzentil_auf_wert(p, anker):
    """Stueckweise lineare Abbildung eines Perzentils auf einen Messwert."""
    p = M.klemme(p, 0.0, 1.0)
    p05, p50, p95 = anker["p05"], anker["p50"], anker["p95"]
    if p <= 0.05:
        return p05 + (p05 - p50) * (0.05 - p) / 0.45
    if p <= 0.50:
        return p05 + (p50 - p05) * (p - 0.05) / 0.45
    if p <= 0.95:
        return p50 + (p95 - p50) * (p - 0.50) / 0.45
    return p95 + (p95 - p50) * (p - 0.95) / 0.45


class Profil:
    """Attributsatz samt Herkunftsvermerk je Attribut."""

    def __init__(self, attribute, herkunft, name=None, position=None):
        self.attribute = attribute
        self.herkunft = herkunft          # attribut -> "gemessen"|"abgeleitet"|"gesetzt"
        self.name = name
        self.position = position

    def anteil_gemessen(self):
        n = len(self.herkunft)
        if not n:
            return 0.0
        return sum(1 for v in self.herkunft.values() if v == "gemessen") / n

    def bericht(self):
        return {
            "name": self.name,
            "position": self.position,
            "anteil_gemessen": round(self.anteil_gemessen(), 3),
            "gesetzt": sorted(k for k, v in self.herkunft.items() if v == "gesetzt"),
            "attribute": {k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in self.attribute.als_dict().items()},
        }


def _positionsversatz(position, attribute):
    versatz = PROFILE.get(position, {})
    for name, d in versatz.items():
        if name in ("v_max", "a_max", "brems", "quer"):
            # physische Werte: Versatz in Standardabweichungen der Ligaverteilung
            anker = PHYSISCH.get(name)
            if anker:
                spanne = (anker["p95"] - anker["p05"]) / 3.29   # p05..p95 = 3.29 sd
                setattr(attribute, name, getattr(attribute, name) + d * spanne)
        else:
            setattr(attribute, name, M.klemme(getattr(attribute, name) + d, 0.02, 0.99))
    return attribute


def aus_perzentilen(perzentile, position="ZM", name=None):
    """Profil aus Ligaperzentilen je Messgroesse (0..1).

    Bekannte Schluessel sind alle Attributnamen. Was fehlt, bleibt auf dem
    Positionsdurchschnitt und wird als `gesetzt` vermerkt.
    """
    attribute = SP.Attribute()
    herkunft = {}
    for name_attr in SP.Attribute.__slots__:
        if name_attr in perzentile:
            p = perzentile[name_attr]
            if name_attr in PHYSISCH:
                setattr(attribute, name_attr, _perzentil_auf_wert(p, PHYSISCH[name_attr]))
            else:
                setattr(attribute, name_attr, M.klemme(p, 0.02, 0.99))
            herkunft[name_attr] = ("gemessen" if name_attr not in KOGNITIV_UNBESTIMMT
                                   else "abgeleitet")
        else:
            herkunft[name_attr] = "gesetzt"
    _positionsversatz(position, attribute)
    return Profil(attribute, herkunft, name, position)


def aus_noten(noten, position="ZM", name=None):
    """Profil aus Scoutingnoten 1-5 (5 = bestmoeglich).

    Passt zum Notenschema des Scout-League-Moduls in diesem Repository. Die
    Abbildung ist bewusst linear: Note 3 entspricht dem Ligadurchschnitt
    (Perzentil 0.5), Note 5 dem Perzentil 0.95, Note 1 dem Perzentil 0.05.
    """
    perzentile = {}
    for k, v in noten.items():
        p = M.klemme(0.05 + (float(v) - 1.0) / 4.0 * 0.90, 0.02, 0.98)
        perzentile[k] = p
    profil = aus_perzentilen(perzentile, position, name)
    for k in noten:
        if k in profil.herkunft:
            profil.herkunft[k] = "abgeleitet"
    return profil


def aus_messwerten(messwerte, perzentile=None, position="ZM", name=None):
    """Profil mit direkt gemessenen physischen Groessen.

    `messwerte` traegt SI-Werte (z. B. `v_max` in m/s aus dem Tracking),
    `perzentile` den Rest. Direkt Gemessenes hat Vorrang.
    """
    profil = aus_perzentilen(perzentile or {}, position, name)
    for k, v in messwerte.items():
        if k not in SP.Attribute.__slots__:
            raise KeyError("unbekanntes Attribut %r" % k)
        setattr(profil.attribute, k, float(v))
        profil.herkunft[k] = "gemessen"
    return profil


# ------------------------------------------------------------ Kaderaufbau
def spieler_aus_profil(profil, nummer, rolle, name=None, torwart=False):
    return SP.Spieler(name or profil.name or "Nr. %d" % nummer, nummer, 0,
                      rolle, profil.attribute, ist_torwart=torwart)


def elf_bauen(formation="4-2-3-1", stufe=0.5, streuung=0.10, seed=0,
              praefix="", namen=None):
    """Synthetische Elf auf einem gewuenschten Niveau.

    `stufe` verschiebt alle Attribute (0.5 = Ligadurchschnitt), `streuung`
    ist die Standardabweichung zwischen den Spielern. Fuer Testlaeufe und als
    Gegner, wenn nur eine Mannschaft als Digital Twin vorliegt.
    """
    rng = random.Random(seed)
    form = T.formation_bauen(formation)
    elf = []
    for i, (rolle, bx, by) in enumerate(form):
        perz = {}
        for attr in ("v_max", "a_max", "brems", "quer", "reaktion", "drehrate",
                     "ausdauer", "passgenauigkeit", "passtempo",
                     "erste_beruehrung", "dribbling", "abschluss", "zweikampf",
                     "kopfball", "antizipation", "aggressivitaet",
                     "risikofreude"):
            perz[attr] = M.klemme(rng.gauss(stufe, streuung), 0.03, 0.97)
        profil = aus_perzentilen(perz, rolle)
        name = (namen[i] if namen and i < len(namen)
                else "%s%s%d" % (praefix, rolle, i + 1))
        elf.append(SP.Spieler(name, i + 1, 0, rolle, profil.attribute,
                              ist_torwart=(rolle == "TW")))
    return elf


def elf_aus_profilen(profile, formation="4-2-3-1"):
    """Elf aus einer geordneten Liste von `Profil` - Reihenfolge = Formation."""
    form = T.formation_bauen(formation)
    if len(profile) != 11:
        raise ValueError("es braucht genau 11 Profile, nicht %d" % len(profile))
    elf = []
    for i, (p, (rolle, bx, by)) in enumerate(zip(profile, form)):
        elf.append(SP.Spieler(p.name or "Nr. %d" % (i + 1), i + 1, 0, rolle,
                              p.attribute, ist_torwart=(rolle == "TW")))
    return elf


def profil_bericht(elf):
    """Uebersicht, wie viel eines Kaders gemessen und wie viel gesetzt ist."""
    return [dict(nummer=s.nummer, name=s.name, rolle=s.rolle,
                 v_max=round(s.attribute.v_max, 2),
                 ausdauer=round(s.attribute.ausdauer, 2))
            for s in elf]
