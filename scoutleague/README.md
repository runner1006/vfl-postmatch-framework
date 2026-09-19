# Scout League — MVP (Stufe 0/1)

Prediction-Game auf echten Talenten. Scouts bewerten wöchentlich fünf Spieler
auf 1–5-Skalen und geben zu jedem drei Wahrscheinlichkeitsprognosen ab. Die
Bewertung wird **sofort** gegen das Modell gespiegelt, die Prognosen
**zeitversetzt** gegen die Realität. Jede aufgelöste Prognose ist ein
Outcome-Label.

Der MVP deckt Stufe 0 und Stufe 1 aus dem One-Pager ab: das interne
Kalibrierungs-Feature und die Closed Beta. Kein Infrastruktur-Invest — reine
Python-Standardbibliothek, eine SQLite-Datei, ein Prozess.

Rev. 0.2 setzt den **Scout Rating Audit (Juni 2026)** um. Der Audit hat die
interne Skala an 187 Bewertungen vermessen und sechs Empfehlungen ausgesprochen;
alle sechs stecken jetzt im Produkt statt in einer Präsentation — siehe
[Was der Audit geändert hat](#was-der-audit-geändert-hat).

## Nur ansehen, ohne alles

`scoutleague/vorschau.html` ist die App als eine Datei — Doppelklick genügt,
kein Server, keine Installation. Sie zeigt beide Ansichten (Scout und Admin)
mit Daten aus einem echten Lauf: zehn Testscouts auf sechs erfundenen Spielern.
Bewerten und Abgeben funktioniert, die Kennzahlen in Profil, Liga und
Kalibrier-Report sind ein Standbild.

Markup, Stylesheet und Skripte kommen unverändert aus `static/` — ersetzt ist
allein `fetch`. Die Vorschau kann also nicht auseinanderlaufen mit dem, was der
Server ausliefert. Neu bauen nach einer UI-Änderung:

```bash
python3 scoutleague/vorschau_bauen.py --daten scoutleague/vorschau_daten.json
```

Die aufgezeichneten Antworten selbst erneuern (braucht einen laufenden Server):

```bash
python3 scoutleague/cli.py demo > codes.txt
SCOUTLEAGUE_ADMIN_TOKEN=geheim python3 scoutleague/serve.py --port 8099 &
python3 scoutleague/vorschau_daten.py --port 8099 --token geheim \
    --codes codes.txt --ziel scoutleague/vorschau_daten.json
```

## In drei Minuten ausprobieren

```bash
export SCOUTLEAGUE_ADMIN_TOKEN='beliebig-aber-geheim'
python3 scoutleague/cli.py demo        # Demo-Pack + 10 Codes
python3 scoutleague/serve.py --port 8080
```

`http://localhost:8080` mit einem der ausgegebenen Codes,
`http://localhost:8080/admin` mit dem Admin-Token.

Das Demo-Pack enthält **erfundene** Spieler. Für den Pilotbetrieb wird es durch
einen echten Case Pack ersetzt.

## Checkliste für den Pilotstart

1. **Case Pack bauen.** `pakete/VORLAGE.json` kopieren, fünf Talente eintragen:
   Steckbrief, Highlight-Video-Link, aggregierte NOVA-Indizes (0–100) und die
   Modellprognosen. Ausschließlich eigene, aggregierte Indizes — keine
   Provider-Rohdaten. Dann:
   ```bash
   python3 scoutleague/cli.py pack --datei scoutleague/pakete/kw35.json
   ```
   Der Import prüft alles vorab und bricht ab, bevor ein halber Pack entsteht.
2. **Codes anlegen** und persönlich verteilen:
   ```bash
   python3 scoutleague/cli.py scouts --namen "Zoran,Miguel,…"
   ```
3. **Demo-Pack schließen**, damit im Feld nur echte Fälle stehen:
   ```bash
   python3 scoutleague/cli.py status --slug demo --auf geschlossen
   ```
4. **Server starten** (siehe Betrieb unten) und den Link plus Code verschicken.
5. **Stand verfolgen:** `python3 scoutleague/cli.py stand`
6. **Nach Ablauf des Prognosehorizonts auflösen** — im Admin-UI oder per CLI:
   ```bash
   python3 scoutleague/cli.py aufloesen --fall 3 --frage top5_12m \
       --ergebnis 1 --quelle "Transfer bestätigt am …"
   ```
   Ab der ersten Auflösung sortiert das Leaderboard nach Brier-Skill.
7. **Labels exportieren:** `python3 scoutleague/cli.py export > labels.csv`

## Was der Audit geändert hat

| Audit-Befund | Empfehlung | Umsetzung |
|---|---|---|
| 58 % aller Noten sind eine „3" | Zentraltendenz aufbrechen, notfalls direkt auf 1–10 | **Level Rating 1–10** als Leitfrage, jede Stufe mit realem Liga-Anker und Marktwertband. Die abstrakte Gesamtnote ist weg. |
| 0,56 Punkte Strenge-Gap zwischen Scouts | pro Scout z-standardisieren | Der Feldvergleich weist **beides** aus: rohen Schnitt und rater-bereinigten Schnitt, jeder Scout an seinen eigenen Abgaben z-standardisiert. |
| Halo r = 0,78 (Final ≈ Attribut-Mittel) | Performance und Development entkoppeln | Zwei **getrennt verankerte** Level-Fragen: bewiesenes Niveau vs. realistisches Ceiling. Halo und Entkopplung werden je Scout gemessen und im Profil angezeigt. |
| ρ = 0,23 Scout ↔ Daten, stark positionsabhängig | Daten als Korrektiv, Konfliktfälle markieren | **Konfliktliste** im Report und Konfliktmarkierung direkt in der Sofort-Rückmeldung, in beide Richtungen gelesen. |
| Attribut-Sets nicht standardisiert, tote Felder mit σ < 0,4 | verpflichtendes Kern-Set je Position | **Sechs Positionsgruppen** (CB, WB, CM, WF, AM, CF), je 4 Kern- plus 4 Positionsattribute, alle mit Verhaltensankern. Der Import lehnt Modellwerte ab, die nicht zum Set der Position gehören. |
| Note und Perzentil stehen nebeneinander | eine gemeinsame Endskala | Die **Brücke** aus Kapitel 9: `liga_level` plus `profile_percentile` ergeben beim Import das Modell-Level, verschoben um höchstens eine Stufe. |

### Skalenrichtung

Der Audit nennt die Richtungs-Umkehr die häufigste Fehlerquelle: das interne
Formular folgt der Schulnote (1 = sehr gut), das Daten-Perzentil läuft
andersherum (100 = Spitze). **In der Scout League gibt es nur eine Richtung:
höher ist besser** — Level 10 wie Attribut 5, gleichlaufend mit dem Perzentil.
Das steht als `skalen_richtung` in `fragebogen.json` und an jeder Skala im
Frontend.

Die Attribute bleiben bei 1–5, nicht bei den 1–6 des Audits: der One-Pager
beschreibt das neue interne System ausdrücklich als „Mehrfragen-Bewertungssystem
(1–5-Skalen)". Der Audit hat die *alte* 1–6-Skala vermessen.

### Der Kalibrier-Report

`/admin` → *Kalibrier-Report* rechnet die fünf Audit-Diagnosen fortlaufend auf
allem, was die Liga abgegeben hat — Zentraltendenz je Frage, Rater-Strenge je
Scout, Halo und Entkopplung, Attribut-Trennschärfe je Positionsgruppe, Scout
gegen Modell — und formuliert die Befunde als Klartext-Warnungen.

Unterhalb von `mindest_faelle_diagnose` (Vorgabe: 5 Bewertungen) diagnostiziert
er bewusst nichts und sagt das auch: wer einen Spieler bewertet hat, hat per
Konstruktion 100 % auf einer Stufe, und das als Zentraltendenz zu melden wäre
Rauschen als Befund verkauft.

## Was der Scout wann sieht

Die wichtigste Grenze im ganzen Produkt läuft zwischen beschreibendem Kontext
und bewertenden Daten.

| Vor der Abgabe | Erst nach der Abgabe |
|---|---|
| Video-Highlight | Aggregierte Indizes |
| Position, Rolle, Jahrgang, Verein, Fuß | Modellerwartung (Level und Attribute) |
| **Liga** | Feldvergleich, roh und rater-bereinigt |
| Marktwertschwelle der Prognosefrage | Konfliktmarkierung |

Die Liga bleibt sichtbar, und zwar zwingend: sie ist der Anker der Level-Frage
— das Level ist die Liga-Stufe, um höchstens eine Stufe verschoben. Ohne sie
wäre die Frage nicht zu beantworten. Die Marktwertschwelle gehört zur Frage,
nicht zu den Belegen.

Die Indizes liegen dagegen hinter der Abgabe, und das ist kein Detail: die
Modellerwartung wird **aus ihnen gerechnet**. Wer Technik 84 und Athletik 48
vorher sieht, vergibt 4 und 2 — und dann misst die Trennschärfe nur noch, ob
jemand Balken in Noten übersetzen kann. Die Konfliktliste bliebe leer, weil
niemand Grund hätte zu widersprechen, und ein Brier-Score auf abgelesenen
Werten belegt keinen Track Record.

Daraus folgt: **das Video ist der einzige Beleg, den der Scout vor seinem
Urteil hat.** Ein Fall ohne Video ist nicht beurteilbar. Der Import warnt
deshalb bei jedem Fall ohne `video_url`, und die Oberfläche sagt es dem Scout
statt ihm ein leeres Formular hinzustellen.

## Woher die Modellerwartung kommt

Der Case Pack braucht je Spieler ein Level 1–10, eine Erwartung je Attribut und
Prognosewahrscheinlichkeiten. Die kamen anfangs von Hand. `modell.py` leitet
sie aus einem NOVA-Export ab — so weit die Daten reichen, und keinen Schritt
weiter:

| Größe | Herkunft |
|---|---|
| Perzentil im Positionspool | gerechnet, gegen den vollen Ligapool ab 400 Minuten |
| Level heute | gerechnet, sobald das Liga-Niveau bekannt ist: Liga-Stufe, um höchstens eine Stufe durch das Perzentil verschoben |
| **Liga-Niveau** | **nicht rechenbar.** Ein Perzentil misst den Rang *in* der Liga, nie die Liga. Steht in `liga_level.json` |
| Attributnote 1–5 | gerechnet aus dem Poolperzentil der zugeordneten Kennzahl — wo keine Kennzahl zeigt, bleibt das Feld leer |
| Ceiling | Heuristik aus Alter und Indexverlauf, offen deklariert. Es gibt keine Outcome-Historie, auf die man fitten könnte |
| Prognosen | brauchen Basisraten aus aufgelösten Fällen; ohne die bleibt das Feld leer |

Ein erster Blick auf einen unbekannten Export:

```bash
python3 scoutleague/modell.py --export export-51.csv
```

Zeigt erkannte Spalten, Indexspalten, Poolqualität und ob die Liga im Register
steht. `pool_pruefen()` verweigert handverlesene Exporte: Zeilen unter 60
Minuten, zu kleine Pools und Perzentile über Ligagrenzen hinweg werden benannt
statt stillschweigend verrechnet.

Die Urteilsschicht darüber ist der Agent `.claude/agents/modell-analyse.md` —
er entscheidet, welche Kennzahl auf welches Attribut zeigt, ordnet neue Ligen
ein und schreibt das Methodenblatt dazu. Der Grundsatz durchgehend: **eine
Lücke ausweisen ist billiger als eine Zahl erfinden.** Ein leeres Feld kostet
ein Stück Sofort-Feedback; eine erfundene Modellerwartung vergiftet
Trennschärfe, Konfliktliste und Sofort-Rückmeldung, ohne dass es auffällt.

## Was gemessen wird

Zwei Blöcke, die bewusst getrennt bleiben statt zu einer Note zu verschmelzen —
dieselbe Logik wie im Post-Match-Framework nebenan.

**Sofort verfügbar** (der eigentliche Zweck von Stufe 0):

| Kennzahl | bedeutet |
|---|---|
| Spreizung | Streuung der Gesamteinschätzung über alle Fälle. Nahe 0 heißt: immer dieselbe Note, also keine Information. |
| Spreizungs-Index | dieselbe Zahl im Verhältnis zum Median des Felds. |
| Bias | Abstand zum Feldmittel — positiv heißt milder als das Feld. |
| Trennschärfe | Rangkorrelation des eigenen Levels mit der Modellerwartung. |
| Modell-Nähe | 0–100 auf der Attributskala. **Kein Gütemaß** — Abweichung mit Recht ist der Punkt der Übung. |
| Halo | Korrelation Level ↔ Attribut-Mittel. Nahe 1 heißt: das Gesamturteil ist nur ein Echo der Einzelnoten. |
| Entkopplung | Korrelation bewiesenes Niveau ↔ Ceiling. Hoch heißt: das Ceiling ist ein Aufschlag, keine eigene Schätzung. |
| Zentraltendenz | Anteil der häufigsten Stufe. Über 35 % kann die Skala nicht mehr ranken. |

**Erst nach Auflösung:**

| Kennzahl | bedeutet |
|---|---|
| Brier | mittlerer quadratischer Prognosefehler. 0 perfekt, 0,25 Münzwurf. |
| Brier-Skill | Brier gegen die Basisrate. Über 0 heißt besser als die Basisrate zu kennen. |
| Kalibrierungsfehler | Abstand zwischen zugesagter und eingetretener Häufigkeit (ECE, fünf Bins). |

Vor der ersten Auflösung ist die Rangfolge vorläufig und sortiert nach
Trennschärfe. Das Frontend sagt das an der Tabelle dazu.

## Aufbau

```
serve.py           HTTP-Server, nur Routing
logik.py           Case Pack, Abgabe, Leaderboard, Profil
metriken.py        die Rechnung: Brier, Kalibrierung, Spreizung, Spearman
db.py              SQLite-Schema, idempotent bei jedem Start
export.py          Admin-Übersicht, Auflösung, CSV
cli.py             Betriebswerkzeug (scouts, pack, status, aufloesen, export, stand)
tests.py           179 Prüfungen: Metrik-Mathematik + End-to-End gegen echten Server
vorschau.html      die App als eine Datei, ohne Server — Doppelklick genügt
vorschau_bauen.py  baut vorschau.html aus static/ plus aufgezeichneten Antworten
vorschau_daten.py  zeichnet die Antworten eines laufenden Servers auf
modell.py          Modellerwartung aus einem NOVA-Export ableiten
liga_level.json    welche Liga auf welcher Stufe des Level Ratings steht
fragebogen.json    Level-Skala, Attribut-Sets je Position, Prognosen und
                   Schwellenwerte als Daten, nicht im Code
pakete/            Case Packs (VORLAGE.json, demo.json)
static/            Frontend: index.html, admin.html, app.js, stil.css
```

Level-Stufen, Attribut-Sets, Prognosen und alle Schwellenwerte lassen sich in
`fragebogen.json` tauschen, ohne Python anzufassen — dieselbe Idee wie
`kpi_varianten.json` im Framework nebenan. Stabil bleiben müssen die
`key`-Werte: wer einen key umbenennt, trennt bestehende Bewertungen von ihrer
Frage.

Die Attribut-Sets sind fachlich plausibel besetzt, aber **nicht die internen
Kern-Sets**. Sobald die echten 20 Attribute je Position vorliegen, gehören sie
unter `bewertung.kern` und `bewertung.positionen` — Code muss dafür nicht
angefasst werden.

## Betrieb

```bash
export SCOUTLEAGUE_ADMIN_TOKEN='…'      # ohne das bleibt /admin gesperrt
export SCOUTLEAGUE_DB=/pfad/scoutleague.db
python3 scoutleague/serve.py --port 8080
```

Oder im Container:

```bash
docker build -t scoutleague scoutleague/
docker run -p 8080:8080 -v scoutleague-daten:/data \
  -e SCOUTLEAGUE_ADMIN_TOKEN='…' scoutleague
```

Sichern heißt: die eine `.db`-Datei kopieren. Für zehn User reicht ein
beliebiger kleiner Server; TLS gehört davor, nicht hier hinein.

Prüfen: `python3 scoutleague/tests.py` — startet einen echten Server auf einer
Wegwerf-Datenbank und geht den kompletten Ablauf durch, von der Anmeldung über
24 Abgaben und 18 Auflösungen bis zum CSV, inklusive Kalibrier-Report, der
Modellableitung aus einem Export und dem Verhalten bei zu dünner Datenlage.

## Grenzen — bewusst offen ausgewiesen

- **Die Anmeldung ist ein geteilter Code, kein Account.** Kein Passwort, keine
  Sitzungsverwaltung, kein Rate-Limit. Ausreichend für einen internen Kreis
  hinter einem privaten Link; für Stufe 2 (Public & White-Label) muss echte
  Authentifizierung davor.
- **Das Modell ist keine Wahrheit.** Modell-Nähe misst Übereinstimmung, nicht
  Güte. Entschieden wird über den Brier-Score gegen die Realität — alles davor
  ist Zwischenstand.
- **Die Auflösung ist manuell.** Wer eine Prognose auflöst, trägt das Ergebnis
  von Hand ein und vermerkt die Quelle. Eine automatische Verknüpfung mit
  Transfer- und Marktwertdaten ist der nächste Ausbauschritt, nicht Teil des MVP.
- **Kalibrierungskennzahlen brauchen Fälle.** Spreizung und Trennschärfe werden
  ab drei bewerteten Fällen aussagekräftig, der Kalibrierungsfehler erst ab
  deutlich mehr aufgelösten Prognosen. Nach einem Pack sind das Indizien, keine
  Urteile. Der Report sagt das selbst, statt es den Zahlen zu überlassen.
- **Die Rangkorrelation je Position braucht mehrere Fälle je Gruppe.** Zehn
  Bewertungen zu einem einzigen Innenverteidiger ergeben keine Rangfolge — der
  Report weist dann „zu wenige Fälle" aus statt einer Zahl. Für die
  positionsweise Auswertung, die der Audit macht, braucht es Packs mit mehreren
  Spielern je Gruppe.
- **Die Attribut-Sets sind ein Vorschlag.** Sie folgen der Struktur, die der
  Audit fordert (Kern plus verpflichtendes Positions-Set, Anker an beiden
  Skalenenden), aber sie sind nicht aus den internen 20 Attributen abgeleitet —
  die lagen nicht vor.
- **Der Feldvergleich erscheint ab drei Abgaben** je Fall — darunter wäre der
  „Schnitt“ die Meinung von zwei Leuten mit Nachkommastelle.

## Rechtliche Leitplanken aus dem One-Pager

Im Code umgesetzt ist die erste; die übrigen sind Betriebs- und Rechtsfragen und
hier nur als Erinnerung vermerkt.

- **Datenlizenz:** Der Case Pack transportiert ausschließlich eigene,
  aggregierte Indizes. `pakete/VORLAGE.json` sagt das an der Stelle, an der die
  Versuchung entsteht.
- **Kein Glücksspiel:** Prognosen ohne Geldeinsatz, keine Auszahlung — die
  rechtliche Abgrenzung ist noch zu prüfen.
- **DSGVO auf beiden Seiten:** minderjährige Talente im Case Pack und junge User
  in der Liga. Vor Stufe 2 zu klären.
