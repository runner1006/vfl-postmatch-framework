# Ergebnisdateien — Schema

Alle Dateien sind tidy (eine Zeile = eine Beobachtung), UTF-8, Komma-getrennt, Dezimalpunkt.
Schlüssel überall: `match_id` + `team_id`. Der Gegner steht in `opponent_id`.

Stand: 01.08.2026 · Datenbasis: 4.343 Spiele / 8.620 Team-Match-Zeilen aus 3 Ligen, 16 Liga-Saisons.

---

## Übersicht

| Datei | Zeilen | Was drin steht | Wofür in der Visualisierung |
|---|---|---|---|
| `kpi_match_level.csv` | 8.620 | Vollmatrix: alle KPIs, z-Werte, Gegnererwartung, bereinigte Residuen, Scores | Ligavergleiche, Verteilungen im Hintergrund der KPI-Streifen |
| `bochum_2526_scored.csv` | 34 | Nur VfL Bochum 2025/26, identische Spalten | Die Post-Match-Seite selbst |
| `corridors.json` | 15 KPIs | Korridoranker L0/L1/U1/U0 in z und in 2.-BL-Einheiten | Idealbereich-Band je KPI-Streifen |
| `reference_cohort_profile.csv` | 15 | Trennschärfe je KPI und Referenzteam | Confidence-Symbole, Methodenanhang |
| `kandidaten_screening.csv` | 58 | Alle geprüften Operationalisierungen mit Trennschärfe | Nachweis der KPI-Auswahl |
| `promotion_analysis.csv` | 10 | Effektgrößen Aufsteiger vs. Rest | Aufstiegs-Benchmarks |
| `loso_validation.csv` | 6 | Out-of-Sample-Güte der Feature-Sets | Methodenanhang |
| `abschlusstabellen_2bl.csv` | 162 | Gerechnete Abschlusstabellen, 9 Saisons | Aufsteiger-Labels, Kontext |
| `team_season_stats.csv` | 162 | Saisonmittel je Team-Saison + Platzierung | Saisonvergleiche |
| `opponent_model_params.csv` | 21 | λ, RMSE, erklärte Streuung je KPI | Methodenanhang, Vorbehalte |
| `outcome_alignment.csv` | 8.620 | Schussvektoren, Torverteilungen, xPoints, Klassifikation | Block C der rechten Seite |
| `redundancy_matrix.csv` | 15×15 | Paarweise Korrelationen der 15 KPIs | Audit |
| `dashboard_data.json` | — | Aggregate für die Übersichtscharts | `dashboard.html` |
| `dashboard_matches.json` | 298 Spiele | Spielweise Rohgrößen + Parameterdokumentation | Spielbericht und Parameterseite in `dashboard.html` |

---

## `kpi_match_level.csv` / `bochum_2526_scored.csv`

Identisches Schema, 163 Spalten.

### Kontext
| Spalte | Bedeutung |
|---|---|
| `match_id`, `team_id`, `team` | Spiel und betrachtetes Team |
| `opponent_id`, `gegner` | Gegner |
| `liga` | `2BL` / `BL` / `AUT` |
| `saison`, `liga_saison` | z. B. `2025/26`, `2BL 2025/26` — **Bezugseinheit jeder z-Standardisierung** |
| `date_utc`, `gameweek`, `is_home` | Zeit, Spieltag, Heimspiel |
| `tore`, `gegentore`, `punkte` | Ergebnis |
| `rote_karten`, `rote_karten_gegner` | Platzverweise (**ohne Minute** — Datenlücke) |
| `eff_min` | effektive Spielzeit in Minuten = (Gesamtzeit − tote Zeit)/60 |
| `ist_aufsteiger_saison` | 1, wenn das Team in dieser Saison direkt aufgestiegen ist |

### Je KPI sechs Spalten
Für jeden der 15 KPIs `<K>`:

| Spalte | Bedeutung |
|---|---|
| `<K>` | Rohwert in fachlicher Einheit |
| `z_<K>` | z-Wert **innerhalb der Liga-Saison** |
| `v_<K>` | orientierter z-Wert: `orient × z`. Positiv = näher an der Spielidee |
| `exp_<K>` | Gegnererwartung aus dem rollierenden Zwei-Wege-Modell (Rohskala) |
| `adj_<K>` | gegnerbereinigtes Residuum `(Rohwert − Erwartung) / SD der Liga-Saison` |
| `score_<K>` | 0–100 über die Korridoranker aus `corridors.json` |

**Für die Darstellung gilt:** `<K>` ist der Wert, den man dem Trainer zeigt. `score_<K>` färbt den Streifen. `adj_<K>` beantwortet „war das gegen diesen Gegner gut?". `exp_<K>` ist die Vergleichslinie.

### Phasen und Gesamt
| Spalte | Bedeutung |
|---|---|
| `phase_offensiv`, `phase_off_umschalten`, `phase_defensiv`, `phase_def_umschalten`, `phase_physisch` | Phasen-Score 0–100, gewichtetes Mittel der drei KPIs |
| `conf_<phase>` | Belastbarkeit **dieses Spiels** 0–1 = gewichtete Ereignis-Confidence × Datenvollständigkeit. Ab Rev. 4 **ohne** KPI-Güte |
| `guete_<phase>` | Trennschärfe der KPIs dieser Phase 0–1, über alle Spiele konstant (Defensiv 0,91 · Def. Umschalten 0,70 · Offensiv 0,64 · Off. Umschalten 0,40 · Physisch 0,92) |
| `gesamtscore_spielstil` | 0–100, gewichtetes Mittel der Phasen (fehlende Phasen werden herausnormiert) |
| `confidence_gesamt` | gewichtete Confidence über die Phasen |
| `guete_gesamt` | gewichtete Trennschärfe über die Phasen |
| `phasen_ohne_daten` | Anzahl Phasen ohne Daten (>0 heißt: Physik fehlt) |
| `warnflags` | Semikolon-getrennt, siehe unten |

### Warnflags
`DIREKT_UNKONTROLLIERT` · `MUTIG_UNGESICHERT` · `UNTERZAHL` · `UEBERZAHL` · `PHYSIK_FEHLT` · `KLEINE_NENNER`

Die Flags verändern **keinen Score**. Sie erklären ihn.

### Teil B
| Spalte | Bedeutung |
|---|---|
| `CC1_npxg`, `CC1d_npxg_gegen` | Non-Penalty xG eigen / zugelassen |
| `npxg_diff`, `adj_npxg_diff` | Differenz roh / gegnerbereinigt |
| `CC2_box_zugriffsrate`, `CC2d_…_gegen` | Ballbesitze mit Box-Erreichung je Ballbesitz |
| `CC3_abschlussqualitaet`, `CC3d_…_gegen` | xG je Schuss |
| `barometer_gesamt` | 0–100: Perzentil der bereinigten npxG-Differenz in der Verteilung der 18 direkten Aufsteiger |
| `barometer_offensiv`, `barometer_defensiv` | dieselbe Logik für npxG eigen bzw. zugelassen |
| `barometer_roh` | ohne Gegnerbereinigung |
| `npg`, `verwertung_vfl`, `verwertung_gegner` | Tore ohne Elfmeter, Torüberschuss beider Teams |
| `torhueter_effekt` | `xg_save` des TW minus Gegentore (**PSxG-Proxy**, Semantik unbestätigt) |

### Teil C
`xpoints` · `p_sieg` · `p_remis` · `p_niederlage` · `delta_punkte` (= Punkte − xPoints) · `klassifikation` · `ergebnis_perzentil` · `top_ergebnisse` · `schussvektor`

### Sekundär-KPIs (berichtet, **nicht** im Score)
`S_fluegelanteil` · `S_flankenpraezision` · `S_cutback_proxy` · `S_aufbaukontrolle` · `S_through_tiefe` · `S_prog_pass_per_poss` · `S_prog_runs_per_poss` · `S_hohe_verluste_anteil` · `S_ballbesitz` · `S_sprintdichte` · `S_hi_count_dichte` · `S_laufdistanz` · `S_dezeleration`

---

## `corridors.json`

Je KPI:
```json
"D1_pressingdruck": {
  "phase": "defensiv", "gewicht_in_phase": 0.35,
  "orientierung": -1,        // niedriger Rohwert = mehr Spielidee
  "form": "band",            // "band" = zweiseitiger Korridor, "up" = einseitig
  "quelle_korridor": "...",  // woher die Anker stammen
  "z": { "L0": …, "L1": …, "U1": …, "U0": … },
  "einheiten_2bl_2526": { … , "liga_mittel": …, "liga_sd": … },
  "kohorte_n": 264
}
```

**Score-Funktion** (identisch für alle KPIs, `v` = orientierter z-Wert):

```
v in [L1, U1]  -> 100
v in [L0, L1)  -> 100 * (v - L0) / (L1 - L0)
v in (U1, U0]  -> 100 * (U0 - v) / (U0 - U1)
sonst          -> 0
```

`U1`/`U0` sind `null` bei einseitigen KPIs — dort bleibt der Score oberhalb von `L1` bei 100.

**Ankerregel** (vorab festgelegt, für alle KPIs gleich): Score 100 = oberes Quartil der Referenzkohorte, Score 0 = Liga-P10. Bei zweiseitigen KPIs ist der 100er-Bereich das Kohorten-Intervall P25–P75, der Abfall auf 0 erfolgt zu Liga-P5 bzw. Liga-P95.

---

## Wichtige Vorbehalte für die Visualisierung

1. **Physik existiert nicht durchgängig.** Rund 21 % der 2.-BL-Zeilen, 38 % der österreichischen und 67 % der Bundesliga-Zeilen haben Physikdaten. Bei fehlender Physik ist `phase_physisch` NaN und der Gesamtscore auf vier Phasen normiert — `phasen_ohne_daten` zeigt das an. **Nicht mit 0 auffüllen.**
2. **`adj_*` ist erst ab Spieltag 6 belastbar** (81 % der Zeilen). Davor ist die Gegnererwartung das bis dahin beobachtete Ligamittel.
3. **Die Umschaltphasen tragen niedrige Confidence** (~0,4–0,5). Das ist eine Datengrenze, kein Rechenfehler: ohne Event-Daten lässt sich kein Umschaltmoment zeitlich isolieren.
4. **`O3_fluegel_boxzuspiel` hat einen normativ gesetzten Korridor**, weil keine der vier Referenzmannschaften flügellastig spielt. Im Report als solcher kennzeichnen.
5. **Kein KPI kommt in Teil A und Teil B zugleich vor.** Teil A enthält weder xG noch Schüsse.

---

## `dashboard_matches.json` — Spielbericht und Normalisierung

Enthält **Rohgrößen, keine fertigen Scores**: `npxg`, `npxg_geg`, `tore`, `gt`, die Modellerwartung
`exp_npxg` / `exp_npxg_geg`, sowie je Liga-Saison das Ligamittel (`ligamittel`) und die Saisonmittel
jedes Teams (`staerke[liga_saison][team_id] = {off, def, n}`). Die Bewertung der rechten Berichtsseite
wird erst im Dashboard gerechnet.

**Der Normalisierungsblock `NORM` in `dashboard.html` ist die einzige Stelle, die das steuert.**
Er definiert drei austauschbare Methoden für die Gegnererwartung:

| Methode | Erwartung an npxG erzeugt / zugelassen |
|---|---|
| `aus` | Ligamittel — ohne Gegnerbezug |
| `einfach` | Was dieser Gegner in der Saison im Schnitt zulässt bzw. erzeugt |
| `modell` (Default) | ŷ aus dem rollierenden Zwei-Wege-Modell (eigene Stärke × Gegner × Heim) |

Score-Abbildung: `Score = 50 + 50 · clamp((Rohwert − Erwartung) / Spanne, −1, +1)`.
Die Spannen sind auf das **95. Perzentil der beobachteten Abweichungen** über alle 298 erfassten Spiele
gesetzt (Kreation 1,40 xG · Verwertung 2,30 Tore); damit erreichen rund 5 % der Spiele je Seite den
Skalenrand. Zielwerte (`ziel`) sind der Aufsteiger-Benchmark der 2. Bundesliga: 1,671 npxG erzeugt,
1,237 zugelassen.

Eine eigene Methode ergänzt man, indem man unter `NORM.methoden` einen Eintrag mit
`erwartung(spiel, kontext) → {off, def}` hinzufügt — alles andere liest den Block nur aus.

### Rev. 3 — was sich geändert hat

**Skala.** Zweistufige Drei-Punkt-Ankerung ersetzt den Vier-Anker-Korridor. Je KPI:
0 = Liga-P5, 50 = Liga-Median, 100 = P90 der Referenzkohorte, angewandt auf die Güte
`g` (einseitig `g = v`, Korridor `g = −|v − Kohortenmitte|`). Dieselbe Ankerung läuft ein
zweites Mal auf Phasen- und Gesamtscore. Folge: **Median jedes Scores exakt 50**,
Sättigung je Rand ≤ 11 % (vorher bis 50 %), Abstand Kohorte ↔ Liga 14,4 statt 7,9 Punkte.
Die Anker stehen je KPI in `corridors.json` unter `anker_guete` (z-Raum) und
`einheiten_2bl_2526` (`score0` / `score50` / `score100`, bei Korridor-KPIs als Wertepaar).

**Confidence.** Neu je Spiel und je KPI: `conf = n/(n+6)` mit der Ereigniszahl `n_<KPI>`.
Beide Spalten stehen in `kpi_match_level.csv`. **Grund:** In 29 % der Spiele gibt es
null Konter; ein einzelner verschiebt OT1 um 0,46 SD ≈ 23 Punkte.
*(Rev. 4 hat die Phasen-Confidence entflochten — siehe unten.)*

**KPI-Set konfigurierbar.** `skripte/kpi_varianten.json` hält das aktive Set und alle
geprüften Alternativen mit δ, Konsistenz und Redundanz-Blockaden. Vier Slots wurden getauscht
(DT3, und dadurch erzwungen D3, OT2, O2) — siehe `aenderungen_rev3` in der Datei.

**Kontext.** `dashboard_matches.json` enthält je Spiel `kontext` / `kontext_p` (elf
Gegnerkennwerte und eigene Nenner mit Perzentil), `blockhoehe` (z-standardisierter
Blockhöhen-Index des Gegners) sowie `kpi_n` / `kpi_conf` / `ph_conf`. Der Abschnitt
`hypothesen` hält fünf vorgerechnete Kontexthypothesen mit r, n und Urteil.

### Rev. 4 — was sich geändert hat

**Trennschärfe von Belastbarkeit getrennt.** Rev. 3 multiplizierte beides in `conf_<phase>`.
Da die KPI-Güte über alle Spiele konstant ist, konnte eine Phase aus drei schwachen KPIs die
Schwelle nie erreichen: Das offensive Umschalten war in **100 %** der Spiele ausgegraut.
Rev. 4 führt `guete_<phase>` (strukturell, stilles Abzeichen) und `conf_<phase>`
(nur Ereigniszahl × Vollständigkeit, Schwelle **0,20**) getrennt. Ergebnis: **5,8 %** der
Umschaltphasen ausgeblendet, alle übrigen Phasen 0 %, bei Bochum 2025/26 kein einziges Spiel.
Ausgeblendet wird nur, wo ein Score existiert.

**Beidseitige Effizienz.** `dashboard_matches.json` führt je Spiel neu `npg` (Tore ohne
Elfmeter), `npg_geg` (Gegentore ohne Elfmeter, aus der Gegnerzeile desselben Spiels),
`tw_effekt` (Torhütereffekt) und `ph_guete`. Das Aufstiegspanel zeigt daraus vier statt drei
Zeilen: Chancenkreation / Abwehrleistung (xG) und Chancenverwertung / **Abwehreffizienz**
(Tore gegen xG). Referenzwerte im `NORM`-Block: `ziel_effizienz = {off: 0,079, def: 0,180,
netto: 0,259}`, Spannen 2,20 je Seite und 3,13 netto. Da beide Seiten dieselbe Größe
verwenden, ist das Ligamittel der Nettoeffizienz konstruktionsbedingt exakt 0,000.

**Korrektur.** Eine Ersatzrechnung in `dashboard_match_data.py` überschrieb die vorhandene
`npg`-Spalte mit den Gesamttoren (die abgefragte Spalte `n_penalties` existierte nie) —
Elfmeter wären in die Effizienz eingegangen. Behoben.

**Build-Schritt.** `skripte/build_dashboard.py` spielt `dashboard_data.json` und
`dashboard_matches.json` in die beiden Konstanten `DATA` und `MD` in `dashboard.html` ein.
Nach jedem Rechenlauf aufrufen; vorher wurde von Hand kopiert.

### Dritte Ansicht: Aufstiegstauglichkeit

Die beiden ersten Panels messen gegen die **Gegnererwartung** (50 = so gut wie erwartbar) und
zeigen als Bezugsmarke den Teamdurchschnitt. Das dritte Panel misst stattdessen gegen die
**Aufstiegsanforderung** — 50 = exakt auf Aufstiegsniveau, markiert als gestrichelte Linie
im Thermometer.

Der Benchmark 1,671 npxG erzeugt / 1,237 zugelassen ist ein Mittel über *alle* Gegner. Gegen
einen starken Gegner ist er nicht erreichbar, gegen einen schwachen zu niedrig. `NORM.ziel_gegnerbereinigt`
verschiebt ihn deshalb additiv um die Abweichung dieses Gegners vom Ligamittel:

```
nötig erzeugt     = 1,671 + (Ø npxG, das dieser Gegner zulässt  − Ligamittel)
erlaubt zugelassen = 1,237 + (Ø npxG, das dieser Gegner erzeugt − Ligamittel)
Aufstiegstauglichkeit = 50 + 50 · clamp((Ist-Differenz − Ziel-Differenz) / 2,10, −1, +1)
```

Die Spanne 2,10 ist das 95. Perzentil von |Ist-Differenz − Ziel-Differenz| über alle 298 Spiele.
Grundlage ist die npxG-Differenz, weil die LOSO-Validierung sie als besten nicht-zirkulären
Prädiktor für Top-3 ausgewiesen hat (AUC 0,899).

**Vergleichslinien** (gerechnet, in `benchmark`): Die 18 direkten Aufsteiger erreichten ihr eigenes
gegnerbereinigtes Niveau in **49,2 %** ihrer 612 Spiele, die 2. Bundesliga insgesamt in **32,6 %**.
Bochum 2025/26 kommt auf 29 %.

Auch dieser Teil ist austauschbar: `ziel_gegnerbereinigt` durch eine eigene Funktion
`(spiel, kontext) → {off, def}` ersetzen, `spanne_aufstieg` und `ziel` anpassen.
