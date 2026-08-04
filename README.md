# VfL Bochum — Quantitatives Post-Match-Framework

Ein Bewertungsrahmen für einzelne Spiele des VfL Bochum, gebaut auf Wyscout-Daten aus drei
Ligen. Er beantwortet drei Fragen und hält sie **strikt auseinander**, statt sie zu einer
undurchsichtigen Note zu verrechnen:

| Ebene | Frage | Ergebnis |
|---|---|---|
| **A — Spielstiltreue** | Wie nah kam das Spiel der Bochumer Spielidee? | 0–100 über 15 KPIs in 5 Spielphasen |
| **B — Aufstiegsperformance** | Hätte diese Leistung gegen diesen Gegner für den Aufstieg gereicht? | 0–100 gegen 18 historische Aufsteiger der 2. Bundesliga |
| **C — Outcome Alignment** | Passt das Ergebnis zur gezeigten Leistung? | xPoints und Ergebnisverteilung aus einer Poisson-Binomial-Faltung |

Ebene A misst **Identität**, nicht Qualität. Ein hoher Stilwert ist keine Aussage über
Aufstiegschancen — dafür ist Ebene B da. Diese Trennung ist der Kern des Ansatzes.

**→ [Dashboard ansehen](https://philipkloeckl.github.io/vfl-postmatch-framework/dashboard.html)**

## Datenbasis

4.343 Spiele · 8.620 Team-Match-Zeilen · 129.986 Spieler-Match-Zeilen aus 16 Liga-Saisons
der 2. Bundesliga, Bundesliga und österreichischen Bundesliga.

Validiert wurde gegen vier vom Verein genannte Referenzmannschaften, jeweils über alle Spiele
unter dem genannten Trainer: RB Leipzig (Werner), Sturm Graz (Ilzer), TSG Hoffenheim (Ilzer)
und mit Abstrichen Schalke 04 (Muslic).

Vergleichbarkeit über Ligen und Saisons entsteht durch z-Standardisierung je Liga-Saison;
alle KPIs sind gelegenheitsbasiert definiert (je Ballbesitz, je Ballgewinn, je effektiver
Spielminute), nicht als Rohvolumen.

## Was das Framework nicht kann

Zwei Punkte, die bewusst offen ausgewiesen sind statt weggerechnet:

- **Der Flügelfokus hat keine Vorbild-Evidenz.** Keine der vier Referenzmannschaften spielt
  flügellastig (Median-z zwischen −0,20 und +0,06). Der Korridor ist deshalb normativ auf das
  obere Ligafünftel gesetzt, nicht aus der Kohorte abgeleitet.
- **Die Umschalt-KPIs trennen schwach.** Ohne Event-Daten mit Zeitstempeln lässt sich kein
  Umschaltmoment isolieren — gemessen wird die Spielsumme je Ballgewinn, nicht die Aktion in
  den ersten Sekunden danach. Das Dashboard zeigt das als dauerhaftes Trennschärfe-Abzeichen
  an der Phasenzeile.

Die vollständige Liste steht in [`framework_spec.md`](framework_spec.md), die
Spaltendokumentation in [`ergebnisse/SCHEMA.md`](ergebnisse/SCHEMA.md).

## Aufbau

```
dashboard.html            in sich geschlossen, keine externen Requests — Doppelklick genügt
framework_spec.md         Methodik, Validierung, Grenzen
ergebnisse/               gerechnete Befunde + SCHEMA.md
skripte/                  die Pipeline
```

### Pipeline

Der Reihe nach, aus `skripte/`:

| | Skript | tut |
|---|---|---|
| 1–2 | `dl_matches.py`, `dl_stats.py` | Rohdaten laden *(braucht Token)* |
| 3 | `kpis.py` | KPIs auf Team-Match-Ebene, z-standardisiert je Liga-Saison |
| 3b | `kandidaten.py` | Screening der Operationalisierungs-Alternativen |
| 4 | `korridore.py` | Referenzkohorte, Korridoranker, Konstruktvalidierung |
| 5 | `outcome.py` | Outcome Alignment über rekonstruierte Schusslisten |
| 6 | `aufstieg.py` | historische Aufstiegsanalyse, Leave-One-Season-Out |
| 7 | `gegnermodell.py` | rollierendes Zwei-Wege-Modell mit Shrinkage |
| 8 | `scoring.py` | Scores, Aufstiegsbarometer, Ergebnisdateien |
| 9 | `dashboard_data.py`, `dashboard_match_data.py` | Anzeigedaten als JSON |
| 10 | `build_dashboard.py` | JSON in `dashboard.html` einspielen |

Prüfen: `python3 verify.py` — 46 Prüfungen über Skalenlage, Redundanz, Leakage-Freiheit,
Kalibrierung und Rechenidentitäten.

Das aktive KPI-Set steht als Daten in `skripte/kpi_varianten.json`, nicht im Code — samt aller
geprüften Alternativen mit Effektstärke, Konsistenz und Redundanz-Blockaden. KPIs lassen sich
dort tauschen, ohne Python anzufassen.

### Zugangsdaten

Die Download-Schritte brauchen einen Token für den Wyscout-MCP-Server:

```bash
export WYSCOUT_MCP_TOKEN='<Token von Strykerlabs>'
```

Alle übrigen Schritte laufen ohne. Der Token steht **nicht** im Code.

### Reproduktion aus einem Klon

Die Wyscout-Rohdaten (`daten/`, 61 MB) und zwei große Zwischendateien
(`ergebnisse/kpi_match_level.csv`, `ergebnisse/outcome_alignment.csv`) liegen bewusst nicht im
Repository — sie sind providerlizenziert und aus den Skripten reproduzierbar. Für einen
vollständigen Lauf die Pipeline ab Schritt 1 durchziehen; bis dahin lässt sich das Dashboard
nur neu bauen (Schritt 10), nicht neu rechnen, und `verify.py` läuft erst nach Schritt 8.
