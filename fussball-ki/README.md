# Fußball-KI — eine Fußball-KI, die sich selbst weiterbaut

Ein Sprachmodell schlägt Prognosemodelle vor, ein Rechenkern prüft sie an
echten Spielen der Bundesliga und 2. Bundesliga, und aus dem Ergebnis schreibt
das Sprachmodell die Anweisungen neu, mit denen es in der nächsten Runde
arbeitet. Gelernt wird auf zwei Ebenen:

| Ebene | Was lernt | Wo es liegt |
|---|---|---|
| **Fußballmodell** | Gewichte eines Logit-, Poisson- oder kleinen Netz-Modells über Vorab-Merkmale (Elo, Form, Saisonstand …) | `wissen/bestes_<aufgabe>.json` |
| **Das LLM selbst** | Sein Wissen und seine Regeln: `erkenntnisse.md` wird nach jeder Runde vom Sprachmodell neu geschrieben und ihm in der nächsten Runde wörtlich vorgelegt | `wissen/erkenntnisse.md` |

Das ist der Kern von „LLM lernt sein eigenes LLM“: Es werden keine
Netzgewichte eines Sprachmodells trainiert. Das Sprachmodell erhält keinen
festen Prompt, sondern einen, den es selbst fortschreibt — aus Zahlen, die es
nicht erfinden kann, weil der Rechenkern sie liefert. Jede Runde steht im
Git-Verlauf: was vorgeschlagen wurde, was herauskam, was daraus geschlossen wurde.

Kurzfassung mit Zielsetzung und Technologieaufbau: [`PROJEKT.md`](PROJEKT.md). Positionspapier zur Football Intelligence Layer, in der dieser Prototyp der Kern ist: [`POSITIONSPAPIER.md`](POSITIONSPAPIER.md), als gesetzte Fassung mit Grafiken [`positionspapier.html`](positionspapier.html).

## In drei Minuten

```bash
pip install numpy                              # einzige Abhängigkeit
python3 -m fussballki lernen --runden 3        # ohne Schlüssel: Offline-Forscher
python3 -m fussballki status --erkenntnisse    # was die KI bisher weiß
python3 -m fussballki vorhersage --naechste    # nächste offene Spiele
python3 -m fussballki vorhersage --heim Bochum --gast Schalke --liga 2
python3 -m fussballki.tests                    # 21 Prüfungen
```

Mit Schlüssel übernimmt der **Claude-Forscher** (Standardmodell
`claude-opus-5`, `--modell` und `--effort` ändern es):

```bash
pip install anthropic
export ANTHROPIC_API_KEY='...'
python3 -m fussballki lernen --runden 3 --vorschlaege 4
```

Fällt der Online-Forscher aus — kein Netz, Ratenlimit, abgelehnte Anfrage —
springt der Offline-Forscher (evolutionäre Suche, regelbasierte
Wissensdestillation) für diese Runde ein. Die Schleife bricht nie ab.

## Daten: offen, ohne Token

Alle Spiele der Bundesliga und 2. Bundesliga seit 2010/11 aus
[openfootball/deutschland](https://github.com/openfootball/deutschland) (CC0),
als Schnappschuss in `daten/` — rund 9.000 gespielte Spiele plus die offenen
Paarungen der laufenden Saison. Es gibt nur Ergebnisse: keine Schüsse, keine
Quoten, keine Aufstellungen. Aktualisieren:

```bash
python3 -m fussballki quellen
```

Aus den nackten Ergebnissen baut `merkmale.py` 44 **leckfreie Vorab-Merkmale**,
jedes ausschließlich aus Spielen vor dem jeweiligen Anpfiff: Elo (mit
Heimvorteil und Tordifferenz-Gewichtung), Form über 5 und 10 Spiele, Heim- und
Auswärtsform, Saisonstand, Ruhetage, direkte Duelle, Vorsaisonplatz,
Auf-/Absteiger. Vereinsnamen, die zwischen Saisons wechseln („1899 Hoffenheim“,
„TSG 1899 Hoffenheim“), werden zusammengeführt und je Saison auf 18 Vereine
geprüft. `python3 -m fussballki daten` zeigt den Katalog.

## Zwei Lernaufgaben

| Aufgabe | Klassen | Benchmarks (gleiche Validierung) |
|---|---|---|
| `ergebnis` | Heimsieg / Unentschieden / Auswärtssieg | Basisrate, Elo-Logit (`elo_diff` allein) |
| `tore` | unter / über 2,5 Tore | Basisrate, Elo-Logit |

Ergebnisse aus nackten Resultaten sind schwer vorherzusagen. Elo allein liegt
bei etwa 1,03 Log-Loss, die Basisrate bei 1,07; Buchmacher erreichen mit weit
mehr Information etwa 0,98. Gewinne von wenigen Tausendstel gegenüber Elo sind
hier real, wenn sie über Saisons stabil bleiben — genau das prüft die Validierung.

## Wie eine Runde läuft

```
Kontext ──► Forscher ──► Hypothesen (JSON) ──► pruefen ──► bewerten ──► Gedächtnis
  ▲          (LLM oder      Merkmale, Formeln,    rechenbar?    Vorwärts-          experimente.jsonl
  │           offline)      Modell, l2 ...        bekannt?      validierung        bestes_<aufgabe>.json
  │                                                                                     │
  └──────────────── erkenntnisse.md  ◄──── Lehrer (LLM oder offline) ◄─────────────────┘
```

1. **Kontext**: Merkmalskatalog mit Mittel, Streuung, Fehlanteil; Benchmarks;
   die selbst geschriebenen Erkenntnisse; die Rangliste bisheriger Experimente.
2. **Vorschlagen**: N Hypothesen als JSON nach Schema — Merkmale, abgeleitete
   Merkmale als Formel, Modelltyp (`logit`, `mlp`, `poisson`), Regularisierung,
   Standardisierung, Begründung und prüfbare Erwartung.
3. **Prüfen**: Das Sprachmodell führt nichts aus. Formeln werden als Syntaxbaum
   abgelaufen (nur Arithmetik und `abs sqrt log log1p exp min max` über
   Katalognamen); unbekannte Merkmale und Modelltypen werden abgelehnt,
   Wiederholungen erkannt. Abgelehnte Vorschläge landen mit Grund im
   Gedächtnis — auch daraus lernt der Forscher.
4. **Bewerten**: Vorwärtsvalidierung über Saisons, Log-Loss als Hauptmetrik.
5. **Merken**: Schlägt eine Hypothese das bisher beste Modell, wird das
   Endmodell auf allen gespielten Spielen gefittet und abgelegt.
6. **Reflektieren**: Nach allen Aufgaben schreibt der Lehrer `erkenntnisse.md`
   neu — Was trägt, was nicht, offene Fragen, Regeln für die nächste Runde.

### Validierung, wie Prognosen im Ernstfall entstehen

| | Saisons |
|---|---|
| Vorwärtsvalidierung (Lernmenge) | Modell auf allen Saisons bis S−1, Prognose für S; Testsaisons 2015/16 bis zur vorletzten vollständigen Saison |
| Prüfsaison (still) | die letzte vollständige Saison |
| laufende Saison | gespielte Spiele nur ins Endmodell; offene Spiele sind die Prognosen |

Die Prüfsaison wird je Experiment mitgerechnet, aber dem Forscher **nicht
gezeigt** — sonst wählt er darauf aus, und sie ist wertlos. Sie erscheint erst
im Bericht (`wissen/bericht.md`).

## Modelle

Alle in `modelle.py`, nur numpy:

- **Logit** — multinomiales Logit, L2, Newton-Verfahren.
- **MLP** — ein verstecktes tanh-Layer, Softmax, Adam, L2.
- **Poisson** — zwei Poisson-Regressionen (Heimtore, Gasttore) mit log-Link;
  Ergebnis- und Über/Unter-Wahrscheinlichkeiten aus der Faltung der
  Torverteilungen. Das fußballnahe Modell: es lernt Torraten, nicht Klassen,
  und gibt erwartete Tore mit aus.

## Aufbau

```
fussballki/
  daten.py        openfootball-Parser (beide Zeilenformate), Vereinsnormalisierung, Konsistenzprüfung
  merkmale.py     leckfreie Vorab-Merkmale: Elo, Form, Saison, Ruhetage, Duelle, Vorsaison
  aufgaben.py     Lerntabellen je Aufgabe, Katalog, offene Spiele
  formeln.py      sichere Formelauswertung ohne eval
  modelle.py      Logit, MLP, Poisson, Standardisierer, Metriken
  hypothese.py    Schema, Prüfung, Fingerabdruck, Startpaket
  bewertung.py    Vorwärtsvalidierung, stille Prüfsaison, Benchmarks, Endmodell, Vorhersage
  gedaechtnis.py  experimente.jsonl, erkenntnisse.md, bestes_<aufgabe>.json, verlauf.json
  forscher.py     ClaudeForscher (Anthropic-SDK) und OfflineForscher, gleiche Schnittstelle
  schleife.py     vorschlagen → prüfen → bewerten → merken → reflektieren
  bericht.py      Kurzstatus und Markdown-Bericht
  quellen.py      Daten von openfootball holen
  __main__.py     Kommandozeile
  tests.py        Prüfungen, ohne Netz
daten/            Schnappschuss der Spieldaten (CC0) + QUELLE.md
wissen/           der Lernstand — eingecheckt, damit jede Runde nachlesbar ist
```

## Was das System nicht ist

- **Kein Training eines Sprachmodells.** Gelernt werden Prognosemodell-Gewichte
  und der Text, mit dem das Sprachmodell arbeitet. Bewusst so: Ein
  fortgeschriebener Prompt ist nachlesbar, ein Gewichtsvektor nicht.
- **Kein Wettwerkzeug.** Ohne Quoten, Aufstellungen und Verletzungen bleibt
  jede Prognose aus Ergebnissen allein nahe an Elo. Das System zeigt, wie eine
  KI sich methodisch verbessert, nicht, wie man Buchmacher schlägt.
- **Kleine Gewinne, ehrlich gemessen.** Die Vorwärtsvalidierung ist fest, damit
  ein Unterschied von 0,002 Log-Loss nicht Rauschen zwischen zwei
  Zufallsaufteilungen ist. Der Offline-Forscher notiert seine Mittelwerte
  ausdrücklich als Beobachtung, nicht als Kausalbefund.
