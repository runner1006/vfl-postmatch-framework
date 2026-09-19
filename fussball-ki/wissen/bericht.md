# Fussball-KI - Lernbericht

Stand: 18.09.2026 18:46 UTC. Automatisch erzeugt aus `wissen/`.

## Aufgabe `ergebnis`

**Bestes Modell:** Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim - liga - gefunden in Runde 7 von offline.

> Offline-Suche, Runde 7: Merkmal liga entfernt (Elternteil: Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim)

| | Vorwaertsvalidierung 2015-16-2024-25 (n=6120) | Pruefsaison 2025-26 (n=405) |
|---|---|---|
| Log-Loss Modell | **1.0293** | **0.9854** |
| Log-Loss Elo-Logit | 1.0304 | 0.9824 |
| Log-Loss Basisrate | 1.0747 | 1.0669 |
| Brier | 0.6180 | 0.5860 |
| Trefferquote | 0.478 | 0.533 |

Merkmale: `elo_heim`, `elo_gast`, `saison_tordiff_heim`, `saison_tordiff_gast`, `elo_diff`, `aufsteiger_heim`. Modell: `{"epochen": 150, "l2": 0.01, "lernrate": 0.02, "typ": "mlp", "versteckt": 4}`, Standardisierung global.

### Je Testsaison

| Saison | Log-Loss Modell |
|---|---|
| 2015-16 | 1.0284 |
| 2016-17 | 1.0221 |
| 2017-18 | 1.0584 |
| 2018-19 | 1.0276 |
| 2019-20 | 1.0377 |
| 2020-21 | 1.0230 |
| 2021-22 | 1.0331 |
| 2022-23 | 1.0160 |
| 2023-24 | 0.9996 |
| 2024-25 | 1.0473 |

### Rangliste (Top 10 von 31 gerechneten Hypothesen)

| # | Runde | Hypothese | Log-Loss | Merkmale | Modell |
|---|---|---|---|---|---|
| 1 | 7 | Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim - liga | 1.0293 | 6 | mlp |
| 2 | 5 | Poisson auf Elo und Saisonstand + elo_diff | 1.0295 | 6 | mlp |
| 3 | 8 | Poisson auf Elo und Saisonstand + diff_liga_elo_gast | 1.0295 | 6 | mlp |
| 4 | 8 | Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim + quot_elo_diff_elo | 1.0295 | 7 | mlp |
| 5 | 2 | Poisson auf Elo und Saisonstand als MLP | 1.0296 | 5 | mlp |
| 6 | 6 | Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim | 1.0296 | 7 | mlp |
| 7 | 7 | Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim - elo_heim | 1.0296 | 6 | mlp |
| 8 | 5 | Poisson auf Elo und Saisonstand + vorsaison_platz_gast | 1.0298 | 6 | mlp |
| 9 | 7 | Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim + absteiger_gast | 1.0298 | 8 | mlp |
| 10 | 7 | Poisson auf Elo und Saisonstand (l2=0.003) | 1.0299 | 5 | mlp |

## Aufgabe `tore`

**Bestes Modell:** Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim - liga - gefunden in Runde 8 von offline.

> Offline-Suche, Runde 8: Merkmal liga entfernt (Elternteil: Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim + form5_tordiff_hei)

| | Vorwaertsvalidierung 2015-16-2024-25 (n=6120) | Pruefsaison 2025-26 (n=405) |
|---|---|---|
| Log-Loss Modell | **0.6784** | **0.6549** |
| Log-Loss Elo-Logit | 0.6836 | 0.6741 |
| Log-Loss Basisrate | 0.6842 | 0.6703 |
| Brier | 0.4856 | 0.4642 |
| Trefferquote | 0.565 | 0.627 |
| AUC | 0.560 | 0.529 |

Merkmale: `elo_heim`, `elo_gast`, `form10_tordiff_heim`, `form10_tordiff_gast`, `form5_gegentore_heim`, `spiele_gesamt_heim`, `form5_tordiff_heim`. Modell: `{"l2": 1.0, "typ": "poisson"}`, Standardisierung global.

### Je Testsaison

| Saison | Log-Loss Modell |
|---|---|
| 2015-16 | 0.6864 |
| 2016-17 | 0.6905 |
| 2017-18 | 0.6859 |
| 2018-19 | 0.6896 |
| 2019-20 | 0.6726 |
| 2020-21 | 0.6745 |
| 2021-22 | 0.6695 |
| 2022-23 | 0.6780 |
| 2023-24 | 0.6680 |
| 2024-25 | 0.6694 |

### Was das Modell gelernt hat (standardisierte Koeffizienten)

Log-Torraten: ein Koeffizient von +0,1 heisst, eine Standardabweichung mehr hebt die erwartete Torzahl um etwa 10 %.

- **Gasttore (log-Rate)**: elo_gast +0.201, elo_heim -0.182, spiele_gesamt_heim +0.031, form10_tordiff_gast +0.026, form5_gegentore_heim +0.019, form5_tordiff_heim +0.015, form10_tordiff_heim -0.011
- **Heimtore (log-Rate)**: elo_heim +0.219, elo_gast -0.178, spiele_gesamt_heim +0.031, form5_gegentore_heim +0.030, form10_tordiff_heim +0.027, form5_tordiff_heim +0.027, form10_tordiff_gast -0.003

### Rangliste (Top 10 von 31 gerechneten Hypothesen)

| # | Runde | Hypothese | Log-Loss | Merkmale | Modell |
|---|---|---|---|---|---|
| 1 | 8 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim - liga | 0.6784 | 7 | poisson |
| 2 | 6 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim + form5_tordiff_hei | 0.6787 | 8 | poisson |
| 3 | 7 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim + quot_elo_gast_spi | 0.6787 | 9 | poisson |
| 4 | 8 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim + auswform5_punkte_ | 0.6787 | 9 | poisson |
| 5 | 5 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim | 0.6789 | 7 | poisson |
| 6 | 7 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim + auswform5_punkte_ | 0.6789 | 8 | poisson |
| 7 | 8 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim + form5_punkte_gast | 0.6789 | 8 | poisson |
| 8 | 8 | Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim (l2=0.1) | 0.6789 | 7 | poisson |
| 9 | 2 | Poisson Torraten + form5_gegentore_heim | 0.6794 | 6 | poisson |
| 10 | 5 | Poisson Torraten + form5_gegentore_heim - elo_gast | 0.6794 | 5 | poisson |

## Lernkurve

| Runde | Forscher | ergebnis | tore |
|---|---|---|---|
| 1 | offline | 1.0304 (neu) | 0.6800 (neu) |
| 2 | offline | 1.0296 (neu) | 0.6794 (neu) |
| 3 | offline | 1.0296 | 0.6794 |
| 4 | offline | 1.0296 | 0.6794 |
| 5 | offline | 1.0295 (neu) | 0.6789 (neu) |
| 6 | offline | 1.0295 | 0.6787 (neu) |
| 7 | offline | 1.0293 (neu) | 0.6787 |
| 8 | offline | 1.0293 | 0.6784 (neu) |

## Erkenntnisse - von der KI selbst geschrieben

<!-- geschrieben von offline nach Runde 8, 2026-09-18 18:46 UTC -->
# Erkenntnisse

Automatisch destilliert vom Offline-Forscher nach Runde 8. Aussagen sind Mittelwerte ueber alle bisherigen Experimente, keine Kausalbefunde.

## Aufgabe ergebnis
**Bestes Modell:** Poisson auf Elo und Saisonstand + elo_diff + aufsteiger_heim - liga (Log-Loss Vorwaertsvalidierung 1.0293, Basisrate 1.0747, Elo-Logit 1.0304).

### Was traegt
- elo_gast: Modelle mit diesem Merkmal im Mittel 0.0028 besser (n=23)
- aufsteiger_heim: Modelle mit diesem Merkmal im Mittel 0.0017 besser (n=5)
- elo_diff: Modelle mit diesem Merkmal im Mittel 0.0016 besser (n=15)
- liga: Modelle mit diesem Merkmal im Mittel 0.0005 besser (n=20)
- vorsaison_platz_gast: Modelle mit diesem Merkmal im Mittel 0.0002 besser (n=3)

### Was nicht traegt
- elo_heim: Modelle mit diesem Merkmal im Mittel 0.0006 schlechter (n=24)
- saison_tordiff_heim: Modelle mit diesem Merkmal im Mittel 0.0004 schlechter (n=25)
- saison_tordiff_gast: Modelle mit diesem Merkmal im Mittel 0.0004 schlechter (n=25)

### Modelltypen
- mlp: bestes 1.0293, Mittel 1.0302 ueber 16 Experimente
- logit: bestes 1.0301, Mittel 1.0314 ueber 11 Experimente
- poisson: bestes 1.0311, Mittel 1.0333 ueber 4 Experimente

### Regeln fuer die naechste Runde
- Vom besten Modell ausgehen; Kern behalten: elo_heim, elo_gast, saison_tordiff_heim, saison_tordiff_gast, elo_diff.
- Merkmale aus 'Was nicht traegt' nur mit neuer Begruendung erneut pruefen.
- Je Runde mindestens eine Hypothese, die etwas Neues prueft (anderer Modelltyp, abgeleitetes Merkmal, andere Standardisierung).

## Aufgabe tore
**Bestes Modell:** Poisson Torraten + form5_gegentore_heim + spiele_gesamt_heim - liga (Log-Loss Vorwaertsvalidierung 0.6784, Basisrate 0.6842, Elo-Logit 0.6836).

### Was traegt
- form10_tordiff_heim: Modelle mit diesem Merkmal im Mittel 0.0019 besser (n=28)
- elo_heim: Modelle mit diesem Merkmal im Mittel 0.0019 besser (n=28)
- form5_tordiff_heim: Modelle mit diesem Merkmal im Mittel 0.0015 besser (n=4)
- form10_tordiff_gast: Modelle mit diesem Merkmal im Mittel 0.0014 besser (n=27)
- spiele_gesamt_heim: Modelle mit diesem Merkmal im Mittel 0.0012 besser (n=9)
- elo_gast: Modelle mit diesem Merkmal im Mittel 0.0010 besser (n=26)

### Was nicht traegt
- form5_tore_heim: Modelle mit diesem Merkmal im Mittel 0.0023 schlechter (n=2)
- form5_tore_gast: Modelle mit diesem Merkmal im Mittel 0.0023 schlechter (n=2)
- form5_gegentore_gast: Modelle mit diesem Merkmal im Mittel 0.0023 schlechter (n=2)
- saison_tordiff_gast: Modelle mit diesem Merkmal im Mittel 0.0008 schlechter (n=3)

### Modelltypen
- poisson: bestes 0.6784, Mittel 0.6795 ueber 24 Experimente
- logit: bestes 0.6808, Mittel 0.6817 ueber 3 Experimente
- mlp: bestes 0.6809, Mittel 0.6810 ueber 4 Experimente

### Regeln fuer die naechste Runde
- Vom besten Modell ausgehen; Kern behalten: elo_heim, elo_gast, form10_tordiff_heim, form10_tordiff_gast, form5_gegentore_heim.
- Merkmale aus 'Was nicht traegt' nur mit neuer Begruendung erneut pruefen.
- Je Runde mindestens eine Hypothese, die etwas Neues prueft (anderer Modelltyp, abgeleitetes Merkmal, andere Standardisierung).
