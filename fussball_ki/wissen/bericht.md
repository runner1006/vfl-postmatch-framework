# Fussball-KI - Lernbericht

Stand: 18.09.2026 18:26 UTC. Automatisch erzeugt aus `wissen/`.

## Aufgabe `spiel`

**Bestes Modell:** npxG-Bilanz + DT2_gefaehrl_verluste - gefunden in Runde 6 von offline.

> Offline-Suche, Runde 6: Merkmal DT2_gefaehrl_verluste hinzugefuegt (Elternteil: npxG-Bilanz)

| | Lernmenge (CV, n=238) | Pruefmenge (n=60) |
|---|---|---|
| Log-Loss Modell | 0.8616 | 1.0481 |
| Log-Loss Basisrate | 1.0334 | 1.0540 |
| Log-Loss Framework-Poisson | 0.8846 | 0.9959 |
| Trefferquote | 0.588 | 0.533 |
| Brier | 0.5074 | 0.6181 |

Merkmale: `npxg`, `npxg_geg`, `DT2_gefaehrl_verluste`. Modell: `{"l2": 1.0, "typ": "logit"}`, Standardisierung global.

### Was das Modell gelernt hat (standardisierte Logit-Koeffizienten)

Referenzklasse ist `Sieg`; ein Koeffizient von +0,5 heisst: eine Standardabweichung mehr hebt den Logit dieser Klasse gegenueber der Referenz um 0,5.

- **Niederlage**: npxg_geg +1.24, npxg -0.97, DT2_gefaehrl_verluste +0.51
- **Remis**: npxg -0.74, npxg_geg +0.47, DT2_gefaehrl_verluste +0.23

### Rangliste (Top 10 von 31 gerechneten Hypothesen)

| # | Runde | Hypothese | Log-Loss CV | Merkmale | Modell |
|---|---|---|---|---|---|
| 1 | 6 | npxG-Bilanz + DT2_gefaehrl_verluste | 0.8616 | 3 | logit |
| 2 | 8 | npxG-Bilanz + DT2_gefaehrl_verluste + ph_def_umschalten | 0.8659 | 4 | logit |
| 3 | 7 | npxG-Bilanz + DT2_gefaehrl_verluste als MLP | 0.8716 | 3 | mlp |
| 4 | 7 | npxG-Bilanz + ph_off_umschalten | 0.8726 | 3 | logit |
| 5 | 7 | npxG-Bilanz + geg_recov_hoch | 0.8738 | 3 | logit |
| 6 | 1 | npxG-Bilanz | 0.8746 | 2 | logit |
| 7 | 1 | npxG plus Kontext | 0.8748 | 7 | logit |
| 8 | 3 | npxG-Bilanz (l2=3.0) | 0.8756 | 2 | logit |
| 9 | 4 | npxG-Bilanz + OT2_tiefenertrag | 0.8764 | 3 | logit |
| 10 | 3 | npxG plus Kontext - heim | 0.8765 | 6 | logit |

## Aufgabe `aufstieg`

**Bestes Modell:** xPoints (global-z) - gefunden in Runde 6 von offline.

> Offline-Suche, Runde 6: Standardisierung auf global (Elternteil: xPoints (l2 halbiert))

| | Lernmenge (CV, n=144) | Pruefmenge (n=18) |
|---|---|---|
| Log-Loss Modell | 0.2695 | 0.1583 |
| Log-Loss Basisrate | 0.4507 | 0.4506 |
| AUC (Mittel je Saison) | 0.903 | 0.978 |
| Top-3-Treffer | 13 von 24 | 2 von 3 |
| Brier | 0.1757 | 0.0865 |

Merkmale: `xpoints`. Modell: `{"l2": 0.25, "typ": "logit"}`, Standardisierung global.

### Was das Modell gelernt hat (standardisierte Logit-Koeffizienten)

Aus Sicht von `Top-3`: ein Koeffizient von +0,5 heisst, eine Standardabweichung mehr hebt den Logit fuer `Top-3` um 0,5.

- **Top-3**: xpoints +2.30

### Rangliste (Top 10 von 31 gerechneten Hypothesen)

| # | Runde | Hypothese | Log-Loss CV | Merkmale | Modell |
|---|---|---|---|---|---|
| 1 | 6 | xPoints (global-z) | 0.2695 | 1 | logit |
| 2 | 5 | xPoints (global-z) | 0.2696 | 1 | logit |
| 3 | 3 | xPoints (l2 halbiert) | 0.2731 | 1 | logit |
| 4 | 4 | xPoints (l2 halbiert) | 0.2731 | 1 | logit |
| 5 | 6 | xPoints (l2 halbiert) | 0.2733 | 1 | logit |
| 6 | 8 | xPoints (l2=0.15) | 0.2733 | 1 | logit |
| 7 | 5 | xPoints (l2=0.75) | 0.2735 | 1 | logit |
| 8 | 8 | xPoints (l2=0.05) | 0.2735 | 1 | logit |
| 9 | 6 | xPoints (l2=0.025) | 0.2736 | 1 | logit |
| 10 | 8 | xPoints + schuesse | 0.2739 | 2 | logit |

## Lernkurve

| Runde | Forscher | spiel | aufstieg |
|---|---|---|---|
| 1 | offline | 0.8746 (neu) | 0.2742 (neu) |
| 2 | offline | 0.8746 | 0.2742 |
| 3 | offline | 0.8746 | 0.2731 (neu) |
| 4 | offline | 0.8746 | 0.2731 |
| 5 | offline | 0.8746 | 0.2696 (neu) |
| 6 | offline | 0.8616 (neu) | 0.2695 (neu) |
| 7 | offline | 0.8616 | 0.2695 |
| 8 | offline | 0.8616 | 0.2695 |

## Erkenntnisse - von der KI selbst geschrieben

<!-- geschrieben von offline nach Runde 8, 2026-09-18 18:26 UTC -->
# Erkenntnisse

Automatisch destilliert vom Offline-Forscher nach Runde 8. Aussagen sind Mittelwerte ueber alle bisherigen Experimente, keine Kausalbefunde.

## Aufgabe spiel
**Bestes Modell:** npxG-Bilanz + DT2_gefaehrl_verluste (Log-Loss CV 0.8616, Basisrate 1.0334, Framework 0.8846).
Benchmark des Frameworks: {"quelle": "Poisson-Modell des Frameworks (psieg/premis/pnied aus npxG)", "logloss": 0.907, "n": 298}

### Was traegt
- npxg: Modelle mit diesem Merkmal im Mittel 0.1363 besser (n=26)
- npxg_geg: Modelle mit diesem Merkmal im Mittel 0.1250 besser (n=25)
- geg_def: Modelle mit diesem Merkmal im Mittel 0.0292 besser (n=6)
- blockhoehe: Modelle mit diesem Merkmal im Mittel 0.0292 besser (n=6)
- geg_off: Modelle mit diesem Merkmal im Mittel 0.0292 besser (n=6)
- DT2_gefaehrl_verluste: Modelle mit diesem Merkmal im Mittel 0.0216 besser (n=5)

### Was nicht traegt
- ph_defensiv: Modelle mit diesem Merkmal im Mittel 0.1523 schlechter (n=4)
- ph_offensiv: Modelle mit diesem Merkmal im Mittel 0.1523 schlechter (n=4)
- ph_physisch: Modelle mit diesem Merkmal im Mittel 0.1523 schlechter (n=4)
- ph_def_umschalten: Modelle mit diesem Merkmal im Mittel 0.1013 schlechter (n=4)
- ph_off_umschalten: Modelle mit diesem Merkmal im Mittel 0.0969 schlechter (n=6)
- heim: Modelle mit diesem Merkmal im Mittel 0.0659 schlechter (n=9)

### Modelltypen
- logit: bestes 0.8616, Mittel 0.9055 ueber 24 Experimente
- mlp: bestes 0.8716, Mittel 0.9175 ueber 7 Experimente

### Regeln fuer die naechste Runde
- Vom besten Modell ausgehen; Kern behalten: npxg, npxg_geg, DT2_gefaehrl_verluste.
- Merkmale aus 'Was nicht traegt' nur mit neuer Begruendung erneut pruefen.
- Je Runde mindestens eine Hypothese, die etwas Neues prueft (anderer Modelltyp, abgeleitetes Merkmal, andere Standardisierung).

## Aufgabe aufstieg
**Bestes Modell:** xPoints (global-z) (Log-Loss CV 0.2695, Basisrate 0.4507).
Benchmark des Frameworks: {"quelle": "LOSO-Validierung des Frameworks: Baseline npxG-Differenz", "auc_mittel": 0.899, "brier": 0.0904, "top3_treffer_von_27": 15}

### Was traegt
- xpoints: Modelle mit diesem Merkmal im Mittel 0.0409 besser (n=28)

### Was nicht traegt
- npxg: Modelle mit diesem Merkmal im Mittel 0.0496 schlechter (n=2)
- npxg_gegen: Modelle mit diesem Merkmal im Mittel 0.0496 schlechter (n=2)
- box_zugriff: Modelle mit diesem Merkmal im Mittel 0.0339 schlechter (n=3)
- abschlussqualitaet_gegen: Modelle mit diesem Merkmal im Mittel 0.0336 schlechter (n=3)
- abschlussqualitaet: Modelle mit diesem Merkmal im Mittel 0.0334 schlechter (n=3)
- box_zugriff_gegen: Modelle mit diesem Merkmal im Mittel 0.0250 schlechter (n=4)

### Modelltypen
- logit: bestes 0.2695, Mittel 0.2807 ueber 26 Experimente
- mlp: bestes 0.2744, Mittel 0.2800 ueber 5 Experimente

### Regeln fuer die naechste Runde
- Vom besten Modell ausgehen; Kern behalten: xpoints.
- Merkmale aus 'Was nicht traegt' nur mit neuer Begruendung erneut pruefen.
- Je Runde mindestens eine Hypothese, die etwas Neues prueft (anderer Modelltyp, abgeleitetes Merkmal, andere Standardisierung).
