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
