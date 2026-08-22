"""Post-Match-Report: eine druckfertige Seite je Spiel, je Klub konfiguriert.

    python3 skripte/report.py --klub vfl-bochum --letztes
    python3 skripte/report.py --klub vfl-bochum --spieltag 12 --pdf
    python3 skripte/report.py --alle-klubs --letztes
    python3 skripte/report.py --klub schalke-04 --alle

Der Klub steckt in `klubs/<slug>.json`, nicht im Code. Ausgabe ist eine in sich
geschlossene HTML-Datei ohne externe Requests; mit --pdf wird sie zusaetzlich
ueber ein lokales Chromium nach A4-PDF gedruckt.
"""
import argparse
import html
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import befund as bf                                                   # noqa: E402
import klubprofil as kp                                               # noqa: E402

AUSGABE = os.path.join(kp.WURZEL, "reports")

URTEIL_KURZ = {
    "stark (>=3/4 Referenzen)": "stark",
    "gemischt (2/4 Referenzen)": "gemischt",
    "normativ gesetzt (keine Vorbild-Evidenz)": "normativ",
    "schwach - Datengrenze, siehe Limitation": "schwach",
}

CHROMIUM = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
]


# ------------------------------------------------------------- Formatierung
def zahl(x, nd=1, plus=False):
    """Deutsche Schreibweise, Minus als echtes Minuszeichen."""
    if x is None:
        return "—"
    s = f"{x:+.{nd}f}" if plus else f"{x:.{nd}f}"
    return s.replace("-", "−").replace(".", ",")


def prozent(x, nd=0):
    return "—" if x is None else zahl(x, nd) + " %"


def esc(s):
    return html.escape(str(s if s is not None else ""))


def datum_de(iso):
    j, m, t = iso.split("-")
    return f"{t}.{m}.{j}"


def balken(score, klasse=""):
    """Score-Balken 0-100 mit Markierung beim Liga-Median 50."""
    if score is None:
        return '<div class="bar leer"><span class="tick"></span></div>'
    return (f'<div class="bar {klasse}"><i style="width:{max(0.0, min(100.0, score)):.1f}%"></i>'
            f'<span class="tick"></span></div>')


def sparkline(verlauf):
    """Saisonverlauf der Stiltreue, das aktuelle Spiel hervorgehoben."""
    pts = [v for v in verlauf if v["score"] is not None]
    if len(pts) < 2:
        return ""
    w, h, rand = 320.0, 34.0, 4.0
    n = len(pts) - 1
    xy = [(rand + i / n * (w - 2 * rand),
           rand + (1 - p["score"] / 100.0) * (h - 2 * rand)) for i, p in enumerate(pts)]
    linie = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    aktiv = [(x, y) for (x, y), p in zip(xy, pts) if p["aktuell"]]
    punkt = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.1" class="jetzt"/>'
                    for x, y in aktiv)
    return (f'<svg class="spark" viewBox="0 0 {w:.0f} {h:.0f}" preserveAspectRatio="none" '
            f'role="img" aria-label="Saisonverlauf der Stiltreue">'
            f'<line x1="0" y1="{h / 2:.1f}" x2="{w:.0f}" y2="{h / 2:.1f}" class="mid"/>'
            f'<polyline points="{linie}" class="pfad"/>{punkt}</svg>')


def wahrscheinlichkeiten(c):
    teile = [("Sieg", c["psieg"]), ("Remis", c["premis"]), ("Niederlage", c["pnied"])]
    if any(p is None for _, p in teile):
        return ""
    seg = "".join(
        f'<span class="p{i}" style="width:{p * 100:.1f}%">{prozent(p * 100)}</span>'
        for i, (_, p) in enumerate(teile))
    beschriftung = "".join(f'<span style="width:{p * 100:.1f}%">{esc(l)}</span>'
                           for l, p in teile)
    return (f'<div class="pbar">{seg}</div>'
            f'<div class="plabels">{beschriftung}</div>')


# ----------------------------------------------------------------- Bausteine
def karte_a(b):
    a, s = b["a"], b["saison"]
    zeilen = []
    for p in a["phasen"]:
        marke = ' <span class="warn" title="wenige Ereignisse">•</span>' if p["unsicher"] else ""
        zeilen.append(
            f'<tr><th>{esc(p["label"])}<span class="gew">{zahl(p["gewicht"] * 100, 0)} %</span>'
            f'<div class="pfrage">{esc(p["frage"])}</div></th>'
            f'<td class="bz">{balken(p["score"])}</td>'
            f'<td class="num">{zahl(p["score"])}{marke}</td></tr>')
    fehlend = (", ".join(a["ohne_daten"]) if a["ohne_daten"] else "keine")
    return f"""
<section class="karte gross-links">
  <div class="kopfzeile"><span class="stufe">A</span> Spielstiltreue
    <span class="frage">Wie nah kam das Spiel der Spielidee?</span></div>
  <div class="kennzahl"><span class="wert">{zahl(a["score"])}</span><span class="von">/ 100</span>
    <div class="neben">Saison-Median {zahl(s["score_median"])} ·
      Rang {s["score_rang"] or "—"} von {s["spiele"]} ·
      Form (letzte 5) {zahl(s["form"])}</div></div>
  {sparkline(s["verlauf"])}
  <table class="phasen"><tbody>{''.join(zeilen)}</tbody></table>
  <div class="fuss">Belastbarkeit dieses Spiels {zahl(a["conf"], 2)} ·
    Phasen ohne Daten: {esc(fehlend)} · Der Wert misst Identität, nicht Qualität.</div>
</section>"""


def karte_b(b):
    e = b["b"]
    if e is None:
        grund = (b["profil"].get("hinweise") or ["Für dieses Profil ist keine "
                                                 "Zielreferenz hinterlegt."])[0]
        return f"""
<section class="karte">
  <div class="kopfzeile"><span class="stufe">B</span> Aufstiegsperformance
    <span class="frage">Hätte das für den Aufstieg gereicht?</span></div>
  <div class="leerkarte">Nicht anwendbar.<br><span>{esc(grund)}</span></div>
</section>"""
    urteil = "gut" if e["erreicht"] else "schlecht"
    text = "Zielmarke erreicht" if e["erreicht"] else "Zielmarke verfehlt"
    anteil = (f'{e["anteil_kohorte"]:.0f} %'.replace(".", ","))
    return f"""
<section class="karte">
  <div class="kopfzeile"><span class="stufe">B</span> Aufstiegsperformance
    <span class="frage">Hätte das gegen diesen Gegner gereicht?</span></div>
  <div class="urteil {urteil}">{text}</div>
  <div class="kennzahl klein"><span class="wert">{zahl(e["delta"], 2, plus=True)}</span>
    <span class="von">npxG-Differenz gegenüber dem Ziel</span></div>
  <table class="ziel"><tbody>
    <tr><th>npxG erzeugt</th><td class="num">{zahl(e["npxg"], 2)}</td>
        <td class="soll">Ziel {zahl(e["ziel_off"], 2)}</td></tr>
    <tr><th>npxG zugelassen</th><td class="num">{zahl(e["npxg_geg"], 2)}</td>
        <td class="soll">Ziel {zahl(e["ziel_def"], 2)}</td></tr>
  </tbody></table>
  <div class="fuss">Ziel = Mittel der {esc(e["kohorte"])}, an die Stärke dieses Gegners
    angepasst. Saison: {b["saison"]["ueber_ziel"]} von {b["saison"]["ueber_ziel_von"]} Spielen
    über Ziel — Aufsteiger selbst schaffen {anteil}.</div>
</section>"""


def karte_c(b):
    c = b["c"]
    d = c["dpkt"]
    urteil = "gut" if (d or 0) > 0.4 else ("schlecht" if (d or 0) < -0.4 else "neutral")
    return f"""
<section class="karte">
  <div class="kopfzeile"><span class="stufe">C</span> Outcome Alignment
    <span class="frage">Passt das Ergebnis zur Leistung?</span></div>
  <div class="kennzahl klein"><span class="wert">{c["punkte"]}</span>
    <span class="von">Punkte gegen {zahl(c["xp"], 2)} xPoints</span></div>
  <div class="urteil {urteil}">{zahl(d, 2, plus=True)} · {esc(c["klasse"])}</div>
  {wahrscheinlichkeiten(c)}
  <table class="ziel"><tbody>
    <tr><th>Verwertung eigen</th><td class="num">{zahl(c["verwertung"], 2, plus=True)}</td>
        <th class="zweit">Gegner</th><td class="num">{zahl(c["verwertung_geg"], 2, plus=True)}</td></tr>
    <tr><th>Torhüter-Effekt</th><td class="num">{zahl(c["tw_effekt"], 2, plus=True)}</td>
        <td colspan="2" class="soll">xG Save − Gegentore</td></tr>
  </tbody></table>
  <div class="fuss">Verwertung = Tore ohne Elfmeter minus npxG.</div>
</section>"""


def kpi_kachel(k):
    zusatz = ' <span class="warn">•</span>' if k["unsicher"] else ""
    return (f'<li><div class="kz"><span class="kurz">{esc(k["kurz"])}</span>'
            f'<span class="kname">{esc(k["name"])}</span>'
            f'<span class="num">{zahl(k["score"])}{zusatz}</span></div>'
            f'{balken(k["score"])}'
            f'<div class="mgmt">{esc(k["mgmt"])}</div></li>')


def stark_schwach(b):
    a = b["a"]
    return f"""
<section class="paar">
  <div><h3>Am nächsten an der Spielidee</h3>
    <ul class="kpiliste">{''.join(kpi_kachel(k) for k in a["stark"])}</ul></div>
  <div><h3>Am weitesten weg</h3>
    <ul class="kpiliste">{''.join(kpi_kachel(k) for k in a["schwach"])}</ul></div>
</section>"""


def hinweise(b):
    """Nur was dieses Spiel betrifft. Profilhinweise stehen auf Seite 2."""
    if not b["flags"]:
        return ""
    text = " · ".join(esc(f["text"]) for f in b["flags"])
    return (f'<section class="hinweise"><b>Zu diesem Spiel:</b> {text}</section>')


def kpi_tabelle(b):
    """Alle 15 KPIs, nach Phasen gruppiert und zweispaltig gesetzt."""
    nach_phase = {}
    for k in b["a"]["kpis"]:
        nach_phase.setdefault(k["phase"], []).append(k)

    gruppen = []
    for p in b["a"]["phasen"]:
        eintraege = nach_phase.get(p["label"], [])
        kopf = (f'<div class="gkopf">{esc(p["label"])}'
                f'<span>{"Phasenscore " + zahl(p["score"]) if eintraege else "keine Daten"}'
                f' · Gewicht {zahl(p["gewicht"] * 100, 0)} %</span></div>')
        zeilen = []
        for k in eintraege:
            marke = ' <span class="warn">•</span>' if k["unsicher"] else ""
            zeilen.append(
                f'<div class="kpiz">'
                f'<div class="kz"><span class="kurz">{esc(k["kurz"])}</span>'
                f'<span class="kname">{esc(k["name"])}</span>'
                f'<span class="num">{zahl(k["score"])}{marke}</span></div>'
                f'{balken(k["score"])}'
                f'<div class="def">{esc(k["definition"])} · '
                f'<b>{zahl(k["roh"], 3)}</b> {esc(k["norm"])} · n = {zahl(k["n"], 0)} · '
                f'Trennschärfe {esc(URTEIL_KURZ.get(k["urteil"], k["urteil"]))}</div>'
                f'</div>')
        gruppen.append(f'<section class="gruppe">{kopf}{"".join(zeilen)}</section>')

    return f"""
<section class="block">
  <h2>Die 15 KPIs im Einzelnen</h2>
  <div class="kpispalten">{''.join(gruppen)}</div>
  <div class="fuss">Score 50 = Median der Liga-Saison, 100 = P90 der Referenzkohorte; der Strich
    im Balken markiert die 50. <span class="warn">•</span> steht für wenige Ereignisse
    (Belastbarkeit unter {zahl(b["conf_schwelle"], 2)}). Die Trennschärfe sagt, wie deutlich der
    KPI die vier Referenzmannschaften vom Ligamittel trennt — eine Eigenschaft des KPIs, nicht
    dieses Spiels.</div>
</section>"""


def kontext_tabelle(b):
    """Gegnerbild, dreispaltig und knapp — es ist der Rahmen, nicht die Aussage."""
    zeilen = []
    for z in b["kontext"]:
        einheit = " %" if z["einheit"] == "%" else ""
        zeilen.append(f'<tr><th>{esc(z["label"])}</th>'
                      f'<td class="num">{zahl(z["wert"], z["nachkomma"])}{einheit}</td>'
                      f'<td class="num perz">P{zahl(z["perzentil"], 0)}</td></tr>')
    je = (len(zeilen) + 2) // 3
    bloecke = [zeilen[i:i + je] for i in range(0, len(zeilen), je)]
    spalten = "".join(f'<table class="kontext"><tbody>{"".join(t)}</tbody></table>'
                      for t in bloecke if t)
    return f"""
<section class="block kontextblock">
  <h3>Spielkontext — was der Gegner getan und zugelassen hat</h3>
  <div class="kontextspalten">{spalten}</div>
  <div class="fuss">P = Perzentil in der Liga-Saison (P50 = Ligamitte). Hoher PPDA-Wert = der
    Gegner läuft nicht an; negative Blockhöhe = er stand tiefer als üblich.</div>
</section>"""


def profilhinweise(p):
    """Was fuer dieses Profil generell gilt — nicht spielbezogen."""
    hs = p.get("hinweise") or []
    if not hs:
        return ""
    return '<ul class="profilhinweise">' + "".join(f"<li>{esc(h)}</li>" for h in hs) + "</ul>"


def methode(b):
    p = b["profil"]
    return f"""
<section class="block methode">
  <h2>Wie zu lesen</h2>
  <div class="spalten">
    <div><h4>Drei Fragen, getrennt gehalten</h4>
      <p><b>A</b> misst Identität: wie nah das Spiel der hinterlegten Spielidee kam.
      Ein hoher Wert ist keine Aussage über Qualität. <b>B</b> misst Niveau gegen die
      Aufstiegsreferenz, gegnerbereinigt. <b>C</b> prüft, ob das Ergebnis zur Leistung passt.
      Die drei Werte werden bewusst nicht zu einer Note verrechnet.</p></div>
    <div><h4>Was der Rahmen nicht kann</h4>
      <p>Der Flügelfokus hat keine Vorbild-Evidenz — sein Korridor ist normativ auf das obere
      Ligafünftel gesetzt. Die Umschalt-KPIs trennen schwach: ohne Event-Daten mit Zeitstempeln
      lässt sich kein Umschaltmoment isolieren, gemessen wird die Spielsumme je Ballgewinn.</p></div>
    <div><h4>Grundlage</h4>
      <p>Spielidee: {esc(p["spielidee"])}. KPI-Set „{esc(p.get("kpi_set", "—"))}“,
      z-standardisiert je Liga-Saison über 4.343 Spiele aus 16 Liga-Saisons.
      Alle Werte sind gerechnet, nicht geschätzt.</p>
      {profilhinweise(p)}</div>
  </div>
</section>"""


CSS = """
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font:9.6pt/1.42 -apple-system,"Segoe UI",system-ui,Helvetica,Arial,sans-serif;
  color:var(--ink);background:#fff}
h2{font-size:11pt;margin:0 0 6px;letter-spacing:-.01em}
h3{font-size:8.6pt;margin:0 0 5px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink2)}
h4{font-size:9pt;margin:0 0 3px}
p{margin:0}
table{border-collapse:collapse;width:100%}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}

.seite{background:#fff}
@media screen{
  body{background:#e8e7e2;padding:22px 0}
  .seite{width:210mm;min-height:297mm;margin:0 auto 20px;padding:11mm 12mm;
    box-shadow:0 2px 16px rgba(0,0,0,.15)}
}
@media print{
  .seite{width:auto;min-height:0;padding:0;box-shadow:none;break-after:page}
  .seite:last-child{break-after:auto}
}

.kopf{display:flex;justify-content:space-between;align-items:flex-start;
  border-bottom:2px solid var(--klub);padding-bottom:6px;margin-bottom:9px}
.marke{display:flex;gap:9px;align-items:center}
.badge{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
  background:var(--klub);color:var(--klub-kontrast);font-weight:700;font-size:9.5pt;
  letter-spacing:.02em;border-radius:4px}
.klub{font-weight:700;font-size:12pt;letter-spacing:-.015em;line-height:1.15}
.doktyp{font-size:8.4pt;color:var(--ink2);text-transform:uppercase;letter-spacing:.1em}
.kopf-rechts{text-align:right;font-size:8.6pt;color:var(--ink2);line-height:1.45}
.kopf-rechts b{color:var(--ink);font-size:9.4pt}

.ergebnis{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;
  margin:0 0 9px;padding-bottom:7px;border-bottom:1px solid var(--line)}
.teams{font-size:15.5pt;letter-spacing:-.02em;font-weight:600;white-space:nowrap}
.punkte{font-size:15.5pt;font-weight:700;line-height:1;white-space:nowrap;
  font-variant-numeric:tabular-nums}
.punkte span{font-size:8.4pt;font-weight:400;color:var(--muted);margin-left:5px}
.teams .tore{margin:0 11px;padding:1px 9px;background:var(--klub);color:var(--klub-kontrast);
  border-radius:4px;font-variant-numeric:tabular-nums}
.teams .geg{font-weight:400;color:var(--ink2)}
.ort{font-size:8.6pt;color:var(--muted)}

.ebenen{display:grid;grid-template-columns:1.32fr 1fr;gap:8px;align-items:stretch}
.rechts{display:grid;gap:8px}
.karte{border:1px solid var(--line);border-radius:5px;padding:8px 9px 9px;background:var(--karte);
  display:flex;flex-direction:column}
.karte .fuss{margin-top:auto;padding-top:5px}
.kopfzeile{font-weight:700;font-size:9.4pt;margin-bottom:6px;display:flex;
  align-items:baseline;gap:6px;flex-wrap:wrap}
.stufe{display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;
  background:var(--klub);color:var(--klub-kontrast);border-radius:3px;font-size:8pt}
.frage{font-weight:400;font-size:8.2pt;color:var(--muted)}
.kennzahl{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;margin:2px 0 6px}
.kennzahl .wert{font-size:26pt;line-height:1;font-weight:700;letter-spacing:-.03em;
  font-variant-numeric:tabular-nums}
.kennzahl.klein .wert{font-size:19pt}
.kennzahl .von{font-size:8.4pt;color:var(--ink2)}
.kennzahl .neben{flex-basis:100%;font-size:8.2pt;color:var(--muted);margin-top:2px}
.fuss{font-size:7.7pt;line-height:1.35;color:var(--muted);margin-top:6px}
.leerkarte{font-size:9pt;color:var(--ink2);padding:8px 0 10px}
.leerkarte span{display:block;font-size:8.2pt;color:var(--muted);margin-top:3px}

.urteil{display:inline-block;font-size:8.4pt;font-weight:600;padding:2px 7px;border-radius:3px;
  margin-bottom:5px}
.urteil.gut{background:#e3f0e8;color:var(--gut)}
.urteil.schlecht{background:#f7e6e2;color:var(--schlecht)}
.urteil.neutral{background:#ecebe5;color:var(--ink2)}

.bar{position:relative;height:5px;background:var(--track);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--klub);border-radius:3px}
.bar.duenn{height:4px}
.bar .tick{position:absolute;left:50%;top:0;width:1px;height:100%;background:rgba(0,0,0,.30)}
.bar.leer{background:repeating-linear-gradient(90deg,var(--track) 0 3px,#fff 3px 6px)}
.bz{width:38%;padding:0 8px}

.phasen th{text-align:left;font-weight:400;padding:2.6px 0;white-space:nowrap}
.phasen .gew{color:var(--muted);font-size:7.8pt;margin-left:5px}
.phasen .pfrage{font-size:7.6pt;color:var(--muted);font-weight:400;white-space:normal;
  max-width:52mm;line-height:1.3;margin-top:1px}
.phasen th{vertical-align:top;padding-right:6px}
.phasen td{padding:2.6px 0;vertical-align:top}
.phasen .bz{padding-top:5px}
.phasen .num{padding-top:0}
.spark{width:100%;height:28px;display:block;margin:0 0 4px}
.spark .pfad{fill:none;stroke:var(--klub);stroke-width:1.4;stroke-linejoin:round}
.spark .mid{stroke:rgba(0,0,0,.18);stroke-width:.8;stroke-dasharray:3 3}
.spark .jetzt{fill:var(--klub);stroke:#fff;stroke-width:1.4}

.ziel th{text-align:left;font-weight:400;padding:2.2px 0}
.ziel .soll{text-align:right;color:var(--muted);font-size:8pt;white-space:nowrap}
.pbar{display:flex;height:15px;border-radius:3px;overflow:hidden;margin:5px 0 2px;
  font-size:7.4pt;color:#fff;line-height:15px;text-align:center}
.pbar .p0{background:var(--klub)}
.pbar .p1{background:#9b9992}
.pbar .p2{background:#3f3e3a}
.plabels{display:flex;font-size:7.4pt;color:var(--muted)}
.plabels span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.plabels span:nth-child(2){text-align:center}
.plabels span:last-child{text-align:right}
.ziel .zweit{text-align:right;font-weight:400;color:var(--ink2);padding-left:10px}

.paar{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:9px}
.kpiliste{list-style:none;margin:0;padding:0}
.kpiliste li{margin-bottom:5px}
.kz{display:flex;align-items:baseline;gap:6px;margin-bottom:2px}
.kurz{display:inline-block;min-width:20px;font-size:7.4pt;font-weight:700;color:var(--klub);
  letter-spacing:.04em}
.kname{font-weight:600}
.kz .num{margin-left:auto;font-weight:700}
.mgmt{font-size:8pt;color:var(--muted);margin-top:2px}

.kontextblock{margin-top:9px}
.kontextspalten{display:grid;grid-template-columns:repeat(3,1fr);gap:0 16px;font-size:8pt}
.kontext td,.kontext th{border-bottom:1px solid var(--line);padding:2.2px 0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kontext th{max-width:33mm}
.kontext .perz{width:9mm;color:var(--muted);font-size:7.4pt}
.hinweise{margin-top:8px;border-top:1px solid var(--line);padding-top:6px;
  font-size:7.9pt;line-height:1.35;color:var(--schlecht)}
.hinweise b{color:var(--ink2)}
.profilhinweise{margin:5px 0 0;padding-left:13px;font-size:7.8pt;color:var(--muted)}

.block{margin-bottom:13px}
.kpispalten{column-count:2;column-gap:16px}
.gruppe{break-inside:avoid;margin-bottom:9px}
.gkopf{background:var(--band);font-weight:700;font-size:8.6pt;padding:3px 6px;
  display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:5px}
.gkopf span{font-weight:400;color:var(--ink2);font-size:7.6pt;white-space:nowrap}
.kpiz{margin-bottom:6px}
.kpiz .def{font-size:7.4pt;line-height:1.3;color:var(--muted);margin-top:2px}
.kpiz .def b{color:var(--ink2);font-weight:600}
.kontext th{text-align:left;font-weight:400}
.warn{color:var(--schlecht);font-weight:700}

.methode .spalten{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:8.2pt;
  color:var(--ink2)}
.seitenfuss{margin-top:auto;padding-top:6px;border-top:1px solid var(--line);
  display:flex;justify-content:space-between;font-size:7.6pt;color:var(--muted)}
.seite{display:flex;flex-direction:column}
"""


def dokument(b):
    p, s = b["profil"], b["spiel"]
    ort = "Heimspiel" if s["heim"] else "Auswärtsspiel"
    titel = f'{p["kurz"]} — {s["gw"]}. Spieltag {s["ls"]} gegen {s["geg"]}'
    fuss = (f'{esc(p["kurz"])} · {esc(s["ls"])} · {s["gw"]}. Spieltag · '
            f'{datum_de(s["datum"])}')
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(titel)}</title>
<style>
:root{{--klub:{esc(p["farbe"])};--klub-kontrast:{esc(p["farbe_kontrast"])};
  --ink:#141412;--ink2:#4d4c48;--muted:#84827b;--line:rgba(20,20,18,.15);
  --track:#e6e5df;--karte:#fbfbf9;--band:#f1f0ec;--gut:#286c47;--schlecht:#a83b2a;}}
@page{{size:A4;margin:11mm 12mm 10mm}}
{CSS}
</style></head>
<body>
<div class="seite">
  <header class="kopf">
    <div class="marke"><span class="badge">{esc(p["kuerzel"])}</span>
      <div><div class="klub">{esc(p["name"])}</div>
        <div class="doktyp">Post-Match-Report</div></div></div>
    <div class="kopf-rechts"><b>{esc(s["ls"])} · {s["gw"]}. Spieltag</b><br>
      {datum_de(s["datum"])} · {ort}</div>
  </header>
  <section class="ergebnis">
    <div>
      <div class="teams"><span>{esc(p["kurz"])}</span>
        <span class="tore">{s["tore"]} : {s["gt"]}</span>
        <span class="geg">{esc(s["geg"])}</span></div>
      <div class="ort">Spielidee: {esc(p["spielidee"])}</div>
    </div>
    <div class="punkte">{s["pkt"]}<span>{"Punkt" if s["pkt"] == 1 else "Punkte"}</span></div>
  </section>
  <div class="ebenen">
    {karte_a(b)}
    <div class="rechts">{karte_b(b)}{karte_c(b)}</div>
  </div>
  {stark_schwach(b)}
  {kontext_tabelle(b)}
  {hinweise(b)}
  <div class="seitenfuss"><span>{fuss}</span><span>Seite 1 von 2</span></div>
</div>
<div class="seite">
  {kpi_tabelle(b)}
  {methode(b)}
  <div class="seitenfuss"><span>{fuss}</span><span>Seite 2 von 2</span></div>
</div>
</body></html>
"""


# ---------------------------------------------------------------- Dateiablage
def dateiname(spiel):
    geg = "".join(c if c.isalnum() else "-" for c in spiel["geg"].lower()).strip("-")
    while "--" in geg:
        geg = geg.replace("--", "-")
    return f'{spiel["gw"]:02d}-{spiel["datum"]}-{geg}.html'


def nach_pdf(html_pfad):
    """Druckt die Seite mit einem lokalen Chromium nach A4-PDF."""
    binaer = next((c for c in CHROMIUM if os.path.exists(c)), None) \
        or shutil.which("chromium") or shutil.which("google-chrome")
    if not binaer:
        print("   kein Chromium gefunden — PDF uebersprungen", file=sys.stderr)
        return None
    pdf_pfad = html_pfad[:-5] + ".pdf"
    subprocess.run([binaer, "--headless", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", f"--print-to-pdf={pdf_pfad}",
                    "file://" + html_pfad],
                   check=True, capture_output=True, timeout=120)
    return pdf_pfad


def schreibe(ds, profil, i, ausgabe, als_pdf=False):
    b = bf.befund(ds, profil, i)
    ordner = os.path.join(ausgabe, profil["slug"])
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, dateiname(b["spiel"]))
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(dokument(b))
    if als_pdf:
        nach_pdf(pfad)
    return pfad, b


def uebersicht(ausgabe, erzeugt):
    """Eine schlichte Startseite ueber alle erzeugten Reports."""
    nach_klub = {}
    for pfad, b in erzeugt:
        nach_klub.setdefault(b["profil"]["slug"], (b["profil"], []))[1].append((pfad, b))
    bloecke = []
    for slug, (p, eintraege) in sorted(nach_klub.items()):
        zeilen = "".join(
            f'<li><a href="{esc(os.path.relpath(pfad, ausgabe))}">'
            f'{b["spiel"]["gw"]}. Spieltag · {esc(b["spiel"]["geg"])} '
            f'{b["spiel"]["tore"]}:{b["spiel"]["gt"]}</a>'
            f'<span>Stiltreue {zahl(b["a"]["score"])}</span></li>'
            for pfad, b in sorted(eintraege, key=lambda e: e[1]["spiel"]["i"]))
        bloecke.append(f'<section><h2><span style="background:{esc(p["farbe"])}"></span>'
                       f'{esc(p["name"])}</h2><ul>{zeilen}</ul></section>')
    doc = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Post-Match-Reports</title><style>
body{{margin:0;background:#f7f7f5;color:#141412;
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:720px;margin:0 auto;padding:48px 20px}}
h1{{font-size:22px;margin:0 0 4px}}
.sub{{color:#84827b;font-size:14px;margin:0 0 28px}}
h2{{font-size:15px;margin:26px 0 8px;display:flex;align-items:center;gap:8px}}
h2 span{{width:11px;height:11px;border-radius:3px;display:inline-block}}
ul{{list-style:none;margin:0;padding:0}}
li{{display:flex;justify-content:space-between;gap:12px;padding:7px 0;
  border-bottom:1px solid rgba(20,20,18,.10);font-size:14px}}
li span{{color:#84827b;font-variant-numeric:tabular-nums}}
a{{color:#141412;text-decoration:none}} a:hover{{text-decoration:underline}}
</style></head><body><div class="wrap">
<h1>Post-Match-Reports</h1>
<p class="sub">Erzeugt aus einem Klubprofil und der gerechneten Datenbasis.
Jede Seite ist in sich geschlossen und druckt als A4.</p>
{''.join(bloecke)}
</div></body></html>
"""
    pfad = os.path.join(ausgabe, "index.html")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(doc)
    return pfad


# ---------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Post-Match-Report je Klub und Spiel")
    ap.add_argument("--klub", help=f"Profil-Slug ({', '.join(kp.slugs()) or 'keins'})")
    ap.add_argument("--alle-klubs", action="store_true", help="alle Profile abarbeiten")
    ap.add_argument("--spieltag", type=int)
    ap.add_argument("--datum", help="YYYY-MM-DD")
    ap.add_argument("--gegner", help="Teil des Gegnernamens")
    ap.add_argument("--letztes", action="store_true", help="jüngstes Spiel")
    ap.add_argument("--alle", action="store_true", help="alle Spiele des Profils")
    ap.add_argument("--liste", action="store_true", help="Spiele auflisten, nichts erzeugen")
    ap.add_argument("--pdf", action="store_true", help="zusätzlich als A4-PDF drucken")
    ap.add_argument("--daten", help="Pfad zu dashboard_matches.json")
    ap.add_argument("--ausgabe", default=AUSGABE)
    a = ap.parse_args(argv)

    if not a.klub and not a.alle_klubs:
        ap.error("--klub <slug> oder --alle-klubs angeben")
    profile = kp.alle() if a.alle_klubs else [kp.lade(a.klub)]
    ds = bf.Datensatz(a.daten)

    erzeugt = []
    for profil in profile:
        spiele = ds.spiele(profil)
        if a.liste:
            print(f'\n{profil["name"]} — {len(spiele)} Spiele')
            for s in spiele:
                print(f'  {s["gw"]:>3}. Spieltag  {s["datum"]}  {s["ls"]:<14} '
                      f'{"H" if s["heim"] else "A"}  {s["geg"]:<26} '
                      f'{s["tore"]}:{s["gt"]}   Stiltreue {zahl(s["score"])}')
            continue

        if a.alle:
            treffer = list(range(len(spiele)))
        elif a.letztes and not (a.spieltag or a.datum or a.gegner):
            treffer = [len(spiele) - 1]
        else:
            treffer = bf.finde(spiele, a.spieltag, a.datum, a.gegner)
            if a.letztes:
                treffer = treffer[-1:]
        if not treffer:
            print(f'{profil["name"]}: kein Spiel passt zum Filter', file=sys.stderr)
            continue
        for i in treffer:
            pfad, b = schreibe(ds, profil, i, a.ausgabe, a.pdf)
            erzeugt.append((pfad, b))
            print(f'{profil["kurz"]:<16} {b["spiel"]["gw"]:>3}. Spieltag  '
                  f'{b["spiel"]["geg"]:<26} {b["spiel"]["tore"]}:{b["spiel"]["gt"]}  '
                  f'-> {os.path.relpath(pfad, kp.WURZEL)}')

    if erzeugt:
        print(f'\n{len(erzeugt)} Report(s) · Übersicht: '
              f'{os.path.relpath(uebersicht(a.ausgabe, erzeugt), kp.WURZEL)}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
