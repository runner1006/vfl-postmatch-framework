"""Bahnaufzeichnung als eigenstaendige HTML-Animation.

Erzeugt eine einzelne Datei ohne externe Requests - dieselbe Regel wie beim
Dashboard des Analyseteils. Doppelklick genuegt.

Dargestellt wird, was die Simulation wirklich gerechnet hat: Positionen aller
22 Agenten und des Balls im Zeitverlauf. Zuschaltbar ist die Raumkontrolle als
Flaeche - sie wird im Browser aus denselben Ankunftszeiten berechnet wie in der
Engine, damit Bild und Modell nicht auseinanderlaufen.

Der Weg zu synthetischem Videomaterial fuehrt ueber genau diese Daten: eine
Bahnaufzeichnung mit 25 Hz ist das, was ein Renderer als Eingabe braucht. Was
hier fehlt, ist die Darstellung - nicht die Simulation.
"""
import json
import os

import konfig as K

_KOPF = """<!doctype html>
<meta charset="utf-8">
<title>%(titel)s</title>
<style>
  :root {
    --gruen: #1f7a3f; --linie: rgba(255,255,255,.75);
    --heim: #005ca9; --gast: #d8232a; --grund: #10151c; --text: #e9eef4;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--grund); color: var(--text);
         font: 14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { padding: 14px 18px 8px; }
  h1 { font-size: 17px; margin: 0 0 2px; font-weight: 620; }
  .sub { color: #93a3b5; font-size: 12.5px; }
  .wrap { padding: 0 18px 18px; max-width: 1180px; }
  canvas { width: 100%%; height: auto; display: block; border-radius: 6px;
           background: var(--gruen); }
  .leiste { display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
            margin: 10px 0 6px; }
  button { background: #1d2733; color: var(--text); border: 1px solid #2c3a4a;
           border-radius: 5px; padding: 5px 12px; font: inherit; cursor: pointer; }
  button:hover { background: #26333f; }
  input[type=range] { flex: 1 1 320px; min-width: 220px; }
  label { display: inline-flex; gap: 5px; align-items: center; font-size: 13px;
          color: #b9c6d4; }
  .uhr { font-variant-numeric: tabular-nums; min-width: 74px; }
  table { border-collapse: collapse; font-size: 13px; margin-top: 14px; }
  th, td { text-align: left; padding: 3px 14px 3px 0; }
  th { color: #93a3b5; font-weight: 560; }
  .ereignis { color: #ffd479; }
</style>
<header>
  <h1>%(titel)s</h1>
  <div class="sub">%(untertitel)s</div>
</header>
<div class="wrap">
<canvas id="c" width="1050" height="680"></canvas>
<div class="leiste">
  <button id="play">Abspielen</button>
  <input type="range" id="zeit" min="0" max="0" value="0" step="1">
  <span class="uhr" id="uhr">0:00</span>
  <label><input type="checkbox" id="kontrolle"> Raumkontrolle</label>
  <label><input type="checkbox" id="spuren" checked> Spuren</label>
  <label>Tempo <select id="tempo">
    <option value="0.5">0,5x</option><option value="1" selected>1x</option>
    <option value="2">2x</option><option value="4">4x</option></select></label>
</div>
<div id="ereignisse"></div>
</div>
<script>
const DATEN = """

_FUSS = """;
const F = { L: %(L)s, B: %(B)s, TOR: %(TOR)s, SR_T: %(SR_T)s, SR_B: %(SR_B)s,
            TR_T: %(TR_T)s, TR_B: %(TR_B)s, KREIS: %(KREIS)s };

const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const RAND = 28;
const sx = v => RAND + (v + F.L / 2) / F.L * (cv.width - 2 * RAND);
const sy = v => RAND + (v + F.B / 2) / F.B * (cv.height - 2 * RAND);
const sl = v => v / F.L * (cv.width - 2 * RAND);

function feld() {
  ctx.fillStyle = '#1f7a3f'; ctx.fillRect(0, 0, cv.width, cv.height);
  // Rasenstreifen
  ctx.fillStyle = 'rgba(255,255,255,.030)';
  for (let i = 0; i < 10; i += 2) {
    const x0 = sx(-F.L / 2 + i * F.L / 10), x1 = sx(-F.L / 2 + (i + 1) * F.L / 10);
    ctx.fillRect(x0, sy(-F.B / 2), x1 - x0, sy(F.B / 2) - sy(-F.B / 2));
  }
  ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 1.6;
  ctx.strokeRect(sx(-F.L / 2), sy(-F.B / 2), sl(F.L), sy(F.B / 2) - sy(-F.B / 2));
  ctx.beginPath(); ctx.moveTo(sx(0), sy(-F.B / 2)); ctx.lineTo(sx(0), sy(F.B / 2)); ctx.stroke();
  ctx.beginPath(); ctx.arc(sx(0), sy(0), sl(F.KREIS), 0, 7); ctx.stroke();
  for (const s of [-1, 1]) {
    const x = s < 0 ? sx(-F.L / 2) : sx(F.L / 2 - F.SR_T);
    ctx.strokeRect(x, sy(-F.SR_B), sl(F.SR_T), sy(F.SR_B) - sy(-F.SR_B));
    const x2 = s < 0 ? sx(-F.L / 2) : sx(F.L / 2 - F.TR_T);
    ctx.strokeRect(x2, sy(-F.TR_B), sl(F.TR_T), sy(F.TR_B) - sy(-F.TR_B));
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(sx(s * F.L / 2), sy(-F.TOR)); ctx.lineTo(sx(s * F.L / 2), sy(F.TOR));
    ctx.stroke(); ctx.lineWidth = 1.6;
  }
}

// Ankunftszeit wie in spieler.zeit_zu_punkt (Zweiphasenmodell)
function tZu(px, py, vx, vy, zx, zy) {
  const dx = zx - px, dy = zy - py, d = Math.hypot(dx, dy);
  let t = 0.22; if (d < 1e-6) return t;
  const vmax = 8.4, a = 10.0, tempo = Math.hypot(vx, vy);
  let v0 = tempo > 0.15 ? tempo * ((vx * dx + vy * dy) / (tempo * d)) : 0;
  if (v0 < 0) { t += -v0 / 8.6; v0 = 0; }
  const dA = (vmax * vmax - v0 * v0) / (2 * a);
  t += d <= dA ? (-v0 + Math.sqrt(v0 * v0 + 2 * a * d)) / a
                : (vmax - v0) / a + (d - dA) / vmax;
  return t;
}

function kontrollflaeche(f) {
  const NX = 34, NY = 22;
  for (let j = 0; j < NY; j++) {
    const y = -F.B / 2 + (j + 0.5) * F.B / NY;
    for (let i = 0; i < NX; i++) {
      const x = -F.L / 2 + (i + 0.5) * F.L / NX;
      let th = 1e9, tg = 1e9;
      for (let k = 0; k < 22; k++) {
        const px = f[1 + k * 2], py = f[2 + k * 2];
        const t = tZu(px, py, 0, 0, x, y);
        if (k < 11) { if (t < th) th = t; } else { if (t < tg) tg = t; }
      }
      const p = 1 / (1 + Math.exp(-(tg - th) / 0.42));
      const a = Math.abs(p - 0.5) * 0.62;
      ctx.fillStyle = p > 0.5 ? `rgba(0,92,169,${a})` : `rgba(216,35,42,${a})`;
      ctx.fillRect(sx(x - F.L / NX / 2), sy(y - F.B / NY / 2),
                   sl(F.L / NX) + 1, (sy(F.B / NY) - sy(0)) + 1);
    }
  }
}

let i = 0, laeuft = false, letzte = 0;
const schieber = document.getElementById('zeit');
schieber.max = DATEN.bahn.length - 1;

function zeichne() {
  const f = DATEN.bahn[i];
  feld();
  if (document.getElementById('kontrolle').checked) kontrollflaeche(f);
  if (document.getElementById('spuren').checked) {
    for (let k = 0; k < 22; k++) {
      ctx.strokeStyle = k < 11 ? 'rgba(0,92,169,.45)' : 'rgba(216,35,42,.45)';
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
    ctx.fillStyle = k < 11 ? '#005ca9' : '#d8232a'; ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.lineWidth = 1.4; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = '600 10px sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(DATEN.nummern[k], x, y + .5);
  }
  const bz = f[45 + 2];
  const bx = sx(f[45]), by = sy(f[46]);
  if (bz > 0.3) {
    ctx.beginPath(); ctx.ellipse(bx, by, 5, 2.5, 0, 0, 7);
    ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fill();
  }
  ctx.beginPath(); ctx.arc(bx, by - Math.min(bz, 6) * 3.4, 5 + Math.min(bz, 6) * .5, 0, 7);
  ctx.fillStyle = '#fff'; ctx.fill();
  ctx.strokeStyle = '#222'; ctx.lineWidth = 1.2; ctx.stroke();

  const t = f[0];
  document.getElementById('uhr').textContent =
    Math.floor(t / 60) + ':' + String(Math.floor(t %% 60)).padStart(2, '0');
  schieber.value = i;
}

function takt(ms) {
  if (laeuft) {
    const tempo = parseFloat(document.getElementById('tempo').value);
    if (ms - letzte > DATEN.schritt * 1000 / tempo) {
      letzte = ms; i = (i + 1) %% DATEN.bahn.length; zeichne();
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

if (DATEN.ereignisse.length) {
  let h = '<table><tr><th>Zeit</th><th>Ereignis</th><th>Team</th><th>Spieler</th></tr>';
  for (const e of DATEN.ereignisse) {
    const m = Math.floor(e.zeit / 60) + ':' + String(Math.floor(e.zeit %% 60)).padStart(2, '0');
    h += `<tr><td><a href="#" data-t="${e.zeit}">${m}</a></td>` +
         `<td class="ereignis">${e.art}</td><td>${e.team === null ? '' : DATEN.namen[e.team]}</td>` +
         `<td>${e.spieler || ''}</td></tr>`;
  }
  document.getElementById('ereignisse').innerHTML = h + '</table>';
  document.querySelectorAll('#ereignisse a').forEach(a => a.onclick = ev => {
    ev.preventDefault();
    const z = +a.dataset.t;
    i = Math.max(0, Math.min(DATEN.bahn.length - 1,
        Math.round(z / DATEN.schritt) - 8));
    zeichne();
  });
}
zeichne(); requestAnimationFrame(takt);
</script>
"""


def html_bauen(sp, pfad, titel="Simuliertes Spiel", untertitel=None,
               nur_ereignisse=("tor", "schuss", "parade", "elfmeter", "abseits")):
    """Aufzeichnung eines `spiel.Spiel` als eigenstaendige HTML-Datei."""
    if not sp.bahn:
        raise ValueError("keine Aufzeichnung vorhanden - Spiel mit "
                         "aufzeichnen=True laufen lassen")
    nummern = [s.nummer for elf in sp.lage.mannschaft for s in elf]
    namen = ["Heim", "Gast"]
    ereignisse = [e.als_dict() for e in sp.ereignisse if e.art in nur_ereignisse]
    daten = {
        "bahn": sp.bahn,
        "nummern": nummern,
        "namen": namen,
        "schritt": round(sp.dt * sp.rate, 3),
        "ereignisse": ereignisse,
        "bericht": sp.bericht(),
    }
    if untertitel is None:
        b = daten["bericht"]
        untertitel = ("%d:%d &middot; xG %.2f:%.2f &middot; %d Bilder mit %.0f Hz"
                      % (b["tore"][0], b["tore"][1], b["xg"][0], b["xg"][1],
                         len(sp.bahn), 1.0 / (sp.dt * sp.rate)))
    kopf = _KOPF % dict(titel=titel, untertitel=untertitel)
    fuss = _FUSS % dict(L=K.FELD_LAENGE, B=K.FELD_BREITE, TOR=K.TOR_HALB_BREITE,
                        SR_T=K.STRAFRAUM_TIEFE, SR_B=K.STRAFRAUM_HALB_BREITE,
                        TR_T=K.TORRAUM_TIEFE, TR_B=K.TORRAUM_HALB_BREITE,
                        KREIS=K.ANSTOSSKREIS)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(kopf)
        json.dump(daten, f, separators=(",", ":"))
        f.write(fuss)
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
            },
            "bahn": sp.bahn,
            "ereignisse": [e.als_dict() for e in sp.ereignisse],
        }, f, separators=(",", ":"))
    return pfad
