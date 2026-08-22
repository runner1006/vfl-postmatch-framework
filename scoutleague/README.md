# Scout League — MVP (Stufe 0/1)

Prediction-Game auf echten Talenten. Scouts bewerten wöchentlich fünf Spieler
auf 1–5-Skalen und geben zu jedem drei Wahrscheinlichkeitsprognosen ab. Die
Bewertung wird **sofort** gegen das Modell gespiegelt, die Prognosen
**zeitversetzt** gegen die Realität. Jede aufgelöste Prognose ist ein
Outcome-Label.

Der MVP deckt Stufe 0 und Stufe 1 aus dem One-Pager ab: das interne
Kalibrierungs-Feature und die Closed Beta. Kein Infrastruktur-Invest — reine
Python-Standardbibliothek, eine SQLite-Datei, ein Prozess.

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

## Was gemessen wird

Zwei Blöcke, die bewusst getrennt bleiben statt zu einer Note zu verschmelzen —
dieselbe Logik wie im Post-Match-Framework nebenan.

**Sofort verfügbar** (der eigentliche Zweck von Stufe 0):

| Kennzahl | bedeutet |
|---|---|
| Spreizung | Streuung der Gesamteinschätzung über alle Fälle. Nahe 0 heißt: immer dieselbe Note, also keine Information. |
| Spreizungs-Index | dieselbe Zahl im Verhältnis zum Median des Felds. |
| Bias | Abstand zum Feldmittel — positiv heißt milder als das Feld. |
| Trennschärfe | Rangkorrelation der eigenen Note mit der Modellerwartung. |
| Modell-Nähe | 0–100 auf der Bewertungsskala. **Kein Gütemaß** — Abweichung mit Recht ist der Punkt der Übung. |

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
tests.py           71 Prüfungen: Metrik-Mathematik + End-to-End gegen echten Server
fragebogen.json    Fragen und Prognosen als Daten, nicht im Code
pakete/            Case Packs (VORLAGE.json, demo.json)
static/            Frontend: index.html, admin.html, app.js, stil.css
```

Fragen und Prognosen lassen sich in `fragebogen.json` tauschen, ohne Python
anzufassen — dieselbe Idee wie `kpi_varianten.json` im Framework nebenan.
Stabil bleiben müssen die `key`-Werte: wer einen key umbenennt, trennt
bestehende Bewertungen von ihrer Frage.

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
zwanzig Abgaben und fünfzehn Auflösungen bis zum CSV.

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
  Urteile.
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
