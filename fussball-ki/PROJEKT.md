# Fußball-KI — Projektbeschreibung

## Zielsetzung

Eine Fußball-KI, die sich selbst weiterbaut. Sie prognostiziert Spiele der
Bundesliga und 2. Bundesliga vor dem Anpfiff und verbessert ihre Modelle ohne
menschliches Zutun: Ein Sprachmodell schlägt Hypothesen vor, ein Rechenkern
prüft sie an echten Spieldaten, und aus dem Ergebnis schreibt das Sprachmodell
sein eigenes Wissen fort. Das Projekt beantwortet drei Fragen:

1. **Kann eine KI ihre eigene Modellentwicklung übernehmen?** Vorschlagen,
   prüfen, verwerfen, festhalten — die ganze Schleife, die sonst ein Analyst
   dreht.
2. **Kann ein Sprachmodell sein eigenes Wissen lernen?** Es bekommt keinen
   festen Prompt, sondern einen, den es selbst nach jeder Runde neu schreibt,
   gestützt auf Zahlen, die es nicht erfinden kann.
3. **Was ist aus offenen Daten ehrlich herauszuholen?** Nur Ergebnisse, keine
   Quoten, keine Aufstellungen. Jede Verbesserung wird gegen Elo und
   Basisrate gemessen, mit einer Validierung, die Prognosen so prüft, wie sie
   im Ernstfall entstehen.

Nicht das Ziel: ein Wettwerkzeug oder das Training eines Sprachmodells. Gelernt
werden Prognosemodell-Gewichte und der Text, mit dem das Sprachmodell arbeitet.

## Grundidee: Lernen auf zwei Ebenen

| Ebene | Was lernt | Wie | Ablage |
|---|---|---|---|
| Fußballmodell | Gewichte über Vorab-Merkmale (Elo, Form, Saisonstand …) | Fit auf allen gespielten Spielen, sobald eine Hypothese die bisher beste schlägt | `wissen/bestes_<aufgabe>.json` |
| Das LLM selbst | Was trägt, was nicht, offene Fragen, Regeln für die nächste Runde | Das Sprachmodell schreibt `erkenntnisse.md` nach jeder Runde neu und bekommt sie in der nächsten wörtlich vorgelegt | `wissen/erkenntnisse.md` |

Beides liegt als Klartext im Repository. Jede Runde ist im Git-Verlauf
nachlesbar: Vorschlag, Ergebnis, Schlussfolgerung.

## Technologieaufbau

Das System besteht aus sechs Schichten, jede ein Modul im Paket `fussballki/`.
Der Datenfluss läuft von oben nach unten, die Schleife schließt ihn.

```
Datenquelle  ──►  Merkmale  ──►  Aufgaben  ──►  Bewertung  ──►  Gedächtnis
openfootball      Elo, Form,     Ergebnis,      Vorwärts-       Experimente,
(CC0, Text)       Duelle …       Tore           validierung     Erkenntnisse
                                                    ▲                │
                                                    │                ▼
                                                Hypothesen  ◄──  Forscher (LLM / offline)
```

**1. Datenschicht** (`daten.py`, `quellen.py`). Alle Spiele seit 2010/11 aus
openfootball/deutschland, als Klartext im Repository und per Befehl direkt von
GitHub aktualisierbar. Der Parser liest beide Zeilenformate des Datensatzes,
leitet Jahreszahlen aus der Saison ab (Nachholspiele stehen nicht
chronologisch) und führt wechselnde Vereinsnamen über einen Schlüssel ohne
Vereinsform und Gründungsjahr zusammen. Eine Konsistenzprüfung verlangt je
Saison und Liga genau 18 Vereine.

**2. Merkmalsmaschine** (`merkmale.py`). Aus nackten Ergebnissen entstehen 44
Vorab-Merkmale, jedes ausschließlich aus Spielen vor dem jeweiligen Anpfiff:
Elo mit Heimvorteil und Tordifferenz-Gewichtung, Form über 5 und 10 Spiele,
Heim- und Auswärtsform, Saisonstand, Ruhetage, direkte Duelle, Vorsaisonplatz,
Auf- und Absteiger. Der Zustand wird erst nach dem Spiel fortgeschrieben, so
ist Datenleckage konstruktiv ausgeschlossen. Offene Spiele bekommen Merkmale,
aber kein Label: das sind die Prognosen.

**3. Aufgaben und Modelle** (`aufgaben.py`, `modelle.py`). Zwei Lernaufgaben
auf derselben Merkmalstabelle: Heimsieg / Unentschieden / Auswärtssieg und
über / unter 2,5 Tore. Drei Modellfamilien mit einer Schnittstelle, nur auf
numpy: multinomiales Logit (Newton, L2), kleines neuronales Netz (Adam) und
ein Poisson-Tormodell, das Heim- und Gasttorraten lernt und daraus
Ergebniswahrscheinlichkeiten faltet. Alle Modelle sind als JSON speicherbar
und laden ohne Neurechnung.

**4. Bewertung** (`bewertung.py`). Vorwärtsvalidierung über Saisons: Modell
auf allen Saisons bis S−1, Prognose für S, Testsaisons 2015/16 bis zur
vorletzten vollständigen. Hauptmetrik ist der Log-Loss als Proper Scoring
Rule. Die letzte vollständige Saison ist stille Prüfsaison: sie wird je
Experiment mitgerechnet, dem Forscher aber nie gezeigt, damit er nicht darauf
auswählt. Basisrate und ein Elo-Logit werden mit derselben Validierung als
Benchmarks geführt.

**5. Hypothesen und Forscher** (`hypothese.py`, `formeln.py`, `forscher.py`).
Eine Hypothese ist ein Bauplan als JSON: Merkmale, abgeleitete Merkmale als
Formel, Modelltyp, Regularisierung, Standardisierung, Begründung, Erwartung.
Der Claude-Forscher erzeugt sie über das Anthropic-SDK mit strukturierter
Ausgabe nach Schema; ein zweiter Aufruf in der Lehrerrolle schreibt die
Erkenntnisse neu. Das Sprachmodell führt nichts aus: Formeln werden als
Syntaxbaum geprüft, nur Arithmetik und wenige Funktionen über Katalognamen
sind erlaubt. Ohne Schlüssel oder bei Ausfall übernimmt der Offline-Forscher
mit evolutionärer Suche und regelbasierter Wissensdestillation, deterministisch
bei gleichem Seed.

**6. Schleife und Gedächtnis** (`schleife.py`, `gedaechtnis.py`,
`bericht.py`). Eine Runde je Aufgabe: Kontext bauen, Hypothesen holen, jede
prüfen (rechenbar? schon bekannt?), bewerten, ins Gedächtnis schreiben, bei
Verbesserung das Endmodell neu fitten; nach allen Aufgaben die Erkenntnisse
neu schreiben. Kein einzelner Vorschlag kann die Runde stoppen; Fehler werden
als Experiment mit Status notiert. Das Gedächtnis sind vier Klartextdateien:
Experimente, Erkenntnisse, bestes Modell je Aufgabe, Lernkurve. Der Bericht
fasst sie für Menschen zusammen.

## Technik

| | |
|---|---|
| Sprache | Python ≥ 3.9 |
| Abhängigkeit | numpy; `anthropic` nur für den Online-Forscher |
| Sprachmodell | Claude Opus 5 als Standard, per Option austauschbar |
| Daten | openfootball/deutschland, CC0, rund 9.000 Spiele plus laufende Saison |
| Laufzeit | eine Runde mit vier Hypothesen je Aufgabe: wenige Sekunden offline |
| Qualitätssicherung | 21 Prüfungen ohne Netz, CI-Workflow für GitHub Actions |
| Bedienung | `python3 -m fussballki lernen / status / vorhersage / bericht / daten / quellen` |

## Grenzen

Aus Ergebnissen allein bleibt jede Prognose nahe an Elo; die gemessenen
Gewinne sind klein und werden so ausgewiesen. Die Vorwärtsvalidierung ist
fest, damit Unterschiede von wenigen Tausendsteln nicht Rauschen zwischen zwei
Zufallsaufteilungen sind. Wer mehr will, braucht mehr Daten: Schüsse, Quoten,
Aufstellungen. Die Datenschicht ist dafür der einzige Anbaupunkt; alles
darüber bleibt gleich.
