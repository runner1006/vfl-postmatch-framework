"""Die Selbstlern-Schleife: vorschlagen -> rechnen -> bewerten -> merken -> reflektieren.

Eine Runde je Aufgabe:
  1. Kontext bauen: Merkmalskatalog, Benchmark, die selbst geschriebenen
     Erkenntnisse, die Rangliste bisheriger Experimente.
  2. Der Forscher schlaegt N Hypothesen vor.
  3. Jede wird geprueft (rechenbar? schon bekannt?), kreuzvalidiert und ins
     Gedaechtnis geschrieben. Schlaegt sie das bisher beste Modell, wird das
     Endmodell neu gefittet und abgelegt.
Nach allen Aufgaben schreibt der Forscher die Erkenntnisse neu - die Fassung,
die er in der naechsten Runde vorgelegt bekommt.

Faellt der Online-Forscher aus (kein Schluessel, Netz, Ratenlimit), springt
der Offline-Forscher fuer diese Runde ein. Die Schleife bricht nie an einem
einzelnen Vorschlag ab: ein Fehler wird als Experiment mit Status notiert.
"""
import datetime as dt
import traceback

from .bewertung import bewerten, endmodell, lern_und_pruefmenge
from .daten import AUFGABEN, katalog, lade
from .forscher import ForscherFehler, OfflineForscher
from .gedaechtnis import Gedaechtnis
from .hypothese import pruefen


class Schleife:
    def __init__(self, forscher, gedaechtnis=None, aufgaben=AUFGABEN, vorschlaege=3,
                 ausgabe=print, ersatz=None):
        self.forscher = forscher
        self.ged = gedaechtnis or Gedaechtnis()
        self.aufgaben = tuple(aufgaben)
        self.n = int(vorschlaege)
        self.sag = ausgabe or (lambda *a: None)
        self.ersatz = ersatz or OfflineForscher(seed=1)
        self._tabellen = {}

    def tabelle(self, aufgabe):
        if aufgabe not in self._tabellen:
            self._tabellen[aufgabe] = lade(aufgabe)
        return self._tabellen[aufgabe]

    # ---------------------------------------------------------------- Kontext
    def kontext(self, aufgabe, runde):
        t = self.tabelle(aufgabe)
        lern, _ = lern_und_pruefmenge(t)
        return {"aufgabe": aufgabe, "tabelle": t, "runde": runde, "anzahl": self.n,
                "katalog": katalog(t), "benchmark": t.benchmark, "n_lern": len(lern),
                "erkenntnisse": self.ged.erkenntnisse(),
                "rangliste": self.ged.rangliste(aufgabe),
                "rangliste_text": self.ged.zusammenfassung(aufgabe),
                "kennungen": self.ged.kennungen(aufgabe),
                "bestes": self.ged.bestes(aufgabe)}

    # ------------------------------------------------------------------ Runde
    def runde(self, nr):
        zusammen = {"runde": nr, "je_aufgabe": {}}
        for aufgabe in self.aufgaben:
            t = self.tabelle(aufgabe)
            kontext = self.kontext(aufgabe, nr)
            quelle = self.forscher.name
            try:
                vorschlaege = self.forscher.vorschlagen(kontext)
            except ForscherFehler as e:
                self.sag("  ! %s - Offline-Forscher springt ein" % e)
                quelle = self.ersatz.name + " (Ersatz)"
                vorschlaege = self.ersatz.vorschlagen(kontext)
            self.sag("Runde %d · %s · %d Vorschlaege von %s" % (nr, aufgabe, len(vorschlaege), quelle))
            best = self.ged.bestes(aufgabe)
            bekannt = set(kontext["kennungen"])
            neu = []
            for v in vorschlaege:
                exp = {"runde": nr, "aufgabe": aufgabe, "forscher": quelle}
                hyp, fehler = pruefen(v, t)
                if fehler:
                    exp.update({"status": "abgelehnt", "name": str((v or {}).get("name", "?"))[:80],
                                "vorschlag": v, "fehler": fehler})
                    self.sag("  x %-40s abgelehnt: %s" % (exp["name"], "; ".join(fehler)))
                elif hyp["kennung"] in bekannt:
                    exp.update({"status": "doppelt", "name": hyp["name"], "hypothese": hyp,
                                "fehler": ["bereits gerechnet"]})
                    self.sag("  = %-40s schon bekannt" % hyp["name"])
                else:
                    bekannt.add(hyp["kennung"])
                    try:
                        erg = bewerten(t, hyp)
                    except Exception as e:  # ein kaputter Vorschlag darf die Runde nicht stoppen
                        exp.update({"status": "fehlgeschlagen", "name": hyp["name"], "hypothese": hyp,
                                    "fehler": [str(e)], "traceback": traceback.format_exc()[-800:]})
                        self.sag("  ! %-40s Rechenfehler: %s" % (hyp["name"], e))
                        self.ged.merken(exp)
                        neu.append(exp)
                        continue
                    exp.update({"status": "ok", "name": hyp["name"], "hypothese": hyp, "ergebnis": erg,
                                "bestes_bisher": False})
                    vergleich = "" if not best else " (bisher %s)" % best["hauptmetrik"]
                    if best is None or erg["hauptmetrik"] < best["hauptmetrik"]:
                        exp["bestes_bisher"] = True
                        best = self.ged.bestes_setzen(aufgabe, endmodell(t, hyp), exp)
                        vergleich += " NEUES BESTES"
                    self.sag("  · %-40s Log-Loss %.4f%s  [%.1fs]" % (
                        hyp["name"][:40], erg["hauptmetrik"], vergleich, erg["dauer_s"]))
                self.ged.merken(exp)
                neu.append(exp)
            zusammen["je_aufgabe"][aufgabe] = {
                "neu": neu, "bestes": best["hauptmetrik"] if best else None,
                "verbessert": any(e.get("bestes_bisher") for e in neu),
                "ok": sum(1 for e in neu if e["status"] == "ok"),
                "abgelehnt": sum(1 for e in neu if e["status"] == "abgelehnt"),
                "doppelt": sum(1 for e in neu if e["status"] == "doppelt"),
                "fehlgeschlagen": sum(1 for e in neu if e["status"] == "fehlgeschlagen"),
                "forscher": quelle}
        return zusammen

    # ------------------------------------------------------------ Reflexion
    def reflektieren(self, zusammen):
        nr = zusammen["runde"]
        kontext = {"runde": nr, "erkenntnisse_alt": self.ged.erkenntnisse(), "je_aufgabe": {}}
        for aufgabe in self.aufgaben:
            kontext["je_aufgabe"][aufgabe] = {
                "rangliste": self.ged.rangliste(aufgabe),
                "rangliste_text": self.ged.zusammenfassung(aufgabe),
                "benchmark": self.tabelle(aufgabe).benchmark,
                "neu": zusammen["je_aufgabe"][aufgabe]["neu"]}
        quelle = self.forscher.name
        try:
            text = self.forscher.reflektieren(kontext)
        except ForscherFehler as e:
            self.sag("  ! %s - Offline-Destillation ersetzt die Reflexion" % e)
            quelle = self.ersatz.name + " (Ersatz)"
            text = self.ersatz.reflektieren(kontext)
        self.ged.erkenntnisse_schreiben(text, nr, quelle)
        self.sag("  Erkenntnisse neu geschrieben von %s (%d Zeichen)" % (quelle, len(text)))
        return text

    # ---------------------------------------------------------------- Lernen
    def lernen(self, runden):
        start = self.ged.naechste_runde()
        verlauf = []
        for nr in range(start, start + int(runden)):
            zusammen = self.runde(nr)
            self.reflektieren(zusammen)
            eintrag = {"runde": nr, "zeit": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                       "forscher": self.forscher.name,
                       "je_aufgabe": {a: {k: v for k, v in z.items() if k != "neu"}
                                      for a, z in zusammen["je_aufgabe"].items()}}
            self.ged.verlauf_anfuegen(eintrag)
            verlauf.append(eintrag)
        return verlauf
