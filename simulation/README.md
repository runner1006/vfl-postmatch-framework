# Agentenbasierte 11-gegen-11-Simulation

Kein Wahrscheinlichkeitsrechner mit Spielfeldtapete. Diese Engine simuliert
22 Spieler als **dynamische physische und taktische Agenten** plus einen Ball
mit eigener Flugphysik, in Schritten von 40 Millisekunden. Der Spielstand
entsteht ausschließlich aus dieser Schleife: Es gibt keine Stelle im Code, an
der ein Ergebnis, ein Torschuss oder ein Ballbesitzwert direkt gezogen wird.
Jede Zahl im Bericht ist ein **gezähltes Ereignis** aus einer räumlich-zeitlichen
Entwicklung.

Das ist der Unterschied zu einer Football-Manager-Simulation, und er ist der
ganze Zweck: nur wenn Tore aus Raum, Zeit und Körpern entstehen, kann man
fragen, was passiert, wenn einer dieser Körper schneller ist.

```
Reale Spieldaten  →  Digital Twin  →  Simulation  →  Kontrafaktisches  →  Entscheidung
   zwilling.py        Attribute        spiel.py       kontrafaktisch.py     Tabelle mit
                                                                           Unsicherheit
```

## Schnellstart

Keine Abhängigkeiten außer Python 3.8+ — die Engine ist reine Standardbibliothek.

```bash
cd simulation

python3 cli.py spiel --minuten 90 --html spiel.html    # Spiel + Animation
python3 cli.py kontrafaktisch --frage schneller_iv --n 20
python3 cli.py situation --ab 12 --n 60 --marken 5,10
python3 cli.py tests                                    # 79 Prüfungen
```

`spiel.html` ist eine einzelne Datei ohne externe Requests — Doppelklick genügt.
Sie zeigt die Bahnen aller 22 Agenten und den Ball mit Höhe, zuschaltbar die
Raumkontrolle, dazu eine anklickbare Ereignisliste.

Links oben stehen Paarung, Stand und die vollständige Parametrisierung des
Laufs — ohne sie ist eine Aufzeichnung nicht nachvollziehbar. Rechts läuft die
Statistik **zum angezeigten Zeitpunkt** mit, nicht der Endstand: Tore, xG,
Schüsse, Kontakte im Strafraum, Pässe ins letzte Drittel, Strafraumeintritte,
Passquote, Ballbesitz, Abwehrhöhe, PPDA, Raumkontrolle und gefährlicher Raum.
Darunter die Laufdistanz je Mannschaft in Kilometern und in Metern je Minute
und Spieler, aufklappbar bis auf den einzelnen Spieler.

Raumkontrolle und gefährlicher Raum werden im Browser aus denselben
Ankunftszeiten berechnet wie in der Engine — Bild und Modell laufen nicht
auseinander.

## Was modelliert ist

**Spieler** (`spieler.py`) — Position, Geschwindigkeit, Beschleunigung getrennt
nach längs und quer, Bremsvermögen, Körperorientierung mit begrenzter Drehrate,
Reaktionszeit, Energiehaushalt. Die Beschleunigung folgt einer
Kraft-Geschwindigkeits-Beziehung; quer steht deutlich weniger zur Verfügung als
geradeaus, und dieser Anteil sinkt zusätzlich mit dem Tempo. Ein Richtungswechsel
kostet dadurch von selbst Zeit — es gibt keine Sonderregel dafür.

**Ball** (`ball.py`) — dreidimensionale Flugbahn mit Schwerkraft, quadratischem
Luftwiderstand, Magnus-Effekt und gedämpftem Aufprall; am Boden Rollreibung. Die
Höhe ist kein Schmuck: ein hoher Ball ist am Ziel langsamer, gibt dem Gegner Zeit
und ist nur mit dem Kopf zu verarbeiten. Genau daran entscheidet sich, ob eine
hohe Abwehrlinie überspielt wird.

**Taktik** (`taktik.py`) — sechs Formationen, zwölf Rollen, dreizehn
Mannschaftsanweisungen in physischen Einheiten: `abwehrhoehe` steht in Metern von
der eigenen Torlinie, nicht auf einer Skala von 1 bis 10. Alle Berechnungen
laufen im **Angriffsrahmen** des jeweiligen Teams, deshalb braucht keine Regel
eine Fallunterscheidung nach Spielrichtung oder Halbzeit.

**Entscheidungen** (`entscheidung.py`) — der Ballführende erzeugt konkrete
räumliche Optionen (dieser Pass zu diesem Punkt mit diesem Tempo), bewertet jede
mit demselben Nutzenmaß in Einheiten von Torwahrscheinlichkeit und führt genau
eine aus — mit Ausführungsfehler. Ob der Pass ankommt, entscheidet danach die
Physik, nicht die Bewertung.

**Regeln** (`spiel.py`) — Aus, Tor, Einwurf, Abstoß, Ecke, Freistoß, Anstoß,
Abseits (geprüft im Moment des Abspiels), Foul, Elfmeter, Torwartparade,
Halbzeit mit Seitenwechsel.

## Die Kette im Einzelnen

### Digital Twin (`zwilling.py`)

Drei Wege von realen Daten zu Agentenattributen: Ligaperzentile, Scoutingnoten
1–5 (passend zum Scout-League-Modul dieses Repositorys) oder direkt gemessene
physische Größen aus Tracking-Daten. Die Ankerwerte stehen als **Daten** in
`kalibrierung.json`, nicht im Code — wie beim KPI-Set des Analyseteils.

Jedes erzeugte Profil trägt in `herkunft` mit, welcher Wert **gemessen** und
welcher **gesetzt** ist. Vier Attribute — Entscheidung, Übersicht, Positionsspiel
und mit Abstrichen Antizipation — sind aus aggregierten Ereignisdaten *nicht
identifizierbar*: Ein Spieler mit vielen Fehlpässen kann schlecht entscheiden
oder in einer Mannschaft spielen, die ihm keine Anspielstationen gibt. Ohne
Scoutingurteil bleiben sie auf dem Durchschnitt und werden als gesetzt
ausgewiesen. Wer diese Unterscheidung wegwirft, bekommt eine Simulation, die
Präzision vortäuscht.

### Kontrafaktisches (`kontrafaktisch.py`)

Eine einzelne Simulation ist wertlos — sie ist eine Stichprobe aus einem sehr
breiten Zufallsprozess. Aussagekraft entsteht erst aus dem paarweisen Vergleich
vieler Wiederholungen, in denen alles gleich ist außer der einen Änderung.

Basis und Variante laufen je Wiederholung mit **demselben Startwert**. Ohne das
verschwindet jeder realistische Effekt im Rauschen. Ausgewiesen wird deshalb
immer die **gepaarte Differenz** mit Bootstrap-Intervall, nie der Unterschied
zweier Mittelwerte. Eine Änderung ohne Wirkung muss exakt Differenz null
ergeben — das ist eine der harten Prüfungen (Nr. 34).

```
$ python3 cli.py kontrafaktisch --frage abwehrhoehe --n 20 --minuten 10

Metrik                  Basis  Differenz        95%-Intervall
--------------------------------------------------------------
xg                      0.450     -0.176   [  -0.391,   +0.052]
passquote               0.467     +0.088   [  +0.048,   +0.135]   deutlich
abwehrhoehe_m          34.285     +3.739   [  +0.699,   +7.032]   deutlich
laufdistanz_km         11.571     +1.384   [  +0.961,   +1.794]   deutlich
```

Fünf durchgerechnete Beispiele samt Lesart stehen in
[`beispiele.md`](beispiele.md) — inklusive der Fälle, in denen die Engine
ausdrücklich *keine* belastbare Aussage liefert.

Fertige Fragen: `abwehrhoehe`, `pressing`, `tiefer_block`, `formation`,
`schneller_iv`, `besserer_stuermer`. Eigene Fragen sind drei Zeilen Code —
`vergleiche(bauer, aenderung, ...)` nimmt jede Funktion, die genau eine Sache
am Spiel verändert.

### Situationen fortschreiben

Der Modus, der einer Trainerfrage am nächsten kommt: nicht „wie endet das
Spiel", sondern „was passiert in den nächsten Sekunden, und wie sicher ist das".
`cli.py situation` nimmt eine Lage, lässt sie sechzig Mal mit verschiedenen
Zufallsfolgen weiterlaufen und gibt die Verteilung von Ballort, Raumkontrolle
und gefährlicher Fläche nach 5 und 10 Sekunden aus.

## Kalibrierungsstand

Die Engine ist gegen messbare Größen kalibriert, nicht gegen Bauchgefühl. Was
stimmt und was nicht, steht hier vollständig — `python3 cli.py tests` gibt
dieselben Zahlen aus und markiert Abweichungen als solche, statt sie zu
verstecken. **57 harte und 8 Richtungsprüfungen bestehen**, 7 der 14
Kalibrierungsprüfungen liegen außerhalb ihrer Bandbreite und werden als
bekannte Abweichung ausgegeben.

**Belastbar kalibriert:**

| Größe | Modell | real |
|---|---|---|
| Sprint 10 / 20 / 30 m aus dem Stand | 1,92 / 3,20 / 4,40 s | 1,9 / 3,1 / 4,3 s |
| Spitzengeschwindigkeit | 8,4 m/s (Attribut, 7,3–9,5) | 8,0–9,5 m/s |
| 180-Grad-Wende aus vollem Lauf | 2,0 s | 1,8–2,3 s |
| Flachpass 20 m mit 18 m/s | 1,32 s Laufzeit | ~1,3 s |
| Flanke 25 m/s bei 32° | Scheitel 6,9 m, Aufkommen 37 m | plausibel |
| xG zentral aus 6 / 11 / 16 / 25 m | 0,45 / 0,26 / 0,13 / 0,04 | 0,45 / 0,29 / 0,12 / 0,035 |
| Torausbeute im Schussdrill | stimmt im Rahmen mit dem eigenen xG-Modell | — |
| Pässe je Team und Spiel | ~590 | ~450 |
| Fouls je Team und Spiel | 8–12 | ~12 |
| Ecken / Freistöße je Spiel | 10 / 26 | ~10 / ~25 |

**Bekannte Abweichungen** — hier ist das Modell noch nicht dort, wo es sein
müsste, und das ist keine Kleinigkeit:

Gemessen als Mittel über drei Läufe à 30 Minuten, hochgerechnet auf 90:

| Größe | Modell | real | Faktor |
|---|---|---|---|
| Schüsse je Team und Spiel | 88 | ~13 | 6,8× |
| xG je Team und Spiel | 5,5 | ~1,4 | 3,9× |
| Tore je Team und Spiel | 14 | ~1,5 | 9× |
| Passquote | 0,53 | ~0,78 | −25 Punkte |
| Zweikämpfe je Team und Spiel | 430 | ~100 | 4,3× |
| Kontakte im Strafraum je Team | ~400 | ~28 | 14× |
| Pässe ins letzte Drittel je Team | ~20 | ~45 | 0,4× |
| Laufdistanz je Spieler | 14,0 km | ~10,5 km | 1,3× |
| Sprintdistanz je Spieler | 870 m | ~250 m | 3,5× |
| Strafraumeintritte je Spiel | ~200 | ~50 | 4× |

Die beiden letzten Zeilen zeigen dieselbe Ursache von zwei Seiten: Der Ball
kommt zu selten **durch einen gespielten Pass** ins letzte Drittel und dafür zu
oft über zweite Bälle und Dribblings — und dort bleibt er dann in einem
Gewühl aus Kontakten hängen, statt dass die Situation nach zwei, drei Aktionen
entschieden ist.

Die Ursache ist bekannt und benannt: Das letzte Drittel ist zu chaotisch. Eine
Passquote von 55 statt 78 Prozent halbiert die Länge jedes Ballbesitzes,
verdoppelt die Zahl der Ballbesitze und damit die Zahl der Strafraumeintritte;
daraus folgen Schuss-, Torschuss- und Torzahlen der Reihe nach. Die Ordnung auf
dem Feld stimmt dagegen: Zonenverteilung des Balls (39 % Mittelfeld), Blocktiefe
22 m und Blockbreite 38 m im Defensivverbund, Formationstreue, Standardarten und
Laufwege sind im realistischen Bereich.

**Was das für die Nutzung heißt:** Absolute Werte aus einem einzelnen Lauf sind
nicht belastbar. Die **gepaarten Differenzen** des kontrafaktischen Modus sind es
eher, weil ein gemeinsamer systematischer Fehler sich zwischen beiden Armen
weitgehend heraushebt. Trotzdem gilt: Ein enges Intervall um +0,3 xG heißt „das
Modell ist sich sicher", nicht „die Mannschaft gewinnt 0,3 xG".

## Weitere Grenzen

- **Die Gefahrenfläche ist eine Ersatzflächenfunktion, kein geschätztes xT.**
  `raumkontrolle.gefahr` ist eine Summe zweier Exponentiale, deren Stützstellen
  den Größenordnungen veröffentlichter xT-Gitter entsprechen. Sie ist *nicht* aus
  Ereignisdaten geschätzt. Wer ein eigenes xT-Gitter hat, ersetzt diese eine
  Funktion — alles andere bleibt unberührt.
- **Keine Auswechslungen, keine Karten, keine Nachspielzeit, kein Wetter, kein
  Wind, kein unebener Rasen.** Rote Karten und Sperren fehlen; ein Foul ist immer
  nur ein Freistoß oder Elfmeter.
- **Standardsituationen sind vereinfacht.** Ecken laufen ohne einstudierte
  Abläufe, Freistöße ohne Mauer im engeren Sinn (der Mindestabstand wird
  erzwungen, die Mauer ist nicht modelliert).
- **Kein Trainerverhalten.** Anweisungen sind über das Spiel konstant; es gibt
  keine Reaktion auf den Spielstand.
- **Kein Lernen.** Die Agenten optimieren je Entscheidung, sie passen sich nicht
  über das Spiel hinweg an den Gegner an.

## Aufbau

```
mathe.py            Vektor- und Kurvenmathematik (kein numpy: 2-Vektoren sind
                    schneller als der numpy-Overhead je Operation)
konfig.py           Feldmaße, Physikkonstanten, Zeitschritt, Modellparameter
spieler.py          Agent: Attribute, Zustand, Bewegungsphysik, Ausdauer
ball.py             Ballphysik und Flugbahnvorhersage
raumkontrolle.py    Ankunftszeiten, Raumkontrolle, xG, Gefahrenfläche
taktik.py           Formationen, Rollen, Anweisungen, Positionsfindung, Pressing
entscheidung.py     Optionen erzeugen, bewerten, ausführen
spiel.py            Simulationsschleife, Regeln, Standards, Kennzahlen
zwilling.py         Digital Twin: reale Messwerte → Agentenattribute
kalibrierung.json   Ankerwerte dieser Abbildung (Daten, nicht Code)
kontrafaktisch.py   gepaarte Vergleiche mit gemeinsamen Zufallszahlen
visual.py           eigenständige HTML-Animation mit mitlaufender Statistik
cli.py              Kommandozeile
beispiele.md        fuenf durchgerechnete Fragen samt Lesart
tests.py            79 Prüfungen: HART, RICHTUNG, KALIBRIERUNG
```

Rechenzeit: rund 30 Sekunden für ein volles Spiel auf einem Kern, rund
7 Sekunden je 15 Minuten Spielzeit. Ein kontrafaktischer Vergleich mit 20
gepaarten Wiederholungen à 10 Minuten braucht etwa vier Minuten.

## Der Weg zu synthetischem Videomaterial

Die Aufzeichnung (`cli.py spiel --bahn bahn.json`) ist eine vollständige
Tracking-Datei: 25 Hz, 22 Spieler, Ball mit Höhe, dazu die Ereignisliste — also
genau das Format, das ein Renderer als Eingabe braucht. Was zwischen dieser Datei
und einem realistischen Spielvideo liegt, ist Darstellung: Kameraführung,
Körperanimation, Texturen. Die Simulation selbst liefert bereits, was solche
Verfahren üblicherweise mühsam aus echtem Videomaterial extrahieren müssen.

Wer den Schritt gehen will, sollte allerdings zuerst die Abweichungen oben
schließen. Ein Video einer Simulation mit acht Toren je Spiel sieht nicht wie
Fußball aus — es sieht aus wie Hallenfußball mit elf Feldspielern.

## Verhältnis zum Analyseteil dieses Repositorys

Das Post-Match-Framework misst, **was war**: 15 KPIs in fünf Spielphasen,
z-standardisiert je Liga-Saison, gegen eine Referenzkohorte und gegen
18 historische Aufsteiger. Es rührt an keiner Stelle in dieses Modul hinein und
umgekehrt.

Die Brücke ist `zwilling.py`. Sobald Spieler-Match-Zeilen oder Scoutingnoten
vorliegen, werden daraus Agentenprofile — und die Fragen, die das Analyseframework
beantwortet („wie nah kam das Spiel der Spielidee"), bekommen ein Gegenstück
(„was wäre passiert, wenn"). Die Trennung der Ebenen ist dabei dieselbe wie dort:
Was gemessen ist, wird gemessen ausgewiesen; was gesetzt ist, wird gesetzt
ausgewiesen; und was das Modell nicht kann, steht in der README und nicht im
Kleingedruckten.
