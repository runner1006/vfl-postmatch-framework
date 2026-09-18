"""Hypothesen: was der Forscher vorschlaegt und was der Rechenkern annimmt.

Eine Hypothese ist ein Bauplan fuer ein Modell - Merkmale, abgeleitete
Merkmale als Formeln, Modelltyp und Regularisierung - plus eine Begruendung
in Worten. Der Forscher (Sprachmodell oder Offline-Suche) liefert sie als
JSON; `pruefen` normalisiert und weist alles ab, was nicht rechenbar ist.
So kann das Sprachmodell nichts ausfuehren, nur vorschlagen.
"""
import hashlib
import json
import re

from .daten import FormelFehler, formel_pruefen

MAX_MERKMALE = 25
MODELLTYPEN = ("logit", "mlp")
STANDARDISIERUNGEN = ("global", "gruppe")

# JSON-Schema fuer die strukturierte Ausgabe des Sprachmodells
SCHEMA = {
    "type": "object",
    "properties": {
        "hypothesen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "begruendung": {"type": "string"},
                    "merkmale": {"type": "array", "items": {"type": "string"}},
                    "abgeleitet": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "formel": {"type": "string"},
                            },
                            "required": ["name", "formel"],
                            "additionalProperties": False,
                        },
                    },
                    "modell": {
                        "type": "object",
                        "properties": {
                            "typ": {"type": "string", "enum": list(MODELLTYPEN)},
                            "l2": {"type": "number"},
                            "versteckt": {"type": "integer"},
                            "epochen": {"type": "integer"},
                            "lernrate": {"type": "number"},
                        },
                        "required": ["typ", "l2", "versteckt", "epochen", "lernrate"],
                        "additionalProperties": False,
                    },
                    "standardisierung": {"type": "string", "enum": list(STANDARDISIERUNGEN)},
                    "erwartung": {"type": "string"},
                },
                "required": ["name", "begruendung", "merkmale", "abgeleitet", "modell",
                             "standardisierung", "erwartung"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["hypothesen"],
    "additionalProperties": False,
}

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _klemme(v, lo, hi, standard):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return standard
    return min(max(v, lo), hi)


def pruefen(vorschlag, tabelle):
    """Vorschlag -> (Hypothese, Fehlerliste). Bei Fehlern ist die Hypothese None."""
    fehler = []
    if not isinstance(vorschlag, dict):
        return None, ["Vorschlag ist kein Objekt"]
    name = str(vorschlag.get("name") or "ohne Namen").strip()[:80]
    begruendung = str(vorschlag.get("begruendung") or "").strip()[:1200]
    erwartung = str(vorschlag.get("erwartung") or "").strip()[:600]

    merkmale = []
    for m in vorschlag.get("merkmale") or []:
        m = str(m).strip()
        if m not in tabelle.merkmale:
            fehler.append("unbekanntes Merkmal %r" % m)
        elif m not in merkmale:
            merkmale.append(m)

    abgeleitet = []
    bekannt = set(tabelle.merkmale)
    for a in vorschlag.get("abgeleitet") or []:
        if not isinstance(a, dict):
            fehler.append("abgeleitetes Merkmal ist kein Objekt")
            continue
        an = str(a.get("name") or "").strip()
        formel = str(a.get("formel") or "").strip()
        if not _NAME.match(an):
            fehler.append("ungueltiger Name fuer abgeleitetes Merkmal %r" % an)
            continue
        if an in bekannt:
            fehler.append("abgeleiteter Name %r kollidiert mit vorhandenem Merkmal" % an)
            continue
        try:
            formel_pruefen(formel, bekannt)
        except FormelFehler as e:
            fehler.append(str(e))
            continue
        abgeleitet.append({"name": an, "formel": formel})
        bekannt.add(an)

    if not merkmale and not abgeleitet:
        fehler.append("keine Merkmale angegeben")
    if len(merkmale) + len(abgeleitet) > MAX_MERKMALE:
        fehler.append("zu viele Merkmale (%d > %d)" % (len(merkmale) + len(abgeleitet), MAX_MERKMALE))

    ms = vorschlag.get("modell") or {}
    if not isinstance(ms, dict):
        ms = {}
    typ = str(ms.get("typ") or "logit")
    if typ not in MODELLTYPEN:
        fehler.append("unbekannter Modelltyp %r" % typ)
        typ = "logit"
    modell = {"typ": typ, "l2": _klemme(ms.get("l2"), 1e-3, 100.0, 1.0)}
    if typ == "mlp":
        modell["versteckt"] = int(_klemme(ms.get("versteckt"), 1, 32, 8))
        modell["epochen"] = int(_klemme(ms.get("epochen"), 20, 600, 200))
        modell["lernrate"] = _klemme(ms.get("lernrate"), 1e-3, 0.2, 0.02)

    std = str(vorschlag.get("standardisierung") or "global")
    if std not in STANDARDISIERUNGEN:
        fehler.append("unbekannte Standardisierung %r" % std)
        std = "global"

    if fehler:
        return None, fehler
    hyp = {"name": name, "begruendung": begruendung, "merkmale": merkmale,
           "abgeleitet": abgeleitet, "modell": modell, "standardisierung": std,
           "erwartung": erwartung}
    hyp["kennung"] = kennung(hyp)
    return hyp, []


def kennung(hyp):
    """Kurzer Fingerabdruck ueber alles, was das Rechenergebnis bestimmt."""
    kern = {"merkmale": sorted(hyp["merkmale"]),
            "abgeleitet": sorted((a["name"], a["formel"]) for a in hyp["abgeleitet"]),
            "modell": hyp["modell"], "standardisierung": hyp["standardisierung"]}
    return hashlib.sha1(json.dumps(kern, sort_keys=True).encode("utf-8")).hexdigest()[:10]


def startpaket(aufgabe):
    """Erste Hypothesen, wenn das Gedaechtnis leer ist. Bewusst schlicht:
    das Framework-Wissen als Ausgangspunkt, nicht als Ziel."""
    if aufgabe == "spiel":
        return [
            {"name": "npxG-Bilanz", "begruendung": "Das Framework erklaert Ergebnisse ueber npxG; "
             "die Differenz ist der naheliegende Startpunkt.",
             "merkmale": ["npxg", "npxg_geg"], "abgeleitet": [], "modell": {"typ": "logit", "l2": 1.0},
             "standardisierung": "global", "erwartung": "Nahe am Framework-Benchmark."},
            {"name": "Fuenf Phasen", "begruendung": "Die Phasenscores buendeln alle 15 KPIs; "
             "reicht der Stil allein, um Ergebnisse zu erklaeren?",
             "merkmale": ["ph_defensiv", "ph_def_umschalten", "ph_offensiv", "ph_off_umschalten",
                          "ph_physisch", "heim"],
             "abgeleitet": [], "modell": {"typ": "logit", "l2": 1.0},
             "standardisierung": "global", "erwartung": "Deutlich schwaecher als npxG."},
            {"name": "npxG plus Kontext", "begruendung": "Gegnerstaerke und Heimvorteil sollten "
             "ueber npxG hinaus Information tragen.",
             "merkmale": ["npxg", "npxg_geg", "heim", "geg_off", "geg_def", "blockhoehe"],
             "abgeleitet": [{"name": "npxg_diff", "formel": "npxg - npxg_geg"}],
             "modell": {"typ": "logit", "l2": 1.0}, "standardisierung": "global",
             "erwartung": "Kleiner Gewinn gegenueber der reinen Bilanz."},
        ]
    return [
        {"name": "npxG-Differenz", "begruendung": "Die staerkste Einzelgroesse der Aufstiegsanalyse.",
         "merkmale": ["npxg_diff"], "abgeleitet": [], "modell": {"typ": "logit", "l2": 1.0},
         "standardisierung": "gruppe", "erwartung": "AUC nahe 0.90 wie im Framework."},
        {"name": "Chance-Creation-Set", "begruendung": "Alle sechs CC-KPIs, wie im Framework validiert.",
         "merkmale": ["npxg", "npxg_gegen", "box_zugriff", "box_zugriff_gegen",
                      "abschlussqualitaet", "abschlussqualitaet_gegen"],
         "abgeleitet": [], "modell": {"typ": "logit", "l2": 1.0}, "standardisierung": "gruppe",
         "erwartung": "Mehr Merkmale, aber kaum mehr Trennschaerfe."},
        {"name": "xPoints", "begruendung": "Erwartete Punkte aus der Schussliste als Einzelmerkmal.",
         "merkmale": ["xpoints"], "abgeleitet": [], "modell": {"typ": "logit", "l2": 1.0},
         "standardisierung": "gruppe", "erwartung": "Aehnlich stark wie die npxG-Differenz."},
    ]
