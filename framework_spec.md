# VfL Bochum — Quantitatives Post-Match-Framework

**Rev. 4 · 04.08.2026 · Konzept, Methodik und gerechnete Modelle**

Datenbasis: MCP Server `datasync` (Wyscout). **4.343 Spiele · 8.620 Team-Match-Zeilen · 129.986 Spieler-Match-Zeilen** aus 3 Ligen und 16 Liga-Saisons.
Alle Zahlen in diesem Dokument sind gerechnet, nicht geschätzt. Die Ergebnisdateien liegen in `ergebnisse/`, das Spaltenschema in `ergebnisse/SCHEMA.md`.

**Reproduktion aus einem Klon.** Die Wyscout-Rohdaten (`daten/`, 61 MB) und zwei große
Zwischendateien (`ergebnisse/kpi_match_level.csv`, `ergebnisse/outcome_alignment.csv`) liegen
bewusst nicht im Repository — sie sind providerlizenziert und aus den Skripten reproduzierbar.
Für einen vollständigen Lauf `skripte/` in der Reihenfolge der Schrittnummern durchziehen
(`dl_matches` → … → `scoring` → `dashboard_*` → `build_dashboard`); die beiden Download-Schritte
brauchen `WYSCOUT_MCP_TOKEN` in der Umgebung, alle übrigen nicht. Ohne vorherigen Rechenlauf
lässt sich das Dashboard neu **bauen**, aber nicht neu **rechnen**, und `verify.py` läuft erst
nach Schritt 8. Die Pipeline-Übersicht steht in der [README](README.md).

**Was Rev. 2 nicht ist:** keine Software, keine Visualisierung. Alle Modelle sind gerechnet und in tidy Dateien abgelegt, damit die Darstellung in einem zweiten Schritt direkt darauf aufsetzen kann.

---

## Leitprinzip: drei getrennte Ebenen

| Ebene | Frage | Ergebnis | Speist sich aus |
|---|---|---|---|
| **A — Spielstiltreue** | Wie nah kam das Spiel der idealen VfL-Spielidee? | 0–100 Identity Fidelity | 15 Stil-KPIs, 5 Phasen |
| **B — Aufstiegsbarometer** | War die Leistung aufstiegsfähig? | 0–100 gegen 18 historische Aufsteiger | Chance Creation, gegnerbereinigt |
| **C — Outcome Alignment** | Passt das Ergebnis zur Leistung? | xPoints, Ergebnisverteilung, Klassifikation | Poisson-Binomial über rekonstruierte Schusslisten |

**Kein KPI erscheint in mehr als einer Ebene** — automatisch geprüft (Abschnitt 9.5).

---

## Was Rev. 4 gegenüber Rev. 3 ändert

Zwei Korrekturen, beide aus der Nutzung heraus aufgefallen.

### 4.1 Trennschärfe und Belastbarkeit sind zwei Dinge

Rev. 3 hat sie multipliziert: `conf_phase = KPI-Güte × Ereignis-Confidence × Vollständigkeit`.
Die Güte (1,0 stark … 0,4 schwach) ist aber eine **Eigenschaft des KPIs**, über alle Spiele
konstant; die Ereigniszahl ist eine **Eigenschaft des Spiels**. Multipliziert heißt: eine
Phase aus drei schwachen KPIs erreicht die Schwelle 0,30 **nie**, egal wie viele Ereignisse
das Spiel hatte. Genau das war beim offensiven Umschalten der Fall — **in 100 % der Spiele
ausgegraut**, also faktisch abgeschaltet.

| Phase | Güte der drei KPIs | Ereignis-Conf (Median) | Rev. 3 `conf` | Rev. 3 grau |
|---|---|---|---|---|
| Defensiv | 1,0 / 1,0 / 0,7 | 0,83 | 0,75 | 0 % |
| Def. Umschalten | 0,7 / 0,4 / 1,0 | 0,92 | 0,64 | 0 % |
| Offensiv | 1,0 / 0,4 / 0,5 | 0,71 | 0,50 | 0 % |
| **Off. Umschalten** | **0,4 / 0,4 / 0,4** | **0,37** | **0,15** | **100 %** |
| Physisch | 1,0 / 1,0 / 0,7 | 0,99 | 0,92 | 0 % |

Rev. 4 trennt beide Größen und verrechnet sie nicht mehr:

| Größe | Art | Wirkung |
|---|---|---|
| `guete_<phase>` | strukturell, je Phase genau ein Wert über alle 8.620 Zeilen | stilles Textabzeichen an der Phasenzeile, blendet **nie** etwas aus |
| `conf_<phase>` | spielweise, **nur** Ereigniszahl × Vollständigkeit | steuert das Ausgrauen, Schwelle **0,20** |

Ergebnis: **5,8 %** der Umschaltphasen ausgeblendet statt 100 %, alle übrigen Phasen 0 % —
bei Bochum 2025/26 **kein einziges** der 34 Spiele. Ausgeblendet wird nur, wo ein Wert
existiert; fehlende Physikdaten bleiben „keine Daten" und gelten nicht zusätzlich als
unsicher. Der Hinweistext benennt weiter den limitierenden KPI mit seiner Ereigniszahl.

Die schwache Trennschärfe der Umschalt-KPIs bleibt damit sichtbar — sie ist ein
Datengrenzen-Befund (Abschnitt 4.3), keine Eigenschaft eines einzelnen Spiels.

### 4.2 Effizienz hat zwei Seiten, gemessen wurde eine

Die Zeile „Chancenverwertung" hat nur `Tore − xG` gezeigt. Man kann aber gut verteidigt und
trotzdem ein Tor bekommen haben; das war nicht darstellbar. Über alle 8.620 Zeilen:

| Komponente | Aufsteiger Ø | 2. BL Ø | Median | p95 des Betrags |
|---|---|---|---|---|
| Offensiv `npG − npxG` | **+0,079** | −0,081 | −0,147 | 2,20 |
| Defensiv `npxG_gegen − npG_gegen` | **+0,180** | +0,081 | +0,147 | 2,20 |
| **Netto** | **+0,259** | 0,000 | 0,000 | 3,13 |

- Beide Seiten sind **praktisch unkorreliert** (r = +0,035) — die offensive Zahl allein wirft
  die Hälfte der Information weg.
- In **50,0 %** der Spiele ist die defensive Komponente die betragsmäßig größere.
- **19,3 %** der Spiele haben deutliches Defensiv-Pech (> 0,8 Gegentore über xG). Davon hatten
  **55,3 %** gleichzeitig eine **unterdurchschnittliche** zugelassene Chancenqualität — exakt
  der Fall „gut verteidigt, trotzdem getroffen worden".
- Der Torhütereffekt (`gk_xg_save − Gegentore`) erklärt die defensive Komponente zu **r = 0,80**
  und ist damit der benennbare Mechanismus. Er steht separat im Erklärtext.

Die Spiegelbildlichkeit von Median und Ligamittel ist kein Zufall, sondern folgt aus der
Definition: Was ein Team an Toren über seinem npxG erzielt, ist für das andere Team ein
Gegentor über dem zugelassenen npxG. Sie dient als Rechenprobe (`verify.py`, Block 12).

Das Aufstiegspanel zeigt daher eine symmetrische 2×2-Struktur:

|  | erzeugt / zugelassen (xG) | was daraus wurde (Tore) |
|---|---|---|
| **offensiv** | Chancenkreation | Chancenverwertung |
| **defensiv** | Abwehrleistung | **Abwehreffizienz** *(neu)* |

Beide Effizienzzeilen sind so gepolt, dass positiv = gut ist, und laufen gegen den
Aufsteigerschnitt bei Score 50. Die **Nettoeffizienz** ist die Summe der beiden rechten
Zellen; sie ist identisch mit „tatsächliche minus erwartete Tordifferenz" und beantwortet
damit direkt, ob das Ergebnis zur Leistung passt.

**Abweichung vom ursprünglichen Plan:** Die defensive Seite verwendet die npG des Gegners
(Gegentore ohne Elfmeter) statt der Gesamt-Gegentore. Damit stehen auf beiden Seiten
dieselben Größen, und das Ligamittel der Nettoeffizienz ist konstruktionsbedingt **exakt
0,000** — jedes Nicht-Elfmeter-Tor ist zugleich jemandes npG und jemandes npG_gegen. Der
Aufsteigerschnitt der defensiven Komponente steigt dadurch von +0,066 auf +0,180.

Dabei fiel ein Fehler in `dashboard_match_data.py` auf: Eine Ersatzrechnung überschrieb die
bereits vorhandene `npg`-Spalte mit den **Gesamttoren**, weil die dort abgefragte Spalte
`n_penalties` nie existiert hat. Elfmeter wären so in die Effizienz eingegangen. Korrigiert.

Alle Zielwerte und Spannen liegen im `NORM`-Block des Dashboards und bleiben austauschbar.

---

## Was Rev. 3 gegenüber Rev. 2 ändert

| Thema | Rev. 2 | Rev. 3 |
|---|---|---|
| **Skala** | Vier-Anker-Korridor. Saturiert: OT1 hatte **Median 100**, O1 46 % bei 100, D2 nur 12 % | **Zweistufige Drei-Punkt-Ankerung.** Jeder KPI: Median exakt 50, Sättigung je Rand ≤ 11 % |
| **Trennung Kohorte ↔ Liga** | 7,9 Punkte im Gesamtscore | **14,4 Punkte** — bei unverändertem Cliff's δ (+0,287), da monotone Transformation |
| **KPI-Set** | im Code verdrahtet | **`skripte/kpi_varianten.json`** — Set und alle geprüften Alternativen als Daten |
| **DT3** | zugelassene Konter: 0/4, δ 0,04, 29 % Nullzähler | **Höhe der Ballverluste: 3/4, δ 0,27**, nie 0 |
| **Confidence** | pauschaler Stichprobenfaktor | **je Spiel aus der Ereigniszahl**: `n/(n+6)` |
| **Konsistenzsumme** | 28/60, zwei KPIs bei 0/4 | **29/60, ein KPI bei 0/4** |

Der DT3-Tausch erzwang zwei weitere Wechsel, weil die Redundanzgrenze |r| < 0,60 bindet:
**D3** (neuer DT3 korreliert 0,70 mit dem alten D3) und **OT2** (0,65) — und dieser wiederum **O2** (0,97).
Alle vier Wechsel und ihre Begründungen stehen maschinenlesbar in `kpi_varianten.json`
unter `aenderungen_rev3`.

**Ein global redundanzfreier Optimierer über alle 58 gescreenten Kandidaten hebt die
Konsistenzsumme nur von 28 auf 30.** Die Nebenbedingungen binden, nicht die KPI-Auswahl —
weitere Suche nach besseren Operationalisierungen lohnt mit dieser Datenbasis nicht.

---

# 1. Data Availability Matrix

## 1.1 Granularitäten

| Ebene | Status | Tabelle | Historie |
|---|---|---|---|
| Match | ✅ | `wyscout_match_sync` | ab 2015/16 |
| **Team-Match (144 Metriken)** | ✅ **lückenlos** | `wyscout_match_team_stats_sync` | 2017/18 – 2025/26 |
| **Spieler-Match (200 Metriken)** | ✅ | `wyscout_match_player_stats_sync` | 2017/18 – 2025/26 |
| Physical (Spieler-Match) | ⚠️ **ab 2023/24, lückenhaft** | `wy_per_90_physical_*`, `wy_totals_physical_max_speed` | siehe 1.3 |
| Auswechslungen mit Minute | ✅ | `wyscout_match_player_substitutions_sync` | vollständig |
| Trainerzuordnung je Spiel | ✅ | `wyscout_match_sync.{home,away}_team_coach_id` | vollständig |
| Possession / Sequence | ⚠️ nur Aggregate | `possession_number`, `reaching_opponent_half/box` | 9 Saisons |
| **Event-Level** | ❌ | — | — |
| **Tracking / SkillCorner** | ❌ **0 Matches** | alle `sc_*` NULL | — |

## 1.2 Geprüfte Datenmenge

| Liga | `competition_id` | Saisons | Spiele | Team-Match-Zeilen |
|---|---|---|---|---|
| 2. Bundesliga | 423 | 9 (2017/18–2025/26) | 2.756 | 5.502 |
| Bundesliga | 426 | 2 (2024/25, 2025/26) | 612 | 1.180 |
| Österreichische Bundesliga | 168 | 5 (2020/21–2024/25) | 975 | 1.938 |
| **Summe** | | **16 Liga-Saisons** | **4.343** | **8.620** |

Alle in Abschnitt 3 verwendeten Team-Statistikspalten sind in allen drei Ligen zu **100 %** befüllt (geprüft).

## 1.3 Korrektur gegenüber Rev. 1: Physikdaten

Rev. 1 stützte sich auf das Metadatenfeld `meta_match_physical_data_downloaded`. **Das Feld ist unbrauchbar.** Die tatsächliche Spaltenbefüllung wurde nachgemessen — der Unterschied ist gravierend:

| Liga-Saison | Anteil Team-Matches mit ≥ 80 % abgedeckten Feldspielerminuten | was der Metadaten-Flag behauptet |
|---|---|---|
| 2BL 2017/18 – 2022/23 | 0 % | 0 % |
| 2BL 2023/24 | **65,2 %** | 0 % |
| 2BL 2024/25 | 37,9 % | 4,9 % |
| 2BL 2025/26 | 86,2 % | 98,7 % |
| **AUT 2023/24** | **94,6 %** | **0 %** |
| **AUT 2024/25** | **94,7 %** | **0 %** |
| BL 2024/25 | 46,6 % | 0,7 % |
| BL 2025/26 | 86,3 % | 99,3 % |

**Folge:** Die Annahme aus Rev. 1, Sturm Graz unter Ilzer habe keine Physikdaten, war falsch. Sturm Graz hat für 42 Spiele (2023/24 und 2024/25) Physikdaten — alle vier Referenzmannschaften tragen die physische Phase.

**Umgang im Code:** Summen über ausschließlich fehlende Werte bleiben NaN (`min_count=1`), und Physik-Aggregate werden verworfen, wenn weniger als 80 % der Feldspielerminuten abgedeckt sind. Ohne diese Regel würde „keine Physikdaten" als „null Laufleistung" gelesen — ein Fehler, der in der ersten Rechnung dieses Projekts auch tatsächlich auftrat und erst durch die Prüfung auffiel.

## 1.4 Die drei defekten bzw. irreführenden Felder

| Feld | Problem | Umgang |
|---|---|---|
| `meta_match_physical_data_downloaded` | bildet die tatsächliche Befüllung nicht ab (siehe 1.3) | verworfen, durch gemessene Minutenabdeckung ersetzt |
| `wy_per_90_pressing_duels_won` | durchgängig 0 | verworfen |
| `wy_totals_passes_smart_passes` | Definitions-Drift (2. BL: 15 → 1–6 je Spiel) | verworfen |
| `wy_totals_general_shots_against` | bedeutet zugelassene Schüsse **aufs Tor**, nicht Schüsse | umdefiniert; Gesamtschüsse über die Gegnerzeile |

Ein vierter Befund betrifft den Client, nicht die Datenbank: Der MCP-Server deklariert kein Charset, weshalb `requests` auf ISO-8859-1 zurückfällt und Umlaute in Team- und Spielernamen zerstört. In `skripte/wyclient.py` explizit auf UTF-8 gezwungen.

---

# 2. Zusammenfassung: Datenlücken

**(1) SkillCorner ist im gesamten Datenbestand leer.** Kein TIP/OTIP-Split, kein PSV-99, keine Game-Intelligence-Metriken. Damit ist der Referenzpunkt „Laufvolumen **mit und gegen den Ball**" nur zur Hälfte messbar — Laufvolumen ja, Ballbesitzkontext nein. Das kollidiert außerdem mit den bestehenden Positionsprofilen (FB-Index, DM-Index, Winger-Profil), die auf SkillCorner-GI aufsetzen (offene Entscheidung 13.1).

**(2) Keine Event- oder Sequence-Ebene.** Kein Umschaltmoment ist zeitlich isolierbar. Das ist die Ursache dafür, dass beide Umschaltphasen im Framework die schwächste Trennschärfe haben (Abschnitt 4.2) — eine Datengrenze, kein Modellfehler.

**(3) Physik lückenhaft und erst ab 2023/24** (Abschnitt 1.3). Physik fließt deshalb ausschließlich in Teil A, nie ins Aufstiegsbarometer.

**(4) Kein Spielstandsverlauf.** Ohne Torminuten und ohne Rote-Karte-Minute ist Match State nur auf Halbzeit-Granularität auflösbar.

---

# 3. Die 15 Spielstil-KPIs

## 3.1 Wie das Set zustande kam

Rev. 1 hatte das Set fachlich hergeleitet. Rev. 2 hat es **empirisch geprüft**: 58 Operationalisierungen über acht taktische Prinzipien wurden gerechnet und daran gemessen, ob sie die vier Referenzmannschaften vom jeweiligen Ligarest trennen (`ergebnisse/kandidaten_screening.csv`). Sieben KPIs aus Rev. 1 fielen dabei durch und wurden ersetzt.

Auswahlkriterien in dieser Reihenfolge:
1. taktische Abdeckung der vier Referenzpunkte und des Ursprungsbriefings,
2. Trennschärfe gegenüber den Referenzteams (Cliff's δ, Konsistenz über die vier Referenzen einzeln),
3. paarweise |r| < 0,60 innerhalb jeder Phase.

**Schutz gegen Überanpassung:** Die Auswahl erfolgt gegen die *Identität* (spielen die Vorbilder so?), nicht gegen *Ergebnisse*. Zusätzlich muss ein KPI in mehreren der vier Referenzen in dieselbe Richtung zeigen, nicht nur gepoolt.

## 3.2 Abbildung der vier Referenzpunkte

| Referenzpunkt des Vereins | Primäre KPIs | messbar? |
|---|---|---|
| **1. Aggressiv / hohes Anlaufen / Vorwärtsverteidigen** | D1, D2, D3 | ✅ vollständig, stärkste Phase des Frameworks |
| **2. Intensiv / dynamisch** — Laufvolumen, Explosivität, Endgeschwindigkeit | P1, P2, P3 | ⚠️ ja, **außer „mit und gegen den Ball"** (SkillCorner fehlt) |
| **3. Vorwärtsgerichtet / Forward Mindset / Vertikalität** | O1, O2 | ✅ |
| **4. Fokus Spiel über die Flügel** | O3 (+ 3 Sekundär-KPIs) | ⚠️ messbar, aber **von keinem Referenzteam belegt** (Abschnitt 4.3) · **Cut Backs nur als Proxy** |

> **Ein Widerspruch im Briefing, der offenbleiben muss:** Das Ursprungsbriefing sagt „keine reine Abhängigkeit von langen Bällen auf einen Zielstürmer", Referenzpunkt 4 sagt „Flanken auf den Zielspieler in der Box". Das ist nicht dasselbe — Langball im Aufbau ≠ Flanke in der Box — wird hier getrennt gehalten und ist in 13.3 als offene Frage vermerkt.

## 3.3 Das Set

Notation: `T.x` = eigener Wert, `G.x` = Gegnerzeile desselben Spiels, `Σₚ` = Summe über Spieler (`wy_per_90_x × Minuten/90`). Spaltennamen ohne die Präfixe `wy_totals_` / `wy_per_90_`.

| # | KPI | Management-Name | Taktisches Prinzip | Formel | Form | Gew. | Konsistenz | Confidence |
|---|---|---|---|---|---|---|---|---|
| **O1** | Vertikalität | „Nach vorne gespielt" | RP3 Forward Mindset | `passes_forward_passes_successful / passes_passes_successful` | Korridor | 0,35 | **3/4** | hoch |
| **O2** | Boxzugang | „Bis in die Box durchgekommen" | Kontrollierte Progression | `possession_reaching_opponent_box / possession_reaching_opponent_half` | ↑ | 0,35 | 1/4 | niedrig |
| **O3** | Flügel-Boxzuspiel | „Von außen gefährlich geworden" | RP4 Flügelfokus | `passes_crosses_successful / possession_possession_number` | ↑ | 0,30 | 1/4 | **normativ** |
| **OT1** | Konterrate | „Umgeschaltet" | Umschaltmoment genutzt | `attacks_counter_attacks / transitions_recoveries_total` (Shrinkage k=12) | Korridor | 0,30 | 0/4 | niedrig |
| **OT2** | Tiefenertrag je Ballgewinn | „Aus Ballgewinnen Tiefe erzeugt" | Ertrag des Ballgewinns | `passes_deep_completed_passes_successful / transitions_recoveries_total` | ↑ | 0,35 | 1/4 | niedrig |
| **OT3** | Ballgewinnqualität | „Gefährlich erobert" | Voraussetzung für Umschalten | `Σₚ dangerous_opponent_half_recoveries / transitions_recoveries_total` | ↑ | 0,35 | 1/4 | niedrig |
| **D1** | Pressingdruck | „Druck gemacht" | RP1 hohes Anlaufen | `defence_pdda` | Korridor | 0,35 | **3/4** | hoch |
| **D2** | Ballgewinnhöhe | „Hoch erobert" | RP1 Vorwärtsverteidigen | `transitions_recoveries_high / eff_min` | ↑ | 0,35 | **3/4** | hoch |
| **D3** | Zugelassene gegn. Progression | „Den Gegner nicht spielen lassen" | RP1 Absicherung | `G.passes_progressive_passes_successful / G.possession_possession_number` | ↓ | 0,30 | 2/4 | mittel |
| **DT1** | Gegenpressing-Quote | „Sofort zurückerobert" | Unmittelbares Gegenpressing | `Σₚ counterpressing_recoveries / transitions_losses_total` | ↑ | 0,40 | 2/4 | mittel |
| **DT2** | Gefährlichkeit der Verluste | „Sauber verloren" | Restverteidigung | `Σₚ dangerous_own_half_losses / transitions_losses_total` | ↓ | 0,30 | 1/4 | niedrig |
| **DT3** | Höhe der Ballverluste | „Weit weg vom eigenen Tor verloren" | Restverteidigung | `transitions_losses_high / transitions_losses_total` | ↑ | 0,30 | **3/4** | hoch |
| **P1** | Intensives Laufvolumen | „Intensität gehalten" | RP2 Laufvolumen | `Σₚ physical_hi_distance / eff_min` | Korridor | 0,40 | **3/4** | hoch |
| **P2** | Explosivität | „Explosiv geblieben" | RP2 Explosivität | `Σₚ physical_count_high_acceleration / eff_min` | Korridor | 0,35 | **3/4** | hoch |
| **P3** | Endgeschwindigkeit | „Spitze abgerufen" | RP2 Endgeschwindigkeit | Mittel der **Top-5** `physical_max_speed` der Feldspieler | ↑ | 0,25 | 2/4 | mittel |

`eff_min` = effektive Spielzeit = (`possession_total_time_seconds` − `possession_dead_time_seconds`)/60.

### Zielkorridore in Einheiten der 2. Bundesliga 2025/26

| KPI | Score 0 bei | Score 100 ab/zwischen |
|---|---|---|
| O1 Vertikalität | 0,255 | **0,300 – 0,355** (darüber wieder fallend bis 0 bei 0,392) |
| O2 Tiefenprogression | 0,030 | **≥ 0,106** |
| O3 Flügel-Boxzuspiel | 0,017 | **≥ 0,069** *(normativ)* |
| OT1 Konterrate | −0,004 | **0,001 – 0,016** |
| OT2 Angriffsrate | 0,327 | **≥ 0,579** |
| OT3 Ballgewinnqualität | 0,011 | **≥ 0,078** |
| **D1 PPDA** | 19,70 (zu passiv) | **10,95 – 8,02** (unter 6,65 wieder 0) |
| D2 Ballgewinnhöhe | 0,123 /Min. | **≥ 0,382** /Min. |
| D3 Zugelassene Hälften-Erreichung | 0,671 | **≤ 0,445** |
| DT1 Gegenpressing-Quote | 0,261 | **≥ 0,400** |
| DT2 Gefährliche Verluste | 0,095 | **≤ 0,028** |
| DT3 Zugelassene Konter | 0,019 | **≈ 0** |
| P1 HI-Distanz | 115,0 m/Min. | **162,5 – 205,5** m/Min. |
| P2 Explosivität | 3,45 /Min. | **4,43 – 5,71** /Min. |
| P3 Endgeschwindigkeit | 32,09 | **≥ 33,77** |

### Sekundär-KPIs (im Report, **nicht** im Score)
`S_fluegelanteil` · `S_flankenpraezision` · `S_cutback_proxy` (flache Flanken) · `S_aufbaukontrolle` (Langball-Anteil) · `S_through_tiefe` · `S_prog_pass_per_poss` · `S_prog_runs_per_poss` · `S_hohe_verluste_anteil` · `S_ballbesitz` · `S_sprintdichte` · `S_hi_count_dichte` · `S_laufdistanz` · `S_dezeleration`

> **Hinweis zu `S_sprintdichte`:** Das ist der **einzige** Kandidat im gesamten Screening mit 4/4 Konsistenz (δ = 0,410). Er steht nur deshalb in der Sekundärebene, weil er mit P1 zu r = 0,90 nahezu kollinear ist. Wer P1 durch die Sprintdichte ersetzt, verliert nichts und gewinnt Konsistenz — das ist eine legitime Alternative (13.5).

## 3.4 Redundanzprüfung — bestanden

Über alle 8.620 Zeilen: **kein Paar der 15 KPIs überschreitet |r| = 0,60.** Vollständige Matrix in `ergebnisse/redundancy_matrix.csv`.

Verworfen wurden dabei unter anderem: `p_deep_per_poss` ↔ `u_deep_per_rec` (r = 0,97), `y_hidist_per_min` ↔ `y_sprint_per_min` (0,90), `d_opp_ownhalf_loss_share` ↔ `d_opphalf_rec_share` (0,87), `y_acc_per_min` ↔ `y_dec_per_min` (0,82).

---

# 4. Referenzmannschaften — Validierung

## 4.1 Datenlage

Trainerfilter über `home_team_coach_id` / `away_team_coach_id`, **nur Ligaspiele** (Pokal, Europapokal und Testspiele ausgeschlossen — dort fehlt eine saubere Liga-Saison-Basis für die z-Standardisierung).

| Referenz | Trainer-ID | Team-ID | Liga | Saisons | Spiele | davon mit Physik | Gewicht |
|---|---|---|---|---|---|---|---|
| RB Leipzig / Ole Werner | 454326 | 2975 | Bundesliga | 2025/26 | 34 | 28 (82 %) | 1,0 |
| Sturm Graz / Christian Ilzer | 357755 | 8742 | Österr. BL | 2020/21 – 2024/25 | 141 | 42 (30 %) | 1,0 |
| TSG Hoffenheim / Ilzer | 357755 | 2482 | Bundesliga | 2024/25 (ab 23.11.), 2025/26 | 55 | 37 (67 %) | 1,0 |
| Schalke 04 / Miron Muslic | 684312 | 2449 | 2. Bundesliga | 2025/26 | 34 | 28 (82 %) | **0,5** |
| **Kohorte gesamt** | | | | | **264** | **135** | |

Schalke mit halbem Gewicht, weil der Verein die Referenz „in Abstrichen" gesetzt hat.

Alle KPIs werden **je Liga-Saison z-standardisiert**, bevor die Kohorte über drei Ligen hinweg gepoolt wird. Der Korridor lebt im z-Raum; für die Darstellung ist er in 2.-BL-2025/26-Einheiten zurückgerechnet.

## 4.2 Trennschärfe je KPI (Cliff's δ, Kohorte gegen Ligarest)

| KPI | δ gesamt | 95-%-CI | Leipzig | Sturm | Hoffenheim | Schalke | ohne Leipzig | Konsistenz |
|---|---|---|---|---|---|---|---|---|
| **P1 Laufvolumen** | **0,492** | 0,40 – 0,57 | 0,10 | **0,65** | **0,58** | **0,62** | 0,60 | 3/4 |
| **D2 Ballgewinnhöhe** | **0,283** | 0,21 – 0,35 | −0,01 | **0,37** | **0,26** | **0,35** | 0,33 | 3/4 |
| **D3 Hälften-Erreichung** | **0,269** | 0,21 – 0,33 | 0,10 | **0,29** | **0,23** | **0,47** | 0,29 | 3/4 |
| **D1 Pressingdruck** | **0,233** | 0,17 – 0,29 | 0,07 | **0,27** | **0,38** | **0,17** | 0,26 | 3/4 |
| **P2 Explosivität** | **0,199** | 0,11 – 0,29 | **0,35** | 0,06 | **0,17** | **0,30** | 0,16 | 3/4 |
| **O1 Vertikalität** | **0,175** | 0,10 – 0,25 | −0,28 | **0,22** | **0,18** | **0,46** | 0,24 | 3/4 |
| P3 Endgeschwindigkeit | 0,159 | 0,05 – 0,25 | **0,43** | **0,26** | −0,04 | 0,02 | 0,09 | 2/4 |
| DT2 Gefährliche Verluste | 0,156 | 0,09 – 0,23 | 0,10 | 0,11 | 0,10 | **0,54** | 0,17 | 1/4 |
| DT1 Gegenpressing | 0,154 | 0,08 – 0,22 | −0,11 | **0,23** | **0,29** | −0,06 | 0,19 | 2/4 |
| OT3 Ballgewinnqualität | 0,149 | 0,08 – 0,21 | 0,14 | **0,21** | 0,03 | 0,15 | 0,15 | 1/4 |
| O2 Tiefenprogression | 0,116 | 0,05 – 0,19 | **0,44** | 0,07 | 0,05 | **0,18** | 0,07 | 2/4 |
| OT2 Angriffsrate | 0,090 | 0,02 – 0,15 | **0,25** | 0,13 | 0,01 | −0,04 | 0,07 | 1/4 |
| DT3 Zugelassene Konter | 0,044 | −0,03 – 0,11 | −0,04 | 0,10 | 0,01 | **0,24** | 0,06 | 1/4 |
| OT1 Konterrate | 0,017 | −0,05 – 0,08 | 0,02 | 0,05 | −0,10 | −0,12 | 0,02 | 0/4 |
| O3 Flügel-Boxzuspiel | −0,002 | −0,07 – 0,06 | 0,03 | −0,03 | 0,16 | −0,15 | 0,00 | 1/4 |

Fettdruck = δ > 0,15 (Konsistenzschwelle).

**Sechs KPIs trennen stark, drei gemischt, sechs schwach.** Die schwachen sind genau die Umschalt- und Restverteidigungs-KPIs — die Familie, für die die Datenbasis keine zeitliche Auflösung liefert. Das ist seit Rev. 4 als **Trennschärfe-Abzeichen** je Phase abgebildet — dauerhaft sichtbar, aber ohne den Wert auszublenden — und wird nicht wegkalibriert.

## 4.3 Zwei Befunde, die das Framework prägen

**Befund 1: Kein Referenzteam spielt flügellastig.** Median-z des Flügelanteils der Angriffe: Leipzig −0,20 · Sturm +0,06 · Hoffenheim +0,05 · Schalke −0,20. Alle neun getesteten Flügel-Operationalisierungen (Flanken je Ballbesitz, Flankenpräzision, Cut-Back-Anteil, Boxzuspiel je Box-Erreichung, Flügelanteil) erreichen höchstens 1/4 Konsistenz. **Bochum selbst ist mit +0,12 flügellastiger als alle vier Vorbilder.**
→ Entscheidung: O3 bleibt primärer KPI, weil der Verein den Punkt als Identität benannt hat, aber sein Korridor ist **normativ** gesetzt (Score 100 = Liga-P80) und im Report als „Zielvorgabe ohne Vorbild-Evidenz" gekennzeichnet.

**Befund 2: RB Leipzig unter Werner ist ein anderer Archetyp.** Median-z im Direktvergleich:

| | Vorwärtspass-Anteil | Hohe Ballgewinne/Min. | Progressive Läufe | Ballbesitz |
|---|---|---|---|---|
| RB Leipzig / Werner | **−0,47** | **−0,18** | **+0,63** | 52 % |
| Sturm Graz / Ilzer | +0,33 | +0,58 | −0,23 | 49 % |
| TSG Hoffenheim / Ilzer | +0,13 | +0,63 | −0,44 | 52 % |
| Schalke 04 / Muslic | +1,20 | +0,43 | −0,77 | 44 % |
| *VfL Bochum 25/26* | *−0,33* | *−0,03* | *−0,20* | *44 %* |

Leipzig ist ein **Trage- und Dribbelteam**, die anderen drei bilden einen kohärenten **Pressing-Vorwärts-Cluster**. Ballbesitzdominanz erklärt es nicht (Hoffenheim hat denselben Ballbesitzanteil und verhält sich wie Sturm).
→ Entscheidung: alle vier bleiben in der Kohorte, Konsistenzschwelle 3 von 4. Die Spalte `delta_ohne_leipzig` in `reference_cohort_profile.csv` ist die Sensitivitätsrechnung; sie verändert das Bild an keiner Stelle qualitativ.

## 4.4 Skalenprüfung

| Gruppe | n | Gesamtscore | bestes Spiel | Defensiv | Offensiv | Def. Umsch. | Off. Umsch. | Physisch |
|---|---|---|---|---|---|---|---|---|
| Sturm Graz / Ilzer | 141 | **67,5** | 92 | 73,6 | 61,2 | 68,0 | 66,2 | 66,3 |
| TSG Hoffenheim / Ilzer | 55 | **66,8** | 91 | 66,9 | 66,0 | 68,6 | 64,6 | 71,4 |
| Schalke 04 / Muslic | 34 | **66,5** | 88 | 77,0 | 52,0 | 68,8 | 67,2 | 63,9 |
| RB Leipzig / Werner | 34 | **64,8** | 89 | 59,5 | 66,9 | 57,3 | 71,5 | 75,0 |
| 2.-BL-Aufsteiger (18 Team-Saisons) | 612 | 64,0 | 96 | 63,6 | 63,4 | 63,8 | 65,0 | 66,2 |
| **VfL Bochum 2025/26** | 34 | **62,5** | 88 | **54,6** | 60,1 | 67,2 | 63,5 | 73,1 |
| 2. Bundesliga gesamt | 5.502 | 59,0 | 99 | 57,3 | 59,1 | 59,9 | 59,4 | 64,6 |

Die Trennung zwischen Referenzkohorte (≈ 66) und Ligaschnitt (59) beträgt rund 7 Punkte. Das ist bewusst nicht größer: Der Gesamtscore mittelt über 15 Dimensionen, von denen sechs stark und sechs schwach trennen. **Auf Phasenebene ist die Trennung deutlich schärfer** — defensiv liegen Schalke (77,0) und Sturm (73,6) rund 16–20 Punkte über dem Ligaschnitt (57,3). Für die Managementdarstellung ist die Phasenebene daher aussagekräftiger als der Gesamtwert.

---

# 5. Historische Aufstiegsanalyse

## 5.1 Aufsteiger-Labels

Die Datenbank enthält keine Relegationsrunde. Die Abschlusstabellen wurden aus den Match-Ergebnissen gerechnet (3/1/0, dann Tordifferenz, dann erzielte Tore) und gegen die realen Tabellen plausibilisiert — **alle neun Saisons stimmen überein**:

| Saison | Meister | Zweiter | Relegation (3.) |
|---|---|---|---|
| 2017/18 | Fortuna Düsseldorf | Nürnberg | Holstein Kiel |
| 2018/19 | Köln | Paderborn | Union Berlin |
| 2019/20 | Arminia Bielefeld | Stuttgart | Heidenheim |
| 2020/21 | **Bochum** | Greuther Fürth | Holstein Kiel |
| 2021/22 | Schalke 04 | Werder Bremen | Hamburger SV |
| 2022/23 | Heidenheim | Darmstadt 98 | Hamburger SV |
| 2023/24 | St. Pauli | Holstein Kiel | Fortuna Düsseldorf |
| 2024/25 | Köln | Hamburger SV | Elversberg |
| 2025/26 | Schalke 04 | Elversberg | Paderborn |

n = 18 direkte Aufsteiger gegen 144 übrige Team-Saisons. Diese Stichprobe ist klein; alle Effektgrößen tragen deshalb Bootstrap-Konfidenzintervalle (10.000 Resamples wären möglich, gerechnet mit 2.000).

## 5.2 Effektgrößen

| KPI | Aufsteiger Ø | Rest Ø | Cliff's δ | 95-%-CI | Saisonstabilität |
|---|---|---|---|---|---|
| xPoints je Spiel | 1,681 | 1,348 | **0,792** | 0,68 – 0,89 | 9/9 |
| **npxG-Differenz** | **+0,434** | **−0,055** | **0,770** | 0,65 – 0,88 | 9/9 |
| npxG erzeugt | 1,671 | 1,368 | 0,734 | 0,60 – 0,85 | 9/9 |
| Schüsse | 14,13 | 12,28 | 0,706 | 0,54 – 0,85 | 9/9 |
| Box-Zugriffsrate | 0,144 | 0,123 | 0,646 | 0,46 – 0,81 | 9/9 |
| Schüsse zugelassen | 11,00 | 12,67 | 0,636 | 0,41 – 0,84 | 9/9 |
| Box-Zugriffsrate zugelassen | 0,111 | 0,127 | 0,558 | 0,24 – 0,81 | 9/9 |
| npxG zugelassen | 1,237 | 1,422 | 0,548 | 0,30 – 0,78 | 9/9 |
| Abschlussqualität (xG/Schuss) | 0,128 | 0,120 | 0,404 | 0,19 – 0,61 | 9/9 |
| Abschlussqualität zugelassen | 0,119 | 0,121 | 0,146 | **−0,14 – 0,43** | 8/9 |

**Konkrete Aufstiegs-Benchmarks:** Ein Aufsteiger erzeugt im Schnitt **1,67 npxG** und lässt **1,24 npxG** zu — Differenz **+0,43 je Spiel**. Nicht-Aufsteiger liegen bei 1,37 : 1,42, also **−0,05**.

**Verworfen:** *Zugelassene Abschlussqualität* — das Konfidenzintervall schließt null ein. Die Qualität der zugelassenen Schüsse unterscheidet Aufsteiger nicht; entscheidend ist ihre **Anzahl**.

## 5.3 Out-of-Sample-Validierung (Leave-One-Season-Out)

Vorhersage „Top 3", 9 Folds, ligaintern z-standardisiert:

| Feature-Set | Features | AUC Ø | AUC min | Brier | Top-3-Treffer (von 27) |
|---|---|---|---|---|---|
| Baseline Tordifferenz *(quasi-zirkulär)* | 1 | 0,983 | 0,944 | 0,045 | 22 |
| **Baseline npxG-Differenz** | **1** | **0,899** | **0,800** | **0,090** | **15** |
| npxG-Diff + Abschlussqualität | 2 | 0,891 | 0,778 | 0,092 | **16** |
| npxG-Diff + Box-Differenz | 2 | 0,881 | 0,778 | 0,091 | 15 |
| CC-Kern (npxG off + def) | 2 | 0,877 | 0,756 | 0,094 | 13 |
| CC-Set (6 KPIs) | 6 | 0,869 | 0,756 | 0,098 | 14 |

**Das ist der wichtigste Befund von Teil B — und er geht gegen die ursprüngliche Modellidee:** Das sechsteilige CC-Set schlägt die einfache npxG-Differenz **nicht**. Mit 144 Trainingszeilen und stark korrelierten Features überwiegt die Varianz den Informationsgewinn.

Die Tordifferenz-Baseline ist zwar mit Abstand am besten, aber **quasi-zirkulär**: Sie ist der Tabellen-Tiebreaker und praktisch eine Umschreibung des Ergebnisses. Sie taugt nicht als Leistungsmaß.

**Konsequenz für das Aufstiegsbarometer:** Es wird auf der **gegnerbereinigten npxG-Differenz** aufgebaut. Box-Zugriffsrate und Abschlussqualität bleiben als **Diagnose der Prozesskette** im Report, treiben den Score aber nicht.

---

# 6. Chance Creation und Chancenverwertung

## 6.1 Prozesskette (Diagnose, nicht Score)

```
Ballbesitz → gegn. Hälfte → Box → Abschluss → Abschlussqualität
```
| Schritt | Umsetzung |
|---|---|
| 1 Hälfte erreichen | `reaching_opponent_half / possession_number` |
| 2 Box erreichen | `reaching_opponent_box / reaching_opponent_half` |
| 3 Abschluss erzeugen | `shots / reaching_opponent_box` |
| 4 Qualität | `xg_per_shot`, gestützt durch `shots_from_danger_zone / shots` |

## 6.2 Score-tragende Größen

| # | KPI | Formel | Spiegel defensiv |
|---|---|---|---|
| CC1 | **npxG** | `general_xg − 0,76 × Elfmeter` | Gegnerzeile |
| CC2 | Box-Zugriffsrate | `reaching_opponent_box / possession_number` | Gegnerzeile |
| CC3 | Abschlussqualität | `general_xg_per_shot` | `general_xg_per_shot_against` |

Elfmeter aus `Σₚ (penalties × min/90)`, Standardwert 0,76 xG — als Approximation gekennzeichnet.
**Zugelassene Gesamtschüsse** kommen aus `G.general_shots`, **nie** aus `shots_against` (siehe 1.4).

**Barometer-Berechnung:** Perzentil der gegnerbereinigten npxG-Differenz in der Verteilung der 612 Team-Match-Zeilen der 18 direkten Aufsteiger. Offensive und defensive Teilbarometer analog auf `adj_CC1_npxg` bzw. `−adj_CC1d_npxg_gegen`.

## 6.3 Chancenverwertung — vier getrennte Komponenten

| # | Komponente | Größe | Confidence |
|---|---|---|---|
| CV1 | Abschlussqualität | `xg_per_shot` (Kontext, nicht doppelt gewertet) | hoch |
| CV2 | Abschlussausführung | `npG − npxG`, für beide Teams getrennt — seit Rev. 4 beidseitig im Aufstiegspanel (9.7) | hoch |
| CV3 | Torhütereffekt | `Σ_TW xg_save − Gegentore` | **mittel — PSxG-Proxy** |
| CV4 | Varianz | Perzentil des Ergebnisses in der Poisson-Binomial-Verteilung | hoch |

**CV3-Vorbehalt:** `wy_per_90_xg_save` ist befüllt und plausibel skaliert, die exakte Wyscout-Definition ist aber nicht gegen die Providerdokumentation verifiziert. Als Proxy führen, vor produktivem Einsatz klären (13.4).

**Regel:** CV2 wird nie ohne CV4 berichtet. Ein Torüberschuss von +0,5 xG liegt in aller Regel innerhalb der normalen Streuung.

---

# 7. Gegneranpassungsmodell

## 7.1 Form

Je Liga-Saison und je KPI ein additives Zwei-Wege-Modell mit Ridge-Shrinkage:

```
y_ij = mu + alpha_i (Erzeugung Team i) + beta_j (Zulassung Gegner j) + gamma · heim + eps
```

Intercept und Heimeffekt bleiben unbestraft, Team- und Gegnereffekte werden mit λ bestraft. λ wird je KPI über den rollierenden Vorhersagefehler in den drei datenreichsten Liga-Saisons dieses KPI gewählt.

**Kein Leakage:** Die Effekte für ein Spiel am Spieltag *g* stammen ausschließlich aus den Spieltagen < *g* derselben Saison. Vor Spieltag 6 ist die Erwartung das bis dahin beobachtete Ligamittel plus Heimeffekt; die Zeile wird markiert. 81,2 % aller Zeilen haben ausreichende Historie.

## 7.2 Erklärte Streuung — wo die Gegneranpassung trägt und wo nicht

| KPI | λ | erklärte Streuung |
|---|---|---|
| P2 Explosivität | 2 | **0,468** |
| CC2 Box-Zugriffsrate | 5 | **0,406** |
| D3 Hälften-Erreichung | 5 | **0,325** |
| D1 Pressingdruck | 5 | **0,324** |
| O2 Tiefenprogression | 5 | 0,317 |
| O1 Vertikalität | 2 | 0,264 |
| P1 Laufvolumen | 5 | 0,239 |
| OT2 Angriffsrate | 5 | 0,179 |
| O3 Flügel-Boxzuspiel | 10 | 0,165 |
| CC1 npxG | 10 | 0,164 |
| CC3 Abschlussqualität | 50 | 0,129 |
| D2 Ballgewinnhöhe | 10 | 0,123 |
| DT1 Gegenpressing | 10 | 0,117 |
| DT2 Gefährliche Verluste | 50 | 0,109 |
| P3 Endgeschwindigkeit | 10 | 0,092 |
| OT3 Ballgewinnqualität | 50 | 0,073 |
| **OT1 Konterrate** | 50 | **−0,226** |
| **DT3 Zugelassene Konter** | 50 | **−0,228** |

**Bei OT1 und DT3 hat die Gegneranpassung keinen Erklärungswert** — beide sind stark geglättete Konterquoten mit kaum Streuung. Für diese zwei KPIs ist `adj_*` nicht zu interpretieren; im Report nur der Rohwert zeigen.

## 7.3 Was bewusst nicht gemacht wird
- **Keine Tabellenplatzkorrektur** — der Platz ist ein Ergebnis, kein Stärkemaß.
- **Keine Korrektur über erwartete Aufstellung** — Aufstellungsdaten liegen vor, erwartete nicht.
- **Kein separater Strength-of-Schedule-Term** — er steckt bereits in β̂.

---

# 8. Outcome-Alignment-Modell

## 8.1 Rekonstruktion und Validierung

Shot-Level-xG existiert nicht. Je Spieler: `n = round(shots₉₀ × min/90)` Schüsse mit je `xG = xg_shot₉₀ × min/90 / n`. Elfmeter werden herausgerechnet und separat als Bernoulli(0,76) angehängt.

**Aggregationskontrolle über alle 8.620 Zeilen:**
- Schussanzahl stimmt in **99,85 %** exakt mit dem Teamwert überein
- xG: Median-Abweichung **0,005**, 99-%-Quantil 0,020, nur 0,12 % der Zeilen über 0,05

**Kalibrierungsprüfung:** Summe xPoints **11.958,7** gegen tatsächlich vergebene **11.786** Punkte — Abweichung **+1,47 %**.

**Zwei bekannte Verzerrungen:** (a) Die Varianz der Schussqualität *innerhalb* eines Spielers geht verloren; die Verteilung wird minimal zu eng. (b) Schüsse mit xG < 0,005 runden in der Per-90-Darstellung auf 0. Beide bleiben unkorrigiert und dokumentiert.

**Eine korrigierte Verzerrung:** Die Faltung lief zunächst mit fest 12 Toren Obergrenze. Bei vier Extremspielen (bis 33 Schüsse) gingen dadurch bis zu 0,34 % Wahrscheinlichkeitsmasse verloren. Die Obergrenze richtet sich jetzt nach der Schussanzahl — die Verteilung ist damit exakt, Kontrolle in `verify.py`.

## 8.2 Verteilung und Klassifikation

Exakte Poisson-Binomial-Faltung (keine Simulation nötig bei 5–25 Schüssen), dann `P(a:b) = P_VfL(a) × P_Gegner(b)` unter Unabhängigkeitsannahme — ohne Torminuten nicht auflösbar, als Limitation ausgewiesen.

| Δ = Punkte − xPoints | Klassifikation |
|---|---|
| > +0,90 | Ergebnis **deutlich besser** als die Leistung |
| +0,30 … +0,90 | Ergebnis **leicht besser** |
| −0,30 … +0,30 | Ergebnis **entspricht klar** der Leistung |
| −0,90 … −0,30 | Ergebnis **leicht schlechter** |
| < −0,90 | Ergebnis **deutlich schlechter** |

## 8.3 Durchgerechnetes Beispiel — Bochum – Hannover 96 1:1 (09.05.2026, ST 33)

| Team | Schussvektor (xG je Schuss) | Σ |
|---|---|---|
| Bochum | 0,280 · 0,120 · 0,120 · 0,060 · 0,060 · 0,040 · 0,040 · 0,020 · 0,010 | 0,75 |
| Hannover | 0,170 · 0,170 · 0,070 · 0,050 · 0,050 · 0,010 · 0,000 · 0,000 · 0,000 | 0,53 |

| Tore | 0 | 1 | 2 | 3 | ≥4 |
|---|---|---|---|---|---|
| Bochum | 44,1 % | 39,8 % | 13,5 % | 2,4 % | 0,3 % |
| Hannover | 57,2 % | 34,4 % | 7,6 % | 0,8 % | 0,0 % |

Sieg Bochum **37,8 %** · Remis **39,9 %** · Sieg Hannover **22,3 %**
Wahrscheinlichste Ergebnisse: 0:0 (25,2 %) · 1:0 (22,8 %) · 0:1 (15,1 %) · **1:1 (13,7 %, eingetreten)** · 2:0 (7,8 %)
**xPoints 1,53 · tatsächlich 1 · Δ = −0,53 → Ergebnis leicht schlechter als die Leistung.**

Spielstil-Scores dieses Spiels: Gesamt **54,2** (Confidence 0,72) — Offensiv 50,7 · Off. Umschalten 80,6 · **Defensiv 15,3** · Def. Umschalten 59,1 · Physisch 81,6. Aufstiegsbarometer 49 (offensiv 8, defensiv 94).
Lesart: Ein kontrolliert-passives Spiel. Die Defensivphase — der Identitätskern — war mit PPDA 16,8 praktisch abwesend; die niedrige Gegner-Chancenkreation entstand aus Tiefe, nicht aus Zugriff.

---

# 9. Berechnungslogik

## 9.1 Vorverarbeitung
**Shrinkage** bei kleinen Zählern (OT1, DT3, k = 12): `x̂ = (Zähler + k·μ) / (Nenner + k)` mit μ = Mittel der Liga-Saison. Ohne sie schwankte OT1 allein durch ±2 Konter über den halben Wertebereich.
**Normalisierung:** alle KPIs sind opportunity-basiert definiert; eine zusätzliche Normierung entfällt.

## 9.2 KPI → 0–100 (Rev. 3: zweistufige Drei-Punkt-Ankerung)

**Stufe 1 — je KPI.** Beide KPI-Formen werden auf eine monoton in Identitätskonformität
steigende Güte `g` gebracht:

```
einseitig:  g = v                     (v = orientierter z-Wert je Liga-Saison)
Korridor:   g = −|v − m|              (m = Median der Referenzkohorte)
```

Darauf drei Anker aus der Ligaverteilung von `g`:

```
Score   0 = Liga-P5
Score  50 = Liga-Median
Score 100 = P90 der Referenzkohorte   (bei normativen KPIs: Liga-P90)
```
stückweise linear, außerhalb geklemmt.

**Stufe 2 — auf Phasen- und Gesamtscore.** Das Mitteln über 15 teilunabhängige Dimensionen
zieht zur Mitte, weil kein Team auf allen gleichzeitig stark ist. Deshalb wird auf den fertigen
gewichteten Mittelwert dieselbe Ankerung erneut angewandt.

**Was das behebt.** In Rev. 2 lag der Median von OT1 bei **100** — die Hälfte aller Spiele
erreichte die Bestnote; bei D2 waren es 12 %. Jetzt liegt der Median jedes KPI-Scores bei
exakt 50,0 und die Sättigung je Rand unter 11 %. Der Abstand zwischen Referenzkohorte und
Ligarest im Gesamtscore wächst dadurch von 7,9 auf **14,4 Punkte**, während Cliff's δ mit
+0,287 unverändert bleibt — die Transformation ist monoton, sie macht vorhandene Trennung
sichtbar statt neue zu erzeugen.

## 9.3 Phasen, Gesamtwert, Confidence

| Phase | Gewicht | Begründung |
|---|---|---|
| Defensiv | 0,25 | RP1 ist der Identitätskern und die datenseitig stärkste Phase |
| Defensives Umschalten | 0,20 | unmittelbares Gegenpressing |
| Offensiv | 0,20 | RP3 + RP4 |
| Offensives Umschalten | 0,20 | Nutzung offener Räume |
| Physisch | 0,15 | RP2 — Voraussetzung, nicht Selbstzweck |

**Fehlende Phase:** Ohne Physikdaten wird auf die übrigen vier Phasen renormiert und `phasen_ohne_daten` gesetzt. **Nie mit 0 auffüllen.**

Rev. 4 führt zwei **getrennte** Größen. Sie beantworten verschiedene Fragen und werden
deshalb nicht miteinander verrechnet:

```
Confidence_KPI   = n_Ereignisse / (n_Ereignisse + 6)
Confidence_Phase = Σ (Confidence_KPI × Gewicht) / Σ Gewicht × Datenvollständigkeit
                   -> "Hatte DIESES Spiel genug Ereignisse?"   blendet aus ab < 0,20
Guete_Phase      = Σ (KPI-Güte × Gewicht) / Σ Gewicht
                   -> "Trennen diese KPIs überhaupt?"          blendet nie aus
  KPI-Güte:  1,0 stark (≥3/4) | 0,7 gemischt (2/4) | 0,5 normativ | 0,4 schwach
```

`Guete_Phase` ist je Phase konstant: Defensiv 0,91 · Def. Umschalten 0,70 · Offensiv 0,64 ·
Off. Umschalten 0,40 · Physisch 0,92. Sie erscheint als stilles Abzeichen (hoch / mittel /
schwach) an der Phasenzeile.

**Warum spielweise statt pauschal.** In 29 % aller Spiele gibt es **null** Konter, in 69 %
höchstens zwei. Ein einziger zusätzlicher Konter verschiebt OT1 um 0,46 SD ≈ 23 Score-Punkte.
Die Confidence bildet das ab: 0 Ereignisse → 0,00 · 1 → 0,14 · 5 → 0,45 · 20 → 0,77.
Im Dashboard werden Phasenzeilen unter **0,20** ausgegraut und mit dem limitierenden KPI
benannt („nur 1 Ereignis bei ‚Konterrate' — Wert nicht belastbar"). Ausgegraut wird nur, wo
ein Score existiert. Der Score selbst bleibt unverändert; sichtbar wird seine Belastbarkeit.

**Warum die Trennung nötig war** und wie stark sie wirkt: Abschnitt „Was Rev. 4 ändert", 4.1.

## 9.4 Warnflags — verändern keinen Score, erklären ihn

`DIREKT_UNKONTROLLIERT` (O1 über Korridor **und** Langball-Anteil im obersten Ligaviertel) · `MUTIG_UNGESICHERT` (D1 und D2 ≥ 80, D3 ≤ 40) · `UNTERZAHL` / `UEBERZAHL` (Minute unbekannt) · `PHYSIK_FEHLT` · `KLEINE_NENNER`

## 9.5 Trennschärfe- und Double-Counting-Prüfung

| Prüfung | Ergebnis |
|---|---|
| KPI in Teil A **und** Teil B? | **Nein.** Teil A enthält weder xG noch Schüsse noch Tore. Teil B enthält keine Physik-, Pressing- oder Gegenpressing-Größen. |
| Zwei KPIs derselben Phase mit \|r\| > 0,60? | **Nein**, geprüft über alle 8.620 Zeilen |
| Paare über alle 15 KPIs mit \|r\| > 0,60? | **Null** |

## 9.6 Aufstiegsbarometer

```
barometer_gesamt   = Perzentil von adj_npxg_diff   in der Verteilung der 18 Aufsteiger
barometer_offensiv = Perzentil von adj_CC1_npxg    in derselben Referenz
barometer_defensiv = Perzentil von −adj_CC1d_npxg  in derselben Referenz
barometer_roh      = wie oben, ohne Gegnerbereinigung
```

## 9.7 Aufstiegspanel je Spiel (Rev. 4)

Vier Parameter, alle auf derselben Skala: **Score 50 = auf Aufstiegsniveau**, Score 0 bzw. 100
bei einer Spanne, die dem 95. Perzentil der beobachteten Abweichungen entspricht.

```
Anforderung gegen DIESEN Gegner (additiv verschoben um seine Abweichung vom Ligamittel):
  ziel_off = 1,671 + (npxG, das dieser Gegner zulässt − Ligamittel)
  ziel_def = 1,237 + (npxG, das dieser Gegner erzeugt − Ligamittel)

  Chancenkreation   = 50 + 50 · clamp((npxG        − ziel_off) / 1,40, −1, 1)
  Abwehrleistung    = 50 + 50 · clamp((ziel_def − npxG_gegen)  / 1,40, −1, 1)
  Chancenverwertung = 50 + 50 · clamp(((npG − npxG)            − 0,079) / 2,20, −1, 1)
  Abwehreffizienz   = 50 + 50 · clamp(((npxG_gegen − npG_geg)  − 0,180) / 2,20, −1, 1)
  Nettoeffizienz    = 50 + 50 · clamp((Verwertung + Abwehreff. − 0,259) / 3,13, −1, 1)
```

Links steht, wie gut die Chancen waren (xG), rechts, was daraus wurde (Tore) — je einmal vorne
und einmal hinten. Beide Effizienzzeilen sind so gepolt, dass positiv = gut ist.

**Nettoeffizienz = tatsächliche minus erwartete Tordifferenz.** Sie beantwortet dieselbe Frage
wie Ebene C, nur in Toren statt in Punkten, und steht mit dem Torhütereffekt im Erklärtext.

**Grenzen.** Über ein einzelnes Spiel ist Effizienz fast reines Rauschen — erst über 10+ Spiele
deutbar. Die Abwehreffizienz enthält Torhüterleistung, Abschlussqualität des Gegners und Zufall
in einer Zahl; der Torhütereffekt allein erklärt sie zu r = 0,80. Elfmeter sind auf beiden
Seiten ausgeschlossen, damit die Größen zum npxG passen.

---

# Kontextualisierung: geprüft und verworfen

Vor Rev. 3 stand die Frage, ob der Spielstil-Score auf die Gegnerausrichtung normalisiert werden
muss. Über alle 298 erfassten Spiele gerechnet:

| Hypothese | r | r² | Urteil |
|---|---|---|---|
| Tiefer Gegnerblock → weniger Umschaltertrag | −0,29 | 8,5 % | schwach — und mit **umgekehrtem Vorzeichen**: gegen tiefe Blöcke steigt der Umschaltscore |
| Tiefer Gegnerblock → weniger Konter | −0,02 | 0,0 % | trägt nicht |
| Gegner-Ballbesitz → eigener Boxzugang | −0,13 | 1,8 % | trägt nicht |
| Mehr Ballgewinne → höherer Umschaltscore | +0,04 | 0,1 % | trägt nicht |
| Gegner läuft hoch an → eigene Vertikalität | +0,07 | 0,4 % | trägt nicht |

Bei tiefem Gegnerblock (PPDA über P75) entstehen **85** eigene Ballgewinne, bei hohem
Gegnerpressing **90** — ein Unterschied von fünf. **Eine Kontextualisierung des Spielstil-Scores
über die Gegnerausrichtung wäre nicht begründbar.**

Der wirkliche Störfaktor ist die Ereigniszahl, nicht der Gegner. Deshalb adressiert Rev. 3 ihn
über die Confidence (9.3) und nicht über eine Normalisierung. Das Hypothesen-Panel im Dashboard
ist bewusst ergebnisoffen gebaut: Jede weitere Kontextgröße lässt sich dort gegen jeden Score
prüfen, mit r, r² und n.

---

# Interpretationsmatrix

| # | Spielstiltreue | Chance Creation | Ergebnis | Interpretation | Handlungsimpuls |
|---|---|---|---|---|---|
| 1 | hoch (≥ 70) | Aufstiegsniveau (≥ 60) | gut | Wie geplant gespielt, aufstiegsfähige Leistung, vom Ergebnis bestätigt | Als Referenzspiel festhalten |
| 2 | hoch (≥ 70) | Aufstiegsniveau (≥ 60) | schlecht | Stil und Leistung stark; Ergebnis durch Verwertung, Torhüter oder Varianz beeinflusst | CV2/CV3/CV4 prüfen, **keine** taktische Korrektur |
| 3 | hoch (≥ 70) | unter Niveau (< 60) | beliebig | Nach der Idee gespielt, aber zu wenig Gefahr bzw. Kontrolle erzeugt | Prozesskette prüfen: bricht sie bei CC2 oder CC3? |
| 4 | niedrig (< 50) | Aufstiegsniveau (≥ 60) | beliebig | Effektiv, aber nicht aus der vorgesehenen Identität | Flag `MATCHPLAN_ABWEICHUNG` prüfen |
| 5 | niedrig (< 50) | schwach (< 50) | gut | Resultat über der Leistung, vermutlich nicht nachhaltig | Δ und CV4 prominent zeigen |

---

# 10. Visualisierungsspezifikation

Zwei getrennte Seiten, keine gemeinsame Farbskala.

## 10.1 Linke Seite — „Nähe zum idealen VfL-Spielstil"

Kopf: Gesamtwert 0–100, Confidence-Balken, darunter wörtlich *„Dieser Wert bewertet Identität und Umsetzung — nicht Aufstiegswahrscheinlichkeit und nicht das Ergebnis."*

Fünf Phasenblöcke mit je Phasen-Score, Confidence-Indikator und drei KPI-Streifen. Je Streifen:

```
KPI-Name (Management-Sprache)                                    Score
   ░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░
   ▲ L0      ▲ L1  ← Idealbereich →  ▲ U1                ▲ U0
              ╎  Verteilung der bisherigen VfL-Spiele (Box/Violin)
              ●  dieses Spiel
```

Datenquellen: `bochum_2526_scored.csv` (Punkt und Score), `kpi_match_level.csv` gefiltert auf Bochum (Verteilung), `corridors.json` → `einheiten_2bl_2526` (Band).
Farbe = ausschließlich Nähe zum Ideal. Divergierende Skala, damit „unter" und „über" dem Korridor bei zweiseitigen KPIs unterscheidbar bleiben.
Warnflags als Klartext-Chips unter dem betroffenen Block.
**O3 trägt eine sichtbare Markierung „normativ gesetzt".**

## 10.2 Rechte Seite — „Aufstiegsbarometer"

**Block A — Chance Creation:** Tabelle npxG / Box-Zugriffsrate / Abschlussqualität × (VfL-Wert · Gegnerwert · erwarteter VfL-Wert · erwarteter Gegnerwert · Aufsteiger-Benchmark · bereinigter Score). Spalten aus `CC*`, `exp_CC*`, `adj_CC*`; Benchmark aus Abschnitt 5.2.
Ergänzt um eine **Trichterdarstellung** der Prozesskette gegen die Aufsteiger-Benchmark, damit sichtbar wird, wo die Kette bricht.

**Block B — Chancenverwertung:** `verwertung_vfl`, `verwertung_gegner`, `torhueter_effekt` (mit Proxy-Hinweis), plus **verpflichtend** `ergebnis_perzentil` als Varianzhinweis.

**Block C — Ergebnis vs. Leistung:** Ergebnis groß · `xpoints` beider Teams · gestapelter Balken aus `p_sieg`/`p_remis`/`p_niederlage` · `top_ergebnisse` als Raster mit hervorgehobenem Eintritt · `klassifikation` als Klartextsatz.

## 10.3 Fußzeile
Ein Interpretationssatz aus der Matrix, Datenstand, Liste aktiver Warnflags.

---

# 11. Minimum Viable Version

Vollständig gerechnet und in `ergebnisse/` abgelegt:

| Komponente | Status |
|---|---|
| 15 Stil-KPIs, alle 8.620 Zeilen | ✅ |
| Korridore aus der Referenzkohorte | ✅ |
| Konstruktvalidierung, 58 Kandidaten | ✅ |
| Phasen-/Gesamtscore, Confidence, Warnflags | ✅ |
| Chance Creation offensiv + defensiv | ✅ |
| Chancenverwertung CV1–CV4 | ✅ (CV3 als Proxy) |
| Rollierendes Gegnermodell, 21 KPIs × 16 Liga-Saisons | ✅ |
| Outcome Alignment, exakte Poisson-Binomial-Faltung | ✅ |
| Aufstiegsanalyse 9 Saisons + LOSO | ✅ |
| Alle 34 Bochum-Spiele 2025/26 gescort | ✅ |

**Offen ist ausschließlich die Visualisierung** — Spezifikation in Abschnitt 10, Datenschema in `ergebnisse/SCHEMA.md`.

---

# 12. Advanced Version

| Voraussetzung | Was freigeschaltet würde |
|---|---|
| **SkillCorner reaktiviert** | TIP/OTIP-Split → Laufvolumen **mit und gegen den Ball** (die fehlende Hälfte von RP2); Pressing-Sprints, Rückwärtsverteidigung, Läufe hinter die Linie; PSV-99 statt Max-Speed; Anschluss an die bestehenden Positionsprofile |
| **Event-Daten mit Zeitstempeln** | Gegenpressing-**Versuche** (nicht nur Erfolge); sequence-isoliertes Umschalten → hebt die sechs schwachen KPIs aus Abschnitt 4.2; erzwungene Rückpässe; Umspielen der ersten Pressinglinie |
| **Shot-Level-xG + PSxG** | exakte Ergebnisverteilung ohne Rekonstruktion; CV3 von Proxy auf gemessen |
| **Torminuten** | echter Spielstandsverlauf; Auflösung der Unabhängigkeitsannahme in 8.2; korrekte Über-/Unterzahl-Normierung |
| **Tracking** | Linienbrüche über Positionsdaten; Kompaktheit und Höhe der Linie; **echte Cut-Backs** statt `crosses_low`-Proxy; Overlap-/Underlap-Runs |

---

# 13. Offene fachliche Entscheidungen

**13.1 — Positionsprofile ↔ verfügbare Daten.** FB-Index, DM-Index und Winger-Profil setzen auf SkillCorner-GI auf, die für keine der drei Ligen verfügbar ist. Zu klären: SkillCorner nachladen oder Profile auf Wyscout-Größen umstellen? Bis dahin liegen Teamframework und Positionsprofile auf unterschiedlichen Datenbasen.

**13.2 — Flügelfokus.** Kein Referenzteam belegt ihn (4.3). Entweder ist der Referenzpunkt anders gemeint, als die Daten ihn messen (Halbraum statt Außenbahn?), oder die Referenzteams passen zu diesem Punkt nicht. Bis zur Klärung ist O3 normativ gesetzt.

**13.3 — Langball vs. Flanke.** Ursprungsbriefing und Referenzpunkt 4 stehen in Spannung (3.2). Klärung mit dem Trainerstab.

**13.4 — Semantik von `wy_per_90_xg_save`.** Vor produktivem Einsatz von CV3 beim Provider bestätigen.

**13.5 — P1 oder Sprintdichte?** `S_sprintdichte` ist der einzige 4/4-Kandidat des Screenings, aber zu r = 0,90 mit P1 kollinear. Ein Tausch wäre vertretbar und würde die Physikphase leicht stärken.

**13.6 — Phasengewichte.** Normativ gesetzt, nicht empirisch hergeleitet. Eine Ableitung aus der Aufstiegsanalyse würde die Trennung der Ebenen aufweichen. Empfehlung: bei der normativen Setzung bleiben.

**13.7 — Semantik von `wy_totals_openplay_*`.** Summe 55–83 je Spiel, deutlich unter dem Gesamtpassvolumen. Betrifft nur den Sekundär-KPI `S_aufbaukontrolle`.

**13.8 — Rote Karten.** Ohne Minute ist die Dauer der Unterzahl unbekannt. Vorschlag: Spiele mit Roter Karte aus der Korridorkalibrierung ausschließen, in der Einzelbewertung mit Warnflag behalten. Aktuell sind sie enthalten.

---

# 14. Bewusst verworfene Parameter

## 14.1 Wegen Datenqualität
| Parameter | Grund |
|---|---|
| **Smart Passes** | Definitions-Drift über Saisons (15 → 1–6) |
| **Pressing-Duell-Erfolg** | Feld durchgängig 0 |
| **`meta_match_physical_data_downloaded`** | bildet die reale Befüllung nicht ab (1.3) |
| **Konter mit Abschluss** | Dekomposition arithmetisch inkonsistent (Restwert 3 bei `counter_attacks` = 1) |
| **`shots_against` als Schussvolumen** | bedeutet Schüsse **aufs Tor** gegen |
| **PSV-99, TIP/OTIP, alle SkillCorner-Metriken** | 0 Matches im Datenbestand |
| **Post-Shot xG, Schussplatzierung, Torminuten** | nicht vorhanden |

## 14.2 Wegen fehlender Trennschärfe (Screening, 58 Kandidaten)
| Parameter | δ | Konsistenz |
|---|---|---|
| Flügelanteil der Angriffe | −0,07 | 0/4 |
| Boxzuspiel je Box-Erreichung *(O3 aus Rev. 1)* | −0,10 | 0/4 |
| Flankenpräzision | −0,03 | 0/4 |
| Progressive Pässe je Ballbesitz *(O2 aus Rev. 1)* | −0,03 | 2/4 |
| Konteranteil an allen Angriffen | 0,00 | 0/4 |
| Luftzweikampfquote | 0,07 | 0/4 |
| Match-Tempo | 0,10 | 0/4 |
| Durchschnittliche Passlänge | −0,14 | 0/4 |
| Defensivduelle je gegnerischem Ballbesitz | −0,08 | 0/4 |
| Zugelassene Abschlussqualität *(Teil B)* | 0,15 | CI schließt 0 ein |

## 14.3 Wegen Redundanz (|r| > 0,60 zum gewählten KPI)
`u_deep_per_rec` (0,97 zu O2) · `y_sprint_per_min` (0,90 zu P1) · `d_opphalf_rec_share` (0,87 zu D2) · `y_dec_per_min` (0,82 zu P2) · `g_highloss_share` (0,70 zu D3) · `d_opp_ownhalf_loss_share` (0,74) · Vertical/Forward Passes · Pässe ins letzte Drittel · Kontakte in der Box · Challenge Intensity · Ballgewinne gegnerische Hälfte

## 14.4 Aus fachlichen Gründen
| Parameter | Grund |
|---|---|
| **Ballbesitzanteil** | Selbstzweck; nur als Kontext gezeigt (`S_ballbesitz`) |
| **Gesamtlaufdistanz** | Laufvolumen ohne Intensitätsbezug; als Sekundär-KPI geführt |
| **Interceptions, Tackles, Clearances** | stark spielstandsverzerrt |
| **Tabellenplatz als Gegnerstärke** | Ergebnisgröße, keine Stärkegröße — ersetzt durch α̂/β̂ |
| **Big-Chance Conversion** | Tore je Zone nicht trennbar |

---

## Anhang A: VfL Bochum 2025/26 — gerechnetes Saisonprofil

34 Spiele · **9. Platz** · 44 Punkte · 49:47 Tore · xPoints **47,6** (also 3,6 Punkte unter Wert)

| | Bochum | 2.-BL-Schnitt | Referenzkohorte (n = 264) | Confidence Bochum |
|---|---|---|---|---|
| **Gesamt Spielstiltreue** | **53,7** | 50,0 | 64,5 | — |
| Defensiv | **46,7** | 50,0 | **66,1** | 0,74 |
| Offensiv | 60,6 | 52,1 | 54,6 | 0,51 |
| Defensives Umschalten | 55,3 | 50,3 | 62,9 | 0,64 |
| Offensives Umschalten | 48,0 | 50,5 | 58,1 | **0,15** |
| Physisch | **60,5** | 49,3 | 61,8 | 0,92 |
| **Aufstiegsbarometer** | **40,3** | 44,1 | 51,0 | — |

*Werte nach der Rev.-3-Kalibrierung: 50 = Ligaschnitt. Die Confidence-Spalte zeigt, wie
belastbar der Phasenwert im Saisonmittel ist — die offensive Umschaltphase liegt mit 0,15
unter der Belastbarkeitsschwelle und ist als Entscheidungsgrundlage nicht geeignet.*

**Lesart nach der Interpretationsmatrix — Fall 3 mit Einschränkung:** Bochum lag offensiv
(60,6) und physisch (60,5) klar über dem Ligaschnitt, offensiv sogar über der Referenzkohorte.
**Die Defensivphase — der Identitätskern der vier Referenzpunkte — lag mit 46,7 unter dem
Ligaschnitt und 19,4 Punkte unter der Referenzkohorte.** Das Aufstiegsbarometer von 40,3 sagt:
Die erzeugte und zugelassene Chancenstruktur lag unter dem Niveau der 18 historischen Aufsteiger.
Die Mannschaft brachte die Intensität auf, setzte sie aber nicht in Zugriff um — die Lücke sitzt
zwischen Referenzpunkt 2 (erfüllt) und Referenzpunkt 1 (nicht erfüllt).

Die schärfere Rev.-3-Skala macht das Bild deutlicher: In Rev. 2 lag Bochum bei 62,5 gegenüber
59,0 Ligaschnitt — ein Abstand von 3,5, der wie Durchschnitt wirkte. Jetzt sind es 53,7 gegenüber
50,0, während die Referenzkohorte auf 64,5 steht. Der Abstand zum Vorbild ist damit als das
sichtbar, was er ist: **10,8 Punkte**, nicht 4,4.

## Anhang B: geprüfte Identifikatoren

| Objekt | ID |
|---|---|
| 2. Bundesliga · Bundesliga · Österr. Bundesliga | 423 · 426 · 168 |
| VfL Bochum (Männer) | **2448** — *nicht* 3030 (Frauen) |
| RB Leipzig · Sturm Graz · Hoffenheim · Schalke 04 | 2975 · 8742 · 2482 · 2449 |
| Ole Werner · Christian Ilzer · Miron Muslic | 454326 · 357755 · 684312 |
| Beispielspiel Bochum – Hannover 96 1:1 | `match_id 5717723` |

**Verwendete MCP-Tabellen:** `wyscout_match_sync` · `wyscout_match_team_stats_sync` · `wyscout_match_player_stats_sync` · `wyscout_team_sync` · `wyscout_coach_sync` · `wyscout_season_sync` · `wyscout_round_sync`

**Reproduktion:** `skripte/` in dieser Reihenfolge — `dl_matches.py` → `dl_stats.py` →
`kpis.py` → `kandidaten.py` → `korridore.py` → `gegnermodell.py` → `outcome.py` →
`aufstieg.py` → `scoring.py` → `dashboard_data.py` → `dashboard_match_data.py` → `verify.py`

**KPI tauschen:** `skripte/kpi_varianten.json` bearbeiten (Slot umschreiben oder `aktiv`
umstellen), dann `kpis.py` → `korridore.py` → `gegnermodell.py` → `scoring.py` → `verify.py`.
Die Datei enthält je Slot die geprüften Alternativen mit δ, Konsistenz und den Redundanz-Blockaden,
sodass keine erneute Suche nötig ist. `verify.py` prüft das neue Set automatisch auf
Redundanz (|r| < 0,60), Skalenlage und Konsistenzsumme.

## Anhang C: Verifikation

`skripte/verify.py` prüft zehn Kriterien und läuft vollständig durch:

| # | Kriterium | Ergebnis |
|---|---|---|
| 1 | Genau 2 Team-Zeilen je Spiel, alle Spiele erfasst, < 1 % NULL | ✅ max 0,02 % |
| 2 | Spielersumme reproduziert Teamwert | ✅ Schüsse 99,85 %, xG-Median 0,005 |
| 3 | Gerechnete Aufsteiger = reale Aufsteiger, 8 prüfbare Saisons | ✅ alle |
| 4 | **Kein Leakage:** Erwartung an Spieltag 20 unverändert, wenn spätere Spiele entfernt werden | ✅ Abweichung 0,0 |
| 5 | Barometer-Basis ist das beste nicht-zirkuläre Feature-Set | ✅ npxG-Diff, AUC 0,899 |
| 6 | Teil A ohne xG/Schüsse/Tore — geprüft über KPI-Namen **und** Quelltext der Formeln | ✅ |
| 7 | Kein KPI-Paar mit \|r\| > 0,60 | ✅ null Paare |
| 8 | Scores in [0, 100]; fehlende Physik als NaN, nicht 0 | ✅ |
| 9 | xPoints-Summe innerhalb 3 %; Wahrscheinlichkeiten summieren auf 1 | ✅ +1,47 % |
| 10 | Alle 15 Korridore vorhanden und wohlgeformt | ✅ |
