"""Hypothesen: was der Forscher vorschlaegt und was der Rechenkern annimmt.

Eine Hypothese ist ein Bauplan fuer ein Prognosemodell - Merkmale,
abgeleitete Merkmale als Formeln, Modelltyp (logit, mlp, poisson) und
Regularisierung - plus eine Begruendung in Worten. Der Forscher (Sprachmodell oder Offline-Suche) liefert sie als
JSON; `pruefen` normalisiert und weist alles ab, was nicht rechenbar ist.
So kann das Sprachmodell nichts ausfuehren, nur vorschlagen.
"""
import hashlib
import json
import re

from .formeln import FormelFehler
from .formeln import pruefen as formel_pruefen

MAX_MERKMALE = 25
MODELLTYPEN = ("logit", "mlp", "poisson")
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
    das Elo-Wissen als Ausgangspunkt, nicht als Ziel."""
    logit = {"typ": "logit", "l2": 1.0}
    if aufgabe == "ergebnis":
        return [
            {"name": "Elo allein", "begruendung": "Elo buendelt die gesamte Ergebnishistorie in einer "
             "Zahl; der klassische Ausgangspunkt jeder Ergebnisprognose.",
             "merkmale": ["elo_diff"], "abgeleitet": [], "modell": logit,
             "standardisierung": "global", "erwartung": "Deutlich unter der Basisrate, nahe am Elo-Benchmark."},
            {"name": "Elo plus Form", "begruendung": "Kurzfristige Form traegt Information, die Elo "
             "nur langsam aufnimmt.",
             "merkmale": ["elo_diff", "form5_punkte_diff", "form10_tordiff_heim", "form10_tordiff_gast"],
             "abgeleitet": [], "modell": logit, "standardisierung": "global",
             "erwartung": "Kleiner Gewinn gegenueber Elo allein."},
            {"name": "Poisson auf Elo und Saisonstand", "begruendung": "Torraten statt Klassen: "
             "das Poisson-Modell nutzt die Tore beider Teams, nicht nur das Ergebnis.",
             "merkmale": ["elo_heim", "elo_gast", "saison_tordiff_heim", "saison_tordiff_gast", "liga"],
             "abgeleitet": [], "modell": {"typ": "poisson", "l2": 1.0}, "standardisierung": "global",
             "erwartung": "Aehnlich wie das Logit, besser kalibrierte Unentschieden."},
        ]
    return [
        {"name": "Torform beider Teams", "begruendung": "Viele Tore fallen, wenn beide Teams "
         "zuletzt viele Tore erzielt und kassiert haben.",
         "merkmale": ["form5_tore_heim", "form5_gegentore_heim", "form5_tore_gast", "form5_gegentore_gast", "liga"],
         "abgeleitet": [], "modell": logit, "standardisierung": "global",
         "erwartung": "Knapp unter der Basisrate."},
        {"name": "Poisson Torraten", "begruendung": "Das Poisson-Modell rechnet die Summe beider "
         "Torraten direkt in eine Ueber/Unter-Wahrscheinlichkeit um.",
         "merkmale": ["elo_heim", "elo_gast", "form10_tordiff_heim", "form10_tordiff_gast", "liga"],
         "abgeleitet": [], "modell": {"typ": "poisson", "l2": 1.0}, "standardisierung": "global",
         "erwartung": "Etwas besser als das Logit auf denselben Merkmalen."},
        {"name": "Elo-Gefaelle", "begruendung": "Ungleiche Paarungen bringen mehr Tore.",
         "merkmale": ["elo_diff", "liga"], "abgeleitet": [{"name": "elo_abstand", "formel": "abs(elo_diff)"}],
         "modell": logit, "standardisierung": "global", "erwartung": "Schwach, aber ueber der Basisrate."},
    ]
