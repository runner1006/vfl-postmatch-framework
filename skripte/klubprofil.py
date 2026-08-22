"""Klubprofile: die Konfiguration, die aus dem Framework ein Produkt macht.

Ein Profil in `klubs/<slug>.json` beschreibt einen Klub vollstaendig — Name,
Farbe, Spielidee, Datenquelle und Zielreferenz. Die Report-Engine kennt keinen
einzigen Klub im Code; sie kennt nur Profile. Ein neuer Klub ist eine neue
JSON-Datei, kein neuer Python-Zweig.
"""
import json
import os

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLUBS = os.path.join(WURZEL, "klubs")
ERGEBNISSE = os.path.join(WURZEL, "ergebnisse")

PFLICHT = ("slug", "name", "kurz", "kuerzel", "farbe", "spielidee", "quelle")


class ProfilFehler(ValueError):
    """Ein Profil ist unvollstaendig oder widerspricht der Datenlage."""


def pfad(slug):
    return os.path.join(KLUBS, f"{slug}.json")


def slugs():
    """Alle vorhandenen Profile, alphabetisch."""
    if not os.path.isdir(KLUBS):
        return []
    return sorted(f[:-5] for f in os.listdir(KLUBS) if f.endswith(".json"))


def lade(slug):
    """Liest ein Profil und prueft es gegen die Pflichtfelder."""
    p = pfad(slug)
    if not os.path.exists(p):
        vorhanden = ", ".join(slugs()) or "keine"
        raise ProfilFehler(f"Kein Profil '{slug}' in {KLUBS} (vorhanden: {vorhanden})")
    with open(p, encoding="utf-8") as f:
        prof = json.load(f)
    fehlt = [k for k in PFLICHT if not prof.get(k)]
    if fehlt:
        raise ProfilFehler(f"Profil '{slug}': Pflichtfelder fehlen -> {', '.join(fehlt)}")
    if prof["slug"] != slug:
        raise ProfilFehler(f"Profil '{slug}': Feld 'slug' lautet '{prof['slug']}'")
    if not prof["quelle"].get("team_key"):
        raise ProfilFehler(f"Profil '{slug}': quelle.team_key fehlt")
    prof.setdefault("farbe_kontrast", "#ffffff")
    prof.setdefault("ziel", {})
    prof.setdefault("hinweise", [])
    return prof


def alle():
    return [lade(s) for s in slugs()]
