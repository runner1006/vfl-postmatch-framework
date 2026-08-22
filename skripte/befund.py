"""Der Befund zu einem einzelnen Spiel — drei Ebenen, strikt getrennt.

Diese Datei rechnet, sie stellt nichts dar. Sie liest ausschliesslich
`ergebnisse/dashboard_matches.json`; dort stehen bereits alle gerechneten
Groessen samt Gegnerstaerke, Ligamittel und Aufsteiger-Benchmark. Damit laeuft
der Report ohne die providerlizenzierten Rohdaten und ohne Fremdpakete.

Ebene A  Spielstiltreue        0-100 aus 15 KPIs in fuenf Phasen
Ebene B  Aufstiegsperformance  npxG-Differenz gegen das gegnerbereinigte Ziel
Ebene C  Outcome Alignment     xPoints gegen tatsaechliche Punkte
"""
import json
import os

from klubprofil import ERGEBNISSE

STANDARD_DATEI = os.path.join(ERGEBNISSE, "dashboard_matches.json")

FLAG_TEXT = {
    "UNTERZAHL": "Rote Karte gegen uns — Werte eingeschränkt vergleichbar",
    "UEBERZAHL": "Rote Karte gegen den Gegner — Werte eingeschränkt vergleichbar",
    "PHYSIK_FEHLT": "Keine Physikdaten — die Phase Physisch bleibt leer",
    "KLEINE_NENNER": "Wenige Ballbesitze oder Ballgewinne — Raten instabil",
    "MUTIG_UNGESICHERT": "Hoch verteidigt, der Gegner kam trotzdem durch",
    "DIREKT_UNKONTROLLIERT": "Hohe Vertikalität bei schwacher Aufbaukontrolle",
}


class Datenfehler(ValueError):
    """Die Datengrundlage passt nicht zum Profil."""


class Datensatz:
    """Die gerechnete Grundlage, einmal geladen."""

    def __init__(self, datei=None):
        self.datei = datei or STANDARD_DATEI
        if not os.path.exists(self.datei):
            raise Datenfehler(
                f"{self.datei} fehlt. Die Datei entsteht in Schritt 9 der Pipeline "
                f"(skripte/dashboard_match_data.py).")
        with open(self.datei, encoding="utf-8") as f:
            self.d = json.load(f)
        self.kpi_doc = {k["key"]: k for k in self.d["doc_kpis"]}
        self.phasen_doc = self.d["doc_phasen"]
        self.conf_schwelle = self.d.get("conf_schwelle", 0.2)
        self.benchmark = self.d["benchmark"]
        self.kontext_def = self.d["kontext_def"]

    def team(self, key):
        for t in self.d["teams"]:
            if t["key"] == key:
                return t
        vorhanden = ", ".join(t["key"] for t in self.d["teams"])
        raise Datenfehler(f"Kein Team '{key}' in {os.path.basename(self.datei)} "
                          f"(vorhanden: {vorhanden})")

    def spiele(self, profil):
        return self.team(profil["quelle"]["team_key"])["spiele"]


# Die Phasenfragen stammen aus dem Bochumer Ursprungsbriefing und nennen den
# Klub beim Namen. Im Produkt steht dort die Mannschaft, sonst liest ein anderer
# Klub in seinem eigenen Report ueber den VfL.
FRAGE_NEUTRAL = (("der VfL", "die Mannschaft"), ("wird er", "wird sie"))


def neutral(text):
    for alt, neu in FRAGE_NEUTRAL:
        text = text.replace(alt, neu)
    return text


# ------------------------------------------------------------------ Ebene A
def ebene_a(ds, spiel):
    """Spielstiltreue: Gesamtscore, Phasen, staerkste und schwaechste KPIs."""
    phasen = []
    for p in ds.phasen_doc:
        k = p["key"]
        score = spiel["ph"].get(k)
        conf = spiel["ph_conf"].get(k)
        phasen.append({
            "key": k, "label": p["label"], "gewicht": p["gewicht"],
            "frage": neutral(p["frage"]), "score": score, "conf": conf,
            "guete": spiel["ph_guete"].get(k),
            "unsicher": score is None or (conf is not None and conf < ds.conf_schwelle),
        })

    einzel = []
    for key, score in spiel["kpi"].items():
        if score is None:
            continue
        doc = ds.kpi_doc[key]
        conf = spiel["kpi_conf"].get(key)
        einzel.append({
            "key": key, "kurz": doc["kurz"], "name": doc["name"], "mgmt": doc["mgmt"],
            "phase": doc["phase_label"], "score": score, "conf": conf,
            "roh": spiel["kpi_roh"].get(key), "n": spiel["kpi_n"].get(key),
            "urteil": doc["urteil"], "normativ": doc["normativ"],
            "definition": doc["definition"], "norm": doc["norm"],
            "unsicher": conf is not None and conf < ds.conf_schwelle,
        })
    sortiert = sorted(einzel, key=lambda e: e["score"], reverse=True)
    return {
        "score": spiel["score"],
        "conf": spiel["conf"],
        "phasen": phasen,
        "kpis": einzel,
        "stark": sortiert[:3],
        "schwach": list(reversed(sortiert[-3:])),
        "ohne_daten": [p["label"] for p in phasen if p["score"] is None],
    }


# ------------------------------------------------------------------ Ebene B
def ebene_b(ds, spiel, profil):
    """Aufstiegsperformance: erreichte gegen gegnerbereinigte Zielmarke.

    Ziel = Aufsteigermittel, additiv um die Abweichung dieses Gegners vom
    Ligamittel verschoben. Gegen einen starken Gegner sinkt die Marke, gegen
    einen schwachen steigt sie — dieselbe Rechnung wie im Dashboard.
    """
    ziel = profil.get("ziel") or {}
    if not ziel:
        return None
    ls = spiel["ls"]
    if ziel.get("gilt_fuer_liga") and not ls.startswith(ziel["gilt_fuer_liga"]):
        return None
    staerke = ds.d["staerke"].get(ls, {}).get(str(spiel["geg_id"]))
    lm = (ds.d["ligamittel"].get(ls) or {}).get("npxg")
    if not staerke or lm is None or spiel["npxg"] is None or spiel["npxg_geg"] is None:
        return None

    b = ds.benchmark
    ziel_off = b["npxg_erzeugt"] + (staerke["def"] - lm)
    ziel_def = b["npxg_zugelassen"] + (staerke["off"] - lm)
    ist_diff = spiel["npxg"] - spiel["npxg_geg"]
    ziel_diff = ziel_off - ziel_def
    return {
        "label": ziel.get("label", "Zielniveau"),
        "kohorte": ziel.get("kohorte", ""),
        "npxg": spiel["npxg"], "npxg_geg": spiel["npxg_geg"],
        "ziel_off": ziel_off, "ziel_def": ziel_def,
        "ist_diff": ist_diff, "ziel_diff": ziel_diff,
        "delta": ist_diff - ziel_diff,
        "erreicht": ist_diff >= ziel_diff,
        "gegner_off": staerke["off"], "gegner_def": staerke["def"], "ligamittel": lm,
        "anteil_kohorte": b["anteil_ueber_ziel"],
        "anteil_liga": b["anteil_ueber_ziel_liga"],
    }


# ------------------------------------------------------------------ Ebene C
def ebene_c(spiel):
    """Outcome Alignment: passt das Ergebnis zur gezeigten Leistung?"""
    def diff(a, b):
        return None if a is None or b is None else a - b

    return {
        "punkte": spiel["pkt"], "xp": spiel["xp"], "dpkt": spiel["dpkt"],
        "psieg": spiel["psieg"], "premis": spiel["premis"], "pnied": spiel["pnied"],
        "klasse": spiel["klasse"],
        "npg": spiel["npg"], "npxg": spiel["npxg"],
        "npg_geg": spiel["npg_geg"], "npxg_geg": spiel["npxg_geg"],
        "verwertung": diff(spiel["npg"], spiel["npxg"]),
        "verwertung_geg": diff(spiel["npg_geg"], spiel["npxg_geg"]),
        "tw_effekt": spiel["tw_effekt"],
    }


# ---------------------------------------------------------------- Saisonlage
def _median(werte):
    w = sorted(x for x in werte if x is not None)
    if not w:
        return None
    m = len(w) // 2
    return w[m] if len(w) % 2 else (w[m - 1] + w[m]) / 2


def saisonlage(ds, spiele, i, profil):
    """Stand der laufenden Liga-Saison bis einschliesslich diesem Spiel."""
    ls = spiele[i]["ls"]
    saison = [s for s in spiele if s["ls"] == ls]
    bis = [s for s in saison if s["i"] <= spiele[i]["i"]]
    scores = [s["score"] for s in bis]
    aktuell = spiele[i]["score"]
    besser = sum(1 for s in scores if s is not None and aktuell is not None and s < aktuell)

    ziele = [ebene_b(ds, s, profil) for s in bis]
    ziele = [z for z in ziele if z]
    return {
        "liga_saison": ls,
        "spiele": len(bis), "spiele_saison": len(saison),
        "punkte": sum(s["pkt"] for s in bis),
        "xp": sum(s["xp"] for s in bis if s["xp"] is not None),
        "tore": sum(s["tore"] for s in bis), "gegentore": sum(s["gt"] for s in bis),
        "score_median": _median(scores),
        "score_rang": len(scores) - besser if aktuell is not None else None,
        "form": _median([s["score"] for s in bis[-5:]]),
        "ueber_ziel": sum(1 for z in ziele if z["erreicht"]),
        "ueber_ziel_von": len(ziele),
        "verlauf": [{"gw": s["gw"], "score": s["score"], "aktuell": s["i"] == spiele[i]["i"]}
                    for s in saison if s["i"] <= spiele[i]["i"]],
    }


# ------------------------------------------------------------------- Kontext
# Kurzfassung der Beschriftungen: die Langform aus dem Dashboard sprengt die
# zwei schmalen Spalten des Reports.
KONTEXT_KURZ = {
    "geg_ballbesitz": "Ballbesitz Gegner",
    "geg_pdda": "PPDA Gegner",
    "geg_recov_hoch": "Ballgewinnhöhe Gegner",
    "geg_fwd_anteil": "Vorwärtspässe Gegner",
    "geg_haelfte_rate": "Gegner in unserer Hälfte",
    "geg_box_rate": "Gegner in unserer Box",
    "geg_konter": "Konter des Gegners",
    "eig_ballgewinne": "Eigene Ballgewinne",
    "eig_ballverluste": "Eigene Ballverluste",
    "eig_ballbesitze": "Eigene Ballbesitze",
    "eig_eff_min": "Effektive Spielzeit",
    "blockhoehe": "Blockhöhe des Gegners",
}

NACHKOMMA = {"%": 1, "Anteil": 2, "Anzahl": 0, "": 2}


def kontext(ds, spiel):
    """Gegnerbild: was der Gegner zugelassen und selbst getan hat."""
    zeilen = []
    for k in ds.kontext_def:
        key = k["key"]
        if key == "blockhoehe":
            wert, perz = spiel.get("blockhoehe"), spiel.get("blockhoehe_p")
        else:
            wert, perz = spiel["kontext"].get(key), spiel["kontext_p"].get(key)
        if wert is None:
            continue
        einheit = k.get("einheit", "")
        zeilen.append({"label": KONTEXT_KURZ.get(key, k["label"]),
                       "einheit": "%" if einheit == "%" else "",
                       "nachkomma": NACHKOMMA.get(einheit, 2),
                       "wert": wert, "perzentil": perz})
    return zeilen


def flags(spiel):
    roh = [f for f in (spiel.get("flags") or "").split(";") if f]
    return [{"key": f, "text": FLAG_TEXT.get(f, f)} for f in roh]


# --------------------------------------------------------------- Gesamtbefund
def befund(ds, profil, i):
    """Alles zu einem Spiel, fertig zum Rendern."""
    spiele = ds.spiele(profil)
    if not -len(spiele) <= i < len(spiele):
        raise Datenfehler(f"Spielindex {i} liegt ausserhalb von 0..{len(spiele) - 1}")
    s = spiele[i]
    return {
        "profil": profil, "spiel": s,
        "a": ebene_a(ds, s), "b": ebene_b(ds, s, profil), "c": ebene_c(s),
        "saison": saisonlage(ds, spiele, i % len(spiele), profil),
        "kontext": kontext(ds, s), "flags": flags(s),
        "benchmark": ds.benchmark, "conf_schwelle": ds.conf_schwelle,
    }


def finde(spiele, spieltag=None, datum=None, gegner=None):
    """Loest --spieltag / --datum / --gegner in einen Index auf."""
    treffer = list(range(len(spiele)))
    if spieltag is not None:
        treffer = [i for i in treffer if spiele[i]["gw"] == spieltag]
    if datum:
        treffer = [i for i in treffer if spiele[i]["datum"] == datum]
    if gegner:
        g = gegner.lower()
        treffer = [i for i in treffer if g in spiele[i]["geg"].lower()]
    return treffer
