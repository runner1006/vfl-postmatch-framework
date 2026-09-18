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
