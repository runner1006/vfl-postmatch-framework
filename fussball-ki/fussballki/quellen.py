"""Datenaktualisierung: Saisondateien direkt aus openfootball/deutschland holen."""
import datetime as dt
import os
import urllib.error
import urllib.request

from .daten import DATEN, LIGEN

BASIS = "https://raw.githubusercontent.com/openfootball/deutschland/master/%s/%s"
ERSTE_SAISON = 2010


def saisonliste(bis_jahr=None):
    bis_jahr = bis_jahr or dt.date.today().year + (1 if dt.date.today().month >= 7 else 0)
    return ["%d-%02d" % (j, (j + 1) % 100) for j in range(ERSTE_SAISON, bis_jahr)]


def holen(saisons=None, verzeichnis=None, ausgabe=print):
    verzeichnis = verzeichnis or DATEN
    geholt, fehlend = [], []
    for saison in saisons or saisonliste():
        for datei in LIGEN:
            url = BASIS % (saison, datei)
            try:
                with urllib.request.urlopen(url, timeout=30) as antwort:
                    text = antwort.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    fehlend.append("%s/%s" % (saison, datei))
                    continue
                raise
            ordner = os.path.join(verzeichnis, saison)
            os.makedirs(ordner, exist_ok=True)
            with open(os.path.join(ordner, datei), "w", encoding="utf-8") as f:
                f.write(text.replace("\r\n", "\n").replace("\r", "\n"))
            geholt.append("%s/%s" % (saison, datei))
            ausgabe("  %s/%s" % (saison, datei))
    with open(os.path.join(verzeichnis, "STAND"), "w", encoding="utf-8") as f:
        f.write(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + "\n")
    return geholt, fehlend
