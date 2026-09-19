"""Datenschicht: Spiele aus openfootball-Textdateien, Vereine vereinheitlicht.

Quelle ist das Projekt openfootball/deutschland (CC0): ein Klartextformat je
Saison und Liga, in zwei Schreibweisen, die hier beide gelesen werden:

    20:30  Borussia Dortmund       v Bayer 04 Leverkusen      2-3 (0-2)
    20:30  FC Bayern München        8-0 (3-0)  FC Schalke 04

Datumszeilen tragen das Jahr nur beim ersten Auftreten ("Fri Aug 23 2024",
danach "Sat Aug 24"); das Jahr folgt aus der Saison (Juli bis Dezember Startjahr,
sonst Folgejahr), weil Nachholspiele nicht chronologisch in der Datei stehen.
Spiele ohne Ergebnis (noch nicht gespielt) bleiben als offene Paarungen
erhalten - das sind die, fuer die `vorhersage --naechste` rechnet.

Vereinsnamen wechseln zwischen Saisons ("Bayern München", "FC Bayern München",
"1899 Hoffenheim", "TSG 1899 Hoffenheim", "Heidenheim" ...). Ein Schluessel
ohne Vereinsformen und Gruendungsjahre fuehrt sie zusammen; die Pruefung, dass
je Saison und Liga genau 18 verschiedene Vereine auftreten, sichert das ab.
"""
import datetime as dt
import os
import re

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
DATEN = os.path.join(WURZEL, "daten", "openfootball")

LIGEN = {"1-bundesliga.txt": 1, "2-bundesliga2.txt": 2}
LIGA_NAMEN = {1: "Bundesliga", 2: "2. Bundesliga"}
KLASSEN = ["Heimsieg", "Unentschieden", "Auswaertssieg"]

_MONATE = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
_DATUM = re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_RUNDE = re.compile(r"^\s*[▪»]\s*(?:Matchday|Regular Season -|Round)?\s*(\d+)")
_RUNDE2 = re.compile(r"^\s*[▪»]\s*(\d+)\.\s*Round")
_ZEIT = r"(?:\d{1,2}[.:]\d{2}\s+)?"
_FORM_A = re.compile(r"^\s*" + _ZEIT + r"(.+?)\s+v\s+(.+?)(?:\s{2,}(\d+)-(\d+)(?:\s*\([^)]*\))?)?\s*(\[[^\]]*\])?\s*$")
_FORM_B = re.compile(r"^\s*" + _ZEIT + r"(.+?)\s{2,}(\d+)-(\d+)(?:\s*\([^)]*\))?\s{2,}(.+?)\s*(\[[^\]]*\])?\s*$")

_FUELLWOERTER = {"fc", "1.", "fsv", "sv", "vfl", "vfb", "vfr", "tsg", "tsv", "sc", "spvgg",
                 "ssv", "msv", "bor.", "borussia", "1846", "1848", "1899", "1903", "1910",
                 "04", "05", "07", "96", "98"}


def schluessel(name):
    """Vereinsschluessel ohne Vereinsform und Gruendungsjahr."""
    n = name.strip().lower().replace("m'gladbach", "mönchengladbach")
    teile = [t for t in n.split() if t not in _FUELLWOERTER]
    return " ".join(teile) or n


class Spiel:
    __slots__ = ("id", "saison", "liga", "spieltag", "datum", "heim", "gast",
                 "heim_name", "gast_name", "tore_heim", "tore_gast", "hinweis")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def gespielt(self):
        return self.tore_heim is not None

    @property
    def ergebnis(self):
        """0 Heimsieg, 1 Unentschieden, 2 Auswaertssieg; None wenn offen."""
        if not self.gespielt:
            return None
        return 0 if self.tore_heim > self.tore_gast else (1 if self.tore_heim == self.tore_gast else 2)

    def als_dict(self):
        d = {k: getattr(self, k) for k in self.__slots__}
        d["datum"] = self.datum.isoformat()
        d["ergebnis"] = self.ergebnis
        return d


def _saison_von_pfad(pfad):
    return os.path.basename(os.path.dirname(pfad))  # "2024-25"


def lese_datei(pfad, liga=None, saison=None):
    """Alle Spiele einer Datei, in Dateireihenfolge."""
    liga = liga if liga is not None else LIGEN.get(os.path.basename(pfad), 0)
    saison = saison or _saison_von_pfad(pfad)
    spiele, datum, spieltag = [], None, None
    startjahr = int(saison[:4])
    with open(pfad, encoding="utf-8") as f:
        for roh in f:
            zeile = roh.rstrip("\r\n")
            s = zeile.strip()
            if not s or s.startswith("#") or s.startswith("=") or s.startswith("("):
                continue
            m = _RUNDE2.match(zeile) or _RUNDE.match(zeile)
            if m:
                spieltag = int(m.group(1))
                continue
            m = _DATUM.match(zeile)
            if m:
                monat, tag = _MONATE[m.group(1)], int(m.group(2))
                # Das Jahr folgt aus der Saison: Juli-Dezember Startjahr, sonst Folgejahr.
                # Nachholspiele stehen in der Datei nicht chronologisch, darum keine
                # Ableitung aus der Reihenfolge der Datumszeilen.
                jahr = int(m.group(3)) if m.group(3) else (startjahr if monat >= 7 else startjahr + 1)
                datum = dt.date(jahr, monat, tag)
                continue
            if re.search(r"\s+v\s+", zeile):
                m = _FORM_A.match(zeile)
                if not m:
                    continue
                heim, gast, th, tg, hinweis = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            else:
                m = _FORM_B.match(zeile)
                if not m or m.group(4).startswith("["):
                    continue
                heim, th, tg, gast, hinweis = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            heim, gast = heim.strip(), gast.strip()
            if not heim or not gast or datum is None:
                continue
            spiele.append(Spiel(
                saison=saison, liga=liga, spieltag=spieltag, datum=datum,
                heim=schluessel(heim), gast=schluessel(gast), heim_name=heim, gast_name=gast,
                tore_heim=int(th) if th is not None else None,
                tore_gast=int(tg) if tg is not None else None,
                hinweis=(hinweis or "").strip("[] ") or None))
    return spiele


def lade_spiele(verzeichnis=None, ligen=(1, 2)):
    """Alle Spiele aller Saisons, chronologisch, mit fortlaufender ID."""
    verzeichnis = verzeichnis or DATEN
    spiele = []
    for saison in sorted(os.listdir(verzeichnis)):
        ordner = os.path.join(verzeichnis, saison)
        if not os.path.isdir(ordner):
            continue
        for datei, liga in LIGEN.items():
            if liga not in ligen:
                continue
            pfad = os.path.join(ordner, datei)
            if os.path.exists(pfad):
                spiele.extend(lese_datei(pfad, liga, saison))
    spiele.sort(key=lambda s: (s.datum, s.liga, s.spieltag or 0, s.heim))
    for i, s in enumerate(spiele):
        s.id = i + 1
    return spiele


def anzeigenamen(spiele):
    """Schluessel -> Originalname aus der juengsten Saison (fuer Ausgaben)."""
    namen = {}
    for s in spiele:  # chronologisch, der letzte gewinnt
        namen[s.heim] = s.heim_name
        namen[s.gast] = s.gast_name
    return namen


def pruefe_konsistenz(spiele):
    """Je Saison und Liga 18 Vereine und hoechstens 306 Spiele - sonst Fehlerliste."""
    fehler = []
    gruppen = {}
    for s in spiele:
        g = gruppen.setdefault((s.saison, s.liga), {"vereine": set(), "n": 0})
        g["vereine"].update((s.heim, s.gast))
        g["n"] += 1
    for (saison, liga), g in sorted(gruppen.items()):
        if len(g["vereine"]) != 18:
            fehler.append("%s Liga %d: %d Vereine statt 18: %s" % (saison, liga, len(g["vereine"]), sorted(g["vereine"])))
        if g["n"] > 306:
            fehler.append("%s Liga %d: %d Spiele (> 306)" % (saison, liga, g["n"]))
    return fehler


def saisons(spiele):
    return sorted({s.saison for s in spiele})
