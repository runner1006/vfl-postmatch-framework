"""Datenschicht: Spiel- und Saisondaten aus ergebnisse/ als Lerntabellen.

Zwei Lernaufgaben, beide aus Dateien, die im Repository liegen (kein Token
noetig):

  spiel     298 Team-Spiel-Zeilen der fuenf Dashboard-Mannschaften. Frage:
            Welche Leistungsmerkmale erklaeren das Ergebnis (Niederlage /
            Remis / Sieg)? Benchmark ist das Poisson-Modell des Frameworks
            (psieg / premis / pnied aus npxG).
  aufstieg  162 Team-Saisons der 2. Bundesliga. Frage: Wer landet unter den
            ersten drei? Benchmark ist die LOSO-Validierung aus
            ergebnisse/loso_validation.csv.

Was hier bewusst NICHT als Merkmal auftaucht: alles, was das Ergebnis selbst
ist oder direkt daraus folgt (Tore, Punkte, xPoints je Spiel, Platz). Sonst
lernt die KI, dass Tore Siege erklaeren.
"""
import ast
import csv
import json
import math
import os

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
ERGEBNISSE = os.path.join(WURZEL, "ergebnisse")

AUFGABEN = ("spiel", "aufstieg")

# Team-IDs der Dashboard-Mannschaften (aus skripte/config.py)
TEAM_IDS = {
    "bochum": 2448,
    "leipzig_werner": 2975,
    "sturm_ilzer": 8742,
    "hoffenheim_ilzer": 2482,
    "schalke_muslic": 2449,
}

KPI_BESCHREIBUNG = {
    "O1_vertikalitaet": "Offensiv: Vertikalitaet im Aufbau (Score 0-100, Band-Korridor)",
    "O2_boxzugang": "Offensiv: Boxzugang je Ballbesitz",
    "O3_fluegel_boxzuspiel": "Offensiv: Boxzuspiele ueber den Fluegel",
    "OT1_konterrate": "Offensives Umschalten: Konterrate je Ballgewinn (Band)",
    "OT2_tiefenertrag": "Offensives Umschalten: Tiefenertrag nach Ballgewinn",
    "OT3_ballgewinnqualitaet": "Offensives Umschalten: Qualitaet der Ballgewinne",
    "D1_pressingdruck": "Defensiv: Pressingdruck (PPDA, Band)",
    "D2_ballgewinnhoehe": "Defensiv: Hoehe der Ballgewinne",
    "D3_gegner_progression": "Defensiv: Gegnerprogression unterbunden",
    "DT1_gegenpressing": "Defensives Umschalten: Gegenpressing nach Ballverlust",
    "DT2_gefaehrl_verluste": "Defensives Umschalten: gefaehrliche Ballverluste vermieden",
    "DT3_hohe_verluste": "Defensives Umschalten: hohe Ballverluste (unkritisch)",
    "P1_laufvolumen_hi": "Physisch: hochintensives Laufvolumen (fehlt in AUT)",
    "P2_explosivitaet": "Physisch: Explosivitaet (fehlt in AUT)",
    "P3_endgeschwindigkeit": "Physisch: Endgeschwindigkeit (fehlt in AUT)",
}
KPI_KEYS = list(KPI_BESCHREIBUNG)

PHASEN = ["defensiv", "def_umschalten", "offensiv", "off_umschalten", "physisch"]

KONTEXT_BESCHREIBUNG = {
    "geg_ballbesitz": "Ballbesitz des Gegners in %",
    "geg_pdda": "PPDA des Gegners (hoch = laeuft nicht an)",
    "geg_recov_hoch": "Anteil hoher Ballgewinne des Gegners",
    "geg_fwd_anteil": "Vorwaertspass-Anteil des Gegners",
    "geg_haelfte_rate": "Rate, mit der der Gegner unsere Haelfte erreicht",
    "geg_box_rate": "Rate, mit der der Gegner unsere Box erreicht",
    "geg_konter": "Konter des Gegners",
    "eig_ballgewinne": "eigene Ballgewinne (Anzahl)",
    "eig_ballverluste": "eigene Ballverluste (Anzahl)",
    "eig_ballbesitze": "eigene Ballbesitze (Anzahl)",
    "eig_eff_min": "effektive Spielzeit in Minuten",
    "blockhoehe": "Blockhoehe des Gegners (z-Wert, negativ = tief)",
}

SAISON_BESCHREIBUNG = {
    "npxg": "npxG erzeugt je Spiel",
    "npxg_gegen": "npxG zugelassen je Spiel",
    "npxg_diff": "npxG-Differenz je Spiel",
    "box_zugriff": "Box-Zugriffsrate offensiv",
    "box_zugriff_gegen": "Box-Zugriffsrate des Gegners",
    "abschlussqualitaet": "npxG je Schuss offensiv",
    "abschlussqualitaet_gegen": "npxG je Schuss des Gegners",
    "schuesse": "Schuesse je Spiel",
    "schuesse_gegen": "zugelassene Schuesse je Spiel",
    "xpoints": "erwartete Punkte je Spiel aus der Schussliste",
}
SAISON_SPALTEN = {
    "npxg": "CC1_npxg",
    "npxg_gegen": "CC1d_npxg_gegen",
    "npxg_diff": "npxg_diff",
    "box_zugriff": "CC2_box_zugriffsrate",
    "box_zugriff_gegen": "CC2d_box_zugriffsrate_gegen",
    "abschlussqualitaet": "CC3_abschlussqualitaet",
    "abschlussqualitaet_gegen": "CC3d_abschlussqualitaet_gegen",
    "schuesse": "wy_totals_general_shots",
    "schuesse_gegen": "schuesse_gegen",
    "xpoints": "xpoints",
}


class Tabelle:
    """Eine Lerntabelle: Zeilen mit Merkmalen, Label, Gruppe und Zeitindex."""

    def __init__(self, aufgabe, zeilen, merkmale, beschreibung, klassen,
                 benchmark, frage):
        self.aufgabe = aufgabe
        self.zeilen = zeilen              # [{id, gruppe, zeit, label, merkmale, extra}]
        self.merkmale = merkmale          # verfuegbare Basismerkmale
        self.beschreibung = beschreibung  # name -> Text
        self.klassen = klassen            # Labelnamen
        self.benchmark = benchmark        # {name: wert} aus dem Framework
        self.frage = frage

    def __len__(self):
        return len(self.zeilen)

    def labels(self):
        return [z["label"] for z in self.zeilen]

    def spalte(self, name):
        return [z["merkmale"].get(name) for z in self.zeilen]

    def statistik(self):
        """Mittel, Streuung und Fehlanteil je Merkmal - fuer den Katalog."""
        out = {}
        for m in self.merkmale:
            werte = [v for v in self.spalte(m) if v is not None and not math.isnan(v)]
            n = len(werte)
            if n == 0:
                out[m] = {"mittel": None, "sd": None, "fehlt": 1.0}
                continue
            mu = sum(werte) / n
            sd = math.sqrt(sum((v - mu) ** 2 for v in werte) / max(n - 1, 1))
            out[m] = {"mittel": mu, "sd": sd, "fehlt": 1 - n / len(self.zeilen)}
        return out


def _zahl(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# ------------------------------------------------------------------ Spiele
def lade_spiele(pfad=None):
    pfad = pfad or os.path.join(ERGEBNISSE, "dashboard_matches.json")
    with open(pfad, encoding="utf-8") as f:
        d = json.load(f)
    staerke = d.get("staerke", {})
    ligamittel = d.get("ligamittel", {})
    zeilen = []
    for team in d["teams"]:
        for s in team["spiele"]:
            ls = s["ls"]
            geg = staerke.get(ls, {}).get(str(s.get("geg_id")), {})
            m = {}
            for k in KPI_KEYS:
                m[k] = _zahl((s.get("kpi") or {}).get(k))
            for p in PHASEN:
                m["ph_" + p] = _zahl((s.get("ph") or {}).get(p))
            m["stil_score"] = _zahl(s.get("score"))
            for k in ("npxg", "npxg_geg", "exp_npxg", "exp_npxg_geg"):
                m[k] = _zahl(s.get(k))
            kontext = s.get("kontext") or {}
            for k in KONTEXT_BESCHREIBUNG:
                if k == "blockhoehe":
                    m[k] = _zahl(s.get("blockhoehe"))
                else:
                    m[k] = _zahl(kontext.get(k))
            m["heim"] = 1.0 if s.get("heim") else 0.0
            m["geg_off"] = _zahl(geg.get("off"))
            m["geg_def"] = _zahl(geg.get("def"))
            m["liga_npxg"] = _zahl(ligamittel.get(ls, {}).get("npxg"))
            pkt = int(s["pkt"])
            label = {0: 0, 1: 1, 3: 2}[pkt]
            zeilen.append({
                "id": s["id"],
                "gruppe": team["key"],
                "zeit": (s["datum"], s["id"]),
                "label": label,
                "merkmale": m,
                "extra": {
                    "team": team["label"], "gegner": s.get("geg"),
                    "datum": s["datum"], "liga_saison": ls,
                    "ergebnis": "%s:%s" % (s.get("tore"), s.get("gt")),
                    "p_framework": [_zahl(s.get("pnied")), _zahl(s.get("premis")),
                                    _zahl(s.get("psieg"))],
                },
            })
    zeilen.sort(key=lambda z: z["zeit"])
    beschreibung = dict(KPI_BESCHREIBUNG)
    beschreibung.update({
        "ph_defensiv": "Phasenscore Defensiv (0-100)",
        "ph_def_umschalten": "Phasenscore Defensives Umschalten (0-100)",
        "ph_offensiv": "Phasenscore Offensiv (0-100)",
        "ph_off_umschalten": "Phasenscore Offensives Umschalten (0-100)",
        "ph_physisch": "Phasenscore Physisch (0-100, fehlt in AUT)",
        "stil_score": "Gesamt-Spielstilscore (0-100)",
        "npxg": "eigene npxG im Spiel",
        "npxg_geg": "npxG des Gegners im Spiel",
        "exp_npxg": "vom Gegnermodell erwartete eigene npxG",
        "exp_npxg_geg": "vom Gegnermodell erwartete gegnerische npxG",
        "heim": "Heimspiel (1) oder auswaerts (0)",
        "geg_off": "Saisonstaerke Gegner offensiv (npxG je Spiel)",
        "geg_def": "Saisonstaerke Gegner defensiv (zugelassene npxG je Spiel)",
        "liga_npxg": "Ligamittel npxG je Spiel in dieser Saison",
    })
    beschreibung.update(KONTEXT_BESCHREIBUNG)
    merkmale = list(beschreibung)
    benchmark = _benchmark_spiel(zeilen)
    return Tabelle("spiel", zeilen, merkmale, beschreibung,
                   ["Niederlage", "Remis", "Sieg"], benchmark,
                   "Welche Leistungsmerkmale eines Spiels erklaeren das Ergebnis "
                   "(Niederlage / Remis / Sieg)?")


def _benchmark_spiel(zeilen):
    """Log-Loss des Framework-Poisson-Modells auf allen Zeilen mit Prognose."""
    from .modelle import log_loss
    p, y = [], []
    for z in zeilen:
        pf = z["extra"]["p_framework"]
        if pf and all(v is not None for v in pf):
            p.append(pf)
            y.append(z["label"])
    if not p:
        return {}
    return {"quelle": "Poisson-Modell des Frameworks (psieg/premis/pnied aus npxG)",
            "logloss": round(log_loss(y, p), 4), "n": len(p)}


# ----------------------------------------------------------------- Saisons
def lade_saisons(pfad=None):
    pfad = pfad or os.path.join(ERGEBNISSE, "team_season_stats.csv")
    zeilen = []
    with open(pfad, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            m = {name: _zahl(r.get(spalte)) for name, spalte in SAISON_SPALTEN.items()}
            zeilen.append({
                "id": "%s-%s" % (r["saison"], r["team_id"]),
                "gruppe": r["saison"],
                "zeit": (r["saison"], r["team"]),
                "label": int(r["top3"]),
                "merkmale": m,
                "extra": {"team": r["team"], "saison": r["saison"],
                          "platz": int(r["platz"]), "punkte": int(r["punkte"]),
                          "aufsteiger": int(r["aufsteiger"])},
            })
    zeilen.sort(key=lambda z: z["zeit"])
    benchmark = _benchmark_aufstieg()
    return Tabelle("aufstieg", zeilen, list(SAISON_SPALTEN), dict(SAISON_BESCHREIBUNG),
                   ["nicht Top-3", "Top-3"], benchmark,
                   "Welche Saisonkennzahlen sagen einen Platz unter den ersten drei "
                   "der 2. Bundesliga voraus?")


def _benchmark_aufstieg(pfad=None):
    pfad = pfad or os.path.join(ERGEBNISSE, "loso_validation.csv")
    if not os.path.exists(pfad):
        return {}
    best = None
    with open(pfad, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if "zirkul" in r["featureset"]:
                continue
            auc = _zahl(r["auc_mittel"])
            if best is None or auc > best["auc_mittel"]:
                best = {"quelle": "LOSO-Validierung des Frameworks: " + r["featureset"],
                        "auc_mittel": auc, "brier": _zahl(r["brier_mittel"]),
                        "top3_treffer_von_27": int(r["top3_treffer_von_27"])}
    return best or {}


def lade(aufgabe):
    if aufgabe == "spiel":
        return lade_spiele()
    if aufgabe == "aufstieg":
        return lade_saisons()
    raise ValueError("unbekannte Aufgabe: %r (erlaubt: %s)" % (aufgabe, ", ".join(AUFGABEN)))


# ----------------------------------------------------- abgeleitete Merkmale
_FUNKTIONEN = {
    "abs": abs, "sqrt": math.sqrt, "log": math.log, "log1p": math.log1p,
    "exp": math.exp, "min": min, "max": max,
}
_OPERATOREN = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}


class FormelFehler(ValueError):
    pass


def formel_pruefen(formel, erlaubte_namen):
    """Statisch pruefen: nur Arithmetik, bekannte Namen, bekannte Funktionen.

    Gibt die Menge der benutzten Merkmalsnamen zurueck oder wirft FormelFehler.
    Kein eval: der Baum wird selbst abgelaufen, alles andere ist verboten.
    """
    try:
        baum = ast.parse(str(formel).strip(), mode="eval")
    except SyntaxError as e:
        raise FormelFehler("Syntaxfehler in %r: %s" % (formel, e))
    benutzt = set()

    def gehe(k):
        if isinstance(k, ast.Expression):
            gehe(k.body)
        elif isinstance(k, ast.Constant) and isinstance(k.value, (int, float)):
            pass
        elif isinstance(k, ast.Name):
            if k.id not in erlaubte_namen:
                raise FormelFehler("unbekanntes Merkmal %r in %r" % (k.id, formel))
            benutzt.add(k.id)
        elif isinstance(k, ast.BinOp) and type(k.op) in _OPERATOREN:
            gehe(k.left)
            gehe(k.right)
        elif isinstance(k, ast.UnaryOp) and isinstance(k.op, (ast.USub, ast.UAdd)):
            gehe(k.operand)
        elif isinstance(k, ast.Call):
            if not isinstance(k.func, ast.Name) or k.func.id not in _FUNKTIONEN:
                raise FormelFehler("Funktion nicht erlaubt in %r" % formel)
            if k.keywords:
                raise FormelFehler("Schluesselwortargumente nicht erlaubt in %r" % formel)
            for a in k.args:
                gehe(a)
        else:
            raise FormelFehler("nicht erlaubter Ausdruck in %r" % formel)

    gehe(baum)
    return benutzt


def formel_auswerten(formel, werte):
    """Formel gegen ein Merkmalsdict auswerten. Rechenfehler und fehlende
    Eingaben ergeben None (wird spaeter wie ein fehlender Wert behandelt)."""
    baum = ast.parse(str(formel).strip(), mode="eval")

    def gehe(k):
        if isinstance(k, ast.Expression):
            return gehe(k.body)
        if isinstance(k, ast.Constant):
            return float(k.value)
        if isinstance(k, ast.Name):
            v = werte.get(k.id)
            if v is None:
                raise FormelFehler("fehlt")
            return float(v)
        if isinstance(k, ast.BinOp):
            return _OPERATOREN[type(k.op)](gehe(k.left), gehe(k.right))
        if isinstance(k, ast.UnaryOp):
            v = gehe(k.operand)
            return -v if isinstance(k.op, ast.USub) else v
        if isinstance(k, ast.Call):
            return float(_FUNKTIONEN[k.func.id](*[gehe(a) for a in k.args]))
        raise FormelFehler("nicht erlaubter Ausdruck")

    try:
        v = gehe(baum)
    except (FormelFehler, ZeroDivisionError, ValueError, OverflowError, TypeError):
        return None
    if isinstance(v, complex) or math.isnan(v) or math.isinf(v):
        return None
    return v


def katalog(tabelle):
    """Merkmalskatalog als Text - das, was der Forscher ueber die Daten weiss."""
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
