/* Scout League - Frontend. Kein Build, kein Framework: eine Datei, die der
   Server so ausliefert, wie sie hier steht. */
"use strict";

const S = {
  code: localStorage.getItem("sl_code") || "",
  name: "",
  daten: null,          // Antwort von /api/pack
  fall: null,           // aktuell geoeffneter Fall
  entwurf: null,        // {antworten, prognosen, notiz}
  begonnen: 0,
};

const $ = (s) => document.querySelector(s);
const el = (s) => document.getElementById(s);

function esc(t) {
  return String(t == null ? "" : t).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function zahl(v, n = 1, fallback = "–") {
  return (v === null || v === undefined || Number.isNaN(v))
    ? fallback : Number(v).toFixed(n);
}

/* Prognoseschluessel auf den Fragetext - das Leaderboard ist auch fuer
   Leute lesbar, die den Fragebogen nicht kennen. */
function prognoseLabel(key) {
  const fb = S.daten && S.daten.fragebogen;
  const p = fb && fb.prognosen.find((x) => x.key === key);
  return p ? p.label : key;
}

async function api(pfad, optionen = {}) {
  const kopf = Object.assign({ "Content-Type": "application/json" },
                             optionen.headers || {});
  if (S.code) kopf["X-Scout-Code"] = S.code;
  const r = await fetch(pfad, Object.assign({}, optionen, { headers: kopf }));
  const text = await r.text();
  let daten = null;
  try { daten = text ? JSON.parse(text) : null; } catch (e) { daten = null; }
  if (!r.ok) throw new Error((daten && daten.fehler) || `Fehler ${r.status}`);
  return daten;
}

function meldung(ziel, text, art = "fehler") {
  el(ziel).innerHTML = text
    ? `<div class="meldung ${art}">${esc(text)}</div>` : "";
}

/* --------------------------------------------------------------- Navigation */
const TABS = ["pack", "fall", "profil", "liga"];

function zeige(tab) {
  TABS.forEach((t) => { el("tab-" + t).hidden = (t !== tab); });
  el("anmeldung").hidden = true;
  el("kopf").hidden = false;
  document.querySelectorAll("#kopf nav button").forEach((b) => {
    b.setAttribute("aria-current", String(b.dataset.tab === tab));
  });
  window.scrollTo(0, 0);
}

document.querySelectorAll("#kopf nav button").forEach((b) => {
  b.addEventListener("click", () => {
    if (b.dataset.tab === "abmelden") return abmelden();
    if (b.dataset.tab === "profil") return profilLaden();
    if (b.dataset.tab === "liga") return ligaLaden();
    packLaden();
  });
});

el("zurueck").addEventListener("click", () => packLaden());

function abmelden() {
  localStorage.removeItem("sl_code");
  location.reload();
}

/* --------------------------------------------------------------- Anmeldung */
el("anmeldeform").addEventListener("submit", async (e) => {
  e.preventDefault();
  const code = el("code").value.trim().toUpperCase();
  if (!code) return;
  try {
    S.code = code;
    const r = await api("/api/anmelden", {
      method: "POST", body: JSON.stringify({ code }),
    });
    S.name = r.name;
    localStorage.setItem("sl_code", code);
    el("wer").textContent = "· " + r.name;
    packLaden();
  } catch (err) {
    S.code = "";
    meldung("anmeldefehler", err.message);
  }
});

/* --------------------------------------------------------------- Case Pack */
async function packLaden() {
  try {
    S.daten = await api("/api/pack");
  } catch (err) {
    if (String(err.message).includes("Scout-Code")) return abmelden();
    zeige("pack");
    el("falliste").innerHTML = "";
    return meldung("packmeldung", err.message);
  }
  const d = S.daten;
  el("packtitel").textContent = d.pack.titel;
  const fertig = d.faelle.filter((f) => f.eigene_bewertung.abgegeben).length;
  el("packsub").textContent =
    `${fertig} von ${d.faelle.length} abgegeben`
    + (d.pack.status === "offen" ? "" : " · Pack geschlossen");
  meldung("packmeldung",
    fertig === d.faelle.length && d.faelle.length
      ? "Pack vollständig. Deine Prognosen lösen wir auf, sobald die Realität geantwortet hat."
      : "", "ok");

  el("falliste").innerHTML = d.faelle.map((f, i) => `
    <button class="fallzeile" data-fall="${f.id}">
      <span class="nr mono">${i + 1}</span>
      <span class="txt">
        <span class="name">${esc(f.name)}</span>
        <span class="meta">${esc([f.position, f.jahrgang, f.verein]
          .filter(Boolean).join(" · "))}</span>
      </span>
      <span class="abzeichen ${f.eigene_bewertung.abgegeben ? "gut" : "offen"}">
        ${f.eigene_bewertung.abgegeben ? "abgegeben" : "offen"}</span>
    </button>`).join("");

  document.querySelectorAll("[data-fall]").forEach((b) => {
    b.addEventListener("click", () => fallOeffnen(Number(b.dataset.fall)));
  });
  zeige("pack");
}

/* -------------------------------------------------------------- Ein Fall */
function fallOeffnen(id) {
  S.fall = S.daten.faelle.find((f) => f.id === id);
  S.entwurf = {
    antworten: Object.assign({}, S.fall.eigene_bewertung.antworten),
    prognosen: Object.assign({}, S.fall.eigene_bewertung.prognosen),
    notiz: S.fall.eigene_bewertung.notiz || "",
  };
  S.begonnen = Date.now();
  fallZeichnen();
  zeige("fall");
}

function videoBlock(url) {
  if (!url || !/^https:\/\//i.test(url)) return "";
  const sicher = esc(url);
  if (/\.(mp4|webm|mov)(\?|$)/i.test(url)) {
    return `<div class="video"><video controls preload="metadata"
              src="${sicher}"></video></div>`;
  }
  return `<div class="video"><iframe src="${sicher}" loading="lazy"
            referrerpolicy="no-referrer"
            allow="accelerometer; encrypted-media; picture-in-picture"
            allowfullscreen></iframe></div>`;
}

function indexBlock(indizes, fragen) {
  const eintraege = fragen
    .filter((q) => indizes[q.key] !== undefined && indizes[q.key] !== null)
    .map((q) => ({ label: q.label, wert: Number(indizes[q.key]) }));
  if (!eintraege.length) return "";
  return `<h3>Aggregierte Indizes</h3>
    <div class="indizes">${eintraege.map((e) => `
      <div class="indexzeile">
        <span class="muted">${esc(e.label)}</span>
        <span class="balken"><i style="width:${Math.max(0, Math.min(100, e.wert))}%"></i></span>
        <span class="mono" style="text-align:right">${Math.round(e.wert)}</span>
      </div>`).join("")}</div>
    <p class="klein muted" style="margin-top:8px">Skala 0&ndash;100, positionsnormiert.
    Eigene Indizes, keine Rohdaten.</p>`;
}

function fallZeichnen() {
  const f = S.fall;
  const fb = S.daten.fragebogen;
  const gesperrt = f.eigene_bewertung.abgegeben || S.daten.pack.status !== "offen";

  const steckbrief = [
    ["Position", f.position], ["Jahrgang", f.jahrgang],
    ["Verein", f.verein], ["Liga", f.liga], ["Fuß", f.fuss],
  ].filter(([, v]) => v).map(([k, v]) =>
    `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("");

  const gruppen = [];
  fb.bewertung.fragen.forEach((q) => {
    const g = q.gruppe || "";
    if (!gruppen.length || gruppen[gruppen.length - 1].name !== g) {
      gruppen.push({ name: g, fragen: [] });
    }
    gruppen[gruppen.length - 1].fragen.push(q);
  });

  const fragenHtml = gruppen.map((g) => `
    ${g.name ? `<h3>${esc(g.name)}</h3>` : ""}
    ${g.fragen.map((q) => `
      <div class="frage">
        <div class="label">${esc(q.label)}</div>
        <div class="anker"><span>1 &ndash; ${esc(q.anker1 || "")}</span>
                           <span>${esc(q.anker5 || "")} &ndash; 5</span></div>
        <div class="skala" data-frage="${esc(q.key)}">
          ${[1, 2, 3, 4, 5].map((n) => `
            <button type="button" data-wert="${n}"
              aria-pressed="${S.entwurf.antworten[q.key] === n}"
              ${gesperrt ? "disabled" : ""}>${n}</button>`).join("")}
        </div>
      </div>`).join("")}`).join("");

  const prognosenHtml = fb.prognosen.map((p) => {
    const param = p.parameter ? (f.parameter || {})[p.parameter] : null;
    const wert = S.entwurf.prognosen[p.key];
    const prozent = wert === undefined ? 50 : Math.round(wert * 100);
    return `<div class="prognose" data-prognose="${esc(p.key)}">
      <div class="kopfzeile">
        <div>
          <div class="label" style="font-weight:600">${esc(p.label)}${
            param ? " &mdash; " + esc(param) : ""}</div>
          <div class="klein muted">${esc(p.erlaeuterung || "")}</div>
        </div>
        <div class="wert mono">${wert === undefined ? "–" : prozent + "%"}</div>
      </div>
      <input type="range" min="0" max="100" step="5" value="${prozent}"
             ${gesperrt ? "disabled" : ""}>
    </div>`;
  }).join("");

  el("fallinhalt").innerHTML = `
    <h1>${esc(f.name)}</h1>
    <p class="sub">${esc([f.position, f.jahrgang, f.verein, f.liga]
      .filter(Boolean).join(" · "))}</p>

    <div class="karte">
      <dl class="steckbrief" style="margin-top:0">${steckbrief}</dl>
      ${videoBlock(f.video_url)}
      ${indexBlock(f.indizes, fb.bewertung.fragen)}
    </div>

    <div id="rueckmeldung"></div>

    <div class="karte">
      <h2 style="margin-top:0">Bewertung</h2>
      <p class="klein muted">Nutze die ganze Skala. Wer überall die 3 vergibt,
      erzeugt keine Information &mdash; das Profil zeigt dir das.</p>
      ${fragenHtml}
    </div>

    <div class="karte">
      <h2 style="margin-top:0">Prognosen</h2>
      <p class="klein muted">Wie wahrscheinlich ist das? 0&nbsp;% heißt sicher nicht,
      100&nbsp;% heißt sicher ja. Bewertet wird mit dem Brier-Score &mdash;
      übertriebene Sicherheit kostet mehr, als sie einbringt.</p>
      ${prognosenHtml}
    </div>

    <div class="karte">
      <label class="klein muted" for="notiz">${esc(fb.notiz.label)}</label>
      <textarea id="notiz" maxlength="${fb.notiz.max_zeichen}"
        ${gesperrt ? "disabled" : ""}>${esc(S.entwurf.notiz)}</textarea>
    </div>

    <div id="fallmeldung"></div>
    ${gesperrt ? `<p class="klein muted">Abgegeben am
        ${esc((f.eigene_bewertung.geaendert_am || "").replace("T", " ").slice(0, 16))}
        &mdash; Bewertungen bleiben danach gesperrt.</p>`
      : `<div class="reihe">
           <button class="knopf" id="abgeben">Abgeben</button>
           <button class="knopf leise" id="speichern">Zwischenstand sichern</button>
           <span class="klein muted" id="fortschritt"></span>
         </div>
         <p class="klein muted" style="margin-top:10px">Nach der Abgabe siehst du
         die Modellerwartung. Vorher bleibt sie verborgen &mdash; sonst wäre die
         Modell-Nähe kein Maß, sondern eine Vorlage.</p>`}
  `;

  if (f.eigene_bewertung.abgegeben) rueckmeldungZeichnen(f.rueckmeldung, f.modell);
  fallVerdrahten(gesperrt);
}

function fallVerdrahten(gesperrt) {
  if (gesperrt) return;

  document.querySelectorAll(".skala").forEach((skala) => {
    skala.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-wert]");
      if (!b) return;
      const key = skala.dataset.frage;
      const wert = Number(b.dataset.wert);
      S.entwurf.antworten[key] = wert;
      skala.querySelectorAll("button").forEach((x) => {
        x.setAttribute("aria-pressed", String(Number(x.dataset.wert) === wert));
      });
      fortschritt();
    });
  });

  document.querySelectorAll(".prognose").forEach((box) => {
    const range = box.querySelector("input[type=range]");
    const anzeige = box.querySelector(".wert");
    const setzen = () => {
      S.entwurf.prognosen[box.dataset.prognose] = Number(range.value) / 100;
      anzeige.textContent = range.value + "%";
      fortschritt();
    };
    range.addEventListener("input", setzen);
    range.addEventListener("change", setzen);
  });

  const notiz = el("notiz");
  if (notiz) notiz.addEventListener("input", () => { S.entwurf.notiz = notiz.value; });

  el("speichern").addEventListener("click", () => senden(false));
  el("abgeben").addEventListener("click", () => senden(true));
  fortschritt();
}

function fortschritt() {
  const fb = S.daten.fragebogen;
  const a = fb.bewertung.fragen.filter(
    (q) => S.entwurf.antworten[q.key] !== undefined).length;
  const p = fb.prognosen.filter(
    (q) => S.entwurf.prognosen[q.key] !== undefined).length;
  const voll = a === fb.bewertung.fragen.length && p === fb.prognosen.length;
  const box = el("fortschritt");
  if (box) {
    box.textContent = `${a}/${fb.bewertung.fragen.length} Bewertungen · `
      + `${p}/${fb.prognosen.length} Prognosen`;
  }
  const knopf = el("abgeben");
  if (knopf) knopf.disabled = !voll;
}

async function senden(abgeben) {
  meldung("fallmeldung", "");
  try {
    const r = await api("/api/bewertung", {
      method: "POST",
      body: JSON.stringify({
        fall_id: S.fall.id,
        antworten: S.entwurf.antworten,
        prognosen: S.entwurf.prognosen,
        notiz: S.entwurf.notiz,
        sekunden: Math.round((Date.now() - S.begonnen) / 1000),
        abgeben: abgeben,
      }),
    });
    if (!abgeben) return meldung("fallmeldung", "Zwischenstand gesichert.", "ok");

    // Der Entwurf ist ab jetzt der Bestand - die Rueckmeldungstabelle liest
    // aus eigene_bewertung, nicht aus dem Entwurf.
    S.fall.eigene_bewertung.antworten = Object.assign({}, S.entwurf.antworten);
    S.fall.eigene_bewertung.prognosen = Object.assign({}, S.entwurf.prognosen);
    S.fall.eigene_bewertung.notiz = S.entwurf.notiz;
    S.fall.eigene_bewertung.abgegeben = true;
    S.fall.eigene_bewertung.geaendert_am = new Date().toISOString();
    S.fall.modell = r.modell;
    S.fall.rueckmeldung = r.rueckmeldung;
    fallZeichnen();
    meldung("fallmeldung", "Abgegeben.", "ok");
  } catch (err) {
    meldung("fallmeldung", err.message);
  }
}

function rueckmeldungZeichnen(r, modell) {
  if (!r) return;
  const fb = S.daten.fragebogen;
  const mb = (modell && modell.bewertung) || {};
  const mp = (modell && modell.prognose) || {};
  const antw = S.fall.eigene_bewertung.antworten;
  const prog = S.fall.eigene_bewertung.prognosen;
  const koh = r.kohorte;

  const zeilen = fb.bewertung.fragen.map((q) => {
    const du = antw[q.key];
    const m = mb[q.key];
    const k = koh && koh.mittel ? koh.mittel[q.key] : null;
    return `<tr><td>${esc(q.label)}</td>
      <td class="zahl">${du === undefined ? "–" : du}</td>
      <td class="zahl">${m === undefined ? "–" : zahl(m, 1)}</td>
      <td class="zahl muted">${k === null || k === undefined ? "–" : zahl(k, 1)}</td></tr>`;
  }).join("");

  const progZeilen = fb.prognosen.map((p) => {
    const du = prog[p.key];
    const m = mp[p.key];
    return `<tr><td>${esc(p.label)}</td>
      <td class="zahl">${du === undefined ? "–" : Math.round(du * 100) + "%"}</td>
      <td class="zahl">${m === undefined ? "–" : Math.round(m * 100) + "%"}</td>
      <td class="zahl muted">offen</td></tr>`;
  }).join("");

  el("rueckmeldung").innerHTML = `
    <div class="karte">
      <h2 style="margin-top:0">Sofort-Rückmeldung</h2>
      <div class="kennzahl">
        <div><div class="k">MODELL-NÄHE</div>
             <div class="v">${zahl(r.modell_naehe, 0)}</div>
             <div class="n">0&ndash;100, Bewertung</div></div>
        <div><div class="k">PROGNOSE-NÄHE</div>
             <div class="v">${zahl(r.prognose_naehe, 0)}</div>
             <div class="n">0&ndash;100, gegen Modell</div></div>
      </div>
      <p class="klein muted" style="margin-top:10px">Nähe ist kein Gütemaß.
      Wer vom Modell abweicht und recht behält, gewinnt die Liga &mdash;
      entschieden wird sie über den Brier-Score gegen die Realität.</p>
      <div class="scroll"><table class="vergleich">
        <tr><th>Bewertung</th><th class="zahl">Du</th><th class="zahl">Modell</th>
            <th class="zahl">Feld</th></tr>
        ${zeilen}
        <tr><th style="padding-top:14px">Prognose</th>
            <th class="zahl" style="padding-top:14px">Du</th>
            <th class="zahl" style="padding-top:14px">Modell</th>
            <th class="zahl" style="padding-top:14px">Realität</th></tr>
        ${progZeilen}
      </table></div>
      ${koh ? `<p class="klein muted">Feld = Mittel aus ${koh.n} Abgaben.</p>`
            : `<p class="klein muted">Der Feldvergleich erscheint ab drei Abgaben
               zu diesem Fall.</p>`}
    </div>`;
}

/* ---------------------------------------------------------------- Profil */
async function profilLaden() {
  zeige("profil");
  el("profilinhalt").innerHTML = `<p class="muted">Lädt …</p>`;
  let p;
  try { p = await api("/api/profil"); }
  catch (err) { return el("profilinhalt").innerHTML =
    `<div class="meldung fehler">${esc(err.message)}</div>`; }

  const v = p.verteilung || {};
  const max = Math.max(1, ...Object.values(v));
  const balken = Object.keys(v).sort().map((k) =>
    `<div style="height:${Math.round((v[k] / max) * 100)}%"><b>${v[k] || ""}</b></div>`
  ).join("");
  const achse = Object.keys(v).sort().map((k) => `<span>${k}</span>`).join("");

  const kurve = (p.kalibrierungskurve || []).filter((b) => b.n > 0);

  el("profilinhalt").innerHTML = `
    <div class="karte">
      <h2 style="margin-top:0">Wie du bewertest</h2>
      <div class="kennzahl">
        <div><div class="k">FÄLLE</div><div class="v">${p.n_faelle}</div>
             <div class="n">abgegeben</div></div>
        <div><div class="k">SPREIZUNG</div><div class="v">${zahl(p.spreizung, 2)}</div>
             <div class="n">Streuung deiner Note</div></div>
        <div><div class="k">BIAS</div>
             <div class="v">${p.bias === null ? "–"
               : (p.bias > 0 ? "+" : "") + zahl(p.bias, 2)}</div>
             <div class="n">gegen das Feld</div></div>
        <div><div class="k">TRENNSCHÄRFE</div>
             <div class="v">${zahl(p.trennschaerfe, 2)}</div>
             <div class="n">Rangkorrelation Modell</div></div>
      </div>
      <h3>Verteilung deiner Gesamteinschätzungen</h3>
      <div class="verteilung">${balken}</div>
      <div class="achse">${achse}</div>
      <p class="klein muted">Eine Spreizung nahe 0 heißt: du vergibst fast immer
      dieselbe Note. Das ist die häufigste Kalibrierungsschwäche &mdash; und der
      Grund, warum diese Zahl hier oben steht.</p>
    </div>

    <div class="karte">
      <h2 style="margin-top:0">Ob du recht behältst</h2>
      ${p.n_aufgeloest ? `
        <div class="kennzahl">
          <div><div class="k">BRIER</div><div class="v">${zahl(p.brier, 3)}</div>
               <div class="n">0 perfekt, 0,25 Münzwurf</div></div>
          <div><div class="k">BRIER-SKILL</div>
               <div class="v">${zahl(p.brier_skill, 2)}</div>
               <div class="n">gegen die Basisrate</div></div>
          <div><div class="k">KALIBRIERUNG</div>
               <div class="v">${zahl(p.kalibrierungsfehler, 3)}</div>
               <div class="n">Abstand gesagt/eingetreten</div></div>
          <div><div class="k">AUFGELÖST</div><div class="v">${p.n_aufgeloest}</div>
               <div class="n">Prognosen</div></div>
        </div>
        ${kurve.length ? `<h3>Kalibrierung</h3>
          <div class="scroll"><table class="vergleich">
            <tr><th>Gesagt</th><th class="zahl">n</th><th class="zahl">Ø gesagt</th>
                <th class="zahl">eingetreten</th></tr>
            ${kurve.map((b) => `<tr>
              <td>${Math.round(b.von * 100)}–${Math.round(b.bis * 100)}%</td>
              <td class="zahl">${b.n}</td>
              <td class="zahl">${Math.round(b.gesagt * 100)}%</td>
              <td class="zahl">${Math.round(b.eingetreten * 100)}%</td></tr>`).join("")}
          </table></div>` : ""}`
        : `<p class="muted">Noch keine deiner Prognosen ist aufgelöst. Das dauert
           bis zum Ende des Prognosehorizonts &mdash; bis dahin zählt oben, wie du
           bewertest.</p>`}
    </div>`;
}

/* ------------------------------------------------------------ Leaderboard */
async function ligaLaden() {
  zeige("liga");
  el("ligainhalt").innerHTML = `<p class="muted">Lädt …</p>`;
  let d;
  try { d = await api("/api/leaderboard"); }
  catch (err) { return el("ligainhalt").innerHTML =
    `<div class="meldung fehler">${esc(err.message)}</div>`; }

  el("ligasub").textContent = d.hinweis;
  if (!d.zeilen.length) {
    return el("ligainhalt").innerHTML =
      `<p class="muted">Noch keine Abgaben.</p>`;
  }

  el("ligainhalt").innerHTML = `
    <div class="karte scroll">
      <table class="tab">
        <tr><th>#</th><th>Scout</th><th class="zahl">Fälle</th>
            <th class="zahl">Trennschärfe</th><th class="zahl">Spreizung</th>
            <th class="zahl">Bias</th><th class="zahl">Modell-Nähe</th>
            <th class="zahl">Brier</th><th class="zahl">Skill</th></tr>
        ${d.zeilen.map((z) => `
          <tr class="${z.name === S.name ? "ich" : ""}">
            <td class="mono">${z.rang}</td>
            <td>${esc(z.name)}</td>
            <td class="zahl">${z.n_faelle}</td>
            <td class="zahl">${zahl(z.trennschaerfe, 2)}</td>
            <td class="zahl">${zahl(z.spreizung, 2)}${
              z.spreizungs_index !== null && z.spreizungs_index !== undefined
                ? ` <span class="muted">(${zahl(z.spreizungs_index, 2)}×)</span>` : ""}</td>
            <td class="zahl">${z.bias === null ? "–"
              : (z.bias > 0 ? "+" : "") + zahl(z.bias, 2)}</td>
            <td class="zahl">${zahl(z.modell_naehe, 0)}</td>
            <td class="zahl">${z.n_aufgeloest ? zahl(z.brier, 3) : "–"}</td>
            <td class="zahl">${z.n_aufgeloest ? zahl(z.brier_skill, 2) : "–"}</td>
          </tr>`).join("")}
      </table>
    </div>
    <div class="karte flach klein muted">
      <b>Spreizung</b> Streuung der Gesamteinschätzung; in Klammern im Verhältnis
      zum Median des Felds. &nbsp;
      <b>Bias</b> Abstand zum Feldmittel &mdash; positiv heißt milder. &nbsp;
      <b>Trennschärfe</b> Rangkorrelation mit dem Modell über alle Fälle. &nbsp;
      <b>Modell-Nähe</b> 0&ndash;100, ausdrücklich kein Gütemaß. &nbsp;
      <b>Brier</b> Prognosefehler gegen die Realität, kleiner ist besser. &nbsp;
      <b>Skill</b> Brier gegen die Basisrate &mdash; über 0 heißt besser als raten.
      ${Object.keys(d.basisraten || {}).length ? `<br><br><b>Basisraten:</b> `
        + Object.entries(d.basisraten).map(([k, v]) =>
            `${esc(prognoseLabel(k))} ${Math.round(v * 100)}%`).join(" · ") : ""}
    </div>`;
}

/* -------------------------------------------------------------------- Start */
(async function start() {
  if (!S.code) return;
  try {
    const r = await api("/api/anmelden", {
      method: "POST", body: JSON.stringify({ code: S.code }),
    });
    S.name = r.name;
    el("wer").textContent = "· " + r.name;
    packLaden();
  } catch (err) {
    localStorage.removeItem("sl_code");
    S.code = "";
  }
})();
