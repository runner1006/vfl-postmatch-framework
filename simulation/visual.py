"""Bahnaufzeichnung als eigenstaendige HTML-Animation mit Live-Statistik.

Erzeugt eine einzelne Datei ohne externe Requests - dieselbe Regel wie beim
Dashboard des Analyseteils. Doppelklick genuegt.

Dargestellt wird, was die Simulation wirklich gerechnet hat: Positionen aller
22 Agenten und des Balls im Zeitverlauf, dazu der **Stand zu genau diesem
Zeitpunkt** - nicht der Endstand. Die Statistikspur wird im selben Takt
aufgezeichnet wie die Positionen, deshalb laeuft die Leiste rechts mit dem
Zeitstrahl mit.

Die Raumkontrolle wird im Browser aus denselben Ankunftszeiten berechnet wie in
der Engine (Zweiphasenmodell mit Reaktionszeit), damit Bild und Modell nicht
auseinanderlaufen.

Der Weg zu synthetischem Videomaterial fuehrt ueber genau diese Daten: eine
Bahnaufzeichnung mit 25 Hz ist das, was ein Renderer als Eingabe braucht. Was
hier fehlt, ist die Darstellung - nicht die Simulation.

Vorlagentechnik: Platzhalter statt Prozentformatierung. In der Datei stehen
CSS-Prozentwerte und JavaScript-Modulo; jede %-Formatierung waere eine
Fehlerquelle ohne Gegenwert.
"""
import json

import konfig as K

# Spaltenbelegung der Statistikspur (siehe spiel.Spiel._aufzeichnen)
STAT_SPALTEN = [
    "tore_h", "tore_g", "xg_h", "xg_g", "schuesse_h", "schuesse_g",
    "box_h", "box_g", "drittel_h", "drittel_g", "hoehe_h", "hoehe_g",
    "ppda_h", "ppda_g", "paesse_h", "paesse_g", "an_h", "an_g",
    "besitz_h", "eintritte_h", "eintritte_g",
]

_VORLAGE = """<!doctype html>
<meta charset="utf-8">
<title>__TITEL__</title>
<style>
  :root {
    --gruen:#1f7a3f; --grund:#0e131a; --karte:#161e28; --rand:#26323f;
    --text:#e9eef4; --gedaempft:#93a3b5;
    --heim:#2f7fd0; --gast:#e0484f;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--grund); color:var(--text);
         font:14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; }
  .huelle { max-width:1500px; margin:0 auto; padding:16px 20px 28px; }

  /* ---------------------------------------------------------- Kopfzeile */
  .kopf { display:flex; flex-wrap:wrap; align-items:flex-start;
          justify-content:flex-start; gap:18px 30px; margin-bottom:14px; }
  .paarung { display:flex; align-items:center; gap:18px; }
  .team { min-width:150px; }
  .team.rechts { text-align:right; }
  .teamname { font-size:17px; font-weight:640; letter-spacing:-.2px; }
  .teamzeile { font-size:12.5px; color:var(--gedaempft); margin-top:1px; }
  .punkt { width:9px; height:9px; border-radius:50%; display:inline-block;
           margin-right:6px; vertical-align:1px; }
  .stand { font-size:34px; font-weight:700; font-variant-numeric:tabular-nums;
           letter-spacing:-1px; white-space:nowrap; }
  .minute { font-size:12.5px; color:var(--gedaempft); text-align:center;
            margin-top:-2px; font-variant-numeric:tabular-nums; }
  .settings { flex:0 1 480px; min-width:300px; max-width:520px;
              background:var(--karte); border:1px solid var(--rand);
              border-radius:8px; padding:9px 12px; }
  .settings h2 { font-size:11px; text-transform:uppercase; letter-spacing:.7px;
                 color:var(--gedaempft); margin:0 0 6px; font-weight:600; }
  .settings table { border-collapse:collapse; width:100%; font-size:12.5px; }
  .settings td { padding:1.5px 0; vertical-align:top; }
  .settings td.k { color:var(--gedaempft); padding-right:10px; white-space:nowrap; }
  .settings td.h { color:var(--heim); text-align:right; width:74px;
                   font-variant-numeric:tabular-nums; }
  .settings td.g { color:var(--gast); text-align:right; width:74px;
                   font-variant-numeric:tabular-nums; }
  .settings tr.voll td { color:var(--gedaempft); padding-top:5px;
                         border-top:1px solid var(--rand); margin-top:4px; }

  /* ------------------------------------------------------------- Buehne */
  .buehne { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:18px;
            align-items:start; }
  @media (max-width:1080px) { .buehne { grid-template-columns:1fr; } }
  canvas { width:100%; height:auto; display:block; border-radius:7px;
           background:var(--gruen); }
  .leiste { display:flex; gap:12px; align-items:center; flex-wrap:wrap;
            margin:10px 0 0; }
  button { background:#1d2733; color:var(--text); border:1px solid var(--rand);
           border-radius:5px; padding:5px 12px; font:inherit; cursor:pointer; }
  button:hover { background:#26333f; }
  input[type=range] { flex:1 1 260px; min-width:180px; accent-color:#2f7fd0; }
  label { display:inline-flex; gap:5px; align-items:center; font-size:13px;
          color:#b9c6d4; }
  .uhr { font-variant-numeric:tabular-nums; min-width:70px; font-weight:600; }

  /* -------------------------------------------------------------- Panel */
  .panel { background:var(--karte); border:1px solid var(--rand);
           border-radius:8px; padding:12px 14px 14px; }
  .panel h2 { font-size:11px; text-transform:uppercase; letter-spacing:.7px;
              color:var(--gedaempft); margin:0 0 2px; font-weight:600; }
  .panel h2.spaeter { margin-top:16px; }
  .zeile { margin:7px 0 0; }
  .zeile .werte { display:flex; justify-content:space-between; font-size:13px;
                  font-variant-numeric:tabular-nums; }
  .zeile .werte b { font-weight:640; }
  .zeile .werte .h { color:var(--heim); }
  .zeile .werte .g { color:var(--gast); }
  .zeile .name { color:var(--gedaempft); font-size:12px; }
  .balken { display:flex; height:5px; border-radius:3px; overflow:hidden;
            background:#0d1219; margin-top:3px; }
  .balken i { display:block; height:100%; }
  .balken i.h { background:var(--heim); }
  .balken i.g { background:var(--gast); }
  details { margin-top:8px; }
  summary { cursor:pointer; font-size:12.5px; color:#b9c6d4; padding:3px 0;
            list-style:none; }
  summary::-webkit-details-marker { display:none; }
  summary:before { content:"\\25B8"; display:inline-block; width:13px;
                   color:var(--gedaempft); transition:transform .15s; }
  details[open] summary:before { transform:rotate(90deg); }
  table.spieler { border-collapse:collapse; width:100%; font-size:12px;
                  font-variant-numeric:tabular-nums; margin-top:4px; }
  table.spieler th { color:var(--gedaempft); font-weight:600; text-align:right;
                     padding:2px 0 3px; font-size:11px; }
  table.spieler th.l, table.spieler td.l { text-align:left; }
  table.spieler td { padding:1.5px 0; }
  table.spieler tr.trenn td { border-top:1px solid var(--rand); padding-top:6px; }
  table.spieler td.nr { color:var(--gedaempft); width:26px; }
  table.spieler td.ro { color:var(--gedaempft); width:34px; }

  /* ---------------------------------------------------------- Ereignisse */
  .ereignisse { margin-top:16px; }
  .ereignisse table { border-collapse:collapse; font-size:13px; }
  .ereignisse th, .ereignisse td { text-align:left; padding:3px 16px 3px 0; }
  .ereignisse th { color:var(--gedaempft); font-weight:600; font-size:11px;
                   text-transform:uppercase; letter-spacing:.6px; }
  .ereignisse a { color:var(--text); text-decoration:none;
                  border-bottom:1px dotted var(--rand); }
  .art { color:#ffd479; }
  .fuss { margin-top:20px; font-size:12px; color:var(--gedaempft);
          max-width:760px; line-height:1.55; }
</style>
<div class="huelle">

<div class="kopf">
  <div class="paarung">
    <div class="team">
      <div class="teamname"><span class="punkt" style="background:var(--heim)"></span>__HEIM__</div>
      <div class="teamzeile">__HEIM_ZEILE__</div>
    </div>
    <div>
      <div class="stand" id="stand">0 : 0</div>
      <div class="minute" id="minute">0:00</div>
    </div>
    <div class="team rechts">
      <div class="teamname">__GAST__<span class="punkt" style="background:var(--gast);margin:0 0 0 6px"></span></div>
      <div class="teamzeile">__GAST_ZEILE__</div>
    </div>
  </div>
  <div class="settings">
    <h2>Parametrisierung der Simulation</h2>
    <table id="settings"></table>
  </div>
</div>

<div class="buehne">
  <div>
    <canvas id="c" width="1050" height="700"></canvas>
    <div class="leiste">
      <button id="play">Abspielen</button>
      <input type="range" id="zeit" min="0" max="0" value="0" step="1">
      <span class="uhr" id="uhr">0:00</span>
      <label><input type="checkbox" id="kontrolle"> Raumkontrolle</label>
      <label><input type="checkbox" id="spuren" checked> Spuren</label>
      <label>Tempo <select id="tempo">
        <option value="0.5">0,5x</option><option value="1" selected>1x</option>
        <option value="2">2x</option><option value="4">4x</option>
        <option value="8">8x</option></select></label>
    </div>
    <div class="ereignisse" id="ereignisse"></div>
    <div class="fuss">__FUSSNOTE__</div>
  </div>

  <div class="panel">
    <h2>Stand zum Zeitpunkt</h2>
    <div id="statistik"></div>
    <h2 class="spaeter">Laufdistanz</h2>
    <div id="laufen"></div>
  </div>
</div>
</div>

<script>
const DATEN = __DATEN__;
const F = __FELD__;

/* ============================================================ Spielfeld */
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const RAND = 28;
const sx = v => RAND + (v + F.L / 2) / F.L * (cv.width - 2 * RAND);
const sy = v => RAND + (v + F.B / 2) / F.B * (cv.height - 2 * RAND);
const sl = v => v / F.L * (cv.width - 2 * RAND);
const sh = v => v / F.B * (cv.height - 2 * RAND);

function feld() {
  ctx.fillStyle = '#1f7a3f'; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = 'rgba(255,255,255,.030)';
  for (let i = 0; i < 10; i += 2) {
    const x0 = sx(-F.L / 2 + i * F.L / 10), x1 = sx(-F.L / 2 + (i + 1) * F.L / 10);
    ctx.fillRect(x0, sy(-F.B / 2), x1 - x0, sh(F.B));
  }
  ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 1.6;
  ctx.strokeRect(sx(-F.L / 2), sy(-F.B / 2), sl(F.L), sh(F.B));
  ctx.beginPath(); ctx.moveTo(sx(0), sy(-F.B / 2)); ctx.lineTo(sx(0), sy(F.B / 2)); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx(0), sy(0), sl(F.KREIS), 0, 7); ctx.stroke();
  for (const s of [-1, 1]) {
    ctx.strokeRect(s < 0 ? sx(-F.L / 2) : sx(F.L / 2 - F.SR_T), sy(-F.SR_B),
                   sl(F.SR_T), sh(2 * F.SR_B));
    ctx.strokeRect(s < 0 ? sx(-F.L / 2) : sx(F.L / 2 - F.TR_T), sy(-F.TR_B),
                   sl(F.TR_T), sh(2 * F.TR_B));
    ctx.lineWidth = 3.4;
    ctx.beginPath();
    ctx.moveTo(sx(s * F.L / 2), sy(-F.TOR)); ctx.lineTo(sx(s * F.L / 2), sy(F.TOR));
    ctx.stroke(); ctx.lineWidth = 1.6;
  }
}

/* Ankunftszeit wie spieler.zeit_zu_punkt - Zweiphasenmodell mit Reaktion. */
function tZu(px, py, zx, zy) {
  const dx = zx - px, dy = zy - py, d = Math.hypot(dx, dy);
  let t = 0.22; if (d < 1e-6) return t;
  const vmax = 8.4, a = 10.0;
  const dA = vmax * vmax / (2 * a);
  t += d <= dA ? Math.sqrt(2 * d / a) : vmax / a + (d - dA) / vmax;
  return t;
}

/* Gefahrenflaeche wie raumkontrolle.gefahr. */
function gefahr(x, y, dir) {
  const d = Math.hypot(dir * F.L / 2 - x, y);
  const r = 0.52 * Math.exp(-d / 7.5) + 0.030 * Math.exp(-d / 28);
  const q = y / 22;
  return r * (0.45 + 0.55 * Math.exp(-q * q));
}

/* Kontrollanteil je Bild - fuer die Flaeche und fuer die Leiste rechts. */
function kontrolle(f, NX, NY, malen) {
  let flH = 0, flG = 0, gefH = 0, gefG = 0;
  const zelle = (F.L / NX) * (F.B / NY);
  for (let j = 0; j < NY; j++) {
    const y = -F.B / 2 + (j + 0.5) * F.B / NY;
    for (let i = 0; i < NX; i++) {
      const x = -F.L / 2 + (i + 0.5) * F.L / NX;
      let th = 1e9, tg = 1e9;
      for (let k = 0; k < 22; k++) {
        const t = tZu(f[1 + k * 2], f[2 + k * 2], x, y);
        if (k < 11) { if (t < th) th = t; } else { if (t < tg) tg = t; }
      }
      const p = 1 / (1 + Math.exp(-(tg - th) / 0.42));
      flH += p * zelle; flG += (1 - p) * zelle;
      gefH += p * zelle * gefahr(x, y, DATEN.richtung_heim);
      gefG += (1 - p) * zelle * gefahr(x, y, -DATEN.richtung_heim);
      if (malen) {
        const a = Math.abs(p - 0.5) * 0.62;
        ctx.fillStyle = p > 0.5 ? 'rgba(47,127,208,' + a + ')'
                                : 'rgba(224,72,79,' + a + ')';
        ctx.fillRect(sx(x - F.L / NX / 2), sy(y - F.B / NY / 2),
                     sl(F.L / NX) + 1, sh(F.B / NY) + 1);
      }
    }
  }
  return { flH, flG, gefH, gefG };
}

/* ============================================================== Zeichnen */
let i = 0, laeuft = false, letzte = 0;
const schieber = document.getElementById('zeit');
schieber.max = DATEN.bahn.length - 1;

function zeichne() {
  const f = DATEN.bahn[i];
  feld();
  const malen = document.getElementById('kontrolle').checked;
  const kk = kontrolle(f, malen ? 34 : 24, malen ? 22 : 15, malen);

  if (document.getElementById('spuren').checked) {
    for (let k = 0; k < 22; k++) {
      ctx.strokeStyle = k < 11 ? 'rgba(47,127,208,.5)' : 'rgba(224,72,79,.5)';
      ctx.lineWidth = 1.4; ctx.beginPath();
      const von = Math.max(0, i - 12);
      for (let j = von; j <= i; j++) {
        const g = DATEN.bahn[j];
        j === von ? ctx.moveTo(sx(g[1 + k * 2]), sy(g[2 + k * 2]))
                  : ctx.lineTo(sx(g[1 + k * 2]), sy(g[2 + k * 2]));
      }
      ctx.stroke();
    }
  }
  for (let k = 0; k < 22; k++) {
    const x = sx(f[1 + k * 2]), y = sy(f[2 + k * 2]);
    ctx.beginPath(); ctx.arc(x, y, 9, 0, 7);
    ctx.fillStyle = k < 11 ? '#2f7fd0' : '#e0484f'; ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 1.4; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = '600 10px sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(DATEN.nummern[k], x, y + .5);
  }
  const bz = f[47], bx = sx(f[45]), by = sy(f[46]);
  if (bz > 0.3) {
    ctx.beginPath(); ctx.ellipse(bx, by, 5, 2.5, 0, 0, 7);
    ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fill();
  }
  ctx.beginPath();
  ctx.arc(bx, by - Math.min(bz, 6) * 3.4, 5 + Math.min(bz, 6) * .5, 0, 7);
  ctx.fillStyle = '#fff'; ctx.fill();
  ctx.strokeStyle = '#222'; ctx.lineWidth = 1.2; ctx.stroke();

  panel(i, kk);
  schieber.value = i;
}

/* ================================================================ Panel */
const uhrText = t => Math.floor(t / 60) + ':' + String(Math.floor(t % 60)).padStart(2, '0');

function zeileHTML(name, h, g, anteilH) {
  const a = Math.max(0, Math.min(100, anteilH * 100));
  return '<div class="zeile"><div class="werte">' +
    '<b class="h">' + h + '</b><span class="name">' + name + '</span>' +
    '<b class="g">' + g + '</b></div>' +
    '<div class="balken"><i class="h" style="width:' + a.toFixed(1) + '%"></i>' +
    '<i class="g" style="width:' + (100 - a).toFixed(1) + '%"></i></div></div>';
}

function anteil(h, g) {
  const s = h + g;
  return s <= 0 ? 0.5 : h / s;
}

function panel(idx, kk) {
  const s = DATEN.stat[idx], t = DATEN.bahn[idx][0];
  document.getElementById('stand').textContent = s[0] + ' : ' + s[1];
  document.getElementById('minute').textContent = uhrText(t);
  document.getElementById('uhr').textContent = uhrText(t);

  const quote = (an, ges) => ges > 0 ? (an / ges * 100).toFixed(0) + ' %' : '–';
  const besitzH = s[18];
  let h = '';
  h += zeileHTML('Tore', s[0], s[1], anteil(s[0], s[1]));
  h += zeileHTML('xG', s[2].toFixed(2), s[3].toFixed(2), anteil(s[2], s[3]));
  h += zeileHTML('Schüsse', s[4], s[5], anteil(s[4], s[5]));
  h += zeileHTML('Kontakte im Strafraum', s[6], s[7], anteil(s[6], s[7]));
  h += zeileHTML('Pässe ins letzte Drittel', s[8], s[9], anteil(s[8], s[9]));
  h += zeileHTML('Strafraumeintritte', s[19], s[20], anteil(s[19], s[20]));
  h += zeileHTML('Pässe (angekommen)', s[14] + ' (' + quote(s[16], s[14]) + ')',
                 s[15] + ' (' + quote(s[17], s[15]) + ')', anteil(s[14], s[15]));
  h += zeileHTML('Ballbesitz', (besitzH * 100).toFixed(0) + ' %',
                 ((1 - besitzH) * 100).toFixed(0) + ' %', besitzH);
  h += zeileHTML('Abwehrhöhe (m)', s[10].toFixed(1), s[11].toFixed(1),
                 anteil(s[10], s[11]));
  h += zeileHTML('PPDA (niedriger = mehr Pressing)', s[12].toFixed(2),
                 s[13].toFixed(2), anteil(s[13], s[12]));
  h += zeileHTML('Raumkontrolle', (kk.flH / (kk.flH + kk.flG) * 100).toFixed(0) + ' %',
                 (kk.flG / (kk.flH + kk.flG) * 100).toFixed(0) + ' %',
                 anteil(kk.flH, kk.flG));
  h += zeileHTML('davon gefährlicher Raum', kk.gefH.toFixed(1), kk.gefG.toFixed(1),
                 anteil(kk.gefH, kk.gefG));
  document.getElementById('statistik').innerHTML = h;
  laufPanel(idx, t);
}

function laufPanel(idx, t) {
  const d = DATEN.dist[idx];
  const min = Math.max(t / 60, 1 / 60);
  let sumH = 0, sumG = 0;
  for (let k = 0; k < 11; k++) sumH += d[k];
  for (let k = 11; k < 22; k++) sumG += d[k];

  let h = zeileHTML('Gesamt (km)', (sumH / 1000).toFixed(2), (sumG / 1000).toFixed(2),
                    anteil(sumH, sumG));
  h += zeileHTML('je Minute und Spieler (m)', (sumH / 11 / min).toFixed(0),
                 (sumG / 11 / min).toFixed(0), anteil(sumH, sumG));

  h += '<details><summary>Einzelne Spieler</summary>' +
       '<table class="spieler"><tr><th class="l">Nr</th><th class="l">Rolle</th>' +
       '<th class="l">Name</th><th>km</th><th>m/min</th></tr>';
  for (let k = 0; k < 22; k++) {
    const farbe = k < 11 ? 'var(--heim)' : 'var(--gast)';
    h += '<tr' + (k === 11 ? ' class="trenn"' : '') + '>' +
         '<td class="nr l">' + DATEN.nummern[k] + '</td>' +
         '<td class="ro l">' + DATEN.rollen[k] + '</td>' +
         '<td class="l" style="color:' + farbe + '">' + DATEN.spielernamen[k] + '</td>' +
         '<td>' + (d[k] / 1000).toFixed(2) + '</td>' +
         '<td>' + (d[k] / min).toFixed(0) + '</td></tr>';
  }
  document.getElementById('laufen').innerHTML = h + '</table></details>';
}

/* =========================================================== Steuerung */
function takt(ms) {
  if (laeuft) {
    const tempo = parseFloat(document.getElementById('tempo').value);
    if (ms - letzte > DATEN.schritt * 1000 / tempo) {
      letzte = ms; i = (i + 1) % DATEN.bahn.length; zeichne();
    }
  }
  requestAnimationFrame(takt);
}
document.getElementById('play').onclick = e => {
  laeuft = !laeuft; e.target.textContent = laeuft ? 'Pause' : 'Abspielen';
};
schieber.oninput = e => { i = +e.target.value; zeichne(); };
document.getElementById('kontrolle').onchange = zeichne;
document.getElementById('spuren').onchange = zeichne;

/* ---------------------------------------------------- Einstellungstabelle */
(function () {
  let h = '';
  for (const [k, vh, vg] of DATEN.settings) {
    if (vg === '') {           // gilt fuer beide Seiten - eine Zeile, kein Umbruch
      h += '<tr class="voll"><td class="k" colspan="3">' + k + ': ' + vh + '</td></tr>';
    } else {
      h += '<tr><td class="k">' + k + '</td><td class="h">' + vh +
           '</td><td class="g">' + vg + '</td></tr>';
    }
  }
  document.getElementById('settings').innerHTML = h;
})();

/* ------------------------------------------------------------ Ereignisse */
if (DATEN.ereignisse.length) {
  let h = '<table><tr><th>Zeit</th><th>Ereignis</th><th>Team</th><th>Spieler</th></tr>';
  for (const e of DATEN.ereignisse) {
    h += '<tr><td><a href="#" data-t="' + e.zeit + '">' + uhrText(e.zeit) + '</a></td>' +
         '<td class="art">' + e.art + '</td>' +
         '<td style="color:' + (e.team === 0 ? 'var(--heim)' : 'var(--gast)') + '">' +
         (e.team === null ? '' : DATEN.namen[e.team]) + '</td>' +
         '<td>' + (e.spieler || '') + '</td></tr>';
  }
  document.getElementById('ereignisse').innerHTML = h + '</table>';
  document.querySelectorAll('#ereignisse a').forEach(a => a.onclick = ev => {
    ev.preventDefault();
    const z = +a.dataset.t;
    i = Math.max(0, Math.min(DATEN.bahn.length - 1,
        Math.round((z - DATEN.bahn[0][0]) / DATEN.schritt) - 8));
    zeichne();
  });
}

zeichne(); requestAnimationFrame(takt);
</script>
"""


def _settings_zeilen(sp):
    """Zeilen der Parametertabelle: was war eingestellt, als das lief.

    Ohne diese Tabelle ist eine Aufzeichnung nicht nachvollziehbar - man sieht
    zwar, was passiert ist, aber nicht, unter welchen Annahmen.
    """
    a0, a1 = sp.lage.anweisung[0], sp.lage.anweisung[1]
    return [
        ("Formation", a0.formation, a1.formation),
        ("Abwehrhöhe", "%.0f m" % a0.abwehrhoehe, "%.0f m" % a1.abwehrhoehe),
        ("Pressing / Auslöser", "%.2f / %.0f m" % (a0.pressing, a0.pressing_ausloeser),
         "%.2f / %.0f m" % (a1.pressing, a1.pressing_ausloeser)),
        ("Kompaktheit", "%.2f" % a0.kompaktheit, "%.2f" % a1.kompaktheit),
        ("Breite im Ballbesitz", "%.0f m" % a0.breite, "%.0f m" % a1.breite),
        ("Tempo / Risiko", "%.2f / %.2f" % (a0.tempo, a0.risiko),
         "%.2f / %.2f" % (a1.tempo, a1.risiko)),
        ("Gegenpressing", "%.2f" % a0.gegenpressing, "%.2f" % a1.gegenpressing),
        ("Manndeckungsanteil", "%.2f" % a0.manndeckung, "%.2f" % a1.manndeckung),
        ("Außen aufrücken", "%.2f" % a0.aufruecken_aussen,
         "%.2f" % a1.aufruecken_aussen),
        ("Nach außen lenken", "%.2f" % a0.lenken, "%.2f" % a1.lenken),
        ("mittleres Spitzentempo",
         "%.2f m/s" % (sum(s.attribute.v_max for s in sp.lage.mannschaft[0]) / 11),
         "%.2f m/s" % (sum(s.attribute.v_max for s in sp.lage.mannschaft[1]) / 11)),
        ("Simulation", "%.0f Hz Zeitschritt · Startwert %d · %.0f min gerechnet"
         % (1.0 / sp.dt, sp.seed, sp.lage.zeit / 60.0), ""),
    ]


def html_bauen(sp, pfad, titel=None, heim_name="Heim", gast_name="Gast",
               nur_ereignisse=("tor", "schuss", "parade", "elfmeter", "abseits")):
    """Aufzeichnung eines `spiel.Spiel` als eigenstaendige HTML-Datei."""
    if not sp.bahn:
        raise ValueError("keine Aufzeichnung vorhanden - Spiel mit "
                         "aufzeichnen=True laufen lassen")
    if len(sp.stat) != len(sp.bahn) or len(sp.dist) != len(sp.bahn):
        raise ValueError("Statistik- und Positionsspur passen nicht zusammen")

    b = sp.bericht()
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
        "settings": _settings_zeilen(sp),
        "bericht": b,
    }
    a0, a1 = sp.lage.anweisung[0], sp.lage.anweisung[1]
    ersatz = {
        "__TITEL__": titel or ("%s – %s  %d:%d" % (heim_name, gast_name,
                                                   b["tore"][0], b["tore"][1])),
        "__HEIM__": heim_name,
        "__GAST__": gast_name,
        "__HEIM_ZEILE__": "%s · Abwehrhöhe %.0f m · Pressing %.2f"
                          % (a0.formation, a0.abwehrhoehe, a0.pressing),
        "__GAST_ZEILE__": "%s · Abwehrhöhe %.0f m · Pressing %.2f"
                          % (a1.formation, a1.abwehrhoehe, a1.pressing),
        "__FUSSNOTE__": (
            "Alle Werte sind gezählte Ereignisse aus der räumlich-zeitlichen "
            "Simulation, nicht gezogene Zufallszahlen; die Leiste rechts zeigt "
            "den Stand zum angezeigten Zeitpunkt. Raumkontrolle und gefährlicher "
            "Raum werden im Browser aus denselben Ankunftszeiten berechnet wie "
            "in der Engine. Absolute Schuss- und Torzahlen liegen noch deutlich "
            "über realen Werten – siehe Abschnitt „Kalibrierungsstand“ in der "
            "README des Moduls."),
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
