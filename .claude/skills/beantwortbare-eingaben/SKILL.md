---
name: beantwortbare-eingaben
description: >
  Sorgt dafür, dass jede Eingabe beantwortbar ist — alles, was jemand zum
  Ausfüllen braucht, steht sichtbar neben der Eingabe, nicht in einem
  Aufklapper, Tooltip oder Info-Icon. Diesen Skill unbedingt laden, bevor du
  ein Formular, einen Fragebogen, eine Umfrage, ein Onboarding, einen Filter
  oder irgendeine Bewertungsskala baust oder überarbeitest — also bei
  Sternen, 1–5, 1–10, NPS, Slidern, Dropdowns, Auswahllisten, Zahlenfeldern.
  Ebenso bei einem Design-Review eines bestehenden Formulars, bei jeder
  Beschwerde über Nutzerverwirrung, uneinheitliche oder unbrauchbare
  Eingabedaten, und immer wenn du gerade dabei bist, eine Eingabe „kompakter",
  „aufgeräumter" oder „platzsparender" zu machen — genau dort entsteht der
  Fehler, den dieser Skill verhindert.
---

# Beantwortbare Eingaben

Eine Eingabe ist nicht fertig, wenn sie einen Wert annimmt. Sie ist fertig,
wenn jemand, der die Antwort **nicht schon kennt**, aus dem, was auf dem
Bildschirm steht, einen richtigen Wert erzeugen kann.

Das ist der ganze Skill. Der Rest erklärt, warum er nötig ist und woran man
den Verstoß erkennt, bevor ihn ein Nutzer meldet.

## Warum das ausgerechnet dir passiert

Zwei Kräfte ziehen zuverlässig in die falsche Richtung:

**Kompaktheit ist messbar, Beantwortbarkeit nicht.** Vertikaler Platz lässt
sich zählen. Ob jemand die Frage beantworten kann, lässt sich nur beurteilen,
indem man sich eine konkrete ahnungslose Person vorstellt. Layout-Regeln
sagen „kompakt halten", niemand sagt „beantwortbar halten" — also gewinnt die
zählbare Größe, außer man wehrt sich bewusst.

**Du bist nie der naive Nutzer.** Wer gerade das Datenmodell, die Skala oder
den Fragebogen geschrieben hat, weiß im Moment des Entwurfs genau, was eine 7
bedeutet. Die Lücke ist für dich unsichtbar, weil du sie in deinem Kopf
längst gefüllt hast. Deshalb reicht es nicht, das Formular anzusehen — du
musst es *für jemand anderen* durchgehen.

Dazu kommt eine Falle: „Progressive Disclosure" ist ein echtes, gutes Muster.
Ein Aufklapper sieht deshalb nach guter Praxis aus und übersteht die eigene
Prüfung. Er ist aber nur dann gute Praxis, wenn ihn *manche* Nutzer
*manchmal* brauchen.

## Der Test, der es fängt

Stelle zu jeder Eingabe genau eine Frage:

> **Woher weiß jemand, was hier hineingehört?**

Zeige mit dem Finger auf die Antwort. Zeigt der Finger irgendwohin, wo gerade
nichts steht — in einen Aufklapper, einen Tooltip, eine andere Seite, eine
Schulung, „das weiß man halt" — dann ist die Eingabe unfertig.

Für alles Aufklappbare gilt zusätzlich:

> **Wer muss das öffnen?**

- *Manche, manchmal* → Aufklapper ist richtig.
- *Alle, jedes Mal* oder *alle beim ersten Mal* → das ist kein Aufklapper,
  das ist eine Hürde im Kostüm einer Best Practice. Auspacken.

Wenn faktisch jeder klickt, hast du nichts gespart. Du hast einen Klick
hinzugefügt und die Information versteckt, die die Eingabe erst möglich macht.

## Der Vorfall, aus dem das kommt

Ein Scouting-Werkzeug ließ Spieler auf einer Skala von 1 bis 10 einordnen.
Jede Stufe entspricht einem realen Liga-Niveau mit Marktwertband — 7 heißt
„Belgian Pro League · 2. Bundesliga · Süper Lig, €1.5–7m". Gebaut wurde:
ein Raster mit den Ziffern 1 bis 10, darunter ein `<details>` mit
„Alle Stufen anzeigen".

Das sah aufgeräumt aus und war unbrauchbar. Niemand weiß, was eine 7
bedeutet, bevor er die Ligen gelesen hat — also hätte jeder Nutzer bei jeder
Bewertung aufklappen müssen. Das Urteil des Kunden: „Die meisten Leute wissen
nicht, was eins bis zehn heißt. Faktisch muss es jeder klicken."

Die Korrektur war, alle zehn Stufen offen als Liste zu zeigen, jede mit
Ligen, Einordnung und Marktwertband. Das kostet rund 500 Pixel. Es ist die
teuerste Fläche im Formular und die einzige, die sie verdient — ohne den
Anker daneben ist die Zahl bedeutungslos, und eine bedeutungslose Zahl ist
kein Datenpunkt, sondern Rauschen in der Datenbank.

## Muster, die immer wieder brechen

| Muster | Warum es bricht | Stattdessen |
|---|---|---|
| Zahlenskala ohne Beschriftung (1–5, 1–10, Sterne, NPS, Slider) | Jeder erfindet seine eigene Bedeutung, und jeder eine andere. Die Daten sind hinterher nicht vergleichbar. | Jede Stufe beschriftet, oder mindestens beide Enden plus Mitte, dauerhaft sichtbar |
| Anker im Aufklapper, Tooltip oder hinter einem Info-Icon | Wer die Antwort nicht kennt, weiß nicht, dass dort eine Antwort liegt | Inline, immer sichtbar |
| Erklärung nur bei Hover | Auf Touch gibt es kein Hover — die Information existiert für die Hälfte der Nutzer nicht | Sichtbarer Text |
| Platzhalter als Beschriftung | Verschwindet beim Tippen, also genau dann, wenn man nachsehen will | Echtes Label über dem Feld |
| Zahlenfeld ohne Einheit oder Größenordnung | „Budget: ___" — Euro? Tausend? Pro Monat? | Einheit am Feld, dazu ein realistisches Beispiel |
| Kürzel und Codes ohne Klartext | „CB, WB, CM" ist Muttersprache für drei Leute im Haus | Kürzel und Klartext nebeneinander |
| Skalenrichtung ungesagt | Ist 1 gut oder ist 10 gut? Wer rät, rät die Hälfte der Zeit falsch | Richtung aus der Beschriftung selbst ablesbar machen |
| Zwei verwandte Urteile, eines prominent, eines nebenbei | Das zweite wird zum Aufschlag auf das erste statt zu einer eigenen Einschätzung | Beide gleich behandeln — gleiche Form, gleiches Gewicht |
| Regel erscheint erst als Fehlermeldung | Der Nutzer erfährt die Anforderung, nachdem er sie verletzt hat | Anforderung am Feld, bevor getippt wird |
| Leerer Zustand ohne Beispiel | „Noch nichts hier" sagt nicht, was hier hingehört | Ein echtes Beispiel zeigen |

## Platz vergeben

Kompaktheit ist ein Mittel, nie ein Ziel. Sie dient dem Zweck, dass das
Wichtige nicht im Unwichtigen untergeht — sie ist kein Wert an sich.

Die Faustregel: **die schwierigste Beurteilung auf der Seite bekommt den
meisten Platz.** Wenn eine Eingabe die eigentliche Entscheidung trägt, ist
sie kein Kandidat fürs Platzsparen. Spare stattdessen dort, wo ohnehin jeder
schnell durchklickt.

Wenn die beantwortbare Fassung wirklich zu lang wird, in dieser Reihenfolge
kürzen:

1. Jede Zeile knapper schreiben — nicht weniger Zeilen zeigen.
2. Nebeninformation auf eine zweite, kleinere Zeile legen.
3. Die Liste optisch verdichten: engere Zeilen, kleinere Schrift, aber alles
   sichtbar.
4. Erst ganz zuletzt: aufklappbar, aber **standardmäßig offen**.

Was nie geht: die Anker verstecken und die nackte Zahl stehen lassen.

## Wann Verbergen richtig ist

Damit das hier kein Absolutismus wird — Aufklapper sind gut für:

- Nachschlagematerial, das eine Minderheit gelegentlich braucht
- Fortgeschrittene oder optionale Einstellungen mit brauchbarem Standardwert
- Lange Rechtstexte
- Erläuterungen **nach** der Entscheidung: warum ein Ergebnis so aussieht,
  wie es aussieht

Der gemeinsame Nenner: nichts davon wird gebraucht, um die eigentliche
Eingabe zu machen.

## Bevor du es abgibst

Geh das Formular einmal als jemand durch, der die Domäne nicht kennt. Für
jede Eingabe der Reihe nach:

1. Benenne, welche Information nötig ist, um sie richtig auszufüllen.
2. Zeige, wo diese Information auf dem Bildschirm steht.
3. Prüfe sie auf Touch: existiert alles auch ohne Hover?
4. Prüfe den ausgefüllten Zustand: bleibt die Antwort lesbar, oder wird sie
   zu einer Zahl ohne Kontext, sobald das Feld geschlossen ist?

Findest du eine Eingabe, bei der Schritt 2 ins Leere zeigt, ist das kein
Schönheitsfehler. Es ist der Grund, warum die gesammelten Daten später nicht
zu gebrauchen sind.
