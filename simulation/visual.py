"""Bahnaufzeichnung als eigenstaendige HTML-Ansicht.

Eine einzelne Datei ohne externe Requests - dieselbe Regel wie beim Dashboard
des Analyseteils, und dieselbe Gestaltungssprache: helle Grundflaeche,
umschaltbares dunkles Thema, dieselben Farbtoken.

Gestaltungsentscheidungen, die nicht offensichtlich sind
--------------------------------------------------------
**Das Spielfeld ist nicht gruen.** Ein gesaettigtes Rasengruen kaempft mit
jeder Datenfarbe, die daraufgelegt wird - besonders mit der Raumkontrolle, die
genau dort als Flaeche erscheint. Die Spielflaeche ist deshalb eine
zurueckhaltende neutrale Flaeche mit angedeuteten Maehstreifen; die Farbe
gehoert den Mannschaften und den Daten.

**Zwei Mannschaftsfarben, nicht drei.** Blau und Orange der Hauspalette
bestehen alle sechs Palettenpruefungen in beiden Themen (schlechtestes
Paar Delta E 24.7 bei Protanopie). Ein dritter kategorialer Farbton faellt
durch - der lose Ball wird deshalb neutral dargestellt, nicht bunt.

**Zahlen tragen Textfarbe, nicht Mannschaftsfarbe.** Die Zugehoerigkeit
tragen die Balken und die Farbpunkte in der Kopfzeile. Werte in Serienfarbe
lesen sich bei zwei Mannschaften noch, bei jeder Erweiterung nicht mehr.

**Jede Einstellung steht auf ihrer Skala.** "Pressing 0.85" ist ohne Anker
bedeutungslos - niemand weiss, ob das viel ist. Die Parameterkarte zeigt
deshalb je Groesse die Spannweite mit beschrifteten Enden und beide
Mannschaften als Punkt darauf. Das kostet Platz und ist der Platz wert.

Der Weg zu synthetischem Videomaterial fuehrt ueber dieselben Daten: eine
Bahnaufzeichnung mit 25 Hz ist das, was ein Renderer als Eingabe braucht.
"""
import json

import konfig as K

# Spaltenbelegung der Statistikspur (siehe spiel.Spiel._aufzeichnen)
STAT_SPALTEN = [
    "tore_h", "tore_g", "xg_h", "xg_g", "schuesse_h", "schuesse_g",
    "box_h", "box_g", "drittel_h", "drittel_g", "hoehe_h", "hoehe_g",
    "ppda_h", "ppda_g", "paesse_h", "paesse_g", "an_h", "an_g",
    "besitz_h", "eintritte_h", "eintritte_g", "rueck_h", "rueck_g",
]

# Einstellbare Groessen mit ihrer Spannweite und beschrifteten Enden.
# Ohne diese Anker ist ein Zahlenwert kein Datenpunkt, sondern Rauschen.
PARAMETER = [
    ("abwehrhoehe", "Abwehrhöhe",
     "Wo die Abwehrkette steht, gemessen von der eigenen Torlinie",
     20.0, 50.0, " m", "tiefer Block", "hohe Kette"),
    ("pressing", "Pressingintensität",
     "Wie viele Spieler zum Ball herausrücken",
     0.0, 1.0, "", "abwarten", "Vollangriff"),
    ("pressing_ausloeser", "Pressing-Auslöser",
     "Ab welcher Ballentfernung überhaupt angelaufen wird",
     10.0, 36.0, " m", "erst spät", "sehr früh"),
    ("kompaktheit", "Kompaktheit",
     "Wie eng der Block in der Tiefe zusammensteht",
     0.0, 1.0, "", "weit", "eng"),
    ("breite", "Breite im Ballbesitz",
     "Wie konsequent die Flügel die Seitenlinie besetzen",
     18.0, 32.0, " m", "schmal", "breit"),
    ("tempo", "Tempo",
     "Wie stark vertikaler Raumgewinn gegenüber Sicherheit zählt",
     0.0, 1.0, "", "kontrolliert", "direkt"),
    ("risiko", "Risikobereitschaft",
     "Wie schwer ein möglicher Ballverlust in der Bewertung wiegt",
     0.0, 1.0, "", "sicher", "risikoreich"),
    ("gegenpressing", "Gegenpressing",
     "Nachsetzen in den ersten fünf Sekunden nach Ballverlust",
     0.0, 1.0, "", "fallen lassen", "sofort nachsetzen"),
    ("manndeckung", "Manndeckungsanteil",
     "Anteil Mann- statt Raumdeckung im eigenen Block",
     0.0, 1.0, "", "reine Raumdeckung", "reine Manndeckung"),
    ("aufruecken_aussen", "Außenverteidiger aufrücken",
     "Wie hoch die Außenverteidiger im Ballbesitz mitschieben",
     0.0, 1.0, "", "hinten bleiben", "hoch schieben"),
    ("lenken", "Nach außen lenken",
     "Anlaufwinkel des ersten Pressers",
     0.0, 1.0, "", "zentral stellen", "auf die Linie lenken"),
]

# Angezeigte Kennzahlen: Gruppe, Beschriftung, Klartext (sichtbar, nicht im
# Tooltip - auf Touch gibt es kein Hover), Spaltenindizes, Formatierung,
# und ob ein hoher Wert dem linken Team guenstig ist.
METRIKEN = [
    ("Ergebnis und Chancen", [
        ("Tore", "", 0, 1, "int", True),
        ("xG (erwartete Tore)",
         "Summe der Torwahrscheinlichkeiten aller Abschlüsse", 2, 3, "2f", True),
        ("Schüsse", "", 4, 5, "int", True),
        ("Kontakte im Strafraum",
         "Ballaktionen im gegnerischen Strafraum", 6, 7, "int", True),
        ("Strafraumeintritte",
         "wie oft der Ball in den gegnerischen Strafraum gelangt", 19, 20,
         "int", True),
    ]),
    ("Ballbesitz und Aufbau", [
        ("Ballbesitz", "Anteil der Zeit mit dem Ball am Fuß", -1, -1, "besitz",
         True),
        ("Pässe (angekommen)", "", 14, 15, "paesse", True),
        ("Pässe ins letzte Drittel",
         "angekommene Pässe von außerhalb in das vordere Felddrittel", 8, 9,
         "int", True),
    ]),
    ("Verteidigen", [
        ("Abwehrhöhe", "mittlerer Ort der Abwehrkette ab eigener Torlinie",
         10, 11, "m1", True),
        ("PPDA", "gegnerische Pässe je eigener Defensivaktion im vorderen "
         "Feld — niedriger heißt mehr Pressing", 12, 13, "2f", False),
        ("Rückeroberung binnen 5 s",
         "Anteil der Ballverluste, die sofort zurückgewonnen werden", 21, 22,
         "prozent", True),
    ]),
    ("Raum", [
        ("Raumkontrolle",
         "Feldanteil, den eine Mannschaft vor der anderen erreicht", -2, -2,
         "raum", True),
        ("davon gefährlicher Raum",
         "dieselbe Fläche, gewichtet mit ihrem Torwert", -3, -3, "gefahr",
         True),
    ]),
]

_VORLAGE = r"""<!doctype html>
<html lang="de">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITEL__</title>
<style>
:root{
  color-scheme: light;
  --plane:#f9f9f7; --surface:#fcfcfb;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834;
  --good:#0ca30c; --warning:#fab219; --critical:#d03b3b;
  --rasen:#ebeee6; --rasen-2:#e4e8de; --linie:#bcbcb1;
  --ball:#fcfcfb; --ballrand:#0b0b0b; --ballschatten:rgba(11,11,11,.20);
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    color-scheme: dark;
    --plane:#0d0d0d; --surface:#1a1a19;
    --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
    --s1:#3987e5; --s2:#d95926;
    --rasen:#16181a; --rasen-2:#1b1e21; --linie:#3d4147;
    --ball:#fff; --ballrand:#0d0d0d; --ballschatten:rgba(0,0,0,.55);
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --plane:#0d0d0d; --surface:#1a1a19;
  --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926;
  --rasen:#16181a; --rasen-2:#1b1e21; --linie:#3d4147;
  --ball:#fff; --ballrand:#0d0d0d; --ballschatten:rgba(0,0,0,.55);
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1460px;margin:0 auto;padding:26px 22px 72px}

header.top{display:flex;justify-content:space-between;align-items:flex-start;
  gap:20px;margin-bottom:20px;flex-wrap:wrap}
h1{font-size:22px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--ink-2);font-size:13.5px;margin:0;max-width:78ch}
.themebtn{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);
  border-radius:8px;padding:7px 13px;font:inherit;font-size:13px;cursor:pointer}
.themebtn:hover{color:var(--ink)}

.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:20px 22px;margin-bottom:18px}
.card > h2{font-size:15px;margin:0 0 3px;letter-spacing:-.005em}
.card > .note{color:var(--ink-2);font-size:13px;margin:0 0 16px;max-width:82ch}

/* ------------------------------------------------------------- Zweck */
.zweck{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);
  border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:18px}
@media(max-width:900px){.zweck{grid-template-columns:1fr}}
.zweck > div{background:var(--surface);padding:13px 16px 14px}
.zweck .k{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--muted);margin-bottom:6px;display:flex;align-items:center;gap:7px}
.zweck .k .marke{width:8px;height:8px;border-radius:2px;flex:none}
.zweck p{margin:0;font-size:13px;color:var(--ink-2);line-height:1.48}
.zweck p + p{margin-top:7px}
.zweck b{color:var(--ink);font-weight:600}

/* ------------------------------------------------------------ Buehne */
.buehne{display:grid;grid-template-columns:minmax(0,1fr) 372px;gap:18px;align-items:start}
@media(max-width:1180px){.buehne{grid-template-columns:1fr}}

.matchkopf{display:flex;align-items:center;gap:20px;flex-wrap:wrap;
  padding:2px 2px 14px;margin-bottom:12px;border-bottom:1px solid var(--border)}
.mteam{display:flex;align-items:center;gap:9px;min-width:0}
.mteam.rechts{flex-direction:row-reverse;text-align:right}
.mteam .marke{width:11px;height:11px;border-radius:3px;flex:none}
.mteam .nam{font-size:16px;font-weight:620;letter-spacing:-.01em}
.mteam .form{font-size:12px;color:var(--muted);margin-top:1px}
.stand{font-size:32px;font-weight:660;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;line-height:1.05}
.standbox{text-align:center;min-width:112px}
.standbox .uhr{font-size:12.5px;color:var(--ink-2);font-variant-numeric:tabular-nums;
  margin-top:2px}
.amball{margin-left:auto;display:inline-flex;align-items:center;gap:7px;
  border:1px solid var(--border);border-radius:999px;padding:5px 12px;
  font-size:12.5px;color:var(--ink-2);white-space:nowrap}
.amball .marke{width:9px;height:9px;border-radius:50%;flex:none;background:var(--muted)}

.feldkarte{background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:14px 16px 16px}
.feldinner{margin:0 auto;max-width:100%}
.feldbox{position:relative;width:100%}
canvas#feld{display:block;margin:0 auto;border-radius:8px;background:var(--rasen);
  max-width:100%}

/* ---------------------------------------------------------- Zeitleiste */
.zeitleiste{position:relative;margin:14px 0 4px;height:34px}
.spur{position:absolute;left:0;right:0;top:14px;height:6px;border-radius:3px;
  background:var(--grid)}
.fortschritt{position:absolute;left:0;top:14px;height:6px;border-radius:3px;
  background:var(--axis)}
.marke-e{position:absolute;top:10px;width:2px;height:14px;border-radius:1px;
  transform:translateX(-1px);cursor:pointer;opacity:.42}
.marke-e:hover{opacity:1;height:20px;top:7px}
.marke-e.tor{top:1px;height:32px;width:4px;opacity:1;border-radius:2px;
  transform:translateX(-2px);box-shadow:0 0 0 2px var(--surface)}
input[type=range]{position:absolute;left:0;right:0;top:8px;width:100%;margin:0;
  height:18px;background:transparent;-webkit-appearance:none;appearance:none;cursor:pointer}
input[type=range]::-webkit-slider-runnable-track{height:18px;background:transparent}
input[type=range]::-moz-range-track{height:18px;background:transparent}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:15px;height:15px;
  border-radius:50%;background:var(--ink);border:2px solid var(--surface);
  margin-top:1px;box-shadow:0 1px 3px rgba(0,0,0,.3)}
input[type=range]::-moz-range-thumb{width:15px;height:15px;border-radius:50%;
  background:var(--ink);border:2px solid var(--surface);box-shadow:0 1px 3px rgba(0,0,0,.3)}
input[type=range]:focus-visible{outline:2px solid var(--s1);outline-offset:3px}

.steuerung{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-top:4px}
.pbtn{border:1px solid var(--border);background:var(--surface);color:var(--ink);
  border-radius:8px;padding:7px 16px;font:inherit;font-size:13.5px;font-weight:550;
  cursor:pointer;min-width:104px}
.pbtn:hover{background:var(--plane)}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.seg button{border:0;border-right:1px solid var(--border);background:var(--surface);
  color:var(--ink-2);font:inherit;font-size:12.5px;padding:6px 11px;cursor:pointer}
.seg button:last-child{border-right:0}
.seg button[aria-pressed="true"]{background:var(--grid);color:var(--ink);font-weight:600}
.seg button:hover:not([aria-pressed="true"]){color:var(--ink)}
.tempoblock{display:inline-flex;align-items:center;gap:8px}
.feldlabel{font-size:11.5px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.05em;white-space:nowrap}
label.schalter{display:inline-flex;gap:7px;align-items:center;font-size:13px;
  color:var(--ink-2);cursor:pointer}
label.schalter input{accent-color:var(--s1);width:15px;height:15px}
.feldlegende{display:flex;gap:16px;flex-wrap:wrap;align-items:center;
  font-size:12px;color:var(--ink-2);margin-top:12px;padding-top:11px;
  border-top:1px solid var(--border)}
.feldlegende span{display:inline-flex;align-items:center;gap:6px}
.feldlegende i{flex:none;display:inline-block}
.feldlegende i.pkt{width:11px;height:11px;border-radius:50%}
.feldlegende i.ring{width:13px;height:13px;border-radius:50%;
  border:2px solid var(--ink-2)}
.feldlegende i.ball{width:9px;height:9px;border-radius:50%;
  background:var(--ball);border:1.5px solid var(--ballrand)}
.feldlegende .fl{color:var(--muted)}
.tastenhinweis{font-size:12px;color:var(--muted);margin-top:9px}
kbd{font:inherit;font-size:11.5px;border:1px solid var(--border);border-bottom-width:2px;
  border-radius:4px;padding:0 5px;color:var(--ink-2);background:var(--plane)}

/* ------------------------------------------------------------- Panel */
.panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:16px 18px 18px;position:sticky;top:18px;max-height:calc(100vh - 36px);
  overflow:auto}
@media(max-width:1180px){.panel{position:static;max-height:none}}
.panel h2{font-size:15px;margin:0 0 2px}
.panel .note{font-size:12.5px;color:var(--ink-2);margin:0 0 14px}
.beine{display:flex;justify-content:space-between;align-items:center;
  font-size:12px;color:var(--ink-2);padding-bottom:8px;margin-bottom:4px;
  border-bottom:1px solid var(--border);position:sticky;top:-16px;
  background:var(--surface);z-index:2}
.beine span{display:inline-flex;align-items:center;gap:6px;font-weight:600;color:var(--ink)}
.beine .marke{width:9px;height:9px;border-radius:2px;flex:none}

.gruppe{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
  color:var(--muted);margin:13px 0 1px;font-weight:600}
.gruppe:first-of-type{margin-top:10px}
.zeile{padding:5px 0 6px;border-bottom:1px solid var(--border)}
.zeile:last-child{border-bottom:0}
.zeile .oben{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.zeile .wert{font-size:15px;font-weight:620;font-variant-numeric:tabular-nums;
  letter-spacing:-.01em;min-width:58px}
.zeile .wert.r{text-align:right}
.zeile .nam{font-size:12.5px;color:var(--ink-2);text-align:center;flex:1;line-height:1.3}
.zeile .klartext{font-size:11px;color:var(--muted);line-height:1.35;margin-top:2px}
.balken{display:flex;gap:2px;height:6px;margin-top:6px}
.balken i{display:block;height:100%;border-radius:3px;min-width:2px}
.balken i.a{background:var(--s1)}
.balken i.b{background:var(--s2)}

/* ------------------------------------------------------------ Verlauf */
.verlaufbox{margin-top:16px;border-top:1px solid var(--border);padding-top:12px}
.verlaufkopf{display:flex;justify-content:space-between;align-items:baseline;
  font-size:12.5px;color:var(--ink-2);margin-bottom:6px}
canvas#verlauf{display:block;width:100%;height:74px}

/* ----------------------------------------------------------- Laufwerte */
details.lauf{margin-top:8px}
details.lauf summary{cursor:pointer;font-size:12.5px;color:var(--ink-2);
  padding:5px 0;list-style:none}
details.lauf summary::-webkit-details-marker{display:none}
details.lauf summary:before{content:"\25B8";display:inline-block;width:14px;
  color:var(--muted);transition:transform .15s}
details.lauf[open] summary:before{transform:rotate(90deg)}
table.spieler{border-collapse:collapse;width:100%;font-size:12px;
  font-variant-numeric:tabular-nums;margin-top:2px}
table.spieler th{color:var(--muted);font-weight:600;text-align:right;
  padding:3px 0 5px;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em}
table.spieler th.l,table.spieler td.l{text-align:left}
table.spieler td{padding:2px 0;border-top:1px solid var(--border)}
table.spieler tr.trenn td{border-top:2px solid var(--axis)}
table.spieler td.nr{color:var(--muted);width:24px}
table.spieler td.ro{color:var(--muted);width:36px}
table.spieler td .marke{width:7px;height:7px;border-radius:2px;display:inline-block;
  margin-right:6px;vertical-align:1px}

/* --------------------------------------------------------- Parameter */
.parameter{display:grid;grid-template-columns:1fr 1fr;gap:2px 34px}
@media(max-width:980px){.parameter{grid-template-columns:1fr}}
.prow{padding:9px 0;border-bottom:1px solid var(--border)}
.pkopf{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.pname{font-size:13.5px;font-weight:560}
.pwerte{font-size:13px;font-variant-numeric:tabular-nums;color:var(--ink);
  white-space:nowrap;display:flex;gap:12px}
.pwerte span{display:inline-flex;align-items:center;gap:5px}
.pwerte .marke{width:8px;height:8px;border-radius:2px;flex:none}
.pklartext{font-size:11.5px;color:var(--muted);margin-top:2px;line-height:1.4}
.skala{position:relative;height:22px;margin-top:7px}
.skala .achse{position:absolute;left:0;right:0;top:7px;height:4px;border-radius:2px;
  background:var(--grid)}
.skala .pkt{position:absolute;top:2px;width:14px;height:14px;border-radius:50%;
  transform:translateX(-7px);border:2px solid var(--surface);
  box-shadow:0 1px 2px rgba(0,0,0,.2)}
.skala .anker{position:absolute;top:14px;font-size:11px;color:var(--muted);
  white-space:nowrap}
.skala .anker.re{right:0}
.pfuss{grid-column:1/-1;font-size:12.5px;color:var(--ink-2);margin-top:14px;
  padding-top:14px;border-top:1px solid var(--border);max-width:88ch}
.pfuss code{font-size:12px;background:var(--plane);border:1px solid var(--border);
  border-radius:4px;padding:1px 5px}

/* -------------------------------------------------------- Ereignisse */
.ereigbox{max-height:330px;overflow:auto;border:1px solid var(--border);
  border-radius:9px}
table.ereig{border-collapse:collapse;width:100%;font-size:13px}
table.ereig th{position:sticky;top:0;background:var(--surface);z-index:1}
table.ereig th,table.ereig td{padding-left:14px}
table.ereig td.wert{text-align:right;font-variant-numeric:tabular-nums;
  padding-right:16px;color:var(--ink-2)}
table.ereig th.wert{text-align:right;padding-right:16px}
table.ereig th,table.ereig td{text-align:left;padding:5px 16px 5px 0;
  border-bottom:1px solid var(--border)}
table.ereig th{color:var(--muted);font-weight:600;font-size:10.5px;
  text-transform:uppercase;letter-spacing:.05em}
table.ereig td.zeit{font-variant-numeric:tabular-nums;width:64px}
table.ereig a{color:var(--ink);text-decoration:none;border-bottom:1px dotted var(--axis)}
table.ereig a:hover{border-bottom-style:solid}
table.ereig td .marke{width:8px;height:8px;border-radius:2px;display:inline-block;
  margin-right:7px;vertical-align:0}
.art{font-weight:560}
.grenze{font-size:12.5px;color:var(--ink-2);max-width:88ch;line-height:1.55}
.grenze b{color:var(--ink)}
</style>

<body data-palette="__PALETTE__">
<div class="wrap">

<header class="top">
  <div>
    <h1>__H1__</h1>
    <p class="sub">__SUB__</p>
  </div>
  <button class="themebtn" id="themebtn" type="button">Dunkel / Hell</button>
</header>

<div class="zweck">
  <div>
    <div class="k"><span class="marke" style="background:var(--s1)"></span>Was hier läuft</div>
    <p>22 Spieler als <b>physische und taktische Agenten</b>, ein Ball mit
       eigener Flugphysik, 25 Bilder je Sekunde. Jeder Wert rechts ist ein
       <b>gezähltes Ereignis</b> aus dieser Entwicklung — keine im Hintergrund
       gezogene Wahrscheinlichkeit.</p>
  </div>
  <div>
    <div class="k"><span class="marke" style="background:var(--s2)"></span>Wofür die Ansicht taugt</div>
    <p>Zu sehen, <b>wie</b> ein Ergebnis zustande kommt: welche Räume entstehen,
       wo die Kette steht, wann der Block reißt. Und um zwei Läufe zu
       vergleichen, in denen genau eine Sache anders eingestellt war — die
       Parameter dazu stehen unten.</p>
  </div>
  <div>
    <div class="k"><span class="marke" style="background:var(--axis)"></span>Wofür nicht</div>
    <p>Für die Vorhersage eines konkreten Spiels und für <b>absolute</b> Schuss-
       und Torzahlen. Die liegen im Modell noch deutlich über realen Werten.
       Belastbar sind Vergleiche zwischen Läufen, nicht die Zahl an sich.</p>
  </div>
</div>

<div class="buehne">
  <div>
    <div class="feldkarte">
     <div class="feldinner">
      <div class="matchkopf">
        <div class="mteam">
          <span class="marke" style="background:var(--s1)"></span>
          <div><div class="nam">__HEIM__</div><div class="form">__HEIM_FORM__</div></div>
        </div>
        <div class="standbox">
          <div class="stand" id="stand">0 : 0</div>
          <div class="uhr" id="uhr">0:00</div>
        </div>
        <div class="mteam rechts">
          <span class="marke" style="background:var(--s2)"></span>
          <div><div class="nam">__GAST__</div><div class="form">__GAST_FORM__</div></div>
        </div>
        <div class="amball"><span class="marke" id="ballmarke"></span>
          <span id="balltext">Ball frei</span></div>
      </div>
      <div class="feldbox"><canvas id="feld"></canvas></div>

      <div class="zeitleiste">
        <div class="spur"></div>
        <div class="fortschritt" id="fortschritt"></div>
        <div id="marken"></div>
        <input type="range" id="zeit" min="0" max="0" value="0" step="1"
               aria-label="Spielzeit">
      </div>

      <div class="steuerung">
        <button class="pbtn" id="play" type="button">Abspielen</button>
        <div class="tempoblock">
          <span class="feldlabel">Tempo</span>
          <span class="seg" id="tempo" role="group" aria-label="Abspieltempo">
            <button type="button" data-v="0.5">0,5×</button>
            <button type="button" data-v="1" aria-pressed="true">1×</button>
            <button type="button" data-v="2">2×</button>
            <button type="button" data-v="4">4×</button>
            <button type="button" data-v="8">8×</button>
          </span>
        </div>
        <label class="schalter"><input type="checkbox" id="kontrolle">
          Raumkontrolle als Fläche</label>
        <label class="schalter"><input type="checkbox" id="spuren" checked>
          Laufspuren</label>
      </div>
      <div class="feldlegende">
        <span><i class="pkt" style="background:var(--s1)"></i>__HEIM__</span>
        <span><i class="pkt" style="background:var(--s2)"></i>__GAST__</span>
        <span><i class="ring"></i>Ballführender</span>
        <span><i class="ball"></i>Ball, gehoben mit Schatten</span>
        <span class="fl">Eingefärbte Fläche: wer diesen Ort vor dem Gegner
          erreichen würde</span>
      </div>
      <div class="tastenhinweis">
        <kbd>Leertaste</kbd> abspielen und anhalten ·
        <kbd>&larr;</kbd> <kbd>&rarr;</kbd> Bild für Bild ·
        <kbd>&#8679;</kbd> dazu zehn Bilder auf einmal
      </div>
     </div>
    </div>
  </div>

  <div class="panel">
    <h2>Stand zum Zeitpunkt</h2>
    <p class="note">Nicht der Endstand — alle Werte gelten für die angezeigte
      Spielminute und laufen mit dem Zeitstrahl mit.</p>
    <div class="beine">
      <span><span class="marke" style="background:var(--s1)"></span>__HEIM__</span>
      <span>__GAST__<span class="marke" style="background:var(--s2)"></span></span>
    </div>
    <div id="metriken"></div>

    <div class="verlaufbox">
      <div class="verlaufkopf">
        <span>xG im Verlauf</span>
        <span id="verlaufwerte"></span>
      </div>
      <canvas id="verlauf"></canvas>
    </div>

    <div class="verlaufbox">
      <div class="gruppe" style="margin-top:0">Laufdistanz</div>
      <div id="laufen"></div>
      <details class="lauf"><summary>Einzelne Spieler anzeigen</summary>
        <table class="spieler" id="spielertabelle"></table>
      </details>
    </div>
  </div>
</div>

<div class="card">
  <h2>Einstellungen dieses Laufs</h2>
  <p class="note">Das ist die <b>Eingabe</b> der Simulation, nicht ihr Ergebnis.
    Jede Größe steht auf ihrer Spannweite, damit ein Zahlenwert ohne Vorwissen
    einzuordnen ist.</p>
  <div class="parameter" id="parameter"></div>
</div>

<div class="card">
  <h2>Ereignisse</h2>
  <p class="note" id="ereignisnote">Anklicken springt an die Stelle im Spiel.</p>
  <div class="ereigbox"><table class="ereig" id="ereignisse"></table></div>
</div>

<div class="card">
  <h2>Was diese Ansicht nicht hergibt</h2>
  <p class="grenze">__GRENZEN__</p>
</div>

</div>

<script>
const DATEN = __DATEN__;
const F = __FELD__;
const N = DATEN.bahn.length;

/* ------------------------------------------------------- Themafarben */
const T = {};
function themaLesen(){
  const cs = getComputedStyle(document.documentElement);
  for (const k of ['s1','s2','ink','ink-2','muted','grid','axis','surface',
                   'rasen','rasen-2','linie','ballschatten','border',
                   'ball','ballrand'])
    T[k] = cs.getPropertyValue('--' + k).trim();
}
themaLesen();
document.getElementById('themebtn').onclick = () => {
  const dunkel = document.documentElement.getAttribute('data-theme') === 'dark'
    || (!document.documentElement.getAttribute('data-theme')
        && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme', dunkel ? 'light' : 'dark');
  themaLesen(); zeichne();
};

/* ---------------------------------------------------------- Spielfeld */
const cv = document.getElementById('feld'), ctx = cv.getContext('2d');
let W = 900, H = 583;
function groesse(){
  const b = cv.parentElement.parentElement.parentElement.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  W = Math.max(320, Math.round(b.width));
  H = Math.round(W * F.B / F.L);
  // Deckel auf die Bildschirmhoehe: sonst schiebt ein breiter Monitor die
  // Bedienleiste unter den sichtbaren Bereich, und man scrollt bei jedem
  // Sprung in der Zeit hin und her.
  const maxH = Math.max(280, window.innerHeight - 430);
  if (H > maxH){ H = Math.round(maxH); W = Math.round(H * F.L / F.B); }
  cv.style.width = W + 'px'; cv.style.height = H + 'px';
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // Zeitleiste, Bedienung und Legende auf dieselbe Breite wie das Feld -
  // sonst schwimmt der Zeitstrahl neben dem Bild, auf das er sich bezieht.
  document.querySelector('.feldinner').style.width = W + 'px';
}
const RAND = () => Math.max(14, W * 0.022);
const sx = v => RAND() + (v + F.L / 2) / F.L * (W - 2 * RAND());
const sy = v => RAND() + (v + F.B / 2) / F.B * (H - 2 * RAND());
const sl = v => v / F.L * (W - 2 * RAND());
const sh = v => v / F.B * (H - 2 * RAND());

function feld(){
  ctx.fillStyle = T['rasen']; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = T['rasen-2'];
  for (let i = 0; i < 10; i += 2){
    const x0 = sx(-F.L/2 + i*F.L/10), x1 = sx(-F.L/2 + (i+1)*F.L/10);
    ctx.fillRect(x0, sy(-F.B/2), x1 - x0, sh(F.B));
  }
  ctx.strokeStyle = T['linie']; ctx.lineWidth = 1.4;
  ctx.strokeRect(sx(-F.L/2), sy(-F.B/2), sl(F.L), sh(F.B));
  ctx.beginPath(); ctx.moveTo(sx(0), sy(-F.B/2)); ctx.lineTo(sx(0), sy(F.B/2)); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx(0), sy(0), sl(F.KREIS), 0, 7); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx(0), sy(0), 2.2, 0, 7); ctx.fillStyle = T['linie']; ctx.fill();
  for (const s of [-1, 1]){
    ctx.strokeRect(s < 0 ? sx(-F.L/2) : sx(F.L/2 - F.SR_T), sy(-F.SR_B),
                   sl(F.SR_T), sh(2*F.SR_B));
    ctx.strokeRect(s < 0 ? sx(-F.L/2) : sx(F.L/2 - F.TR_T), sy(-F.TR_B),
                   sl(F.TR_T), sh(2*F.TR_B));
    ctx.lineWidth = 3.2; ctx.beginPath();
    ctx.moveTo(sx(s*F.L/2), sy(-F.TOR)); ctx.lineTo(sx(s*F.L/2), sy(F.TOR));
    ctx.stroke(); ctx.lineWidth = 1.4;
  }
}

/* Ankunftszeit wie spieler.zeit_zu_punkt - Zweiphasenmodell mit Reaktion. */
function tZu(px, py, zx, zy){
  const d = Math.hypot(zx - px, zy - py);
  let t = 0.22; if (d < 1e-6) return t;
  const vmax = 8.4, a = 10.0, dA = vmax*vmax/(2*a);
  t += d <= dA ? Math.sqrt(2*d/a) : vmax/a + (d - dA)/vmax;
  return t;
}
/* Gefahrenflaeche wie raumkontrolle.gefahr. */
function gefahr(x, y, dir){
  const d = Math.hypot(dir*F.L/2 - x, y);
  const q = y/22;
  return (0.52*Math.exp(-d/7.5) + 0.030*Math.exp(-d/28)) * (0.45 + 0.55*Math.exp(-q*q));
}

function raum(f, NX, NY, malen){
  let flH = 0, flG = 0, gefH = 0, gefG = 0;
  const zelle = (F.L/NX) * (F.B/NY);
  for (let j = 0; j < NY; j++){
    const y = -F.B/2 + (j + 0.5)*F.B/NY;
    for (let i = 0; i < NX; i++){
      const x = -F.L/2 + (i + 0.5)*F.L/NX;
      let th = 1e9, tg = 1e9;
      for (let k = 0; k < 22; k++){
        const t = tZu(f[1 + k*2], f[2 + k*2], x, y);
        if (k < 11){ if (t < th) th = t; } else { if (t < tg) tg = t; }
      }
      const p = 1/(1 + Math.exp(-(tg - th)/0.42));
      flH += p*zelle; flG += (1 - p)*zelle;
      gefH += p*zelle*gefahr(x, y, DATEN.richtung_heim);
      gefG += (1 - p)*zelle*gefahr(x, y, -DATEN.richtung_heim);
      if (malen){
        const a = Math.abs(p - 0.5)*1.15;
        ctx.globalAlpha = Math.min(a, .5);
        ctx.fillStyle = p > 0.5 ? T['s1'] : T['s2'];
        ctx.fillRect(sx(x - F.L/NX/2), sy(y - F.B/NY/2), sl(F.L/NX) + 1, sh(F.B/NY) + 1);
        ctx.globalAlpha = 1;
      }
    }
  }
  return {flH, flG, gefH, gefG};
}

/* ============================================================ Zeichnen */
let i = 0, laeuft = false, letzte = 0, tempoWert = 1;
const schieber = document.getElementById('zeit');
schieber.max = N - 1;

function zeichne(){
  const f = DATEN.bahn[i];
  feld();
  const malen = document.getElementById('kontrolle').checked;
  const kk = raum(f, malen ? 36 : 24, malen ? 23 : 15, malen);

  if (document.getElementById('spuren').checked){
    // Segmentweise zeichnen, damit die Spur nach hinten ausblendet - eine
    // gleichmaessig deckende Spur liest sich wie ein zweiter Spieler.
    const LAENGE = 10;
    ctx.lineWidth = 1.6; ctx.lineCap = 'round';
    for (let k = 0; k < 22; k++){
      ctx.strokeStyle = k < 11 ? T['s1'] : T['s2'];
      const von = Math.max(0, i - LAENGE);
      for (let j = von; j < i; j++){
        const g = DATEN.bahn[j], g2 = DATEN.bahn[j + 1];
        ctx.globalAlpha = 0.10 + 0.42 * (j - von) / LAENGE;
        ctx.beginPath();
        ctx.moveTo(sx(g[1 + k*2]), sy(g[2 + k*2]));
        ctx.lineTo(sx(g2[1 + k*2]), sy(g2[2 + k*2]));
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  const besitz = f[48];
  const bx = f[45], by = f[46], bz = f[47];
  let traeger = -1, bd = 4.0;
  if (besitz >= 0){
    for (let k = besitz*11; k < besitz*11 + 11; k++){
      const d = Math.hypot(f[1 + k*2] - bx, f[2 + k*2] - by);
      if (d < bd){ bd = d; traeger = k; }
    }
  }
  const r = Math.max(7, W/118);
  for (let k = 0; k < 22; k++){
    const x = sx(f[1 + k*2]), y = sy(f[2 + k*2]);
    if (k === traeger){
      ctx.beginPath(); ctx.arc(x, y, r + 4.5, 0, 7);
      ctx.strokeStyle = k < 11 ? T['s1'] : T['s2']; ctx.lineWidth = 2; ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(x, y, r, 0, 7);
    ctx.fillStyle = k < 11 ? T['s1'] : T['s2']; ctx.fill();
    ctx.strokeStyle = T['surface']; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '600 ' + Math.round(r*1.1) + 'px system-ui,sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(DATEN.nummern[k], x, y + .5);
  }
  const px = sx(bx), py = sy(by);
  if (bz > 0.3){
    ctx.beginPath(); ctx.ellipse(px, py, r*.55, r*.28, 0, 0, 7);
    ctx.fillStyle = T['ballschatten']; ctx.fill();
  }
  // Der Ball darf nicht wie ein Spieler aussehen: deutlich kleiner, mit Ring.
  ctx.beginPath();
  ctx.arc(px, py - Math.min(bz, 6)*3.0, r*.45 + Math.min(bz, 6)*.35, 0, 7);
  ctx.fillStyle = T['ball']; ctx.fill();
  ctx.strokeStyle = T['ballrand']; ctx.lineWidth = 1.6; ctx.stroke();

  aktualisieren(i, kk);
  schieber.value = i;
  document.getElementById('fortschritt').style.width =
    (N < 2 ? 0 : i/(N - 1)*100).toFixed(2) + '%';
}

/* ================================================================ Panel */
const uhrText = t => Math.floor(t/60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');
const knoten = {};

function metrikenAufbauen(){
  let h = '';
  for (const [gruppe, zeilen] of DATEN.metriken){
    h += '<div class="gruppe">' + gruppe + '</div>';
    for (const z of zeilen){
      const id = z.id;
      h += '<div class="zeile"><div class="oben">' +
           '<span class="wert" id="' + id + '_a">–</span>' +
           '<span class="nam">' + z.name + '</span>' +
           '<span class="wert r" id="' + id + '_b">–</span></div>' +
           (z.klartext ? '<div class="klartext">' + z.klartext + '</div>' : '') +
           '<div class="balken"><i class="a" id="' + id + '_ba"></i>' +
           '<i class="b" id="' + id + '_bb"></i></div></div>';
    }
  }
  document.getElementById('metriken').innerHTML = h;
  for (const [, zeilen] of DATEN.metriken)
    for (const z of zeilen)
      for (const s of ['_a', '_b', '_ba', '_bb'])
        knoten[z.id + s] = document.getElementById(z.id + s);
}

function laufAufbauen(){
  document.getElementById('laufen').innerHTML =
    '<div class="zeile"><div class="oben">' +
    '<span class="wert" id="lauf_a">–</span><span class="nam">Gesamt (km)</span>' +
    '<span class="wert r" id="lauf_b">–</span></div>' +
    '<div class="balken"><i class="a" id="lauf_ba"></i><i class="b" id="lauf_bb"></i></div></div>' +
    '<div class="zeile"><div class="oben">' +
    '<span class="wert" id="min_a">–</span>' +
    '<span class="nam">je Spieler und Minute (m)</span>' +
    '<span class="wert r" id="min_b">–</span></div></div>';
  let h = '<tr><th class="l">Nr</th><th class="l">Rolle</th><th class="l">Name</th>' +
          '<th>km</th><th>m/min</th></tr>';
  for (let k = 0; k < 22; k++){
    h += '<tr' + (k === 11 ? ' class="trenn"' : '') + '>' +
         '<td class="nr l">' + DATEN.nummern[k] + '</td>' +
         '<td class="ro l">' + DATEN.rollen[k] + '</td>' +
         '<td class="l"><span class="marke" style="background:var(--' +
         (k < 11 ? 's1' : 's2') + ')"></span>' + DATEN.spielernamen[k] + '</td>' +
         '<td id="sp' + k + '_km">–</td><td id="sp' + k + '_min">–</td></tr>';
  }
  document.getElementById('spielertabelle').innerHTML = h;
  for (const id of ['lauf_a','lauf_b','lauf_ba','lauf_bb','min_a','min_b'])
    knoten[id] = document.getElementById(id);
  for (let k = 0; k < 22; k++){
    knoten['sp' + k + '_km'] = document.getElementById('sp' + k + '_km');
    knoten['sp' + k + '_min'] = document.getElementById('sp' + k + '_min');
  }
}

function formatiere(art, a, b, s, kk){
  const q = (an, ges) => ges > 0 ? Math.round(an/ges*100) + ' %' : '–';
  switch (art){
    case 'int':     return [String(a), String(b), a, b];
    case '2f':      return [a.toFixed(2), b.toFixed(2), a, b];
    case 'm1':      return [a.toFixed(1) + ' m', b.toFixed(1) + ' m', a, b];
    case 'prozent': return [Math.round(a*100) + ' %', Math.round(b*100) + ' %', a, b];
    case 'besitz':  return [Math.round(s[18]*100) + ' %',
                            Math.round((1 - s[18])*100) + ' %', s[18], 1 - s[18]];
    case 'paesse':  return [s[14] + ' (' + q(s[16], s[14]) + ')',
                            s[15] + ' (' + q(s[17], s[15]) + ')', s[14], s[15]];
    case 'raum':    return [Math.round(kk.flH/(kk.flH + kk.flG)*100) + ' %',
                            Math.round(kk.flG/(kk.flH + kk.flG)*100) + ' %',
                            kk.flH, kk.flG];
    case 'gefahr':  return [kk.gefH.toFixed(1), kk.gefG.toFixed(1), kk.gefH, kk.gefG];
  }
  return ['–', '–', 0, 0];
}

function aktualisieren(idx, kk){
  const s = DATEN.stat[idx], t = DATEN.bahn[idx][0];
  document.getElementById('stand').textContent = s[0] + ' : ' + s[1];
  document.getElementById('uhr').textContent = uhrText(t) + ' Min.';

  const besitz = DATEN.bahn[idx][48];
  const bm = document.getElementById('ballmarke');
  bm.style.background = besitz === 0 ? 'var(--s1)' : besitz === 1 ? 'var(--s2)' : 'var(--muted)';
  document.getElementById('balltext').textContent =
    besitz < 0 ? 'Ball frei' : DATEN.namen[besitz] + ' am Ball';

  for (const [, zeilen] of DATEN.metriken){
    for (const z of zeilen){
      const [ta, tb, va, vb] = formatiere(z.art, z.ia >= 0 ? s[z.ia] : 0,
                                          z.ib >= 0 ? s[z.ib] : 0, s, kk);
      knoten[z.id + '_a'].textContent = ta;
      knoten[z.id + '_b'].textContent = tb;
      const summe = va + vb;
      const p = summe <= 0 ? 50 : va/summe*100;
      knoten[z.id + '_ba'].style.width = (z.hochGut ? p : 100 - p).toFixed(1) + '%';
      knoten[z.id + '_bb'].style.width = (z.hochGut ? 100 - p : p).toFixed(1) + '%';
    }
  }

  const d = DATEN.dist[idx], min = Math.max(t/60, 1/60);
  let sumH = 0, sumG = 0;
  for (let k = 0; k < 11; k++) sumH += d[k];
  for (let k = 11; k < 22; k++) sumG += d[k];
  knoten['lauf_a'].textContent = (sumH/1000).toFixed(2);
  knoten['lauf_b'].textContent = (sumG/1000).toFixed(2);
  const ps = sumH + sumG <= 0 ? 50 : sumH/(sumH + sumG)*100;
  knoten['lauf_ba'].style.width = ps.toFixed(1) + '%';
  knoten['lauf_bb'].style.width = (100 - ps).toFixed(1) + '%';
  knoten['min_a'].textContent = Math.round(sumH/11/min);
  knoten['min_b'].textContent = Math.round(sumG/11/min);
  for (let k = 0; k < 22; k++){
    knoten['sp' + k + '_km'].textContent = (d[k]/1000).toFixed(2);
    knoten['sp' + k + '_min'].textContent = Math.round(d[k]/min);
  }
  verlauf(idx);
}

/* ------------------------------------------------------------- Verlauf */
const vcv = document.getElementById('verlauf'), vctx = vcv.getContext('2d');
function verlauf(idx){
  const b = vcv.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(120, Math.round(b.width)), h = 74;
  if (vcv.width !== Math.round(w*dpr)){
    vcv.width = Math.round(w*dpr); vcv.height = Math.round(h*dpr);
  }
  vctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  vctx.clearRect(0, 0, w, h);
  const letzteS = DATEN.stat[N - 1];
  const max = Math.max(0.35, letzteS[2], letzteS[3]);
  const px = j => j/(N - 1 || 1)*(w - 2) + 1;
  const py = v => h - 3 - v/max*(h - 12);

  vctx.strokeStyle = T['grid']; vctx.lineWidth = 1;
  vctx.beginPath(); vctx.moveTo(0, py(0) + .5); vctx.lineTo(w, py(0) + .5); vctx.stroke();

  for (const [spalte, farbe] of [[2, T['s1']], [3, T['s2']]]){
    vctx.strokeStyle = farbe; vctx.lineWidth = 2;
    vctx.lineJoin = 'round'; vctx.beginPath();
    const schritt = Math.max(1, Math.floor(N/420));
    for (let j = 0; j < N; j += schritt){
      const x = px(j), y = py(DATEN.stat[j][spalte]);
      j === 0 ? vctx.moveTo(x, y) : vctx.lineTo(x, y);
    }
    vctx.stroke();
  }
  vctx.strokeStyle = T['ink-2']; vctx.lineWidth = 1;
  vctx.beginPath(); vctx.moveTo(px(idx) + .5, 2); vctx.lineTo(px(idx) + .5, h - 2); vctx.stroke();
  for (const [spalte, farbe] of [[2, T['s1']], [3, T['s2']]]){
    vctx.beginPath(); vctx.arc(px(idx), py(DATEN.stat[idx][spalte]), 3.2, 0, 7);
    vctx.fillStyle = farbe; vctx.fill();
    vctx.strokeStyle = T['surface']; vctx.lineWidth = 1.6; vctx.stroke();
  }
  const s = DATEN.stat[idx];
  document.getElementById('verlaufwerte').innerHTML =
    '<span style="font-variant-numeric:tabular-nums">' + s[2].toFixed(2) +
    ' &nbsp;·&nbsp; ' + s[3].toFixed(2) + '</span>';
}

/* ------------------------------------------------------ Zeitleistenmarken */
function markenAufbauen(){
  const box = document.getElementById('marken');
  const t0 = DATEN.bahn[0][0], t1 = DATEN.bahn[N - 1][0];
  let h = '';
  for (const e of DATEN.ereignisse){
    const p = (e.zeit - t0)/Math.max(t1 - t0, 1e-6);
    if (p < 0 || p > 1) continue;
    const farbe = e.team === 0 ? 'var(--s1)' : e.team === 1 ? 'var(--s2)' : 'var(--muted)';
    h += '<div class="marke-e' + (e.art === 'tor' ? ' tor' : '') + '" ' +
         'style="left:' + (p*100).toFixed(3) + '%;background:' + farbe + '" ' +
         'data-t="' + e.zeit + '" title="' + uhrText(e.zeit) + ' ' + e.art + '"></div>';
  }
  box.innerHTML = h;
  box.querySelectorAll('.marke-e').forEach(m => m.onclick = () => springe(+m.dataset.t));
}
function springe(zeit){
  const t0 = DATEN.bahn[0][0];
  i = Math.max(0, Math.min(N - 1, Math.round((zeit - t0)/DATEN.schritt) - 6));
  zeichne();
}

/* ------------------------------------------------------------ Parameter */
function parameterAufbauen(){
  let h = '';
  for (const p of DATEN.parameter){
    if (p.art === 'text'){
      h += '<div class="prow"><div class="pkopf"><span class="pname">' + p.name +
           '</span><span class="pwerte">' +
           '<span><span class="marke" style="background:var(--s1)"></span>' + p.a + '</span>' +
           '<span><span class="marke" style="background:var(--s2)"></span>' + p.b + '</span>' +
           '</span></div>' +
           (p.klartext ? '<div class="pklartext">' + p.klartext + '</div>' : '') + '</div>';
      continue;
    }
    const pa = (p.a - p.min)/(p.max - p.min)*100;
    const pb = (p.b - p.min)/(p.max - p.min)*100;
    h += '<div class="prow"><div class="pkopf"><span class="pname">' + p.name +
         '</span><span class="pwerte">' +
         '<span><span class="marke" style="background:var(--s1)"></span>' + p.at + '</span>' +
         '<span><span class="marke" style="background:var(--s2)"></span>' + p.bt + '</span>' +
         '</span></div>' +
         '<div class="pklartext">' + p.klartext + '</div>' +
         '<div class="skala"><div class="achse"></div>' +
         '<div class="pkt" style="left:' + pa.toFixed(1) + '%;background:var(--s1)"></div>' +
         '<div class="pkt" style="left:' + pb.toFixed(1) + '%;background:var(--s2)"></div>' +
         '<div class="anker">' + p.ankerMin + '</div>' +
         '<div class="anker re">' + p.ankerMax + '</div></div></div>';
  }
  h += '<div class="pfuss">' + DATEN.parameterFuss + '</div>';
  document.getElementById('parameter').innerHTML = h;
}

/* ----------------------------------------------------------- Ereignisse */
function ereignisseAufbauen(){
  const tab = document.getElementById('ereignisse');
  if (!DATEN.ereignisse.length){
    tab.parentElement.style.display = 'none'; return;
  }
  let h = '<tr><th>Zeit</th><th>Ereignis</th><th>Mannschaft</th><th>Spieler</th>' +
          '<th class="wert">xG</th></tr>';
  for (const e of DATEN.ereignisse){
    const farbe = e.team === 0 ? 's1' : 's2';
    h += '<tr><td class="zeit"><a href="#" data-t="' + e.zeit + '">' +
         uhrText(e.zeit) + '</a></td><td class="art">' + e.art + '</td>' +
         '<td>' + (e.team === null ? '' :
           '<span class="marke" style="background:var(--' + farbe + ')"></span>' +
           DATEN.namen[e.team]) + '</td>' +
         '<td>' + (e.spieler || '') + '</td>' +
         '<td class="wert">' + (e.art === 'schuss' && e.wert !== null
           ? e.wert.toFixed(2) : '') + '</td></tr>';
  }
  tab.innerHTML = h;
  document.getElementById('ereignisnote').textContent =
    DATEN.ereignisse.length + ' Ereignisse — Anklicken springt an die Stelle im Spiel.';
  tab.querySelectorAll('a').forEach(a => a.onclick = ev => {
    ev.preventDefault(); springe(+a.dataset.t);
  });
}

/* ------------------------------------------------------------ Steuerung */
function takt(ms){
  if (laeuft && ms - letzte > DATEN.schritt*1000/tempoWert){
    letzte = ms; i = (i + 1) % N; zeichne();
  }
  requestAnimationFrame(takt);
}
const playBtn = document.getElementById('play');
function umschalten(){
  laeuft = !laeuft;
  playBtn.textContent = laeuft ? 'Anhalten' : 'Abspielen';
}
playBtn.onclick = umschalten;
schieber.oninput = e => { i = +e.target.value; zeichne(); };
document.getElementById('kontrolle').onchange = zeichne;
document.getElementById('spuren').onchange = zeichne;
document.getElementById('tempo').onclick = e => {
  const b = e.target.closest('button'); if (!b) return;
  tempoWert = parseFloat(b.dataset.v);
  for (const x of e.currentTarget.children)
    x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
};
addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' && e.target.type !== 'range') return;
  if (e.code === 'Space'){ e.preventDefault(); umschalten(); }
  else if (e.key === 'ArrowRight'){ e.preventDefault();
    i = Math.min(N - 1, i + (e.shiftKey ? 10 : 1)); zeichne(); }
  else if (e.key === 'ArrowLeft'){ e.preventDefault();
    i = Math.max(0, i - (e.shiftKey ? 10 : 1)); zeichne(); }
});
let neuzeichnen;
addEventListener('resize', () => {
  clearTimeout(neuzeichnen);
  neuzeichnen = setTimeout(() => { groesse(); zeichne(); }, 120);
});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  themaLesen(); zeichne();
});

metrikenAufbauen(); laufAufbauen(); parameterAufbauen();
ereignisseAufbauen(); markenAufbauen();
groesse(); zeichne(); requestAnimationFrame(takt);
</script>
"""


def _metriken_daten():
    """Kennzahlenliste in die Form, die die Anzeige braucht."""
    gruppen = []
    nr = 0
    for gruppe, zeilen in METRIKEN:
        aus = []
        for name, klartext, ia, ib, art, hoch_gut in zeilen:
            nr += 1
            aus.append({"id": "m%d" % nr, "name": name, "klartext": klartext,
                        "ia": ia, "ib": ib, "art": art, "hochGut": hoch_gut})
        gruppen.append([gruppe, aus])
    return gruppen


def _parameter_daten(sp):
    """Einstellungen mit Spannweite und beschrifteten Enden."""
    a0, a1 = sp.lage.anweisung[0], sp.lage.anweisung[1]
    zeilen = [{
        "art": "text", "name": "Formation", "klartext": "Grundordnung der Elf",
        "a": a0.formation, "b": a1.formation,
    }]
    for attr, name, klartext, lo, hi, einheit, anker_lo, anker_hi in PARAMETER:
        wa, wb = getattr(a0, attr), getattr(a1, attr)
        fmt = (lambda v: "%.0f%s" % (v, einheit)) if einheit else \
              (lambda v: "%.2f" % v)
        zeilen.append({
            "art": "skala", "name": name, "klartext": klartext,
            "min": lo, "max": hi, "a": max(lo, min(hi, wa)), "b": max(lo, min(hi, wb)),
            "at": fmt(wa), "bt": fmt(wb),
            "ankerMin": "%s (%.0f%s)" % (anker_lo, lo, einheit or ""),
            "ankerMax": "%s (%.0f%s)" % (anker_hi, hi, einheit or ""),
        })
    mv = [sum(s.attribute.v_max for s in elf) / 11 for elf in sp.lage.mannschaft]
    zeilen.append({
        "art": "text", "name": "mittleres Spitzentempo der Elf",
        "klartext": "Mittelwert über alle elf Spieler; Ligaspanne etwa 7,3 bis 9,5 m/s",
        "a": "%.2f m/s" % mv[0], "b": "%.2f m/s" % mv[1],
    })
    zeilen.append({
        "art": "text", "name": "Lauf der Simulation",
        "klartext": "Zeitschritt, Startwert des Zufallszahlengebers und gerechnete Spielzeit",
        "a": "%.0f Hz · Startwert %d" % (1.0 / sp.dt, sp.seed),
        "b": "%.0f Minuten" % (sp.lage.zeit / 60.0),
    })
    return zeilen


PARAMETER_FUSS = (
    "Diese Werte sind die Eingabe, nicht das Ergebnis. Geändert werden sie beim "
    "Start des Laufs — grob über eine Vorlage "
    "(<code>--heim-stil hoch_pressend</code>, <code>tiefer_block</code>, "
    "<code>ballbesitz</code>, <code>ausgeglichen</code>) und die Formation "
    "(<code>--heim-formation 3-4-3</code>), fein über jedes einzelne Feld von "
    "<code>taktik.Teamanweisung</code>. Wer wissen will, was eine Änderung "
    "bewirkt, vergleicht sie nicht am Einzelspiel, sondern gepaart über viele "
    "Wiederholungen: <code>cli.py kontrafaktisch --frage abwehrhoehe</code>.")

GRENZEN = (
    "Ein einzelner Lauf ist eine Stichprobe aus einem sehr breiten Zufallsprozess. "
    "Was hier zu sehen ist, wäre bei einem anderen Startwert anders ausgegangen — "
    "<b>aus dieser Ansicht lässt sich kein Urteil über eine Mannschaft ableiten</b>. "
    "Dazu kommen bekannte Kalibrierungsgrenzen: Schuss-, Torschuss- und Torzahlen "
    "liegen im Modell um ein Vielfaches über realen Werten, die Passquote rund "
    "25 Prozentpunkte darunter. Belastbar sind die Sprintkinematik, der Ballflug, "
    "die xG-Kurve über die Entfernung sowie die Ordnung auf dem Feld. "
    "Für Aussagen mit Unsicherheitsangabe ist der kontrafaktische Modus da; "
    "die vollständige Kalibrierungstabelle steht in der README des Moduls.")


def html_bauen(sp, pfad, titel=None, heim_name="Heim", gast_name="Gast",
               nur_ereignisse=("tor", "schuss", "parade", "elfmeter", "abseits")):
    """Aufzeichnung eines `spiel.Spiel` als eigenstaendige HTML-Datei."""
    if not sp.bahn:
        raise ValueError("keine Aufzeichnung vorhanden - Spiel mit "
                         "aufzeichnen=True laufen lassen")
    if len(sp.stat) != len(sp.bahn) or len(sp.dist) != len(sp.bahn):
        raise ValueError("Statistik- und Positionsspur passen nicht zusammen")

    b = sp.bericht()
    a0, a1 = sp.lage.anweisung[0], sp.lage.anweisung[1]
    daten = {
        "bahn": sp.bahn,
        "stat": sp.stat,
        "dist": sp.dist,
        "nummern": [s.nummer for elf in sp.lage.mannschaft for s in elf],
        "rollen": [s.rolle for elf in sp.lage.mannschaft for s in elf],
        "spielernamen": [s.name for elf in sp.lage.mannschaft for s in elf],
        "namen": [heim_name, gast_name],
        "richtung_heim": sp.lage.richtung[0],
        "schritt": round(sp.dt * sp.rate, 3),
        "ereignisse": [e.als_dict() for e in sp.ereignisse if e.art in nur_ereignisse],
        "metriken": _metriken_daten(),
        "parameter": _parameter_daten(sp),
        "parameterFuss": PARAMETER_FUSS,
        "bericht": b,
    }
    ersatz = {
        "__TITEL__": titel or ("%s – %s  %d:%d" % (heim_name, gast_name,
                                                   b["tore"][0], b["tore"][1])),
        "__H1__": "Simulierte Partie · %s – %s" % (heim_name, gast_name),
        "__SUB__": ("Agentenbasierte 11-gegen-11-Simulation aus dem VfL-Bochum-"
                    "Framework. %.0f Minuten Spielzeit, aufgezeichnet mit %.0f Hz."
                    % (sp.lage.zeit / 60.0, 1.0 / (sp.dt * sp.rate))),
        "__HEIM__": heim_name,
        "__GAST__": gast_name,
        "__HEIM_FORM__": "%s · Abwehrhöhe %.0f m" % (a0.formation, a0.abwehrhoehe),
        "__GAST_FORM__": "%s · Abwehrhöhe %.0f m" % (a1.formation, a1.abwehrhoehe),
        "__GRENZEN__": GRENZEN,
        "__PALETTE__": "#2a78d6,#eb6834",
        "__FELD__": json.dumps({
            "L": K.FELD_LAENGE, "B": K.FELD_BREITE, "TOR": K.TOR_HALB_BREITE,
            "SR_T": K.STRAFRAUM_TIEFE, "SR_B": K.STRAFRAUM_HALB_BREITE,
            "TR_T": K.TORRAUM_TIEFE, "TR_B": K.TORRAUM_HALB_BREITE,
            "KREIS": K.ANSTOSSKREIS}),
        "__DATEN__": json.dumps(daten, separators=(",", ":"), ensure_ascii=False),
    }
    seite = _VORLAGE
    for marke, wert in ersatz.items():
        seite = seite.replace(marke, wert)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(seite)
    return pfad


def bahn_schreiben(sp, pfad):
    """Rohaufzeichnung als JSON - Eingabe fuer eigene Renderer."""
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump({
            "kopf": {
                "hz": round(1.0 / (sp.dt * sp.rate), 3),
                "feld": [K.FELD_LAENGE, K.FELD_BREITE],
                "spalten": (["t"]
                            + ["%s_%d_%s" % ("heim" if team == 0 else "gast",
                                             s.nummer, achse)
                               for team, elf in enumerate(sp.lage.mannschaft)
                               for s in elf for achse in ("x", "y")]
                            + ["ball_x", "ball_y", "ball_z", "ballbesitz"]),
                "stat_spalten": STAT_SPALTEN,
                "dist_spalten": ["%s_%d" % ("heim" if team == 0 else "gast", s.nummer)
                                 for team, elf in enumerate(sp.lage.mannschaft)
                                 for s in elf],
            },
            "bahn": sp.bahn,
            "stat": sp.stat,
            "dist": sp.dist,
            "ereignisse": [e.als_dict() for e in sp.ereignisse],
        }, f, separators=(",", ":"))
    return pfad
