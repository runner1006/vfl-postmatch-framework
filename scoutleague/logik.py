"""Zwischen Datenbank und HTTP: Case Pack zusammenstellen, Bewertung
entgegennehmen, Leaderboard rechnen. Alles, was mehr als eine Tabelle
anfasst, steht hier - serve.py bleibt reines Routing."""
import json
import os

import db
import metriken

FRAGEBOGEN_PFAD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "fragebogen.json")


def fragebogen():
    with open(FRAGEBOGEN_PFAD, encoding="utf-8") as f:
        return json.load(f)


def leitfrage(fb=None):
    fb = fb or fragebogen()
    for f in fb["bewertung"]["fragen"]:
        if f.get("leitfrage"):
            return f["key"]
    return fb["bewertung"]["fragen"][-1]["key"]


class Fehler(Exception):
    def __init__(self, text, status=400):
        super().__init__(text)
        self.text = text
        self.status = status


# ------------------------------------------------------------------- Case Pack
def pack_fuer_scout(con, scout, slug=None):
    pack = db.aktives_pack(con, slug)
    if pack is None:
        raise Fehler("Kein offenes Case Pack.", 404)

    faelle = db.faelle_von(con, pack["id"])
    eigene = {
        r["fall_id"]: r
        for r in con.execute(
            "SELECT * FROM bewertungen WHERE scout_id = ?", (scout["id"],)
        )
    }

    ausgabe = []
    for f in faelle:
        b = eigene.get(f["id"])
        abgegeben = bool(b and b["abgegeben"])
        d = db.fall_dict(f, mit_modell=abgegeben)
        d["eigene_bewertung"] = {
            "antworten": json.loads(b["antworten_json"]) if b else {},
            "prognosen": json.loads(b["prognosen_json"]) if b else {},
            "notiz": b["notiz"] if b else "",
            "abgegeben": abgegeben,
            "geaendert_am": b["geaendert_am"] if b else None,
        }
        if abgegeben:
            m = json.loads(f["modell_json"])
            d["rueckmeldung"] = {
                "modell_naehe": metriken.modell_naehe(
                    d["eigene_bewertung"]["antworten"], m.get("bewertung")),
                "prognose_naehe": metriken.prognose_naehe(
                    d["eigene_bewertung"]["prognosen"], m.get("prognose")),
                "kohorte": kohorten_schnitt(con, f["id"]),
            }
        ausgabe.append(d)

    return {
        "pack": {"slug": pack["slug"], "titel": pack["titel"],
                 "status": pack["status"], "schliesst_am": pack["schliesst_am"]},
        "faelle": ausgabe,
        "fragebogen": fragebogen(),
    }


def kohorten_schnitt(con, fall_id):
    """Was das Feld zu diesem Fall gesagt hat. Erst ab drei Abgaben, sonst
    ist der 'Schnitt' die Meinung von zwei Leuten mit Nachkommastelle."""
    rows = con.execute(
        "SELECT antworten_json FROM bewertungen WHERE fall_id = ? AND abgegeben = 1",
        (fall_id,),
    ).fetchall()
    if len(rows) < 3:
        return None
    gesammelt = {}
    for r in rows:
        for k, v in json.loads(r["antworten_json"]).items():
            if v is not None:
                gesammelt.setdefault(k, []).append(float(v))
    return {"n": len(rows),
            "mittel": {k: round(metriken.mittel(v), 2) for k, v in gesammelt.items()}}


# ------------------------------------------------------------------- Speichern
def bewertung_speichern(con, scout, fall_id, antworten, prognosen, notiz,
                        sekunden, abgeben):
    fall = con.execute("SELECT * FROM faelle WHERE id = ?", (fall_id,)).fetchone()
    if fall is None:
        raise Fehler("Fall unbekannt.", 404)
    pack = con.execute("SELECT * FROM packs WHERE id = ?", (fall["pack_id"],)).fetchone()
    if pack["status"] != "offen":
        raise Fehler("Das Case Pack ist geschlossen.", 409)

    fb = fragebogen()
    gueltige_fragen = {f["key"] for f in fb["bewertung"]["fragen"]}
    gueltige_prognosen = {p["key"] for p in fb["prognosen"]}
    smin, smax = fb["bewertung"]["skala"]["min"], fb["bewertung"]["skala"]["max"]

    sauber_a = {}
    for k, v in (antworten or {}).items():
        if k not in gueltige_fragen or v is None or v == "":
            continue
        iv = int(v)
        if not smin <= iv <= smax:
            raise Fehler(f"Bewertung '{k}' liegt außerhalb der Skala {smin}–{smax}.")
        sauber_a[k] = iv

    sauber_p = {}
    for k, v in (prognosen or {}).items():
        if k not in gueltige_prognosen or v is None or v == "":
            continue
        fv = float(v)
        if not 0.0 <= fv <= 1.0:
            raise Fehler(f"Prognose '{k}' muss zwischen 0 und 1 liegen.")
        sauber_p[k] = round(fv, 3)

    if abgeben:
        fehlend = sorted(gueltige_fragen - set(sauber_a))
        if fehlend:
            raise Fehler("Vor der Abgabe fehlen noch Bewertungen: "
                         + ", ".join(fehlend))
        fehlend_p = sorted(gueltige_prognosen - set(sauber_p))
        if fehlend_p:
            raise Fehler("Vor der Abgabe fehlen noch Prognosen: "
                         + ", ".join(fehlend_p))

    vorher = con.execute(
        "SELECT abgegeben FROM bewertungen WHERE scout_id = ? AND fall_id = ?",
        (scout["id"], fall_id),
    ).fetchone()
    if vorher and vorher["abgegeben"]:
        raise Fehler("Dieser Fall ist bereits abgegeben und bleibt gesperrt.", 409)

    notiz = (notiz or "")[: fb["notiz"]["max_zeichen"]]
    with con:
        con.execute(
            """INSERT INTO bewertungen
                 (scout_id, fall_id, antworten_json, prognosen_json, notiz,
                  sekunden, abgegeben, geaendert_am)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(scout_id, fall_id) DO UPDATE SET
                 antworten_json = excluded.antworten_json,
                 prognosen_json = excluded.prognosen_json,
                 notiz          = excluded.notiz,
                 sekunden       = excluded.sekunden,
                 abgegeben      = excluded.abgegeben,
                 geaendert_am   = excluded.geaendert_am""",
            (scout["id"], fall_id, json.dumps(sauber_a), json.dumps(sauber_p),
             notiz, int(sekunden or 0), 1 if abgeben else 0, db.jetzt()),
        )
        db.protokoll(con, scout["id"],
                     "abgabe" if abgeben else "zwischenstand", str(fall_id))

    if not abgeben:
        return {"gespeichert": True, "abgegeben": False}

    modell = json.loads(fall["modell_json"])
    return {
        "gespeichert": True,
        "abgegeben": True,
        "modell": modell,
        "rueckmeldung": {
            "modell_naehe": metriken.modell_naehe(sauber_a, modell.get("bewertung")),
            "prognose_naehe": metriken.prognose_naehe(sauber_p, modell.get("prognose")),
            "kohorte": kohorten_schnitt(con, fall_id),
        },
    }


# ----------------------------------------------------------------- Leaderboard
def _rohdaten(con, pack_slug=None):
    if pack_slug:
        faelle = con.execute(
            """SELECT f.* FROM faelle f JOIN packs p ON p.id = f.pack_id
               WHERE p.slug = ?""", (pack_slug,)).fetchall()
    else:
        faelle = con.execute("SELECT * FROM faelle").fetchall()
    fall_ids = {f["id"] for f in faelle}
    modelle = {f["id"]: json.loads(f["modell_json"]) for f in faelle}

    bew = [b for b in con.execute(
        "SELECT * FROM bewertungen WHERE abgegeben = 1") if b["fall_id"] in fall_ids]

    aufl = {(r["fall_id"], r["frage"]): r["ergebnis"]
            for r in con.execute("SELECT * FROM aufloesungen")
            if r["fall_id"] in fall_ids}
    return faelle, modelle, bew, aufl


def leaderboard(con, pack_slug=None):
    fb = fragebogen()
    leit = leitfrage(fb)
    _faelle, modelle, bew, aufl = _rohdaten(con, pack_slug)

    scouts = {r["id"]: r for r in con.execute("SELECT * FROM scouts")}

    # Kohorte: alle Leitfragen-Werte je Fall, fuer den Bias-Vergleich
    kohorte = {}
    for b in bew:
        antw = json.loads(b["antworten_json"])
        if antw.get(leit) is not None:
            kohorte.setdefault(b["fall_id"], {}).setdefault(leit, []).append(
                float(antw[leit]))

    je_scout = {}
    for b in bew:
        je_scout.setdefault(b["scout_id"], []).append({
            "fall_id": b["fall_id"],
            "antworten": json.loads(b["antworten_json"]),
            "prognosen": json.loads(b["prognosen_json"]),
            "modell": modelle.get(b["fall_id"], {}),
        })

    raten = metriken.basisraten(aufl)
    roh = {}
    for sid, abgaben in je_scout.items():
        m = metriken.scout_metriken(abgaben, kohorte, aufl, leitfrage=leit)
        m["brier_skill"] = metriken.skill_gesamt(m.pop("_paare_je_frage"), raten)
        roh[sid] = m

    kohorten_sd = _median([m["spreizung"] for m in roh.values()
                           if m["spreizung"] is not None])

    zeilen = []
    for sid, m in roh.items():
        s = scouts.get(sid)
        if s is None:
            continue
        m = dict(m)
        m.pop("kalibrierungskurve", None)
        m["spreizungs_index"] = metriken.spreizungs_index(m["spreizung"], kohorten_sd)
        m["scout_id"] = sid
        m["name"] = s["name"]
        zeilen.append(m)

    # Rang: sobald aufgeloest wurde, entscheidet der Brier-Skill. Davor die
    # Trennschaerfe - wer ueberall dieselbe Zahl vergibt, steht unten, und das
    # ist in Stufe 0 genau die Aussage, die interessiert.
    aufgeloest = any(z["n_aufgeloest"] for z in zeilen)
    if aufgeloest:
        zeilen.sort(key=lambda z: (-(z["brier_skill"] if z["brier_skill"] is not None else -9),
                                   z["brier"] if z["brier"] is not None else 9))
    else:
        zeilen.sort(key=lambda z: (-(z["trennschaerfe"] if z["trennschaerfe"] is not None else -9),
                                   -(z["spreizungs_index"] or 0)))
    for i, z in enumerate(zeilen, 1):
        z["rang"] = i

    return {
        "zeilen": zeilen,
        "kohorten_spreizung": round(kohorten_sd, 2) if kohorten_sd else None,
        "basisraten": {k: round(v, 3) for k, v in raten.items()},
        "aufgeloest": aufgeloest,
        "leitfrage": leit,
        "hinweis": ("Rangfolge nach Brier-Skill gegen die Basisrate."
                    if aufgeloest else
                    "Noch keine Prognose aufgelöst \u2014 die Rangfolge ist vorläufig "
                    "und sortiert nach Trennschärfe gegen das Modell."),
    }


def profil(con, scout, pack_slug=None):
    fb = fragebogen()
    leit = leitfrage(fb)
    _faelle, modelle, bew, aufl = _rohdaten(con, pack_slug)

    kohorte = {}
    for b in bew:
        antw = json.loads(b["antworten_json"])
        if antw.get(leit) is not None:
            kohorte.setdefault(b["fall_id"], {}).setdefault(leit, []).append(
                float(antw[leit]))

    abgaben = [{
        "fall_id": b["fall_id"],
        "antworten": json.loads(b["antworten_json"]),
        "prognosen": json.loads(b["prognosen_json"]),
        "modell": modelle.get(b["fall_id"], {}),
    } for b in bew if b["scout_id"] == scout["id"]]

    m = metriken.scout_metriken(abgaben, kohorte, aufl, leitfrage=leit)
    m["brier_skill"] = metriken.skill_gesamt(m.pop("_paare_je_frage"),
                                             metriken.basisraten(aufl))
    m["name"] = scout["name"]

    # Verteilung der eigenen Leitfragen-Werte - macht "immer die 3" sofort sichtbar
    verteilung = {str(i): 0 for i in range(fb["bewertung"]["skala"]["min"],
                                           fb["bewertung"]["skala"]["max"] + 1)}
    for a in abgaben:
        v = a["antworten"].get(leit)
        if v is not None:
            verteilung[str(int(v))] += 1
    m["verteilung"] = verteilung
    return m


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
