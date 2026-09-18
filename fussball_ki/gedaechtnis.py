"""Gedaechtnis der KI - alles, was zwischen zwei Runden ueberlebt.

    wissen/experimente.jsonl   jede gerechnete oder abgelehnte Hypothese samt Ergebnis
    wissen/erkenntnisse.md     das Wissen, das der Forscher sich selbst schreibt und
                               in der naechsten Runde woertlich vorgelegt bekommt
    wissen/bestes_<aufgabe>.json  das beste Modell je Aufgabe, fertig fuer `vorhersage`
    wissen/verlauf.json        Lernkurve: je Runde die beste Hauptmetrik

Alles Klartext, damit sich jeder Lernschritt im Git-Verlauf nachlesen laesst.
"""
import datetime as dt
import json
import os

HIER = os.path.dirname(os.path.abspath(__file__))
WISSEN = os.path.join(HIER, "wissen")

ERKENNTNISSE_LEER = """# Erkenntnisse

Noch keine. Diese Datei schreibt die KI nach jeder Lernrunde selbst neu; sie
ist ihr einziges Langzeitgedaechtnis ueber Zahlen hinaus.
"""


class Gedaechtnis:
    def __init__(self, pfad=WISSEN):
        self.pfad = pfad
        os.makedirs(pfad, exist_ok=True)
        self._exp = os.path.join(pfad, "experimente.jsonl")
        self._erk = os.path.join(pfad, "erkenntnisse.md")
        self._verlauf = os.path.join(pfad, "verlauf.json")

    # ------------------------------------------------------------ Experimente
    def experimente(self, aufgabe=None, nur_ok=False):
        out = []
        if not os.path.exists(self._exp):
            return out
        with open(self._exp, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile:
                    continue
                e = json.loads(zeile)
                if aufgabe and e.get("aufgabe") != aufgabe:
                    continue
                if nur_ok and e.get("status") != "ok":
                    continue
                out.append(e)
        return out

    def merken(self, experiment):
        experiment.setdefault("zeit", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        with open(self._exp, "a", encoding="utf-8") as f:
            f.write(json.dumps(experiment, ensure_ascii=False, sort_keys=True) + "\n")
        return experiment

    def kennungen(self, aufgabe):
        return {e["hypothese"]["kennung"] for e in self.experimente(aufgabe)
                if e.get("hypothese") and e["hypothese"].get("kennung")}

    def rangliste(self, aufgabe):
        """Erfolgreiche Experimente, beste zuerst (Hauptmetrik: kleiner ist besser)."""
        ok = self.experimente(aufgabe, nur_ok=True)
        return sorted(ok, key=lambda e: e["ergebnis"]["hauptmetrik"])

    # ----------------------------------------------------------- Erkenntnisse
    def erkenntnisse(self):
        if not os.path.exists(self._erk):
            return ERKENNTNISSE_LEER
        with open(self._erk, encoding="utf-8") as f:
            return f.read()

    def erkenntnisse_schreiben(self, text, runde, quelle):
        kopf = "<!-- geschrieben von %s nach Runde %d, %s -->\n" % (
            quelle, runde, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        with open(self._erk, "w", encoding="utf-8") as f:
            f.write(kopf + text.strip() + "\n")

    # ------------------------------------------------------------- Bestes
    def _bestes_pfad(self, aufgabe):
        return os.path.join(self.pfad, "bestes_%s.json" % aufgabe)

    def bestes(self, aufgabe):
        p = self._bestes_pfad(aufgabe)
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def bestes_setzen(self, aufgabe, endmodell, experiment):
        eintrag = {"aufgabe": aufgabe, "hauptmetrik": experiment["ergebnis"]["hauptmetrik"],
                   "runde": experiment.get("runde"), "forscher": experiment.get("forscher"),
                   "zeit": experiment.get("zeit"), "ergebnis": experiment["ergebnis"],
                   "endmodell": endmodell}
        with open(self._bestes_pfad(aufgabe), "w", encoding="utf-8") as f:
            json.dump(eintrag, f, ensure_ascii=False, indent=1, sort_keys=True)
        return eintrag

    # ------------------------------------------------------------- Verlauf
    def verlauf(self):
        if not os.path.exists(self._verlauf):
            return []
        with open(self._verlauf, encoding="utf-8") as f:
            return json.load(f)

    def verlauf_anfuegen(self, eintrag):
        v = self.verlauf()
        v.append(eintrag)
        with open(self._verlauf, "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False, indent=1)
        return v

    def naechste_runde(self):
        v = self.verlauf()
        return (max(e["runde"] for e in v) + 1) if v else 1

    # ---------------------------------------------------- Text fuer Prompts
    def zusammenfassung(self, aufgabe, limit=12):
        """Rangliste als Text: die besten `limit` plus die letzten drei Runden.
        Zeigt nur Lernmengen-Metriken - die Pruefmenge bleibt dem Forscher verborgen."""
        rang = self.rangliste(aufgabe)
        alle = self.experimente(aufgabe)
        if not alle:
            return "Noch keine Experimente."
        gezeigt = rang[:limit]
        kennungen = {e["hypothese"]["kennung"] for e in gezeigt}
        letzte_runde = max(e.get("runde", 0) for e in alle)
        for e in rang:
            if e.get("runde", 0) >= letzte_runde - 2 and e["hypothese"]["kennung"] not in kennungen:
                gezeigt.append(e)
                kennungen.add(e["hypothese"]["kennung"])
        zeilen = ["Rang | Runde | Name | Hauptmetrik (Log-Loss CV) | weitere Metriken | Merkmale | Modell"]
        for i, e in enumerate(gezeigt):
            r = e["ergebnis"]
            hyp = e["hypothese"]
            weitere = ", ".join("%s=%s" % (k, v) for k, v in r["metriken"].items()
                                if k not in ("logloss",) and not k.startswith("logloss_auf"))
            merk = ", ".join(hyp["merkmale"] + ["%s=%s" % (a["name"], a["formel"]) for a in hyp["abgeleitet"]])
            modell = json.dumps(hyp["modell"], sort_keys=True) + " / " + hyp["standardisierung"]
            rangnr = rang.index(e) + 1
            zeilen.append("%d | %s | %s | %s | %s | %s | %s" % (
                rangnr, e.get("runde"), hyp["name"], r["hauptmetrik"], weitere, merk, modell))
        abgelehnt = [e for e in alle if e.get("status") == "abgelehnt"]
        if abgelehnt:
            zeilen.append("")
            zeilen.append("Abgelehnte Vorschlaege (nicht rechenbar), zuletzt:")
            for e in abgelehnt[-5:]:
                zeilen.append("- %s: %s" % (e.get("name", "?"), "; ".join(e.get("fehler", []))))
        doppelt = sum(1 for e in alle if e.get("status") == "doppelt")
        if doppelt:
            zeilen.append("")
            zeilen.append("%d Vorschlaege waren Wiederholungen bereits gerechneter Hypothesen." % doppelt)
        return "\n".join(zeilen)
