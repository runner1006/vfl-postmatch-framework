# Durchgerechnete Beispiele

Alle Ergebnisse hier sind Ausgaben der Engine, nicht Illustrationen. Sie
stammen aus 14 gepaarten Wiederholungen à 7 Minuten Spielzeit mit gemeinsamen
Zufallszahlen; „deutlich" heißt, dass das 95-Prozent-Bootstrap-Intervall der
gepaarten Differenz die Null nicht enthält.

Und die Warnung gleich vorweg, weil sie für jedes dieser Ergebnisse gilt: Die
Intervalle beschreiben die Unsicherheit **im Modell**. Der
[Kalibrierungsstand](README.md#kalibrierungsstand) ist bei Schuss- und Torzahlen
noch deutlich neben der Wirklichkeit. Diese Beispiele zeigen, was die Engine
kann — nicht, was der VfL Bochum tun sollte.

---

## 1. Was ändert ein schnellerer Innenverteidiger?

`python3 cli.py kontrafaktisch --frage schneller_iv --n 14 --minuten 7`

Innenverteidiger Nr. 2 bekommt 9,5 statt 8,4 m/s Spitzentempo, sonst bleibt
alles gleich.

```
Metrik                 Basis  Differenz        95%-Intervall
-------------------------------------------------------------
abwehrhoehe_m         34.642     +0.622   [  -2.056,   +3.285]
ppda                   2.409     +0.096   [  -0.314,   +0.536]
rueckeroberung_5s      0.656     +0.019   [  -0.012,   +0.050]
gefahrflaeche         11.875     +1.422   [  -0.939,   +3.854]

Gegnerseite:
xg                     0.383     -0.115   [  -0.289,   +0.046]
schuesse               7.643     -1.571   [  -3.857,   +0.786]
strafraumeintritte     9.286     -0.714   [  -2.857,   +1.571]
```

**Lesart:** Alles zeigt in die erwartete Richtung — die Kette steht etwas höher,
der Gegner kommt zu weniger Abschlüssen — aber **nichts davon ist deutlich**.
Ein einzelner Spieler auf einer einzelnen Position bewegt in sieben Minuten
weniger, als das Spiel von selbst schwankt. Das ist kein Mangel der Engine,
sondern die richtige Antwort: Wer aus einer solchen Zahl eine
Transferentscheidung ableitet, liest Rauschen.

Wer die Frage belastbar beantworten will, braucht mehr Wiederholungen oder
längere Läufe. Bei `--n 60 --minuten 20` liegt die Rechenzeit bei rund zwei
Stunden auf einem Kern — die Engine ist dafür gebaut, aber es ist kein
Knopfdruck.

## 2. Was ändert 3-4-3 statt 4-2-3-1?

`python3 cli.py kontrafaktisch --frage formation --formation 3-4-3 --n 14`

```
Eigene Seite:
xg                     0.411     +0.128   [  -0.024,   +0.286]
schuesse               5.786     +1.714   [  +0.071,   +3.286]   deutlich
ballbesitz             0.487     -0.002   [  -0.048,   +0.040]
abwehrhoehe_m         34.642     -0.182   [  -2.769,   +2.184]
laufdistanz_km        12.189     -0.051   [  -0.426,   +0.291]

Gegnerseite:
xg                     0.383     -0.173   [  -0.346,   -0.007]   deutlich
strafraumeintritte     9.286     -1.286   [  -4.214,   +1.714]
```

**Lesart:** Eine Formationsänderung verschiebt zehn Positionen gleichzeitig und
ist deshalb messbar, wo ein Spielertausch es nicht ist: mehr eigene Abschlüsse
und weniger gegnerisches xG, beides deutlich. Ballbesitz und Laufdistanz ändern
sich praktisch nicht — die Mannschaft läuft nicht mehr, sie läuft anders.

## 3. Welcher Stürmertyp funktioniert?

Zwei Varianten desselben Spielers, gegen dieselbe Restverteidigung:

```
ST #11: Abschluss und Timing auf Topniveau
xg                     0.411     -0.073   [  -0.257,   +0.103]
schuesse               5.786     +0.929   [  -1.143,   +3.071]
strafraumeintritte     7.714     +2.571   [  -0.286,   +5.357]

ST #11: Tiefenlaeufer (9.6 m/s, starkes Dribbling)
xg                     0.411     +0.237   [  -0.025,   +0.531]
schuesse               5.786     +3.286   [  +1.143,   +5.429]   deutlich
strafraumeintritte     7.714     +4.929   [  +1.929,   +7.571]   deutlich
```

**Lesart:** Gegen diese Restverteidigung bringt der Tiefenläufer deutlich mehr
Strafraumeintritte und Abschlüsse; der bessere Abschlussspieler bringt nichts
Messbares. Das ist die Art von Antwort, für die die ganze Engine gebaut ist —
und sie ist zugleich das beste Beispiel dafür, wie leicht man sie überinterpretiert:
Der Effekt liegt an *dieser* Gegenformation und *dieser* Abwehrhöhe. Andere
Restverteidigung, anderes Ergebnis. Genau deshalb steht in der Ausgabe die
Basis mit dabei.

## 4. Welche Räume entstehen nach 5 bis 10 Sekunden?

`python3 cli.py situation --ab 9 --n 50 --marken 5,10 --seed 4`

```
Ausgangslage bei 9.0 min, Ball bei (34.8, -2.7), Ballbesitz Heim

Nach 5 Sekunden (50 Wiederholungen):
  Ball x   Median   +40.4 m   [+0.3, +51.5]
  Ball y   Median    +0.0 m   [-13.1, +18.1]
  gefaehrliche Flaeche Heim     25.8   Gast     3.5
  Ballbesitz Heim  34 %

Nach 10 Sekunden (50 Wiederholungen):
  Ball x   Median   +24.8 m   [-13.9, +52.2]
  Ball y   Median    +1.7 m   [-13.9, +23.8]
  gefaehrliche Flaeche Heim     22.4   Gast     4.4
  Ballbesitz Heim  40 %
```

**Lesart:** Aus einer Lage 18 Meter vor dem gegnerischen Tor liegt der Ball nach
fünf Sekunden im Median noch tiefer im Angriffsdrittel, nach zehn Sekunden ist
er im Median zurück ins Mittelfeld gewandert — und die Streuung ist gewaltig:
Das 10-bis-90-Prozent-Band reicht nach zehn Sekunden von der eigenen Hälfte bis
zur gegnerischen Torlinie. Genau diese Streuung ist die eigentliche Aussage.
Eine Simulation, die auf „nach zehn Sekunden steht der Ball hier" antwortet,
lügt; eine, die die Verteilung zeigt, ist brauchbar.

## 5. Pressing als Anweisung

Voller Kontrast zwischen Abwarten (`pressing=0.15`, Auslöser 14 m) und
Vollangriff (`pressing=0.95`, Auslöser 34 m), zehn gepaarte Wiederholungen:

```
ppda                   3.220     -1.054   [  -1.870,   -0.235]   deutlich
rueckeroberung_5s      0.632     +0.060   [  +0.004,   +0.118]   deutlich
laufdistanz_km        11.189     +1.056   [  +0.935,   +1.206]   deutlich
abwehrhoehe_m         34.693     +1.980   [  -1.717,   +5.702]
xg                     0.386     -0.012   [  -0.241,   +0.202]
```

**Lesart:** Pressing kostet gut einen Kilometer je Spieler und liefert dafür
niedrigeres PPDA und sechs Prozentpunkte mehr Rückeroberungen binnen fünf
Sekunden — alles drei deutlich. Das eigene xG bewegt sich dabei **nicht**
messbar. Die Engine kennt keine Regel „Pressing ist gut"; sie zeigt den Preis
und den Ertrag getrennt und überlässt die Abwägung dem Menschen.
