/* Scout League - Frontend. Kein Build, kein Framework: eine Datei, die der
   Server so ausliefert, wie sie hier steht. */
"use strict";

/* Browser-Speicher kann werfen, nicht nur leer sein - privates Fenster,
   blockierte Site-Daten. Ein Anmeldecode ist Bequemlichkeit, kein Zustand,
   ohne den die App laufen muesste. */
const speicher = {
  lies(key) {
    try { return localStorage.getItem(key) || ""; } catch (e) { return ""; }
  },
  schreib(key, wert) {
    try { localStorage.setItem(key, wert); } catch (e) { /* egal */ }
  },
  loesche(key) {
    try { localStorage.removeItem(key); } catch (e) { /* egal */ }
  },
};

const S = {
  code: speicher.lies("sl_code"),
  name: "",
  daten: null,          // Antwort von /api/pack
  fall: null,           // aktuell geoeffneter Fall
  entwurf: null,        // {antworten, prognosen, notiz}
  begonnen: 0,
};

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
  speicher.loesche("sl_code");
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
    speicher.schreib("sl_code", code);
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
    level: Object.assign({}, S.fall.eigene_bewertung.level),
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

function indexBlock(indizes, attribute) {
  const eintraege = attribute
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

/* Level Rating. Zehn Stufen mit echten Liga-Ankern - der Punkt aus dem Audit
   ist, dass die Anker im Moment der Entscheidung sichtbar sein muessen, nicht
   in einer Fussnote. Deshalb steht unter der Auswahl immer die Stufe, die
   gerade gewaehlt ist, und die volle Tabelle liegt einen Klick daneben. */
function levelBlock(frage, stufen, wert, gesperrt) {
  const gewaehlt = stufen.find((st) => st.wert === wert);
  return `<div class="levelfrage" data-level="${esc(frage.key)}">
    <div class="label">${esc(frage.frage)}</div>
    <div class="klein muted" style="margin-bottom:8px">${esc(frage.erlaeuterung || "")}</div>
    <div class="levelskala">
      ${stufen.slice().sort((a, b) => a.wert - b.wert).map((st) => `
        <button type="button" data-wert="${st.wert}"
          aria-pressed="${wert === st.wert}" title="${esc(st.ligen)}"
          ${gesperrt ? "disabled" : ""}>${st.wert}</button>`).join("")}
    </div>
    <div class="levelanker">${gewaehlt ? `
      <b>${gewaehlt.wert} · ${esc(gewaehlt.ligen)}</b>
      <span class="muted">${esc(gewaehlt.kontext)} · ${esc(gewaehlt.marktwert)}</span>`
      : `<span class="muted">Noch keine Stufe gewählt.</span>`}</div>
    <details class="leveltabelle">
      <summary class="klein">Alle Stufen anzeigen</summary>
      <table class="vergleich">
        ${stufen.map((st) => `<tr${st.wert === wert ? ' class="ich"' : ""}>
          <td class="zahl mono" style="width:26px">${st.wert}</td>
          <td>${esc(st.ligen)}<br><span class="muted klein">${esc(st.kontext)}</span></td>
          <td class="zahl muted" style="white-space:nowrap">${esc(st.marktwert)}</td>
        </tr>`).join("")}
      </table>
    </details>
  </div>`;
}

function fallZeichnen() {
  const f = S.fall;
  const fb = S.daten.fragebogen;
  const gesperrt = f.eigene_bewertung.abgegeben || S.daten.pack.status !== "offen";

  const steckbrief = [
    ["Position", f.position], ["Rolle", f.positionsgruppe_label],
    ["Jahrgang", f.jahrgang], ["Verein", f.verein], ["Liga", f.liga],
    ["Fuß", f.fuss],
  ].filter(([, v]) => v).map(([k, v]) =>
    `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("");

  const levelHtml = fb.level.fragen.map((q) =>
    levelBlock(q, fb.level.stufen, S.entwurf.level[q.key], gesperrt)).join("");

  const attrHtml = f.attribute.map((q) => `
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
    </div>`).join("");

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
      ${indexBlock(f.indizes, f.attribute)}
    </div>

    <div id="rueckmeldung"></div>

    <div class="karte">
      <h2 style="margin-top:0">${esc(fb.level.titel)}</h2>
      <p class="klein muted">Jede Stufe ist ein reales Liga-Niveau mit
      Marktwertband. Beide Fragen unabhängig beantworten &mdash; das Ceiling ist
      kein Aufschlag auf das bewiesene Niveau.</p>
      ${levelHtml}
    </div>

    <div class="karte">
      <h2 style="margin-top:0">Attribute
        <span class="abzeichen">${esc(f.positionsgruppe)}</span></h2>
      <p class="klein muted">Verpflichtendes Set für
      ${esc(f.positionsgruppe_label)}. Höher ist besser &mdash; auf jeder Skala
      hier. Nutze die ganze Breite: wer überall die 3 vergibt, erzeugt keine
      Information.</p>
      ${attrHtml}
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

  document.querySelectorAll(".levelfrage").forEach((box) => {
    box.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-wert]");
      if (!b) return;
      const key = box.dataset.level;
      const wert = Number(b.dataset.wert);
      S.entwurf.level[key] = wert;
      // Nur den Ankertext und die Markierung nachziehen. Das Element neu zu
      // bauen wuerde bei jedem Klick weitere Listener anhaengen - und die
      // Abgabe dann mehrfach abschicken.
      box.querySelectorAll(".levelskala button").forEach((x) => {
        x.setAttribute("aria-pressed", String(Number(x.dataset.wert) === wert));
      });
      const stufe = S.daten.fragebogen.level.stufen.find((st) => st.wert === wert);
      const anker = box.querySelector(".levelanker");
      if (anker && stufe) {
        anker.innerHTML = `<b>${stufe.wert} · ${esc(stufe.ligen)}</b>`
          + `<span class="muted">${esc(stufe.kontext)} · ${esc(stufe.marktwert)}</span>`;
      }
      box.querySelectorAll(".leveltabelle tr").forEach((tr) => {
        tr.classList.toggle("ich",
          Number(tr.firstElementChild.textContent.trim()) === wert);
      });
      fortschritt();
    });
  });

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
  const attribute = S.fall.attribute;
  const l = fb.level.fragen.filter(
    (q) => S.entwurf.level[q.key] !== undefined).length;
  const a = attribute.filter(
    (q) => S.entwurf.antworten[q.key] !== undefined).length;
  const p = fb.prognosen.filter(
    (q) => S.entwurf.prognosen[q.key] !== undefined).length;
  const voll = l === fb.level.fragen.length && a === attribute.length
    && p === fb.prognosen.length;
  const box = el("fortschritt");
  if (box) {
    box.textContent = `${l}/${fb.level.fragen.length} Level · `
      + `${a}/${attribute.length} Attribute · `
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
        level: S.entwurf.level,
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
    S.fall.eigene_bewertung.level = Object.assign({}, S.entwurf.level);
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
  const ml = (modell && modell.level) || {};
  const antw = S.fall.eigene_bewertung.antworten;
  const lvl = S.fall.eigene_bewertung.level;
  const prog = S.fall.eigene_bewertung.prognosen;
  const koh = r.kohorte;

  const kohWert = (key) => {
    if (!koh || !koh.mittel) return "–";
    const v = koh.mittel[key];
    return v === undefined || v === null ? "–" : zahl(v, 1);
  };

  const levelZeilen = fb.level.fragen.map((q) => `
    <tr><td>${esc(q.label)}</td>
      <td class="zahl">${lvl[q.key] === undefined ? "–" : lvl[q.key]}</td>
      <td class="zahl">${ml[q.key] === undefined ? "–" : zahl(ml[q.key], 1)}</td>
      <td class="zahl muted">${kohWert(q.key)}</td></tr>`).join("");

  const attrZeilen = S.fall.attribute.map((q) => `
    <tr><td>${esc(q.label)}</td>
      <td class="zahl">${antw[q.key] === undefined ? "–" : antw[q.key]}</td>
      <td class="zahl">${mb[q.key] === undefined ? "–" : zahl(mb[q.key], 1)}</td>
      <td class="zahl muted">${kohWert(q.key)}</td></tr>`).join("");

  const progZeilen = fb.prognosen.map((p) => `
    <tr><td>${esc(p.label)}</td>
      <td class="zahl">${prog[p.key] === undefined ? "–"
        : Math.round(prog[p.key] * 100) + "%"}</td>
      <td class="zahl">${mp[p.key] === undefined ? "–"
        : Math.round(mp[p.key] * 100) + "%"}</td>
      <td class="zahl muted">offen</td></tr>`).join("");

  const k = r.konflikt;
  const konfliktBox = k ? `
    <div class="meldung ${k.richtung === "scout_hoeher" ? "warn" : "warn"}"
         style="margin:12px 0 0">
      <b>Konfliktfall.</b> ${k.richtung === "scout_hoeher"
        ? `Du siehst ihn ${Math.abs(k.differenz)} Stufen über dem Modell —
           Bauchgefühl ohne Datenstütze, oder das Modell übersieht etwas.`
        : `Das Modell sieht ihn ${Math.abs(k.differenz)} Stufen über dir —
           möglicherweise ein Übersehener.`}
      Solche Fälle landen auf der Review-Liste; dort steckt laut Audit der
      meiste Erkenntnisgewinn.
    </div>` : "";

  el("rueckmeldung").innerHTML = `
    <div class="karte">
      <h2 style="margin-top:0">Sofort-Rückmeldung</h2>
      <div class="kennzahl">
        <div><div class="k">LEVEL-ABSTAND</div>
             <div class="v">${r.level_abstand === null ? "–"
               : (r.level_abstand > 0 ? "+" : "") + zahl(r.level_abstand, 1)}</div>
             <div class="n">du gegen Modell</div></div>
        <div><div class="k">MODELL-NÄHE</div>
             <div class="v">${zahl(r.modell_naehe, 0)}</div>
             <div class="n">0&ndash;100, Attribute</div></div>
        <div><div class="k">PROGNOSE-NÄHE</div>
             <div class="v">${zahl(r.prognose_naehe, 0)}</div>
             <div class="n">0&ndash;100, gegen Modell</div></div>
        <div><div class="k">ATTRIBUT-MITTEL</div>
             <div class="v">${zahl(r.attribut_mittel, 1)}</div>
             <div class="n">dein Schnitt, 1&ndash;5</div></div>
      </div>
      ${konfliktBox}
      <p class="klein muted" style="margin-top:10px">Nähe ist kein Gütemaß.
      Wer vom Modell abweicht und recht behält, gewinnt die Liga &mdash;
      entschieden wird sie über den Brier-Score gegen die Realität.</p>
      <div class="scroll"><table class="vergleich">
        <tr><th>Level Rating</th><th class="zahl">Du</th><th class="zahl">Modell</th>
            <th class="zahl">Feld</th></tr>
        ${levelZeilen}
        <tr><th style="padding-top:14px">Attribut</th>
            <th class="zahl" style="padding-top:14px">Du</th>
            <th class="zahl" style="padding-top:14px">Modell</th>
            <th class="zahl" style="padding-top:14px">Feld</th></tr>
        ${attrZeilen}
        <tr><th style="padding-top:14px">Prognose</th>
            <th class="zahl" style="padding-top:14px">Du</th>
            <th class="zahl" style="padding-top:14px">Modell</th>
            <th class="zahl" style="padding-top:14px">Realität</th></tr>
        ${progZeilen}
      </table></div>
      ${koh ? `<p class="klein muted">Feld = Mittel aus ${koh.n} Abgaben.${
          koh.mittel_bereinigt !== undefined
            ? ` Rater-bereinigt (jeder Scout an seinen eigenen Abgaben
                z-standardisiert): <b>${zahl(koh.mittel_bereinigt, 1)}</b>
                auf der Leitfrage.` : ""}</p>`
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

  const sw = p.schwellen || {};
  const v = p.verteilung || {};
  const stufen = Object.keys(v).sort((a, b) => Number(a) - Number(b));
  const max = Math.max(1, ...Object.values(v));
  const balken = stufen.map((k) =>
    `<div style="height:${Math.round((v[k] / max) * 100)}%"><b>${v[k] || ""}</b></div>`
  ).join("");
  const achse = stufen.map((k) => `<span>${k}</span>`).join("");

  // Unter einer Handvoll Faellen ist jede dieser Diagnosen Rauschen: wer einen
  // Spieler bewertet hat, hat per Konstruktion 100 % auf einer Stufe.
  const mind = sw.mindest_faelle_diagnose || 5;
  const genug = p.n_faelle >= mind;
  const zt = p.zentraltendenz;
  const ztWarn = genug && zt && zt.anteil > (sw.zentraltendenz_max || 0.35);
  const haloWarn = p.halo !== null && p.halo >= (sw.halo_warnung || 0.75);
  const entWarn = p.entkopplung !== null
    && p.entkopplung >= (sw.entkopplung_warnung || 0.55);
  const messbar = p.halo !== null || p.entkopplung !== null;
  const kurve = (p.kalibrierungskurve || []).filter((b) => b.n > 0);

  el("profilinhalt").innerHTML = `
    <div class="karte">
      <h2 style="margin-top:0">Wie du bewertest</h2>
      <div class="kennzahl">
        <div><div class="k">FÄLLE</div><div class="v">${p.n_faelle}</div>
             <div class="n">abgegeben</div></div>
        <div><div class="k">SPREIZUNG</div><div class="v">${zahl(p.spreizung, 2)}</div>
             <div class="n">Streuung deiner Level</div></div>
        <div><div class="k">BIAS</div>
             <div class="v">${p.bias === null ? "–"
               : (p.bias > 0 ? "+" : "") + zahl(p.bias, 2)}</div>
             <div class="n">gegen das Feld</div></div>
        <div><div class="k">TRENNSCHÄRFE</div>
             <div class="v">${zahl(p.trennschaerfe, 2)}</div>
             <div class="n">Rangkorrelation Modell</div></div>
      </div>
      <h3>Verteilung deiner bewiesenen Level</h3>
      <div class="verteilung">${balken}</div>
      <div class="achse">${achse}</div>
      ${zt ? `<p class="klein ${ztWarn ? "warnton" : "muted"}">
        ${Math.round(zt.anteil * 100)}&nbsp;% deiner Level entfallen auf Stufe
        ${zt.modalwert}; du nutzt ${zt.genutzte_stufen} der 10 Stufen.
        ${!genug ? `Als Diagnose zählt das erst ab ${mind} bewerteten Fällen —
           bis dahin ist die Zahl eine Momentaufnahme.`
          : ztWarn ? `Ziel sind höchstens ${Math.round(
            (sw.zentraltendenz_max || 0.35) * 100)}&nbsp;% auf einer Stufe —
            darunter kann die Skala nicht ranken.`
          : "Das liegt im Zielkorridor."}</p>` : ""}
    </div>

    <div class="karte">
      <h2 style="margin-top:0">Wie eigenständig deine Urteile sind</h2>
      <div class="kennzahl">
        <div><div class="k">HALO</div><div class="v">${zahl(p.halo, 2)}</div>
             <div class="n">Level ↔ Attribut-Mittel</div></div>
        <div><div class="k">ENTKOPPLUNG</div>
             <div class="v">${zahl(p.entkopplung, 2)}</div>
             <div class="n">Niveau ↔ Ceiling</div></div>
      </div>
      <p class="klein ${haloWarn || entWarn ? "warnton" : "muted"}">
        ${!messbar ? `Beide Korrelationen brauchen mindestens drei abgegebene
           Fälle mit unterschiedlichen Bewertungen. Wer überall dasselbe
           vergibt, hat keinen messbaren Halo — das zeigt dann die Spreizung
           oben.` : ""}
        ${haloWarn ? `Dein Level folgt dem Attribut-Mittel fast eins zu eins
           (r = ${zahl(p.halo, 2)}) — das Gesamturteil trägt dann kaum eigene
           Information. ` : ""}
        ${entWarn ? `Bewiesenes Niveau und Ceiling laufen bei dir gleich
           (r = ${zahl(p.entkopplung, 2)}) — das Ceiling wirkt wie ein Aufschlag
           statt wie eine eigene Schätzung. ` : ""}
        ${messbar && !haloWarn && !entWarn ? `Was messbar ist, liegt im
           unkritischen Bereich: dein Gesamturteil ist mehr als der Schnitt der
           Attribute, und das Ceiling ist eine eigene Einschätzung.` : ""}
      </p>
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
            <th class="zahl">Bias</th><th class="zahl">Halo</th>
            <th class="zahl">Modell-Nähe</th>
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
            <td class="zahl">${zahl(z.halo, 2)}</td>
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
      <b>Halo</b> wie stark das Level dem Attribut-Mittel folgt — nahe 1 heißt,
      das Gesamturteil ist nur ein Echo. &nbsp;
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
    speicher.loesche("sl_code");
    S.code = "";
  }
})();
