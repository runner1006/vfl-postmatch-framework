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

**→ [Spielberichte öffnen](https://runner1006.github.io/vfl-postmatch-framework/app.html)** ·
[Dashboard](https://runner1006.github.io/vfl-postmatch-framework/dashboard.html) ·
[Beispiel-Report](https://runner1006.github.io/vfl-postmatch-framework/beispiel-report.html)

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

## Die Oberfläche

`app.html` ist der Arbeitsplatz für den Tag nach dem Spiel: links Klub und Saison wählen, die
Spiele der Saison als Liste mit Ergebnis, Stiltreue und Ziel-Marker (✓/✗), rechts der Bericht
zum ausgewählten Spiel. Pfeiltasten wechseln das Spiel, die Adresszeile hält den Stand fest
(`app.html#klub=vfl-bochum&spiel=33`), *Drucken / PDF* gibt exakt die zwei A4-Seiten aus.

Wie das Dashboard ist die App eine einzelne Datei ohne externe Requests — Doppelklick genügt.
Nach einem Rechenlauf neu einspielen:

```bash
python3 skripte/build_app.py        # Daten, Klubprofile, Texte und report.css in app.html
```

Die Rechnung steht damit zweimal: in `befund.py` für den Druck und in `app.html` für die
Oberfläche. Das ist bewusst so — die App soll ohne Server laufen, und Python läuft nicht im
Browser. Damit beide nicht auseinanderlaufen, prüft `python3 skripte/test_frontend.py` die App
in einem lokalen Chromium gegen Python: **jedes Spiel jedes Profils, Zahl für Zahl.** Alles,
was nur Text ist — Flag-Texte, Kurzbeschriftungen, Rundungsregeln, Trennschärfe-Wörter —
liefert `build_app.py` aus dem Python-Code in die App, steht also ohnehin nur einmal. Das
Aussehen liegt in `skripte/report.css` und wird von beiden Seiten benutzt.

## Post-Match-Report

Der Report ist das Produkt: **zwei A4-Seiten je Spiel** — vorne die drei Ebenen,
Stärken und Schwächen sowie das Gegnerbild, hinten alle 15 KPIs im Einzelnen und die Lesehilfe.
Er ist white-label: Name, Kürzel, Farbe, Spielidee und Zielreferenz stehen in einem Klubprofil,
nicht im Code.

```bash
python3 skripte/report.py --klub vfl-bochum --letztes          # jüngstes Spiel
python3 skripte/report.py --klub vfl-bochum --spieltag 12 --pdf
python3 skripte/report.py --klub schalke-04 --alle             # ganze Saison
python3 skripte/report.py --alle-klubs --letztes               # alle Profile
python3 skripte/report.py --klub vfl-bochum --liste            # nur auflisten
```

Ausgabe landet in `reports/<slug>/` samt Übersichtsseite; `--pdf` druckt zusätzlich über ein
lokal installiertes Chromium nach A4. Eine eingecheckte Musterseite liegt als
[`beispiel-report.html`](beispiel-report.html) im Wurzelverzeichnis.

### Ein neuer Klub

Eine JSON-Datei in `klubs/`, kein Python:

```json
{
  "slug": "schalke-04", "name": "FC Schalke 04", "kurz": "Schalke 04", "kuerzel": "S04",
  "farbe": "#004d9d", "spielidee": "…", "kpi_set": "rev3", "primaer": false,
  "quelle": { "team_key": "schalke_muslic" },
  "ziel": { "referenz": "aufsteiger_2bl", "gilt_fuer_liga": "2BL", "label": "Aufstieg" },
  "hinweise": ["…"]
}
```

`quelle.team_key` zeigt auf einen Datenblock in `ergebnisse/dashboard_matches.json`. `ziel`
schaltet Ebene B: Ohne Eintrag — oder in einer Liga, für die die Aufstiegsreferenz nicht gilt —
weist der Report sie als *nicht anwendbar* aus, statt eine unpassende Marke zu rechnen. Was für
ein Profil grundsätzlich gilt, steht unter `hinweise` und erscheint in der Lesehilfe. `primaer`
markiert den Klub, dem die App gehört — er steht in der Auswahl oben und öffnet sich zuerst.

Die Engine liest ausschließlich `ergebnisse/dashboard_matches.json`, kommt ohne Fremdpakete aus
und rechnet nichts nach, was die Pipeline schon gerechnet hat. Prüfen:
`python3 skripte/test_report.py` — 23 Tests über Profile, die drei Ebenen, die Saisonlage,
Kreuzproben gegen `bochum_2526_scored.csv` und das Rendern **aller** Spiele **aller** Profile.

## Aufbau

```
app.html                  die Oberfläche: Klub, Saison, Spiel, Bericht, Druck
dashboard.html            in sich geschlossen, keine externen Requests — Doppelklick genügt
beispiel-report.html      Musterseite der Report-Engine
framework_spec.md         Methodik, Validierung, Grenzen
klubs/                    ein JSON je Klub — Name, Farbe, Spielidee, Zielreferenz
ergebnisse/               gerechnete Befunde + SCHEMA.md
skripte/                  die Pipeline und die Report-Engine
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
| 11 | `report.py` | Post-Match-Report je Klub und Spiel *(braucht nur Schritt 9)* |
| 12 | `build_app.py` | Daten, Profile und Aussehen in `app.html` einspielen |

Report-Engine und App hängen allein an Schritt 9: `befund.py` rechnet die drei Ebenen aus
`dashboard_matches.json`, `klubprofil.py` lädt und prüft das Klubprofil, `report.py` setzt die
Druckseite, `build_app.py` dieselben Daten in `app.html`.

Prüfen: `python3 verify.py` — 46 Prüfungen über Skalenlage, Redundanz, Leakage-Freiheit,
Kalibrierung und Rechenidentitäten. Dazu `python3 skripte/test_report.py` (Report-Engine) und
`python3 skripte/test_frontend.py` (App gegen Druck, braucht ein lokales Chromium).

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
Report-Engine und App (Schritte 11 und 12) laufen dagegen aus einem frischen Klon heraus — sie
brauchen nur `ergebnisse/dashboard_matches.json`, und die liegt im Repository. `app.html` ist
fertig gebaut eingecheckt und geht per Doppelklick auf.
