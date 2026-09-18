"""Lernaufgaben: aus Spielen und Merkmalen werden Tabellen mit Labels.

  ergebnis   Heimsieg / Unentschieden / Auswaertssieg - die klassische Frage.
  tore       unter / ueber 2,5 Tore - dieselben Merkmale, anderes Label.

Beide Aufgaben teilen sich die Merkmalstabelle; sie wird einmal gerechnet.
Offene Spiele (ohne Ergebnis) sind keine Lernzeilen, bekommen aber Merkmale
und stehen fuer Vorhersagen bereit.
"""
import math

from . import merkmale as mk
from .daten import KLASSEN, anzeigenamen, lade_spiele, saisons

AUFGABEN = ("ergebnis", "tore")
KLASSEN_JE_AUFGABE = {"ergebnis": list(KLASSEN), "tore": ["unter 2,5", "ueber 2,5"]}
FRAGE = {
    "ergebnis": "Wie wahrscheinlich sind Heimsieg, Unentschieden und Auswaertssieg - "
                "vor dem Anpfiff, nur aus Ergebnissen frueherer Spiele?",
    "tore": "Wie wahrscheinlich fallen in einem Spiel mehr als 2,5 Tore?",
}


class Tabelle:
    def __init__(self, aufgabe, zeilen, offen, merkmale, beschreibung, klassen, frage, namen):
        self.aufgabe = aufgabe
        self.zeilen = zeilen            # gespielte Spiele mit Label
        self.offen = offen              # offene Spiele mit Merkmalen, ohne Label
        self.merkmale = merkmale
        self.beschreibung = beschreibung
        self.klassen = klassen
        self.frage = frage
        self.namen = namen              # Vereinsschluessel -> Anzeigename
        self.benchmark = {}             # wird von bewertung.benchmarks() gefuellt

    def __len__(self):
        return len(self.zeilen)

    def labels(self):
        return [z["label"] for z in self.zeilen]

    def saisons(self):
        return sorted({z["gruppe"] for z in self.zeilen})

    def statistik(self):
        out = {}
        for m in self.merkmale:
            werte = [z["merkmale"][m] for z in self.zeilen if z["merkmale"][m] is not None]
            n = len(werte)
            if n == 0:
                out[m] = {"mittel": None, "sd": None, "fehlt": 1.0}
                continue
            mu = sum(werte) / n
            sd = math.sqrt(sum((v - mu) ** 2 for v in werte) / max(n - 1, 1))
            out[m] = {"mittel": mu, "sd": sd, "fehlt": 1 - n / len(self.zeilen)}
        return out


_CACHE = {}


def _grundlage(verzeichnis=None):
    """Spiele + Merkmale, einmal gerechnet und zwischengespeichert."""
    key = verzeichnis or "standard"
    if key not in _CACHE:
        spiele = lade_spiele(verzeichnis)
        _CACHE[key] = (spiele, mk.berechne(spiele), anzeigenamen(spiele))
    return _CACHE[key]


def label(aufgabe, spiel):
    if aufgabe == "ergebnis":
        return spiel.ergebnis
    if aufgabe == "tore":
        return 1 if spiel.tore_heim + spiel.tore_gast >= 3 else 0
    raise ValueError("unbekannte Aufgabe %r (erlaubt: %s)" % (aufgabe, ", ".join(AUFGABEN)))


def _zeile(spiel, m, namen, aufgabe):
    return {"id": spiel.id, "gruppe": spiel.saison, "zeit": (spiel.datum.isoformat(), spiel.id),
            "label": label(aufgabe, spiel) if spiel.gespielt else None, "merkmale": m,
            "extra": {"heim": namen.get(spiel.heim, spiel.heim), "gast": namen.get(spiel.gast, spiel.gast),
                      "heim_key": spiel.heim, "gast_key": spiel.gast,
                      "datum": spiel.datum.isoformat(), "liga": spiel.liga, "spieltag": spiel.spieltag,
                      "tore": (spiel.tore_heim, spiel.tore_gast) if spiel.gespielt else None}}


def lade(aufgabe, verzeichnis=None):
    if aufgabe not in AUFGABEN:
        raise ValueError("unbekannte Aufgabe %r (erlaubt: %s)" % (aufgabe, ", ".join(AUFGABEN)))
    spiele, M, namen = _grundlage(verzeichnis)
    zeilen, offen = [], []
    for s, m in zip(spiele, M):
        z = _zeile(s, m, namen, aufgabe)
        (zeilen if s.gespielt else offen).append(z)
    return Tabelle(aufgabe, zeilen, offen, list(mk.MERKMALE), dict(mk.BESCHREIBUNG),
                   KLASSEN_JE_AUFGABE[aufgabe], FRAGE[aufgabe], namen)


def katalog(tabelle):
    """Merkmalskatalog als Text - was der Forscher ueber die Daten weiss."""
    stat = tabelle.statistik()
    zeilen = ["Merkmal | Bedeutung | Mittel | SD | fehlt"]
    for m in tabelle.merkmale:
        s = stat[m]
        if s["mittel"] is None:
            zeilen.append("%s | %s | - | - | 100%%" % (m, tabelle.beschreibung.get(m, "")))
        else:
            zeilen.append("%s | %s | %.3g | %.3g | %.0f%%" % (
                m, tabelle.beschreibung.get(m, ""), s["mittel"], s["sd"], 100 * s["fehlt"]))
    return "\n".join(zeilen)


def naechste_spiele(tabelle, ab_datum=None, limit=None):
    """Offene Spiele ab einem Datum (Standard: ab dem letzten gespielten Tag)."""
    if ab_datum is None:
        ab_datum = max(z["extra"]["datum"] for z in tabelle.zeilen) if tabelle.zeilen else "0000"
    offen = [z for z in tabelle.offen if z["extra"]["datum"] >= ab_datum]
    offen.sort(key=lambda z: z["zeit"])
    return offen[:limit] if limit else offen
