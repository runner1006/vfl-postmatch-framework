# Die Football-Lernschleife

**Positionspapier zur technischen Umsetzung einer modellunabhängigen Football Intelligence Layer**

Stand: September 2026. Grundlage sind das interne Strategiememo zum Football Foundation Model, die beiden Architekturpapiere „Football AI Hub“ und „Knowledge Hub und Benchmark-Ökosystem“ sowie der lauffähige Prototyp `fussball-ki`.

---

## Kurzfassung

Wir bauen kein Fußball-LLM. Wir bauen die Schleife, in der Fußball-KI messbar besser wird, und besitzen alles, was darin nicht austauschbar ist: den Datenstandard, das Wissen, die Aufgaben, den Benchmark, die Expertenurteile und die Entscheidungshistorie. Das Sprachmodell ist ein Stecker. Es darf morgen ein anderes sein.

Drei Grundsätze bestimmen die Umsetzung:

1. **Der Hub ist die Quelle der Wahrheit, das LLM ist Orchestrator und Reasoning-Schicht.** Fakten, Daten, Dokumente und Klubwissen bleiben außerhalb des Modells, versioniert, mit Rechten und Provenienz. Fine-Tuning formt Verhalten, Ontologie und Format, nicht Wissen.
2. **Nichts wird eingesetzt, was seinen Gewinn nicht auf einem verborgenen Benchmark bewiesen hat.** Modellwechsel, RAG-Pack, Prompt, Skill, Router-Regel: jede Änderung ist eine falsifizierbare Hypothese gegen denselben eingefrorenen Zustand.
3. **Jede Interaktion mit einem Experten ist ein Datenpunkt, aber erst nach Kuratierung ein Lernsignal.** Trainer korrigieren, Outcomes kommen dazu, Präferenz und Ergebnis werden getrennt gemessen. Nie lernt das System ungeprüft aus seinen eigenen Antworten.

Modellunabhängigkeit heißt nicht, alles selbst zu entwickeln. Sie heißt: Wenn ein besseres Basismodell erscheint, tauschen wir den Reasoning-Layer und behalten Millionen Fälle, Evaluationssets, Korrekturen, Outcomes, Ontologien und Spezialmodelle.

---

## 1. Position

### Was das Asset ist

| Asset | Inhalt | Warum schwer kopierbar |
|---|---|---|
| Football Data Standard | kanonisches, versioniertes Modell für Events, Tracking, Video, Training, Medizin, Scouting, Taktik; Provider über Adapter | Cross-Provider-Identität und Metrikdefinitionen sind mühsam und werden mit jedem Anbieter wertvoller |
| Knowledge Hub | Dokumente, Klubdoktrin, Skills und Multimedia mit Rechten, Provenienz und Snapshots | rechtebewusstes, zitierfähiges Wissen statt Vektorindex |
| Football Benchmark | private, versionierte Aufgaben mit Gold-Standard und Expertenrubrik, verborgener Testsplit | die einzige Instanz, die „besser“ beweisen kann |
| Expert Judgement | strukturierte, blinde Bewertungen von Trainern, Scouts, Analysten mit gemessener Reliabilität | proprietärer Maßstab dafür, was im Fußball eine gute Entscheidung ist |
| Football Intelligence Data | Fälle der Form Situation → Frage → Analyse → Hypothese → Korrektur → Entscheidung → Intervention → Outcome | entsteht nur im Produktbetrieb mit Profis, wächst mit jedem Klub |

### Was nicht gebaut wird

Kein Pretraining von null. Kein „alle Bücher in den Kontext“. Kein Multi-LLM-Frontend, das drei Modelle dieselbe Frage stellt und abstimmen lässt. Kein System, das autonom Transfer-, Vertrags- oder personenbezogene Entscheidungen trifft.

### Lernen auf zwei Ebenen

Der Prototyp zeigt das Prinzip im Kleinen: Ein Forscher-LLM schlägt Modellhypothesen vor, ein Rechenkern prüft sie per Vorwärtsvalidierung, ein Lehrer-LLM schreibt danach die Erkenntnisse neu, die der Forscher in der nächsten Runde vorgelegt bekommt. Gelernt werden Gewichte der Fußballmodelle und das Wissen, mit dem das LLM arbeitet. Beides liegt als Klartext im Versionsverlauf. Die Plattform skaliert genau diese Schleife: mehr Aufgaben, mehr Modalitäten, echte Experten statt eines Rechenkerns als Korrektiv.

---

## 2. Zielarchitektur

```
            Trainer · Analyst · Scout · Data Scientist · Sportdirektor
                                    │
                        Ask Football · Compare · Decision Room
                        Knowledge Studio · Benchmark Lab · Workflow Builder
                                    │
 ┌──────────────────────────────────▼──────────────────────────────────┐
 │  TASK RESOLVER  →  POLICY & CAPABILITY ENGINE  →  WORKFLOW ORCHESTRATOR │
 └───────┬────────────────────┬────────────────────────┬───────────────┘
         │                    │                        │
   KNOWLEDGE SERVICE    FOOTBALL DATA SERVICE     SKILL / TOOL REGISTRY
   hybrides Retrieval   kanonische DB, Feature-   versionierte Fußball-
   Rechte, Snapshots    Service, Event/Tracking   funktionen als Code
         │                    │                        │
 ┌───────▼────────────────────▼────────────────────────▼───────────────┐
 │  MODEL ROUTER  →  Provider-neutraler Gateway  →  Frontier · Open-Weights │
 │                                                 lokal (vLLM) · Spezialmodelle │
 └───────┬──────────────────────────────────────────────────────────────┘
         │
   EXPERIMENT RUNNER → EVALUATION ENGINE → ENSEMBLE / DECISION ENGINE
         │                                          │
   BENCHMARK STORE                          HUMAN REVIEW → DECISION OBJECT
         ▲                                          │
         └──────────── FEEDBACK / OUTCOME ◄─────────┘
                       Audit · Tracing · Kosten über alles
```

Schichten, Aufgaben und Technikentscheidungen:

| Schicht | Aufgabe | Technik | Leitprinzip |
|---|---|---|---|
| Lakehouse | Rohdaten unveränderlich, kanonische Daten, Tracking columnar | Object Storage, Parquet, Iceberg (Schema-Evolution, Time Travel) | Bronze → Silber → Gold; jeder Snapshot reproduzierbar |
| Operational Store | Tenants, Nutzer, Rechte, Tasks, Annotationen, Konfiguration, Embeddings | PostgreSQL mit Row-Level Security, pgvector | Control Plane relational, Embeddings zunächst im selben System |
| Search | Keyword plus semantisch plus Metadatenfilter, ACL beim Retrieval | Postgres Full-Text plus pgvector, später OpenSearch | Fußballbegriffe brauchen exakte Treffer, nicht nur Ähnlichkeit |
| Analytics / Tools | SQL und OLAP auf Events und Tracking, Fußballfunktionen | Feature-Service, Python-Pakete mit JSON-Schema | Das LLM bekommt Funktionen, keine Millionen Zeilen |
| Workflow | graphbasierte, persistente Entscheidungsprozesse mit Human-in-the-Loop | Graph-Orchestrierung mit Checkpoints | Workflow ist Version, nicht Prompt |
| Model Gateway | eine API für Frontier-, offene und eigene Modelle | Adapter je Provider, vLLM für lokale Modelle | Domänenlogik hängt an keinem Anbieter |
| Router | Hard Gates, dann empirischer Score | eigene Policy Engine | nie ein LLM fragen, welches LLM besser ist |
| Experimente / Evals | Manifest, Matrix, Metriken, Regression | MLflow für Runs, Prompt- und Modellregistry; eigener Benchmark-Layer | der fußballspezifische Teil bleibt proprietär |
| Observability | jede Aktion mit Run-ID | OpenTelemetry, append-only Audit Store | Logs selbst sind sensibel |
| Deployment | Multi-Tenant EU, Single Tenant, Hybrid, On-Prem | Container, Kubernetes ab Skalierung | eine logische Architektur, mehrere Betriebsformen |

---

## 3. Kanonisches Datenmodell und Evidenz

**Regel eins:** Kein Provider-Schema wird zum internen Standard. Jeder Anbieter bekommt einen Adapter auf das kanonische Modell. Rohwert und kanonischer Wert bleiben nebeneinander erhalten, damit sichtbar bleibt, ob ein Unterschied aus dem Fußball oder aus der Übersetzung stammt.

**Pflichtmetadaten jedes Objekts:** `canonical_id`, `source_system`, `source_external_id`, `schema_version`, `ontology_version`, `captured_at`, `ingested_at`, `valid_from`, `valid_to`, `confidence`, `provenance`, `rights_scope`, `tenant_id`, `data_snapshot_id`.

**Zeit und Raum:** Periode, Match-Uhr in Millisekunden, absoluter Video-Timecode, Pitch-Dimensionen, metrische und normalisierte Koordinaten, Angriffsrichtung. Ohne diese Synchronisationsschicht lassen sich Event, Tracking und Video nicht gemeinsam nutzen.

**Der Standard ist modular,** fünf Contracts statt einer Spezifikation: Football Core (Spieler, Team, Wettbewerb, Match, Saison, Position, Rolle), Football Event, Football Tracking, Football Metric (Definition, Formel, Nenner, Population, Einheit, Provider, Version) und Football AI Evaluation (Task, Inputs, Wissen, erwarteter Output, Benchmark, Expertenrating). Jede Metrik hat eine Definition, nicht nur einen Namen: „Pressures“ oder „Progressive Pass“ bedeuten bei zwei Anbietern nicht dasselbe.

**Domänenobjekte jenseits des Spiels:** Trainingssession mit Drills und individueller Exposure (Rohmetriken plus Threshold-Version, sRPE neben externer Last), Medical Episode nach IOC-Systematik mit FHIR-inspirierter Grenze und ICD-11-Mapping, Scouting Report mit Rating-Schema-Version und Evidenz, Tactical Concept als explizite Entscheidungsregel (Phase, Prinzip, Trigger, Zone, Rolle, gewünschtes Verhalten, Ausnahme), Knowledge Asset mit Originalquelle und Zitierfähigkeit.

**Evidence Link als universelle Beweisschicht.** Die ideale Antwort lautet nicht „der Gegner ist anfällig hinter dem linken Außenverteidiger“, sondern maschinenlesbar: Claim → Match → Events → Tracking-Fenster → Clips mit Timecodes → Tactical Concept. Dieselbe Behauptung kann dann vom Trainer, vom Benchmark-Rater und von einem anderen Modell geprüft werden.

**Rights Registry statt Vektorindex.** Jede Quelle führt `copyright_owner`, `license_type`, `lawful_access_basis`, `retrieval_allowed`, `training_allowed`, `quotation_constraints`, `TDM_rights_reserved`, `territory`, `expiry_date`. Retrieval und Training sind getrennte Rechte.

**Fünf Datenklassen steuern das Routing:** Public, Licensed, Club Confidential, Personal Restricted, Highly Sensitive. Jeder Provider hat `allowed_data_classes`, `allowed_regions`, `retention_policy`, `training_policy`, `contract_id`, `DPA_status`. Eine Anfrage wird technisch blockiert, bevor Daten den falschen Endpoint erreichen. Medizinische Daten liegen in einer eigenen Enclave mit eigener Verschlüsselung; nur freigegebene Aggregate verlassen sie.

---

## 4. Task-Objekt und Workflow-Engine

Das zentrale Produktobjekt ist nicht der Chat, sondern der Task. Jede Anfrage wird zuerst in eine `TaskDefinition` übersetzt:

```json
{
  "task_type": "player_market_value",
  "decision_type": "recruitment",
  "target": "expected_transfer_fee",
  "as_of_date": "2026-08-13",
  "player_id": "hub_player_123",
  "club_context": "hub_club_456",
  "required_modalities": ["structured_data", "text"],
  "required_knowledge_packs": ["transfer_economics", "club_recruitment_policy"],
  "required_skills": ["market_value_model", "comparables_search", "uncertainty_analysis"],
  "risk_level": "high",
  "output_schema": "player_valuation_v2"
}
```

Damit werden „Bewerte Spieler X“ und „Wie viel zahlen wir maximal für X?“ zwei verschiedene Aufgaben mit verschiedenen Zielen, Daten und Metriken.

**Task Context** entsteht additiv: allgemeines Modellwissen plus kanonische Daten plus aufgabenspezifisches Knowledge Pack plus klubspezifisches Knowledge Pack plus Skill plus aktuelle Daten. Knowledge Packs sind kuratiert und versioniert („Pressing & Counterpressing v4“, „Club Game Model 2026/27“); jeder Run referenziert einen `knowledge_snapshot_id`.

**Fünf Wissensarten, fünf Zugriffswege.** Strukturierte Fakten über SQL und Feature-Service. Dokumente über RAG. Klubdoktrin über privates RAG plus Regeln. Multimedia über Media- und Vision-Tools. Ausführbares Wissen (xG, Role Fit, Marktwertmodell) als Skill. „Wie viele progressive Läufe in den letzten zehn Spielen?“ ist eine Abfrage, keine Retrieval-Frage.

**Skills sind Code, nicht Prompts:** versionierte Python-Pakete mit JSON-Schema, Unit- und Integrationstests, `code_hash` in der Registry.

**Output ist ein Entscheidungsobjekt mit Unsicherheit,** nicht eine Zahl. Beispiel Marktwert: Referenzwert mit 80-Prozent-Intervall, erwartete Ablöse mit Intervall, klubspezifischer Fair Value, empfohlenes Maximalgebot, Confidence, Modell-Disagreement, Treiber, Annahmen, Evidenz, `human_approval_required`. Das Synthese-LLM ersetzt die Einzeloutputs nicht; Modell A, B, C und die quantitativen Anker bleiben sichtbar.

**Das Experiment-Manifest** friert jeden Run ein: Task-, Case-, Daten-, Knowledge-, Prompt-, Skill-, Workflow-, Retriever-, Reranker-, Schema-Versionen, Provider und exakte Modell-ID mit Konfiguration, Code-Commit, Container, Zeitpunkt, Region, Roh- und normalisierter Output, Latenz, Tokens, Kosten, Evaluationsergebnisse. Reproduzierbarkeit bedeutet bei generativen Modellen nicht byte-identischen Text, sondern identische dokumentierte Inputs und statistisch wiederholbare Bewertung, bei sensiblen Benchmarks mit mehreren Wiederholungen je Konfiguration.

---

## 5. Model Router

Der Gateway vereinheitlicht APIs. Die Intelligenz sitzt im Router, in zwei Stufen.

**Stufe 1, Hard Gates:** Unterstützt das Modell die Modalität? Darf diese Datenklasse an diesen Provider? Unterstützt es Output-Schema und Tools? Erfüllt es Latenz- und Budgetgrenze?

**Stufe 2, empirischer Score** über die verbleibenden Kandidaten:

```
RouteScore(m, t) = Q(m, t) − λc·Cost − λl·Latency − λr·Risk + λp·PrivacyFit
```

Q ist die erwartete Qualität auf ähnlichen Benchmark-Aufgaben. Die Gewichte sind nicht global: Ein Trainer mit zehn Sekunden priorisiert anders als ein Sportdirektor vor einem Transfer. D1-Faktenfragen gehen an strukturierte Abfragen plus kleines Modell, D4-Taktikfragen an ein starkes multimodales Modell.

**Die Registry enthält nicht nur LLMs.** Marktwertmodell, Rollenklassifikator, Ähnlichkeitsmodell, Ligaübersetzung, Verfügbarkeitsmodell, xG, Possession Value, Pass Choice, physisches Modell aus Tracking, Embedding-Modell, Reranker, Vision-Modell. Für numerische Fußballprobleme sind diese Modelle wichtiger als das LLM.

**Hybrides Zielbild nach Datenklasse:** öffentliches Fußballwissen an Cloud-Modelle, lizenzierte Daten nur an freigegebene Provider, interne Taktik an ausgewählte Enterprise-Endpoints, Verträge auf eine eingeschränkte Route, Medizin lokal. Offene Modelle laufen über vLLM hinter derselben Hub-API.

---

## 6. Benchmark und Validierung

Ein Fußball-Benchmark ist kein Trivia-Test. Er misst ein Profil, nicht eine Zahl.

**Dimensionen:** Fußballwissen, taktisches Reasoning, Matchanalyse, Spielerbewertung, Recruitment-Logik, quantitative Analyse, Marktbewertung, Trainingsdesign, Evidence Grounding, Unsicherheit, multimodales Reasoning, Klubadaption.

**Schwierigkeitsstufen:** D1 Retrieval und Messung, D2 Interpretation mit Fußballsemantik, D3 Integration mehrerer Quellen, D4 Elite und adversarial mit unvollständiger oder widersprüchlicher Information, wo „nicht genug Evidenz“ die richtige Antwort sein kann. Zielverteilung etwa 25, 35, 30 und 10 Prozent.

**Aufbau in Stufen:** 100 bis 150 Pilotaufgaben zur Rubrik-Kalibrierung, dann 500, dann 1.500 bis 2.500, zuletzt 5.000. Domänen: Matchanalyse, Scouting, Trainingsplanung, Taktik, Verletzungsrisiko. Messqualität vor Menge.

**Gold-Standard:** Jede Aufgabe hat einen Autor und einen unabhängigen Verifier. Deterministische Aufgaben bekommen einen aus dem Snapshot berechneten Goldwert. Offene Aufgaben bekommen ein Acceptable Answer Set: mehrere gültige Lösungspfade, notwendige Evidenzen, verbotene Behauptungen, detaillierte Rubrik.

**Rubrik für offene Antworten,** 100 Punkte: fachliche Korrektheit 30, Evidenz 20, Fußball-Reasoning 20, Umsetzbarkeit 20, Kalibrierung 10. Safety ist bei medizinischen Aufgaben kein Punktwert, sondern ein Hard Gate.

**Reliabilität als Quality Gate:** Routineaufgaben von zwei Experten, strittige von drei, Dissens in eine Adjudication Queue. Krippendorffs Alpha ab 0,80 akzeptiert Gold, zwischen 0,67 und 0,80 wird adjudiziert, darunter wird die Aufgabe neu entworfen. So wird schlechte Benchmarkqualität nicht dem Modell angelastet.

**Blind:** Rater sehen weder Anbieter noch Modellname, Reihenfolge randomisiert, Positionen gespiegelt. LLM-as-Judge skaliert Vorbewertungen, ist aber nie der primäre Gold-Rater.

**Drei Splits:** DEV intern, VALIDATION privat, TEST verborgen. Der Hidden Test wird nie für Prompt-Tuning, Fine-Tuning oder Fehleranalyse geöffnet; er wächst quartalsweise und rotiert halbjährlich teilweise. Saisonale und zeitliche Splits verhindern, dass dasselbe Spiel Training und Test prägt.

**Zwei Scores statt eines Leaderboards.** Der Football Quality Score misst nur Qualität. Der Operational Utility Score verrechnet Qualität mit Kosten, Latenz, Risiko und Privacy-Fit. Damit kann Modell A qualitativ das beste und Modell B operativ die bessere Wahl sein. Gewichte, Benchmark- und Modellversion werden immer mitveröffentlicht.

**Statistik:** gepaarte Fallanalyse, Bootstrap-Konfidenzintervalle auf Fallebene, ein Holdout getrennt vom täglichen Prompt Engineering. Die belastbare Aussage lautet nicht „30 Prozent besser“, sondern: Benchmark-Version, Score, Anzahl privater Fälle, paarweise Win Rate, Konfidenzintervall.

**Benchmark-CI:** Jeder Merge, der Prompt, Policy, Retriever, Ontologie oder Modell ändert, löst aus: Unit-Tests → Schema-Tests → Retrieval-Tests → 50-Aufgaben-Smoke-Benchmark → Safety-Tests → volle Regression → Freigabe.

---

## 7. Die Lernschleife

### Football Intelligence Data

Ein Fall ist eine Sequenz, nicht ein Prompt-Antwort-Paar:

```
Situation → Frage → Analyse → Hypothese → Expertenkorrektur → Entscheidung → Intervention → Outcome
```

Beispiel: Die KI schlägt 4-gegen-4 Small-Sided Games vor. Der Trainer lehnt ab, weil drei Spieler über 700 Meter Hochgeschwindigkeitsläufe aus dem Spiel tragen und in 72 Stunden das nächste Spiel ansteht. Das ist ein Signal mit Kontext, Empfehlung, Korrektur, Begründung und, am Samstag, einem Outcome.

### Drei Signale, streng getrennt

| Signal | Frage | Was es kann | Was es nicht kann |
|---|---|---|---|
| Preference Reward | Was akzeptieren professionelle Trainer? | Verhalten, Sprache, Umsetzbarkeit formen | Wahrheit beweisen; Präferenz ist nicht Richtigkeit |
| Outcome Reward | Was war mit dem definierten Ziel verbunden? | getroffene Entscheidungen bewerten | die abgelehnte Empfehlung bewerten; das Kontrafaktische fehlt |
| Causal Evidence | Verursacht Intervention X Ergebnis Y? | Branchenüberzeugungen prüfen | ohne gestaltete Variation über viele Klubs nicht entstehen |

Der Outcome Reward gilt Entscheidungen, nicht Empfehlungen. Wer B wählt, sieht nie, was A bewirkt hätte. Deshalb: natürliche Experimente über Klubs, Surrogatziele wie prognostizierte Belastung oder xG, und keine Kausalbehauptung ohne Design.

### Kuratierte Pipeline

```
Produktionsinteraktion → Nutzerfeedback → Fehlertriage → Expertenannotation
→ Gold- / Trainingskandidat → unabhängige QA → Benchmark-Regression
→ Shadow Deployment → Canary → Produktion
```

Nur menschlich verifiziertes Feedback wird Gold oder Trainingsmaterial. Modelloutputs werden nie als Wahrheit zurücktrainiert. Jede Änderung trägt die volle Versionskette: Schema, Ontologie, Daten-Snapshot, Wissenskorpus, Benchmark, Annotationsrichtlinie, Retriever, Prompt und Policy, Modell. Sechs Monate später ist beantwortbar, warum Agent v4.7 am 12. März diese Empfehlung gab, was er wusste und welches Setup sie erzeugte.

### Bias-Kontrolle

Wer korrigiert, ist nicht zufällig. Gewichtung nach Ergebnisqualität des Experten, Vereins-Adapter über einem gemeinsamen Kern statt eines globalen Modells, damit die Spielidee von Klub A nie bei Klub B erscheint, und Tiefe vor Breite: zweihundert Profitrainer mit verknüpften Fällen sind mehr wert als fünftausend flache Interaktionen.

### Was der Prototyp bereits leistet

| Prinzip der Plattform | Umsetzung in `fussball-ki` |
|---|---|
| modellunabhängiger Reasoning-Layer | Forscher und Lehrer haben eine Schnittstelle; Claude und Offline-Suche austauschbar, Ersatz bei Ausfall |
| Hypothese als strukturiertes Objekt | JSON nach Schema; Formeln als Syntaxbaum geprüft, das LLM führt nichts aus |
| eingefrorene Validierung | Vorwärtsvalidierung über Saisons, feste Falten, Basisrate- und Elo-Benchmark |
| verborgener Test | Prüfsaison wird mitgerechnet und dem Forscher nie gezeigt |
| Gedächtnis als Klartext | Experimente, Erkenntnisse, bestes Modell, Lernkurve im Versionsverlauf |
| LLM lernt sein eigenes Wissen | Erkenntnisse werden nach jeder Runde vom LLM neu geschrieben und ihm wieder vorgelegt |
| fehlt noch | der Expertenkanal: Annahme, Korrektur, Ablehnung mit Begründung als Präferenzpaar |

Der nächste Schritt im Prototyp ist genau dieser Kanal: ein Befehl für Korrekturen, Präferenzpaare im Kontext des Lehrers, und getrennte Kennzahlen für Übereinstimmung mit Experten und mit Outcomes.

---

## 8. Modellstrategie in vier Stufen

| Stufe | Was läuft | Was uns gehört | Eintrittskriterium |
|---|---|---|---|
| 1 Modellunabhängig | Frontier- und offene Modelle austauschbar hinter Gateway und Router | Daten, MCP/API, Skills, Memory, Evals | jetzt |
| 2 Self-hosted | Open-Weights-Modell auf eigener oder gemieteter GPU-Infrastruktur, vLLM | Fine-Tunes, Adapter, Football-Embeddings, Reranker, Reward-Modelle | Benchmark v1 mit 500 Aufgaben stabil; Kernaufgaben mit lokalem Modell im Quality/Cost-Vergleich belegt |
| 3 Football Models | spezialisierte Modelle, die zusammenarbeiten: Text, Video, Spielerrepräsentation, taktischer Zustand, Trainerpräferenz, Entscheidung | die Modellfamilie | genügend kuratierte Fälle je Modell; jedes Modell schlägt seinen Vorgänger auf dem Hidden Test |
| 4 Foundation Model | wesentlicher Teil des Basismodells selbst trainiert | das Basismodell | Millionen hochwertige, multimodale, rechtlich saubere Beispiele; nachgewiesene Grenze der Stufen 2 und 3 |

**Reihenfolge innerhalb der Stufen:** Das erste eigene Modell ist kein Sprachmodell. Spielerrepräsentationen aus Event- und Trackingdaten, ein Reward-Modell aus Präferenzpaaren und ein Klassifikator für taktische Spielzustände sind billig, verteidigbar und sofort benchmarkbar. LoRA formt Terminologie, Analyseabläufe, Tool-Aufrufe, Antwortformat, Abstention. RAFT kommt, sobald RAG und Benchmark stabil sind. Continued Pretraining erst, wenn ein besserer Datensatz nachweislich nicht mehr hilft.

**Alle Wirkungsannahmen sind Hypothesen,** keine Versprechen: RAG plus fünf bis fünfzehn Punkte auf Grounding-Aufgaben, strukturierte Tools plus zehn bis fünfundzwanzig auf datenintensiven, multimodales Retrieval plus fünf bis zwanzig auf Taktik, LoRA plus drei bis zehn auf Workflow-Rubriken. Basismodell, RAG, RAG plus Tools, RAG plus LoRA werden auf demselben Hidden Test gemessen. Keine Architekturentscheidung aus Hype.

**Forschungskorpus und kommerzieller Korpus bleiben getrennt.** SoccerNet und lizenzkompatible offene Datensätze dienen Experimenten, Architektur und Benchmarks. Kommerzielles Training läuft nur auf Klubs mit Rechten, eigenen Videoquellen, eigenen Daten und zulässigen Interaktionen.

---

## 9. Governance und Sicherheit ab Version eins

- **Tenant-Isolation** auf Datenbank- und Storage-Ebene, Row-Level Security, Least Privilege für Menschen, Dienste und Skills.
- **ACL-bewusstes Retrieval:** Ein Modell erhält nie ein Dokument, das der Nutzer nicht sehen darf.
- **Tool-Allowlisting und Output-Schema-Validierung,** bevor ein Ergebnis in einen Folgeprozess gelangt.
- **Redaktion sensibler Felder** vor externen Aufrufen, Verschlüsselung, Key-Management.
- **Unveränderliche Audit-IDs,** die Modellaufruf, Retrieval, Tool Calls und Entscheidung verbinden; Logs selbst sind geschützt.
- **Human-in-the-Loop als Gate:** Niedriges Risiko liefert automatisch, hohes Risiko stoppt für Freigabe, Ablehnung oder Änderung. Jede Freigabe wird Benchmark-Datenpunkt: Empfehlung, Override, Grund, finale Entscheidung, Outcome.
- **Keine autonome Aktion** bei Transfers, Verträgen oder personenbezogenen Entscheidungen.
- **Regulatorik als Produktfeature:** Audit-Logging, Datenprovenienz, Human Oversight, Accuracy-Monitoring, Risikomanagement, Zugriffskontrolle, Entscheidungs-Traceability und Modellversionierung sind ohnehin nötig. Wird ein Recruitment-Use-Case später als High-Risk im Sinne des AI Act eingestuft, steht die Grundlage. Gesundheitsdaten verlangen DPIA und Medical Enclave. Ein Player Data Ledger macht Herkunft, Zweck, Zugriff und Freigabe für Spieler sichtbar.

---

## 10. Umsetzungsplan

Der MVP beweist den vertikalen Loop an wenigen Aufgaben, nicht die Breite. Drei Startworkflows decken alle Personas: Player Evaluation und Role Fit, Market Value und Transferentscheidung, Opponent und Match Analysis.

| Phase | Richtwert | Ergebnis | Exit-Kriterium |
|---|---|---|---|
| Foundation | Woche 0 bis 6 | kanonisches Schema v0.1, Tenant und Auth, Model-Adapter für drei Provider, Run-Manifest, Audit | derselbe Case läuft reproduzierbar über mehrere Modelle |
| Hub MVP | Woche 6 bis 12 | RAG, Skills, Prompt Registry, Knowledge Packs, Compare View, Daten-Snapshots | Skills laufen als sauberes Experiment mit identischen Daten und Prompts |
| Validation Beta | Woche 12 bis 20 | Benchmark-Suite, Expertenrubrik, blindes Rating, Router v1, Market-Value-Workflow | das System zeigt empirisch, welches Modell je Task besser ist |
| Enterprise Layer | Woche 20 bis 28 | RBAC/ABAC, Datenklassen, private Deployments, Provider-Policies | ein Profiklub nutzt vertrauliche Daten kontrolliert |
| Football Standard | Woche 28 bis 40 | öffentliche Schemas, Benchmark-Versionierung, Data Contracts, SDK | externe Teams integrieren nach unserem Standard |
| Learning Platform | danach | Outcome-Feedback, Meta-Router, gelernte Ensembles, anonymisiertes Cross-Club-Benchmarking | der Hub optimiert anhand realer Outcomes, nicht nur statischer Fälle |

**Prioritäten in dieser Reihenfolge:** A Standard und Reproduzierbarkeit. B Benchmark und Expertenvalidierung. C Workflow-Engine. D Router und Ensemble. E weitere Modelle. Der fünfte Provider ist weniger wert als ein sauberer Benchmark für die ersten drei.

**Team** für eine produktionsreife erste Generation: sieben bis zehn Vollzeitäquivalente im Kern (Football Domain Lead, AI und Platform Lead, Backend und AI Engineers, Data Engineer, ML und Data Scientist, Frontend, MLOps und Security, Evaluation Research Lead), Privacy und Legal anteilig, dazu ein Pool von zehn bis fünfundzwanzig Teilzeit-Fußballexperten für Gold Labels und Adjudication. Das größere Zielbild mit Video, Tracking und Medizin liegt bei elf bis siebzehn. Zu Beginn dominieren Ontologie, Data Engineering und Fußballmethodik; sobald der Benchmark steht, verschiebt sich der Bedarf zu Expertenrating, ML und Integrationen.

**Kosten** für Datenrechte, Video, Tracking, GPU und LLM-APIs bleiben unspezifiziert, bis Ligen, Nutzerzahlen, Latenz-SLA und Betriebsform feststehen. Sie sind der größte Hebel der Kostenstruktur.

---

## 11. Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Benchmark-Leakage und Overfitting auf eigene Tests | Hidden Test, zeitliche Splits, Canary-Aufgaben, Rotation |
| schlechter Gold-Standard | mehrere Experten, Reliabilitätsmessung, Adjudication, Acceptable Answer Sets |
| Provider-Lock-in | kanonisches Schema, Adapter, Contract Tests |
| Ontology Drift | versionierte Definitionen mit Beispielen, Football Methodology Board |
| Halluzinationen | evidenzpflichtige Antworten, Grounding Score, Abstention |
| medizinisches Overclaiming | Enclave, Clinician-in-the-Loop, Kalibrierung, Safety Gates; „Decision Support“, nie „Vorhersage mit Sicherheit X“ |
| Datenschutz und Spielerrechte | Purpose Limitation, Zugriff, Audit, DPIA, Rights Ledger |
| Urheberrecht | Rechte für Retrieval und Training getrennt in der Registry |
| Feedback-Selbstkontamination | nur menschlich verifiziertes Feedback wird Gold oder Training |
| Kosten und Latenz | Routing, Caching, Precomputation, kleine Modelle für D1 und D2 |
| Trainer-Adoption | Utility und Umsetzbarkeit messen, Antworten mit Clips und Evidenz |
| Interaktionsrechte fehlen im Vertrag | Klausel zur anonymisierten Nutzung für Modellverbesserung ab dem ersten Klub |

---

## 12. Das Versprechen

Nicht: „Unsere KI weiß am meisten über Fußball.“

Sondern: „Wir können beweisen, wie gut Fußball-KI ist. Wir definieren Daten, Aufgaben, Gold-Standards und Messverfahren, und unser eigener Agent muss sich denselben Tests stellen wie jedes andere Modell.“

Daraus folgt der Weg: Football Data Standard → Football Knowledge Standard → Football Workflow Standard → Football Benchmark Standard → Football AI Standard. Der Moat ist nicht „wir haben auch ein LLM“. Der Moat ist: Wir besitzen die Football-Lernschleife.

---

### Quellen

- Internes Strategiememo: Football Foundation Model, Modellunabhängigkeit, Football Intelligence Data, Flywheel (September 2026)
- Architektur für einen Football AI Hub: Modelle, Wissen, Benchmarks und Entscheidungs-Workflows (August 2026)
- Produktionsreifer Knowledge Hub und Benchmark-Ökosystem für eine Top-Fußball-KI (2026)
- Prototyp `fussball-ki`: selbstlernende Fußball-KI auf offenen Spieldaten, siehe `README.md` und `PROJEKT.md`
