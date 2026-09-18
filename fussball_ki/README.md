# Fussball-KI — eine KI, die sich selbst weiterbaut

Ein Sprachmodell schlägt Fußballmodelle vor, ein Rechenkern prüft sie an echten
Daten, und aus dem Ergebnis schreibt das Sprachmodell die Anweisungen neu, mit
denen es in der nächsten Runde arbeitet. Gelernt wird auf zwei Ebenen:

| Ebene | Was lernt | Wo es liegt |
|---|---|---|
| **Fußballmodell** | Gewichte eines Logit-Modells oder kleinen neuronalen Netzes über Leistungsmerkmale | `wissen/bestes_<aufgabe>.json` |
| **Das LLM selbst** | Sein Wissen und seine Regeln: `erkenntnisse.md` wird nach jeder Runde vom Sprachmodell neu geschrieben und ihm in der nächsten Runde wörtlich vorgelegt | `wissen/erkenntnisse.md` |

Das ist der Kern von „LLM lernt sein eigenes LLM": Es werden keine Netzgewichte
eines Sprachmodells trainiert. Das Sprachmodell erhält keinen festen Prompt,
sondern einen, den es selbst fortschreibt — aus Zahlen, die es nicht erfinden
kann, weil der Rechenkern sie liefert. Jede Runde steht im Git-Verlauf: was
vorgeschlagen wurde, was herauskam, was daraus geschlossen wurde.

## Was die KI kann

```bash
python3 -m fussball_ki lernen --runden 3            # Selbstlern-Schleife
python3 -m fussball_ki status --erkenntnisse         # was sie bisher weiß
python3 -m fussball_ki vorhersage --aufgabe spiel --id 5717436
python3 -m fussball_ki vorhersage --aufgabe aufstieg --team Bochum --saison 2025/26
python3 -m fussball_ki bericht                       # wissen/bericht.md
python3 -m fussball_ki daten                         # Merkmalskatalog
python3 -m fussball_ki.tests                         # 19 Prüfungen
```

Ohne `ANTHROPIC_API_KEY` läuft dieselbe Schleife mit dem **Offline-Forscher**
(evolutionäre Suche plus regelbasierte Wissensdestillation). Mit Schlüssel
übernimmt der **Claude-Forscher**:

```bash
pip install anthropic
export ANTHROPIC_API_KEY='...'
python3 -m fussball_ki lernen --runden 3 --vorschlaege 4
```

Standardmodell ist `claude-opus-5` (`--modell` ändert es, `--effort` die
Denktiefe). Fällt der Online-Forscher aus — kein Netz, Ratenlimit, abgelehnte
Anfrage — springt der Offline-Forscher für diese Runde ein; die Schleife bricht
nie ab.

## Zwei Lernaufgaben, beide aus Dateien im Repository

| Aufgabe | Daten | Frage | Benchmark des Frameworks |
|---|---|---|---|
| `spiel` | 298 Team-Spiel-Zeilen der fünf Dashboard-Mannschaften (`ergebnisse/dashboard_matches.json`) | Welche Leistungsmerkmale erklären das Ergebnis Niederlage / Remis / Sieg? | Poisson-Modell aus npxG (`psieg`, `premis`, `pnied`) |
| `aufstieg` | 162 Team-Saisons der 2. Bundesliga (`ergebnisse/team_season_stats.csv`) | Wer landet unter den ersten drei? | LOSO-Validierung (`ergebnisse/loso_validation.csv`) |

Merkmale, die das Ergebnis selbst sind (Tore, Punkte, Platz, xPoints je Spiel),
gibt es im Katalog absichtlich nicht.

## Wie eine Runde läuft

```
Kontext ──► Forscher ──► Hypothesen (JSON) ──► pruefen ──► bewerten ──► Gedächtnis
  ▲          (LLM oder      Merkmale, Formeln,    rechenbar?    Kreuzvalidierung   experimente.jsonl
  │           offline)      Modell, l2 ...        bekannt?      + stille Prüfung   bestes_<aufgabe>.json
  │                                                                                     │
  └──────────────── erkenntnisse.md  ◄──── Lehrer (LLM oder offline) ◄─────────────────┘
```

1. **Kontext**: Merkmalskatalog mit Mittel, Streuung, Fehlanteil; Benchmark;
   die selbst geschriebenen Erkenntnisse; die Rangliste bisheriger Experimente.
2. **Vorschlagen**: N Hypothesen als JSON nach Schema — Merkmale, abgeleitete
   Merkmale als Formel, Modelltyp (`logit` / `mlp`), Regularisierung,
   Standardisierung, Begründung und prüfbare Erwartung.
3. **Prüfen**: Das Sprachmodell führt nichts aus. Formeln werden als Syntaxbaum
   abgelaufen (nur Arithmetik und `abs sqrt log log1p exp min max` über
   Katalognamen), unbekannte Merkmale und Modelltypen werden abgelehnt,
   Wiederholungen erkannt. Abgelehnte Vorschläge landen mit Grund im
   Gedächtnis — auch daraus lernt der Forscher.
4. **Bewerten**: Kreuzvalidierung auf der Lernmenge, Log-Loss als Hauptmetrik
   (Proper Scoring Rule: Kalibrierung und Trennschärfe zugleich).
5. **Merken**: Schlägt eine Hypothese das bisher beste Modell, wird das
   Endmodell auf allen Zeilen gefittet und abgelegt.
6. **Reflektieren**: Nach allen Aufgaben schreibt der Lehrer
   `erkenntnisse.md` neu — Was trägt, was nicht, offene Fragen, Regeln für die
   nächste Runde.

### Lernmenge und Prüfmenge

| | Lernmenge (Kreuzvalidierung) | Prüfmenge (still) |
|---|---|---|
| `spiel` | zeitlich früheste 80 % der Spiele, 2 × 5 Falten mit festem Seed | späteste 20 % |
| `aufstieg` | Leave-one-season-out über 2017/18 – 2024/25 | Saison 2025/26 |

Die Prüfmenge wird je Experiment mitgerechnet, aber dem Forscher **nicht
gezeigt**. Sonst wählt er darauf aus, und sie ist wertlos. Sie erscheint erst im
Bericht — und dort ehrlich: Für `spiel` liegt sie deutlich über der
Kreuzvalidierung, weil die späten Spiele fast nur aus der Saison 2025/26
stammen, die Lernmenge aber von fünf Sturm-Graz-Saisons dominiert wird. Das
Framework-Poisson-Modell fällt auf denselben Zeilen genauso ab.

## Aufbau

```
fussball_ki/
  daten.py        Lerntabellen aus ergebnisse/, Merkmalskatalog, sichere Formelauswertung
  modelle.py      Logit (Newton, L2), MLP (Adam), Standardisierer, Metriken — reine Standardbibliothek
  hypothese.py    Schema, Prüfung, Fingerabdruck, Startpaket
  bewertung.py    feste Falten, Kreuzvalidierung, stille Prüfung, Endmodell, Vorhersage
  gedaechtnis.py  experimente.jsonl, erkenntnisse.md, bestes_<aufgabe>.json, verlauf.json
  forscher.py     ClaudeForscher (Anthropic-SDK) und OfflineForscher, gleiche Schnittstelle
  schleife.py     vorschlagen → prüfen → bewerten → merken → reflektieren
  bericht.py      Kurzstatus und Markdown-Bericht
  __main__.py     Kommandozeile
  tests.py        Prüfungen, ohne Netz (Claude-Forscher mit Attrappen-Client)
  wissen/         der Lernstand — eingecheckt, damit jede Runde nachlesbar ist
```

Der Rechenkern braucht kein numpy: 298 Zeilen und höchstens 25 Merkmale fittet
ein Newton-Logit in Sekundenbruchteilen. Eine Runde mit vier Hypothesen je
Aufgabe dauert offline wenige Sekunden.

## Was das System nicht ist

- **Kein Training eines Sprachmodells.** Gelernt werden Fußballmodell-Gewichte
  und der Text, mit dem das Sprachmodell arbeitet. Das ist bewusst so: Für ein
  eigenes Sprachmodell gäbe es hier weder Daten noch Rechner, und ein
  fortgeschriebener Prompt ist nachlesbar, ein Gewichtsvektor nicht.
- **Keine Vorhersage vor dem Spiel.** Die Aufgabe `spiel` erklärt Ergebnisse aus
  der gezeigten Leistung (Outcome Alignment), so wie Ebene C des Frameworks.
  Für Vorab-Prognosen fehlen Aufstellungen, Form und Quoten.
- **Kleine Datenbasis.** 298 bzw. 162 Zeilen. Die Kreuzvalidierung ist auf
  feste Falten gestellt, damit Verbesserungen von 0,005 Log-Loss nicht Rauschen
  zwischen zwei Zufallsaufteilungen sind — aber sie bleiben klein. Der
  Offline-Forscher notiert seine Mittelwerte deshalb ausdrücklich als
  Beobachtung, nicht als Kausalbefund.
