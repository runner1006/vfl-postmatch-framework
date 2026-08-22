#!/usr/bin/env python3
"""Baut eine eigenstaendige Vorschau der App - eine HTML-Datei, kein Server.

Der Sinn ist Zeigen, nicht Nachbauen: Markup, Stylesheet und Skripte kommen
unveraendert aus static/, damit die Vorschau nicht auseinanderlaeuft mit dem,
was der Server ausliefert. Ersetzt wird genau eine Sache - `fetch` gegen einen
Stellvertreter, der aufgezeichnete Antworten des echten Servers zurueckgibt.

    python3 scoutleague/vorschau_bauen.py --daten vorschau_daten.json \
                                          --ziel scoutleague/vorschau.html

Die Datei mit den Antworten entsteht mit vorschau_daten.py gegen einen
laufenden Server.
"""
import argparse
import json
import os
import re

HIER = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HIER, "static")


def lies(name):
    with open(os.path.join(STATIC, name), encoding="utf-8") as f:
        return f.read()


def koerper_von(html):
    """Alles zwischen <body> und </body>, ohne die Skript-Tags."""
    inner = html[html.index("<body>") + 6: html.rindex("</body>")]
    return re.sub(r"<script\b[^>]*>.*?</script>", "", inner, flags=re.S).strip()


def skript_von(html):
    treffer = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    return "\n".join(treffer).strip()


def einsperren(js, wurzel_id):
    """Skript in eine eigene Funktion legen und seine DOM-Abfragen auf den
    eigenen Teilbaum begrenzen.

    Beide Apps liegen in derselben Seite, und beide fragen global nach
    Attributen wie [data-frage]. Ohne Begrenzung wuerde die Scout-Ansicht die
    Knoepfe der Admin-Ansicht mit einsammeln. `document.getElementById` bleibt,
    weil die IDs ueber beide Ansichten eindeutig sind.
    """
    js = js.replace("document.querySelectorAll(", "WURZEL.querySelectorAll(")
    return (f'(function () {{\n'
            f'  const WURZEL = document.getElementById("{wurzel_id}");\n'
            f'{js}\n}})();')


SHIM = r"""
/* ------------------------------------------------------------------ Attrappe
   Statt eines Servers: aufgezeichnete Antworten eines echten Laufs. Nur die
   Abgabe wird hier gerechnet, weil sie von der Eingabe abhaengt - drei
   Formeln, die im Original in metriken.py stehen. Alles andere ist wortwoertlich
   das, was der Server geliefert hat.                                        */
const DATEN = window.__SL_DATEN;
const ZUSTAND = JSON.parse(JSON.stringify(DATEN.pack));

const mittel = (xs) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

function naehe(werte, modell, spanne) {
  const d = Object.keys(modell || {})
    .filter((k) => werte[k] !== undefined && werte[k] !== null)
    .map((k) => Math.abs(Number(werte[k]) - Number(modell[k])));
  return d.length ? Math.round((100 * (1 - mittel(d) / spanne)) * 10) / 10 : null;
}

function abgabe(koerper) {
  const fall = ZUSTAND.faelle.find((f) => f.id === koerper.fall_id);
  const modell = DATEN.modelle[String(koerper.fall_id)] || {};
  const leit = ZUSTAND.fragebogen.level.fragen.find((q) => q.leitfrage).key;

  fall.eigene_bewertung = {
    level: koerper.level || {}, antworten: koerper.antworten || {},
    prognosen: koerper.prognosen || {}, notiz: koerper.notiz || "",
    abgegeben: !!koerper.abgeben, geaendert_am: new Date().toISOString(),
  };
  if (!koerper.abgeben) return { gespeichert: true, abgegeben: false };

  const meins = Number((koerper.level || {})[leit]);
  const seins = Number((modell.level || {})[leit]);
  const abstand = (Number.isFinite(meins) && Number.isFinite(seins))
    ? Math.round((meins - seins) * 10) / 10 : null;
  const attr = fall.attribute
    .map((a) => Number((koerper.antworten || {})[a.key]))
    .filter(Number.isFinite);

  fall.modell = modell;
  fall.rueckmeldung = {
    modell_naehe: naehe(koerper.antworten || {}, modell.bewertung, 4),
    prognose_naehe: naehe(koerper.prognosen || {}, modell.prognose, 1),
    level_abstand: abstand,
    konflikt: (abstand !== null && Math.abs(abstand) >= 2)
      ? { differenz: abstand,
          richtung: abstand > 0 ? "scout_hoeher" : "modell_hoeher" } : null,
    attribut_mittel: attr.length ? Math.round(mittel(attr) * 100) / 100 : null,
    kohorte: DATEN.kohorten[String(koerper.fall_id)] || null,
  };
  return { gespeichert: true, abgegeben: true, modell: modell,
           rueckmeldung: fall.rueckmeldung };
}

const ROUTEN = {
  "/api/fragebogen": () => DATEN.fragebogen,
  "/api/anmelden": () => DATEN.anmelden,
  "/api/pack": () => ZUSTAND,
  "/api/profil": () => DATEN.profil,
  "/api/leaderboard": () => DATEN.leaderboard,
  "/api/admin/uebersicht": () => DATEN.uebersicht,
  "/api/admin/kalibrierung": () => DATEN.kalibrierung,
  "/api/admin/pack_status": () => ({ hinweis: "In der Vorschau ohne Wirkung." }),
  "/api/admin/aufloesen": () => ({ hinweis: "In der Vorschau ohne Wirkung." }),
};

window.fetch = function (eingabe, optionen) {
  const pfad = String(eingabe).replace(/^https?:\/\/[^/]+/, "").split("?")[0];
  let antwort;
  if (pfad === "/api/bewertung") {
    antwort = abgabe(JSON.parse((optionen || {}).body || "{}"));
  } else if (pfad === "/api/admin/export.csv") {
    return Promise.resolve(new Response(DATEN.csv,
      { status: 200, headers: { "Content-Type": "text/csv" } }));
  } else if (ROUTEN[pfad]) {
    antwort = ROUTEN[pfad]();
  } else {
    return Promise.resolve(new Response(
      JSON.stringify({ fehler: "In der Vorschau nicht hinterlegt." }),
      { status: 404, headers: { "Content-Type": "application/json" } }));
  }
  return Promise.resolve(new Response(JSON.stringify(antwort),
    { status: 200, headers: { "Content-Type": "application/json" } }));
};

/* Angemeldet starten - ein Code-Eingabefeld waere in einer Vorschau nur eine
   Huerde vor dem, was gezeigt werden soll. */
try { localStorage.setItem("sl_code", DATEN.anmelden.code); } catch (e) {}
try { sessionStorage.setItem("sl_admin", "vorschau"); } catch (e) {}
"""

RAHMEN_CSS = r"""
/* --------------------------------------------------------------- Rahmen
   Die Vorschau selbst tritt zurueck: eine Leiste, die sagt was man sieht und
   zwischen den beiden Ansichten umschaltet. Alles darunter ist die App mit
   ihren eigenen Token. */
/* Die Buehne liegt eine Stufe tiefer als die App, damit der Geraeterahmen
   darauf aufsitzt. Kein body-Tag in dieser Datei - die Umgebung erzeugt es -
   deshalb greift die Regel am Element, nicht an einer Klasse. */
body{background:var(--surface-2)}
.rahmen{
  position:sticky;top:0;z-index:60;background:var(--plane);
  border-bottom:1px solid var(--border)
}
.rahmen .zeile{
  max-width:1180px;margin:0 auto;padding:11px 18px;
  display:flex;align-items:center;gap:16px;flex-wrap:wrap
}
.rahmen .titel{font-weight:650;font-size:14.5px;letter-spacing:-.01em}
.rahmen .titel small{
  display:block;font-weight:400;font-size:11.5px;color:var(--muted);
  letter-spacing:.04em;text-transform:uppercase;margin-top:1px
}
.schalter{display:flex;gap:3px;margin-left:auto;background:var(--surface-2);
  padding:3px;border-radius:9px}
.schalter button{
  background:none;border:none;font:inherit;font-size:13.5px;color:var(--ink-2);
  padding:6px 14px;border-radius:7px;cursor:pointer
}
.schalter button[aria-pressed="true"]{background:var(--surface);color:var(--ink);
  font-weight:600;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.schalter button:focus-visible,.rahmen a:focus-visible{outline:2px solid var(--s1);
  outline-offset:2px}

.notiz{
  max-width:1180px;margin:0 auto;padding:10px 18px 0;
  font-size:12.5px;line-height:1.55;color:var(--muted)
}
.notiz b{color:var(--ink-2);font-weight:600}
.notiz code{
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
  background:var(--surface);border:1px solid var(--border);border-radius:4px;
  padding:1px 5px
}

.buehne{max-width:1180px;margin:0 auto;padding:14px 18px 60px}
/* Die Scout-Ansicht ist fuers Telefon gebaut - also auch so zeigen. */
.buehne.eng{max-width:472px;padding-left:0;padding-right:0}
.geraet{
  background:var(--plane);border:1px solid var(--border);border-radius:16px;
  overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.05),0 12px 32px rgba(0,0,0,.06)
}
.geraet > .wrap{padding-top:14px}
/* Die App-Kopfzeile klebt im Betrieb am Fensterrand. Im Geraeterahmen der
   Vorschau waere das der falsche Bezugspunkt - sie wuerde ueber die
   Rahmenleiste wandern. */
.geraet header.kopf{position:static;border-radius:16px 16px 0 0}
@media (prefers-reduced-motion:no-preference){
  .buehne{animation:auf .22s ease-out}
  @keyframes auf{from{opacity:0;transform:translateY(3px)}to{opacity:1}}
}
"""


RAHMEN_JS = r"""
/* Umschalter. Beide Ansichten sind bereits gezeichnet; hier wird nur sichtbar
   gemacht, was gerade gefragt ist. */
(function () {
  const TEXTE = {
    scout: "<b>Das sieht ein Scout.</b> Vier Fälle sind offen und "
      + "ausfüllbar, zwei sind abgegeben und zeigen die "
      + "Sofort-Rückmeldung. Die Daten stammen aus einem echten Lauf mit "
      + "zehn Testscouts auf erfundenen Spielern.",
    admin: "<b>Das sieht die Redaktion.</b> Abgabestand und Auflösung "
      + "unter <i>Übersicht</i>, die fünf Diagnosen aus dem Scout "
      + "Rating Audit unter <i>Kalibrier-Report</i>.",
  };
  const HINWEIS = " Kennzahlen in Profil, Liga und Report sind ein Standbild: "
    + "sie rechnen im Betrieb live mit, in dieser Vorschau nicht. Der volle "
    + "Umfang läuft mit <code>python3 scoutleague/serve.py</code>.";

  const notiz = document.getElementById("notiz");
  const buehnen = { scout: document.getElementById("buehne-scout"),
                    admin: document.getElementById("buehne-admin") };

  function waehle(welche) {
    Object.entries(buehnen).forEach(([k, n]) => { n.hidden = k !== welche; });
    document.querySelectorAll("[data-ansicht-wahl]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.ansichtWahl === welche));
    });
    notiz.innerHTML = TEXTE[welche] + HINWEIS;
    window.scrollTo(0, 0);
  }

  document.querySelectorAll("[data-ansicht-wahl]").forEach((b) => {
    b.addEventListener("click", () => waehle(b.dataset.ansichtWahl));
  });

  /* Der Export laedt im Betrieb eine Datei herunter. In einer eingebetteten
     Vorschau ist Herunterladen gesperrt, und ein toter Knopf waere schlechter
     als gar keiner - also hier zeigen statt liefern. Abgefangen wird in der
     Erfassungsphase, damit der eigentliche Handler nicht mehr laeuft. */
  document.getElementById("app-admin").addEventListener("click", (e) => {
    const knopf = e.target.closest("#csv");
    if (!knopf) return;
    e.preventDefault();
    e.stopPropagation();
    const offen = document.getElementById("csv-vorschau");
    if (offen) { offen.remove(); return; }
    const zeilen = String(window.__SL_DATEN.csv || "").trim().split("\n");
    const schutz = (t) => t.replace(/[&<>]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const kasten = document.createElement("div");
    kasten.id = "csv-vorschau";
    kasten.className = "karte flach";
    kasten.style.marginTop = "12px";
    kasten.innerHTML =
      '<p class="klein muted" style="margin:0 0 8px">Im Betrieb lädt dieser '
      + 'Knopf eine CSV herunter — eine Zeile je Scout × Fall × '
      + 'Prognose, mit Outcome-Label. Hier stehen die ersten Zeilen von '
      + '<b>' + (zeilen.length - 1) + '</b>.</p>'
      + '<div class="scroll"><pre style="margin:0;font-size:11px;line-height:1.5">'
      + zeilen.slice(0, 6).map(schutz).join("\n")
      + (zeilen.length > 6 ? "\n…" : "") + '</pre></div>';
    knopf.closest(".karte").appendChild(kasten);
  }, true);

  waehle("scout");
})();
"""


def bauen(daten_pfad, ziel):
    with open(daten_pfad, encoding="utf-8") as f:
        daten = json.load(f)

    css = lies("stil.css")
    scout_html = lies("index.html")
    admin_html = lies("admin.html")
    app_js = lies("app.js")

    seite = f"""<title>Scout League Vorschau</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
{css}
{RAHMEN_CSS}
</style>

<header class="rahmen">
  <div class="zeile">
    <div class="titel">Scout League
      <small>Vorschau &middot; Rev. 0.2 &middot; Testdaten</small></div>
    <div class="schalter" role="group" aria-label="Ansicht wählen">
      <button type="button" data-ansicht-wahl="scout" aria-pressed="true">Scout</button>
      <button type="button" data-ansicht-wahl="admin" aria-pressed="false">Admin</button>
    </div>
  </div>
</header>

<p class="notiz" id="notiz"></p>

<div class="buehne eng" id="buehne-scout">
  <div class="geraet" id="app-scout">
{koerper_von(scout_html)}
  </div>
</div>

<div class="buehne" id="buehne-admin" hidden>
  <div id="app-admin">
{koerper_von(admin_html)}
  </div>
</div>

<script>
window.__SL_DATEN = {json.dumps(daten, ensure_ascii=False)};
</script>

<script>
{SHIM}
</script>

<script>
{einsperren(app_js, "app-scout")}
</script>

<script>
{einsperren(skript_von(admin_html), "app-admin")}
</script>

<script>
{RAHMEN_JS}
</script>
"""
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(seite)
    return len(seite)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Eigenstaendige Vorschau bauen")
    p.add_argument("--daten", required=True)
    p.add_argument("--ziel", default=os.path.join(HIER, "vorschau.html"))
    a = p.parse_args()
    n = bauen(a.daten, a.ziel)
    print(f"{a.ziel} geschrieben, {n / 1024:.0f} KB")
