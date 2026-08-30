# Prompt: LASK — Ökonomisches Entscheidungs-Framework

Dieser Text ist **der Prompt selbst**, nicht die Beschreibung eines Prompts. Alles ab der
Trennlinie in ein leeres Claude-Code-Projekt kopieren (eigenes Repository, nicht dieses hier —
das VfL-Framework ist die Stilvorlage, nicht die Codebasis).

Zwei Dinge vorher entscheiden und im Prompt ersetzen:

- `<SAISON>` — die Saison, für die gerechnet wird (z. B. 2026/27).
- `<STICHTAG>` — der Spieltag, an dem der Punktwert ausgewiesen wird (der Punktwert ist eine
  Funktion des Saisonzustands, kein Jahresmittel; ohne Stichtag ist die Frage unterbestimmt).

---

# LASK — Was ist ein Punkt wert, und was kostet eine Minute?

Du baust ein quantitatives Entscheidungs-Framework für den LASK. Es beantwortet **eine**
ökonomische Kernfrage und drei Fragen, die dafür gebraucht werden. Sprache durchgängig
Deutsch: Code-Kommentare, Dateinamen, Spaltennamen, Dashboard, Dokumentation.

## Die Kernfrage

> Der LASK setzt in den Altersbändern mit der **höchsten Wertsteigerungsrendite je Minute**
> faktisch keine Spieler ein. Ist das ökonomisch richtig?

Das ist keine Meinungsfrage, sondern eine Ungleichung. Setze sie hin, fülle jede Größe mit
einer gerechneten Zahl, und beantworte sie mit Vorzeichen und Betrag:

```
Minute an einen U21-Spieler statt an einen Etablierten lohnt sich, wenn

    ΔMW(U21)  −  ΔMW(Etablierter)  +  Fördertopf-Effekt          [Ertrag, € je 1.000 Min]
  ≥ Punktwert(Saisonzustand S)  ×  ΔPunkte(Qualitätsdifferenz)   [Kosten,  € je 1.000 Min]
```

Weil die rechte Seite unsicher ist, ist die **belastbarere Form der Antwort die Umkehrung**:

> **Break-even-Minutenrendite** — wie viel Euro Wertzuwachs müsste eine U21-Minute erzeugen,
> damit sie den erwarteten Punktverlust bezahlt? Diese Schwelle gegen die geschätzte
> Renditekurve halten. Liegt die Kurve klar darüber oder klar darunter, steht die Antwort
> auch dann, wenn beide Schätzungen breite Konfidenzintervalle haben.

Die Antwort ist mit hoher Wahrscheinlichkeit **zustandsabhängig**, nicht pauschal. Rechne sie
deshalb je Spieltag und je Tabellenlage durch und weise aus, **ab wann** sie kippt. Ein Satz
wie „Jugend lohnt sich" ohne Angabe des Saisonzustands ist kein Ergebnis.

## Baustein A — Punktwert

Ein Ligapunkt hat keinen Durchschnittswert. Er hat einen **Grenzwert**, und der hängt davon
ab, wo die Mannschaft steht: Erlös ist eine Treppenfunktion der Platzierung, also ist der
Punktwert dort groß, wo ein Punkt die Wahrscheinlichkeit verschiebt, eine Stufe zu nehmen —
und nahe null überall sonst.

```
W(S)          = E[ Erlös | Saisonzustand S ]
Punktwert(S)  = W(S ⊕ 1 Punkt) − W(S)
```

**So rechnest du `W(S)`:**

1. **Restsaison simulieren.** Monte-Carlo über alle verbleibenden Ligaspiele, mindestens
   50.000 Läufe, mit Zufallsstartwert im Code fixiert. Torerwartung je Paarung aus einem
   Poisson-Modell mit Angriffs-/Abwehrstärke je Team und Heimvorteil, kalibriert auf
   mindestens fünf Saisons österreichische Bundesliga; Stärke aus xG, nicht aus Toren.
2. **Regelwerk exakt abbilden.** Ligamodus der österreichischen Bundesliga: Grunddurchgang,
   Punkteteilung beim Split, Meister- und Qualifikationsgruppe, Europa-League-Play-off der
   Qualifikationsgruppe, Auf-/Abstiegsregel. **Diese Regeln nicht aus dem Gedächtnis setzen** —
   aus dem gültigen Ligastatut für `<SAISON>` holen, Fundstelle in `register/regelwerk.json`
   vermerken. Die Teilungs- und Rundungsregel ist nicht kosmetisch: sie halbiert den Wert
   jedes Punktes aus dem Grunddurchgang und macht einen ungeraden Punktestand verschieden
   wertvoll von einem geraden.
3. **ÖFB-Cup mitmodellieren.** Der Cupsieg ist ein zweiter Weg nach Europa und verändert den
   Grenzwert eines Ligapunkts (er macht ihn kleiner, solange der Cup noch läuft). Als eigenen
   Ast mit Runden-Fortschrittswahrscheinlichkeiten führen.
4. **Erlös je Endzustand summieren.** Mindestens diese Posten, jeder mit Quelle:

   | Posten | Bemerkung |
   |---|---|
   | Medien- und Ligaerlös | Verteilschlüssel der Liga, platzierungsabhängiger Anteil separat |
   | UEFA-Antrittsprämie | je Wettbewerb und erreichter Runde, laufender Zyklus |
   | UEFA-Leistungsprämien | Sieg/Unentschieden Ligaphase, K.-o.-Runden |
   | UEFA-Koeffizientenanteil | Klub- und Verbandskoeffizient, mehrjährig nachlaufend |
   | Marktpool / Value-Anteil | für Österreich klein, aber nicht null |
   | Zuschauer, Hospitality, Merchandising | Elastizität gegen Platzierung aus eigenen Zahlen |
   | Sponsoring-Boni | falls vertraglich platzierungs- oder europapokalgebunden |

   **Keine UEFA-Prämie aus dem Gedächtnis eintragen.** Alle Beträge in
   `register/erloese.json` mit `quelle` und `basis`; unbelegte Werte als
   `quelle: "geschaetzt"` markieren, damit sie im Dashboard sichtbar bleiben.
5. **Verzögerte Erlöse abzinsen.** Der Koeffizientenanteil wirkt über Jahre. Barwert mit einem
   Zinssatz aus `register/annahmen.json`, nicht mit einer im Code versteckten Zahl.

**Auszugeben:**

- `punktwert_je_spieltag.csv` — Grenzwert eines Punktes über die Saison, mit Konfidenzband.
- `punktwert_je_zustand.csv` — Gitter aus Spieltag × Punktestand → € je Punkt.
- **Zerlegung** je Zustand: welcher Anteil des Punktwerts stammt aus welcher Schwelle
  (Meistergruppe, Platz 1, Platz 2, Platz 3, Abstieg). Ohne diese Zerlegung ist eine große
  Zahl nicht interpretierbar.
- Der Wert am `<STICHTAG>` als eine Zahl mit Intervall — das ist die Antwort auf „Wie viel
  bringt gerade jeder Punkt?".

## Baustein B — Minutenrendite nach Altersband

**Altersbänder** (Alter am 30.06. der Saison): `0–17`, `18–20`, `21–23`, `24–26`, `27–29`,
`30+`. Die Bänder liegen als Daten in `register/altersbaender.json`, nicht im Code.

**Zielgröße:** Marktwertänderung je Spieler und Saison, erklärt durch Einsatzminuten:

```
ΔMW(i,t) = f( Alter, Minuten, Ligastufe, Position, MW(i,t), Vertragsrestlaufzeit,
              Verein-Fixeffekt, Saison-Fixeffekt ) + ε
```

Ausgewiesen wird `∂ΔMW / ∂Minuten` **je Altersband**, als **€ je 1.000 Minuten**, mit
Konfidenzintervall und Fallzahl. Panel über mehrere Saisons und mehrere Ligen; Ligastufe aus
einem Register wie `liga_level.json` im VfL-Projekt.

**Der schwierige Teil, und er ist nicht optional: Endogenität.** Gute Spieler bekommen sowohl
Minuten als auch Wertzuwachs. Eine naive Regression überschätzt die Minutenrendite
systematisch. Mindestens zwei dieser vier Gegenmaßnahmen umsetzen und ihre Wirkung auf den
Koeffizienten zeigen:

1. Spieler-Fixeffekte (Identifikation aus der Veränderung innerhalb eines Spielers).
2. Kontrolle auf Leistungsperzentil **vor** der Saison, nicht währenddessen.
3. Instrument: verletzungs- oder sperrenbedingter Ausfall eines Konkurrenten auf der Position
   — erzeugt Minuten, die nicht aus der Qualität des Spielers folgen.
4. Placebo-Test: dieselbe Spezifikation auf das Altersband `30+`, wo die Rendite theoretisch
   negativ sein muss. Kommt dort ein deutlich positiver Wert heraus, misst das Modell
   Selektion, nicht Rendite — dann ist der Befund nicht verwendbar und das ist zu schreiben.

**Zusätzlich zu prüfen und, falls einschlägig, als eigener Ertragsposten zu führen:** Gibt es
in `<SAISON>` eine Ausschüttung der Liga oder des ÖFB, die an Einsatzminuten junger und/oder
österreichischer Spieler gekoppelt ist (Nachwuchsförderung, Österreicher-Topf, Legionärs- oder
Ausbildungsregelung)? Falls ja, ist das **direkte Cash-Rendite je Jugendminute** und gehört
mit Betrag und Fundstelle in `register/foerderung.json`. Falls nein oder nicht belegbar: als
`0` mit Begründung eintragen, nicht weglassen.

**Ist-Aufnahme LASK:** Minutenverteilung des LASK über die Altersbänder in `<SAISON>`, gegen
den Ligadurchschnitt und gegen die drei Vereine der Liga mit dem höchsten Transferertrag der
letzten fünf Jahre. Erst diese Tabelle belegt die Prämisse der Kernfrage — falls sie sie
**nicht** belegt, ist das das Ergebnis und die Kernfrage wird entsprechend umformuliert.

## Baustein C — Ideales Sportbudget

```
max_K   E[ Erlös( Punkte(K) ) ]  −  K  −  Transfersaldo(K)

u. d. N.  K / Umsatz ≤ Obergrenze der UEFA-Kaderkostenregel
          Liquidität und Lizenzauflagen der Bundesliga eingehalten
```

- `Punkte(K)`: Elastizität der Punkte gegen die Kaderkosten, geschätzt über die
  österreichische Bundesliga plus vergleichbare Ligen (Ligastufe 5–7). Log-lineare
  Spezifikation, R² und Streuung mit ausweisen — die Elastizität ist real, aber die Streuung
  um sie herum ist groß, und genau die entscheidet über das Risiko.
- Ergebnis ist **kein Punktwert, sondern ein Band**: Kaderkosten-Korridor in Euro, plus
  Ausfallrisiko (Wahrscheinlichkeit, den Europacup zu verfehlen, je Budgetstufe).
- Die geltende Obergrenze der Kaderkostenregel und ihren Übergangspfad aus der Quelle holen,
  nicht aus dem Gedächtnis, und in `register/annahmen.json` legen.
- Zweites Ergebnis: **Umschichtung statt Aufstockung** — wie viel des Optimums erreicht man
  bei unverändertem Budget allein durch die Minutenallokation aus Baustein B?

## Baustein D — Spielermarkt: Kennzahlen und Wachstum

Alle Kennzahlen mit exakter Formel in `ergebnisse/SCHEMA.md`, alle je Saison und je
Altersband, wo es sinnvoll ist:

| Kennzahl | Definition |
|---|---|
| Kadermarktwert | Summe MW, Stichtag und Quelle vermerkt |
| Alterspyramide | Kaderanteil und Minutenanteil je Altersband, getrennt ausweisen |
| Wertwachstum p. a. | CAGR Kadermarktwert, bereinigt um Zu- und Abgänge |
| Organischer Wertzuwachs | Wertänderung der durchgehend gehaltenen Spieler — die einzige Zahl, die Ausbildung misst |
| Transferbilanz | Erlöse − Ausgaben, inkl. Boni und Weiterverkaufsbeteiligungen |
| Ausbildungs-ROI | Transferertrag ÷ (Akademiekosten + Gehaltssumme der Ausbildungsjahre) |
| Kadereffizienz | Kadermarktwert je erzieltem Punkt, im Ligavergleich |
| Reinvestitionsquote | Anteil der Transfererlöse, der in Zugänge zurückfließt |
| Vertragsrisiko | Marktwert × Restlaufzeitfaktor — Wertverfall bei auslaufenden Verträgen |
| Verkaufsfenster | Alter mit dem historisch höchsten Verkaufserlös je Position |

Marktwerte: Quelle, Stichtag und Lizenzlage klären, bevor du sie beschaffst. Wenn die Quelle
kein Massenabruf erlaubt, **nicht scrapen** — manuellen oder lizenzierten Export einlesen und
den Weg in der README dokumentieren. Ein Marktwert ist außerdem eine Schätzung Dritter, keine
Beobachtung: das gehört in die Grenzen-Sektion, und wo möglich wird gegen tatsächlich
realisierte Ablösen validiert.

## Regeln, die für alles gelten

1. **Keine erfundenen Zahlen.** Jeder Parameter, den du nicht selbst gerechnet hast, steht in
   einer Registerdatei unter `register/` mit `wert`, `quelle` (`vorgegeben` | `abgeleitet` |
   `geschaetzt`), `basis` (Fundstelle) und `stand` (Datum). Der Code liest Register, er enthält
   keine Konstanten. Ein `geschaetzt`-Wert ist erlaubt — unmarkiert wäre er es nicht.
2. **Grenzwert statt Mittelwert.** Überall dort, wo eine Entscheidung ansteht, ist die
   marginale Größe gefragt, nicht der Durchschnitt.
3. **Unsicherheit wird gezeigt, nicht wegformuliert.** Jede Kernzahl mit Intervall. Wo ein
   Intervall das Vorzeichen der Antwort umdreht, steht das im Ergebnis.
4. **Trennung der Ebenen.** Sportlicher Erfolg, Wertsteigerung und Liquidität werden nicht zu
   einer Note verrechnet. Sie werden in einer gemeinsamen Währung (Euro) verglichen und
   getrennt ausgewiesen.
5. **Kein Leakage.** Modelle, die eine Saison bewerten, dürfen keine Information aus deren
   Ende benutzen. Validierung leave-one-season-out.
6. **`verify.py` ist Pflicht**, nicht Kür. Mindestens: Rechenidentitäten (Summanden ergeben die
   Summe), Skalenlage jeder Kennzahl, Kalibrierung des Simulationsmodells (simulierte
   Punkteverteilung gegen tatsächliche Abschlusstabellen vergangener Saisons), Leakage-Freiheit,
   Registerabdeckung (kein im Code hartkodierter Parameter), Monotonie (mehr Punkte dürfen den
   Erwartungserlös nie senken) und der Placebo-Test aus Baustein B.

## Dashboard

Eine Datei, `dashboard.html`, in sich geschlossen — keine externen Requests, keine CDN, keine
Fonts von außen. Doppelklick genügt. Daten werden aus JSON eingespielt (`skripte/dashboard_data.py`
→ `skripte/build_dashboard.py`), nicht im Markup gepflegt. Hell- und Dunkelmodus.

Vier Ansichten:

| Ansicht | Zeigt |
|---|---|
| **Punktwert** | Kurve über die Saison, Zerlegung nach Schwellen, Was-wäre-wenn-Gitter |
| **Minuten** | Renditekurve je Altersband mit Intervall, Ist-Verteilung LASK gegen Liga, Break-even-Linie |
| **Entscheidung** | Die Ungleichung als eine Ansicht: Ertrag gegen Kosten je Altersband, Vorzeichen groß, Kipppunkt benannt |
| **Markt & Budget** | Kennzahlen aus D, Budgetkorridor aus C mit Ausfallrisiko |

Zwei Anforderungen, die über Kosmetik hinausgehen:

- **Regler für die strittigen Annahmen** (Punktwert-Niveau, Qualitätsdifferenz je Swap,
  Diskontsatz). Der Nutzer muss sehen, ob die Antwort robust ist oder an einer Annahme hängt.
  Die Regler ändern die Anzeige, nie die abgelegten Ergebnisse.
- **Herkunftsabzeichen an jeder Zahl**: gerechnet / abgeleitet / geschätzt, aus dem Register
  gespeist. Eine geschätzte Zahl darf im Dashboard nicht so aussehen wie eine gerechnete.

Bevor du eine Grafik oder eine Eingabe baust: den Skill `dataviz` laden, und für jede
Eingabe oder Skala zusätzlich `beantwortbare-eingaben`.

## Aufbau

```
README.md                 Einstieg, Pipeline, Reproduktion aus einem Klon
framework_spec.md         Methodik, Validierung, Grenzen — alle Zahlen gerechnet
dashboard.html            in sich geschlossen
register/                 alle Parameter mit Quelle: erloese, regelwerk, altersbaender,
                          foerderung, annahmen, liga_level
skripte/                  nummerierte Pipeline, verify.py
ergebnisse/               tidy CSV/JSON + SCHEMA.md mit jeder Spalte
daten/                    Rohdaten, nicht im Repository (Lizenz), reproduzierbar
```

Pipeline in nummerierten Schritten, jeder für sich lauffähig, jeder schreibt in `ergebnisse/`.
Zugangsdaten ausschließlich über Umgebungsvariablen, niemals im Code, niemals im Commit.

## Reihenfolge

Arbeite in dieser Reihenfolge und **halte nach jeder Stufe an**, um das Zwischenergebnis zu
zeigen. Nicht alles auf einmal bauen.

1. **Stufe 0 — Datenlage.** Was ist beschaffbar, was lizenziert, was fehlt? Eine Tabelle:
   Größe, Quelle, Lizenz, Aufwand, Ersatz falls nicht verfügbar. Erst danach Code.
2. **Stufe 1 — Punktwert.** Baustein A vollständig, inklusive Kalibrierung gegen vergangene
   Saisons. Das ist die Zahl, nach der gefragt wurde; sie steht allein.
3. **Stufe 2 — Minutenrendite.** Baustein B inklusive Endogenitätsbehandlung und Placebo-Test.
4. **Stufe 3 — Die Antwort.** Ungleichung und Break-even, je Saisonzustand, mit Kipppunkt.
5. **Stufe 4 — Budget und Markt.** Bausteine C und D.
6. **Stufe 5 — Dashboard.**

## Fertig ist es, wenn

- die Frage „Wie viel bringt gerade jeder Punkt?" mit **einer Zahl, einem Intervall und einem
  Datum** beantwortet ist,
- die Frage „Ist es okay, dort keine Spieler einzusetzen?" mit **Vorzeichen, Betrag und
  Kipppunkt** beantwortet ist — inklusive der ehrlichen Variante, falls die Datenlage nur die
  Break-even-Schwelle hergibt und nicht die Renditekurve,
- `python3 skripte/verify.py` durchläuft und die Zahl der Prüfungen nennt,
- `framework_spec.md` einen Abschnitt **„Was das Framework nicht kann"** hat, der die
  Schwachstellen benennt statt sie wegzurechnen — mindestens: Endogenität der Minutenrendite,
  Marktwerte als Fremdschätzung, Fallzahl der österreichischen Bundesliga, Unsicherheit der
  Erlösregister,
- kein Parameter im Code steht, den nicht ein Register belegt.

## Umgangston

Nüchtern, deutsch, ohne Superlative. Tabellen statt Aufzählungen, wo etwas verglichen wird.
Wenn eine Zahl nicht belastbar ist, schreibst du das hin, statt sie zu runden, bis sie
seriös aussieht. Ein sauber begründetes „das gibt die Datenlage nicht her" ist ein Ergebnis;
eine hübsche Zahl ohne Herkunft ist keines.
