"""Berichte aus dem Gedaechtnis: Kurzstatus fuer die Konsole, Markdown fuer Menschen."""
import datetime as dt
import json
import os

from .daten import AUFGABEN
from .gedaechtnis import WISSEN


def _f(v, stellen=4):
    if v is None:
        return "-"
    if isinstance(v, float):
        return ("%%.%df" % stellen) % v
    return str(v)


def _zeile_metriken(m):
    schluessel = ["logloss", "logloss_basis", "logloss_framework", "brier", "treffer",
                  "auc_mittel", "auc_min", "auc_gesamt", "top3_treffer", "top3_von"]
    return ", ".join("%s %s" % (k, _f(m[k])) for k in schluessel if k in m)


def status_text(ged):
    zeilen = []
    verlauf = ged.verlauf()
    zeilen.append("Runden gelernt: %d" % len(verlauf))
    for aufgabe in AUFGABEN:
        best = ged.bestes(aufgabe)
        alle = ged.experimente(aufgabe)
        ok = [e for e in alle if e["status"] == "ok"]
        zeilen.append("")
        zeilen.append("[%s] %d Experimente (%d gerechnet, %d abgelehnt, %d doppelt)" % (
            aufgabe, len(alle), len(ok), sum(1 for e in alle if e["status"] == "abgelehnt"),
            sum(1 for e in alle if e["status"] == "doppelt")))
        if not best:
            zeilen.append("  noch kein Modell")
            continue
        h = best["endmodell"]["hypothese"]
        zeilen.append("  bestes: %s (Runde %s, %s)" % (h["name"], best.get("runde"), best.get("forscher")))
        zeilen.append("  Merkmale: %s" % ", ".join(best["endmodell"]["merkmale"]))
        zeilen.append("  Modell: %s / %s" % (json.dumps(h["modell"], sort_keys=True), h["standardisierung"]))
        zeilen.append("  Lernmenge (CV): %s" % _zeile_metriken(best["ergebnis"]["metriken"]))
        zeilen.append("  Pruefmenge:     %s" % _zeile_metriken(best["ergebnis"]["pruef"]))
    if verlauf:
        zeilen.append("")
        zeilen.append("Lernkurve (beste Hauptmetrik je Runde):")
        for e in verlauf:
            zeilen.append("  Runde %2d  %s" % (e["runde"], "  ".join(
                "%s %s%s" % (a, _f(z.get("bestes")), "*" if z.get("verbessert") else "")
                for a, z in e["je_aufgabe"].items())))
    return "\n".join(zeilen)


def bericht_markdown(ged):
    t = ["# Fussball-KI - Lernbericht", "",
         "Stand: %s. Automatisch erzeugt aus `wissen/`." % dt.datetime.now(dt.timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
         ""]
    verlauf = ged.verlauf()
    for aufgabe in AUFGABEN:
        best = ged.bestes(aufgabe)
        rang = ged.rangliste(aufgabe)
        t.append("## Aufgabe `%s`" % aufgabe)
        t.append("")
        if not best:
            t.append("Noch kein Modell.")
            t.append("")
            continue
        h = best["endmodell"]["hypothese"]
        m, p = best["ergebnis"]["metriken"], best["ergebnis"]["pruef"]
        t.append("**Bestes Modell:** %s - gefunden in Runde %s von %s." % (h["name"], best.get("runde"), best.get("forscher")))
        t.append("")
        t.append("> %s" % h.get("begruendung", "").replace("\n", " "))
        t.append("")
        t.append("| | Lernmenge (CV, n=%d) | Pruefmenge (n=%d) |" % (best["ergebnis"]["n_lern"], best["ergebnis"]["n_pruef"]))
        t.append("|---|---|---|")
        t.append("| Log-Loss Modell | %s | %s |" % (_f(m.get("logloss")), _f(p.get("logloss"))))
        t.append("| Log-Loss Basisrate | %s | %s |" % (_f(m.get("logloss_basis")), _f(p.get("logloss_basis"))))
        if "logloss_framework" in m:
            t.append("| Log-Loss Framework-Poisson | %s | %s |" % (_f(m.get("logloss_framework")), _f(p.get("logloss_framework"))))
        if "treffer" in m:
            t.append("| Trefferquote | %s | %s |" % (_f(m.get("treffer"), 3), _f(p.get("treffer"), 3)))
        if "auc_mittel" in m:
            t.append("| AUC (Mittel je Saison) | %s | %s |" % (_f(m.get("auc_mittel"), 3), _f(p.get("auc_mittel"), 3)))
            t.append("| Top-3-Treffer | %s von %s | %s von %s |" % (m.get("top3_treffer"), m.get("top3_von"), p.get("top3_treffer"), p.get("top3_von")))
        t.append("| Brier | %s | %s |" % (_f(m.get("brier")), _f(p.get("brier"))))
        t.append("")
        t.append("Merkmale: %s. Modell: `%s`, Standardisierung %s." % (
            ", ".join("`%s`" % x for x in best["endmodell"]["merkmale"]),
            json.dumps(h["modell"], sort_keys=True), h["standardisierung"]))
        if h.get("abgeleitet"):
            t.append("")
            t.append("Abgeleitete Merkmale: " + "; ".join("`%s = %s`" % (a["name"], a["formel"]) for a in h["abgeleitet"]))
        t.append("")
        ko = best["endmodell"].get("koeffizienten")
        if ko:
            t.append("### Was das Modell gelernt hat (standardisierte Logit-Koeffizienten)")
            t.append("")
            klassen = best["endmodell"]["klassen"]
            if len(klassen) == 2:
                t.append("Aus Sicht von `%s`: ein Koeffizient von +0,5 heisst, eine Standardabweichung mehr "
                         "hebt den Logit fuer `%s` um 0,5." % (klassen[1], klassen[1]))
            else:
                t.append("Referenzklasse ist `%s`; ein Koeffizient von +0,5 heisst: eine Standardabweichung mehr "
                         "hebt den Logit dieser Klasse gegenueber der Referenz um 0,5." % klassen[-1])
            t.append("")
            for klasse, ks in ko.items():
                oben = sorted(((k, v) for k, v in ks.items() if k != "achse"), key=lambda kv: -abs(kv[1]))[:8]
                t.append("- **%s**: " % klasse + ", ".join("%s %+.2f" % kv for kv in oben))
            t.append("")
        t.append("### Rangliste (Top 10 von %d gerechneten Hypothesen)" % len(rang))
        t.append("")
        t.append("| # | Runde | Hypothese | Log-Loss CV | Merkmale | Modell |")
        t.append("|---|---|---|---|---|---|")
        for i, e in enumerate(rang[:10], 1):
            hyp = e["hypothese"]
            t.append("| %d | %s | %s | %s | %d | %s |" % (
                i, e.get("runde"), hyp["name"].replace("|", "/"), _f(e["ergebnis"]["hauptmetrik"]),
                len(hyp["merkmale"]) + len(hyp["abgeleitet"]), hyp["modell"]["typ"]))
        t.append("")
    if verlauf:
        t.append("## Lernkurve")
        t.append("")
        t.append("| Runde | Forscher | " + " | ".join(AUFGABEN) + " |")
        t.append("|---|---|" + "---|" * len(AUFGABEN))
        for e in verlauf:
            t.append("| %d | %s | %s |" % (e["runde"], e.get("forscher", "-"), " | ".join(
                "%s%s" % (_f(e["je_aufgabe"].get(a, {}).get("bestes")),
                          " (neu)" if e["je_aufgabe"].get(a, {}).get("verbessert") else "")
                for a in AUFGABEN)))
        t.append("")
    t.append("## Erkenntnisse - von der KI selbst geschrieben")
    t.append("")
    t.append(ged.erkenntnisse().strip())
    t.append("")
    return "\n".join(t)


def bericht_schreiben(ged, pfad=None):
    pfad = pfad or os.path.join(ged.pfad if hasattr(ged, "pfad") else WISSEN, "bericht.md")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(bericht_markdown(ged))
    return pfad
