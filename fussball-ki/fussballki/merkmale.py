"""Merkmalsmaschine: aus nackten Ergebnissen leckfreie Vorab-Merkmale.

Die Spiele werden chronologisch durchlaufen. Fuer jedes Spiel entstehen die
Merkmale ausschliesslich aus dem Zustand VOR dem Anpfiff (Elo, Form, Saison-
stand, Ruhetage, direkte Duelle, Vorsaison); erst danach wird der Zustand mit
dem Ergebnis fortgeschrieben. Offene Spiele bekommen ebenfalls Merkmale, aber
kein Label - das sind die Paarungen fuer `vorhersage --naechste`.

Alle Merkmale sind aus Heimsicht benannt (heim / gast / diff = heim - gast).
Fehlende Werte (erstes Spiel eines Vereins, kein Vorsaisonplatz) sind None.
"""
import datetime as dt
import math

from .daten import KLASSEN

ELO_START = {1: 1500.0, 2: 1400.0}
ELO_K = 20.0
ELO_HEIMVORTEIL = 65.0
RUHETAGE_MAX = 30

BESCHREIBUNG = {
    "liga": "Liga (1 = Bundesliga, 2 = 2. Bundesliga)",
    "spieltag": "Spieltag (1-34)",
    "saison_fortschritt": "Spieltag / 34",
    "elo_heim": "Elo des Heimteams vor dem Spiel (Start 1500 / 1400, K = 20, Tordifferenz gewichtet)",
    "elo_gast": "Elo des Gastteams vor dem Spiel",
    "elo_diff": "elo_heim - elo_gast",
    "elo_erwartung": "erwarteter Punktanteil des Heimteams aus Elo inkl. 65 Punkten Heimvorteil (0-1)",
    "form5_punkte_heim": "Heimteam: Punkte je Spiel in den letzten 5 Spielen (alle Wettbewerbe der Daten)",
    "form5_punkte_gast": "Gastteam: Punkte je Spiel in den letzten 5 Spielen",
    "form5_punkte_diff": "form5_punkte_heim - form5_punkte_gast",
    "form10_punkte_heim": "Heimteam: Punkte je Spiel in den letzten 10 Spielen",
    "form10_punkte_gast": "Gastteam: Punkte je Spiel in den letzten 10 Spielen",
    "form10_punkte_diff": "form10_punkte_heim - form10_punkte_gast",
    "form5_tordiff_heim": "Heimteam: Tordifferenz je Spiel in den letzten 5 Spielen",
    "form5_tordiff_gast": "Gastteam: Tordifferenz je Spiel in den letzten 5 Spielen",
    "form10_tordiff_heim": "Heimteam: Tordifferenz je Spiel in den letzten 10 Spielen",
    "form10_tordiff_gast": "Gastteam: Tordifferenz je Spiel in den letzten 10 Spielen",
    "form5_tore_heim": "Heimteam: erzielte Tore je Spiel, letzte 5",
    "form5_gegentore_heim": "Heimteam: Gegentore je Spiel, letzte 5",
    "form5_tore_gast": "Gastteam: erzielte Tore je Spiel, letzte 5",
    "form5_gegentore_gast": "Gastteam: Gegentore je Spiel, letzte 5",
    "heimform5_punkte_heim": "Heimteam: Punkte je Spiel in den letzten 5 Heimspielen",
    "auswform5_punkte_gast": "Gastteam: Punkte je Spiel in den letzten 5 Auswaertsspielen",
    "saison_ppg_heim": "Heimteam: Punkte je Spiel in der laufenden Saison (None am 1. Spieltag)",
    "saison_ppg_gast": "Gastteam: Punkte je Spiel in der laufenden Saison",
    "saison_ppg_diff": "saison_ppg_heim - saison_ppg_gast",
    "saison_tordiff_heim": "Heimteam: Tordifferenz je Spiel in der laufenden Saison",
    "saison_tordiff_gast": "Gastteam: Tordifferenz je Spiel in der laufenden Saison",
    "ruhetage_heim": "Tage seit dem letzten Spiel des Heimteams in den Daten (max 30)",
    "ruhetage_gast": "Tage seit dem letzten Spiel des Gastteams (max 30)",
    "ruhetage_diff": "ruhetage_heim - ruhetage_gast",
    "h2h5_tordiff": "Tordifferenz aus Heimsicht je Spiel in den letzten 5 direkten Duellen (None ohne Duell)",
    "h2h5_punkte_heim": "Punkte je Spiel des heutigen Heimteams in den letzten 5 direkten Duellen",
    "vorsaison_platz_heim": "Heimteam: Tabellenplatz der Vorsaison (1-18), None wenn nicht in Liga 1/2",
    "vorsaison_platz_gast": "Gastteam: Tabellenplatz der Vorsaison",
    "vorsaison_platz_diff": "vorsaison_platz_heim - vorsaison_platz_gast",
    "vorsaison_liga_heim": "Heimteam: Liga der Vorsaison (1/2), None wenn nicht dabei",
    "vorsaison_liga_gast": "Gastteam: Liga der Vorsaison",
    "aufsteiger_heim": "1 wenn das Heimteam aus einer tieferen Liga (oder von ausserhalb) kommt",
    "aufsteiger_gast": "1 wenn das Gastteam Aufsteiger ist",
    "absteiger_heim": "1 wenn das Heimteam aus einer hoeheren Liga kommt",
    "absteiger_gast": "1 wenn das Gastteam Absteiger ist",
    "spiele_gesamt_heim": "Anzahl Spiele des Heimteams in der Historie (Datendichte)",
    "spiele_gesamt_gast": "Anzahl Spiele des Gastteams in der Historie",
}
MERKMALE = list(BESCHREIBUNG)


def _mittel(werte):
    return sum(werte) / len(werte) if werte else None


def _elo_erwartung(elo_heim, elo_gast):
    return 1.0 / (1.0 + 10 ** ((elo_gast - elo_heim - ELO_HEIMVORTEIL) / 400.0))


def _tabellen(spiele):
    """(saison, liga) -> {verein: platz} aus gespielten Spielen."""
    stand = {}
    for s in spiele:
        if not s.gespielt:
            continue
        t = stand.setdefault((s.saison, s.liga), {})
        for verein, tore, gegen in ((s.heim, s.tore_heim, s.tore_gast), (s.gast, s.tore_gast, s.tore_heim)):
            e = t.setdefault(verein, [0, 0, 0])  # Punkte, Tordifferenz, Tore
            e[0] += 3 if tore > gegen else (1 if tore == gegen else 0)
            e[1] += tore - gegen
            e[2] += tore
    plaetze = {}
    for key, t in stand.items():
        reihe = sorted(t.items(), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2], kv[0]))
        plaetze[key] = {verein: i + 1 for i, (verein, _) in enumerate(reihe)}
    return plaetze


def _vorsaison(saison):
    j = int(saison[:4])
    return "%d-%02d" % (j - 1, j % 100)


class _Verein:
    __slots__ = ("elo", "verlauf", "letztes_datum")

    def __init__(self, liga):
        self.elo = ELO_START.get(liga, 1400.0)
        self.verlauf = []          # dicts: datum, saison, heim, tore, gegentore, punkte
        self.letztes_datum = None

    def letzte(self, n, heim=None):
        v = self.verlauf if heim is None else [e for e in self.verlauf if e["heim"] == heim]
        return v[-n:]

    def saison(self, saison):
        return [e for e in self.verlauf if e["saison"] == saison]


def berechne(spiele):
    """Liste von Merkmalsdicts, eine je Spiel, in der Reihenfolge der Eingabe
    (die chronologisch sein muss)."""
    plaetze = _tabellen(spiele)
    vereine = {}
    duelle = {}    # frozenset({a,b}) -> [(datum, heim, tore_heim, tore_gast)]
    out = []
    for s in spiele:
        vh = vereine.get(s.heim) or vereine.setdefault(s.heim, _Verein(s.liga))
        vg = vereine.get(s.gast) or vereine.setdefault(s.gast, _Verein(s.liga))
        m = {"liga": float(s.liga), "spieltag": float(s.spieltag or 0),
             "saison_fortschritt": (s.spieltag or 0) / 34.0,
             "elo_heim": vh.elo, "elo_gast": vg.elo, "elo_diff": vh.elo - vg.elo,
             "elo_erwartung": _elo_erwartung(vh.elo, vg.elo)}
        for seite, v in (("heim", vh), ("gast", vg)):
            l5, l10 = v.letzte(5), v.letzte(10)
            m["form5_punkte_" + seite] = _mittel([e["punkte"] for e in l5])
            m["form10_punkte_" + seite] = _mittel([e["punkte"] for e in l10])
            m["form5_tordiff_" + seite] = _mittel([e["tore"] - e["gegentore"] for e in l5])
            m["form10_tordiff_" + seite] = _mittel([e["tore"] - e["gegentore"] for e in l10])
            m["form5_tore_" + seite] = _mittel([e["tore"] for e in l5])
            m["form5_gegentore_" + seite] = _mittel([e["gegentore"] for e in l5])
            sais = v.saison(s.saison)
            m["saison_ppg_" + seite] = _mittel([e["punkte"] for e in sais])
            m["saison_tordiff_" + seite] = _mittel([e["tore"] - e["gegentore"] for e in sais])
            m["ruhetage_" + seite] = (None if v.letztes_datum is None
                                      else float(min((s.datum - v.letztes_datum).days, RUHETAGE_MAX)))
            m["spiele_gesamt_" + seite] = float(len(v.verlauf))
            vs = _vorsaison(s.saison)
            platz, liga_vs = None, None
            for liga in (1, 2):
                p = plaetze.get((vs, liga), {}).get(s.heim if seite == "heim" else s.gast)
                if p is not None:
                    platz, liga_vs = float(p), float(liga)
            m["vorsaison_platz_" + seite] = platz
            m["vorsaison_liga_" + seite] = liga_vs
            m["aufsteiger_" + seite] = 1.0 if (liga_vs is None or liga_vs > s.liga) else 0.0
            m["absteiger_" + seite] = 1.0 if (liga_vs is not None and liga_vs < s.liga) else 0.0
        m["heimform5_punkte_heim"] = _mittel([e["punkte"] for e in vh.letzte(5, heim=True)])
        m["auswform5_punkte_gast"] = _mittel([e["punkte"] for e in vg.letzte(5, heim=False)])
        for name in ("form5_punkte", "form10_punkte", "saison_ppg", "ruhetage", "vorsaison_platz"):
            a, b = m[name + "_heim"], m[name + "_gast"]
            m[name + "_diff"] = None if a is None or b is None else a - b
        d = duelle.get(frozenset((s.heim, s.gast)), [])[-5:]
        if d:
            m["h2h5_tordiff"] = _mittel([(th - tg) if h == s.heim else (tg - th) for _, h, th, tg in d])
            m["h2h5_punkte_heim"] = _mittel([
                (3 if th > tg else 1 if th == tg else 0) if h == s.heim else (3 if tg > th else 1 if th == tg else 0)
                for _, h, th, tg in d])
        else:
            m["h2h5_tordiff"] = None
            m["h2h5_punkte_heim"] = None
        out.append({k: m.get(k) for k in MERKMALE})
        if not s.gespielt:
            continue
        # Zustand fortschreiben
        th, tg = s.tore_heim, s.tore_gast
        erwartung = _elo_erwartung(vh.elo, vg.elo)
        ergebnis = 1.0 if th > tg else (0.5 if th == tg else 0.0)
        diff = abs(th - tg)
        faktor = 1.0 if diff <= 1 else (1.5 if diff == 2 else (11 + diff) / 8.0)
        delta = ELO_K * faktor * (ergebnis - erwartung)
        vh.elo += delta
        vg.elo -= delta
        vh.verlauf.append({"datum": s.datum, "saison": s.saison, "heim": True, "tore": th,
                           "gegentore": tg, "punkte": 3 if th > tg else (1 if th == tg else 0)})
        vg.verlauf.append({"datum": s.datum, "saison": s.saison, "heim": False, "tore": tg,
                           "gegentore": th, "punkte": 3 if tg > th else (1 if th == tg else 0)})
        vh.letztes_datum = vg.letztes_datum = s.datum
        duelle.setdefault(frozenset((s.heim, s.gast)), []).append((s.datum, s.heim, th, tg))
    return out


def elo_stand(spiele):
    """Aktuelle Elo-Werte nach allen gespielten Spielen (fuer `status`)."""
    vereine = {}
    for s in spiele:
        if not s.gespielt:
            continue
        vh = vereine.get(s.heim) or vereine.setdefault(s.heim, _Verein(s.liga))
        vg = vereine.get(s.gast) or vereine.setdefault(s.gast, _Verein(s.liga))
        erwartung = _elo_erwartung(vh.elo, vg.elo)
        ergebnis = 1.0 if s.tore_heim > s.tore_gast else (0.5 if s.tore_heim == s.tore_gast else 0.0)
        diff = abs(s.tore_heim - s.tore_gast)
        faktor = 1.0 if diff <= 1 else (1.5 if diff == 2 else (11 + diff) / 8.0)
        delta = ELO_K * faktor * (ergebnis - erwartung)
        vh.elo += delta
        vg.elo -= delta
    return {k: v.elo for k, v in vereine.items()}
