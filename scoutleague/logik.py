"""Zwischen Datenbank und HTTP: Case Pack zusammenstellen, Bewertung
entgegennehmen, Leaderboard, Profil und Kalibrier-Report rechnen. Alles, was
mehr als eine Tabelle anfasst, steht hier - serve.py bleibt reines Routing.

Rev. 0.2 setzt den Scout Rating Audit um. Die drei Stellen, an denen das
sichtbar wird:

  * Die Leitfrage ist das Level Rating 1-10 mit Liga-Ankern, nicht mehr eine
    abstrakte Gesamtnote. Zehn verankerte Stufen brechen die Zentraltendenz,
    die der Audit mit 58 % Dreiern beziffert.
  * Der Feldvergleich laeuft ueber z-standardisierte Werte. Damit verschwindet
    der Strenge-Gap zwischen Scouts, den der Audit mit 0,56 Notenpunkten misst.
  * Der Kalibrier-Report rechnet die fuenf Audit-Diagnosen fortlaufend auf den
    Abgaben der Liga - Zentraltendenz, Strenge, Halo, Entkopplung, tote
    Attribute - plus die Konfliktliste Scout gegen Modell.
"""
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
    for f in fb["level"]["fragen"]:
        if f.get("leitfrage"):
            return f["key"]
    return fb["level"]["fragen"][0]["key"]


class Fehler(Exception):
    def __init__(self, text, status=400):
        super().__init__(text)
        self.text = text
        self.status = status


# ------------------------------------------------------------------ Positionen
def positionsgruppe(position, fb=None):
    """Rohposition aus dem Case Pack auf eine der sechs Audit-Gruppen abbilden.
    Unbekanntes faellt auf die Standardgruppe zurueck, statt den Fall aus dem
    Pack zu werfen - ein Tippfehler in der Positionsspalte darf keinen
    Scouting-Termin kosten."""
    fb = fb or fragebogen()
    zuordnung = fb["bewertung"]["gruppen_zuordnung"]
    p = (position or "").strip().upper()
    for gruppe, varianten in zuordnung.items():
        if p in {v.upper() for v in varianten}:
            return gruppe
    return fb["bewertung"]["standardgruppe"]


def attribute_fuer(position, fb=None):
    """Kern-Set plus verpflichtendes Positions-Set. Der Audit haelt fest, dass
    die Sets heute nicht standardisiert sind - willingness_to_attack wird beim
    WB zu 78 %, beim CB zu 4 % erhoben. Hier entscheidet die Position, nicht
    die Tagesform des Scouts."""
    fb = fb or fragebogen()
    gruppe = positionsgruppe(position, fb)
    return (list(fb["bewertung"]["kern"])
            + list(fb["bewertung"]["positionen"][gruppe]["attribute"]))


def attribut_keys(position, fb=None):
    return [a["key"] for a in attribute_fuer(position, fb)]


# ------------------------------------------------------------------- Case Pack
def pack_fuer_scout(con, scout, slug=None):
    fb = fragebogen()
    pack = db.aktives_pack(con, slug)
    if pack is None:
        raise Fehler("Kein offenes Case Pack.", 404)

    faelle = db.faelle_von(con, pack["id"])
    eigene = {
        r["fall_id"]: r
        for r in con.execute(
            "SELECT * FROM bewertungen WHERE scout_id = ?", (scout["id"],))
    }

    ausgabe = []
    for f in faelle:
        b = eigene.get(f["id"])
        abgegeben = bool(b and b["abgegeben"])
        d = db.fall_dict(f, mit_modell=abgegeben)
        gruppe = positionsgruppe(f["position"], fb)
        d["positionsgruppe"] = gruppe
        d["positionsgruppe_label"] = fb["bewertung"]["positionen"][gruppe]["label"]
        d["attribute"] = attribute_fuer(f["position"], fb)
        d["eigene_bewertung"] = {
            "level": json.loads(b["level_json"]) if b else {},
            "antworten": json.loads(b["antworten_json"]) if b else {},
            "prognosen": json.loads(b["prognosen_json"]) if b else {},
            "notiz": b["notiz"] if b else "",
            "abgegeben": abgegeben,
            "geaendert_am": b["geaendert_am"] if b else None,
        }
        if abgegeben:
            d["rueckmeldung"] = rueckmeldung(
                con, f, d["eigene_bewertung"], json.loads(f["modell_json"]), fb)
        ausgabe.append(d)

    return {
        "pack": {"slug": pack["slug"], "titel": pack["titel"],
                 "status": pack["status"], "schliesst_am": pack["schliesst_am"]},
        "faelle": ausgabe,
        "fragebogen": {k: fb[k] for k in
                       ("version", "skalen_richtung", "level", "prognosen",
                        "notiz", "schwellen")} | {"skala": fb["bewertung"]["skala"]},
    }


def rueckmeldung(con, fall_row, eigene, modell, fb):
    leit = leitfrage(fb)
    keys = attribut_keys(fall_row["position"], fb)
    antw = eigene["antworten"]
    lvl = eigene["level"]
    m_bew = (modell or {}).get("bewertung") or {}
    m_lvl = (modell or {}).get("level") or {}

    scout_level = lvl.get(leit)
    modell_level = m_lvl.get(leit)
    attr_werte = [float(antw[k]) for k in keys if antw.get(k) is not None]

    return {
        "modell_naehe": metriken.modell_naehe(antw, m_bew),
        "prognose_naehe": metriken.prognose_naehe(
            eigene["prognosen"], (modell or {}).get("prognose")),
        "level_abstand": (round(float(scout_level) - float(modell_level), 1)
                          if scout_level is not None and modell_level is not None
                          else None),
        "konflikt": metriken.konflikt(
            scout_level, modell_level,
            fb["schwellen"]["konflikt_level_abstand"]),
        "attribut_mittel": (round(metriken.mittel(attr_werte), 2)
                            if attr_werte else None),
        "kohorte": kohorten_schnitt(con, fall_row["id"], fb),
    }


def kohorten_schnitt(con, fall_id, fb=None):
    """Was das Feld zu diesem Fall gesagt hat - roh und rater-bereinigt.

    Der rohe Schnitt vermischt die Einschaetzung mit der Strenge der Scouts,
    die zufaellig abgegeben haben. Der bereinigte Schnitt z-standardisiert
    jeden Scout an seinen eigenen Abgaben und rechnet das Feldmittel danach
    auf die Skala zurueck. Erst ab drei Abgaben, sonst waere der 'Schnitt' die
    Meinung von zwei Leuten mit Nachkommastelle.
    """
    fb = fb or fragebogen()
    leit = leitfrage(fb)
    rows = con.execute(
        """SELECT scout_id, level_json, antworten_json FROM bewertungen
           WHERE fall_id = ? AND abgegeben = 1""", (fall_id,)).fetchall()
    if len(rows) < 3:
        return None

    gesammelt = {}
    for r in rows:
        for quelle in (json.loads(r["antworten_json"]), json.loads(r["level_json"])):
            for k, v in quelle.items():
                if v is not None:
                    gesammelt.setdefault(k, []).append(float(v))

    ergebnis = {"n": len(rows),
                "mittel": {k: round(metriken.mittel(v), 2)
                           for k, v in gesammelt.items()}}

    # Rater-Bereinigung auf der Leitfrage: jeder Scout gegen sein eigenes
    # Mittel und seine eigene Streuung ueber alle bisherigen Abgaben.
    alle = {}
    for r in con.execute(
            "SELECT scout_id, level_json FROM bewertungen WHERE abgegeben = 1"):
        v = json.loads(r["level_json"]).get(leit)
        if v is not None:
            alle.setdefault(r["scout_id"], []).append(float(v))

    z_hier, pool = [], [x for w in alle.values() for x in w]
    for r in rows:
        v = json.loads(r["level_json"]).get(leit)
        eigene = alle.get(r["scout_id"], [])
        if v is None or len(eigene) < 3:
            continue
        s = metriken.stdabw(eigene)
        if not s:
            continue
        z_hier.append((float(v) - metriken.mittel(eigene)) / s)

    if len(z_hier) >= 3 and len(pool) >= 3:
        pool_s = metriken.stdabw(pool)
        if pool_s:
            ergebnis["mittel_bereinigt"] = round(
                metriken.mittel(pool) + metriken.mittel(z_hier) * pool_s, 2)
            ergebnis["n_bereinigt"] = len(z_hier)
    return ergebnis


# ------------------------------------------------------------------- Speichern
def bewertung_speichern(con, scout, fall_id, level, antworten, prognosen, notiz,
                        sekunden, abgeben):
    fb = fragebogen()
    fall = con.execute("SELECT * FROM faelle WHERE id = ?", (fall_id,)).fetchone()
    if fall is None:
        raise Fehler("Fall unbekannt.", 404)
    pack = con.execute("SELECT * FROM packs WHERE id = ?",
                       (fall["pack_id"],)).fetchone()
    if pack["status"] != "offen":
        raise Fehler("Das Case Pack ist geschlossen.", 409)

    lmin, lmax = fb["level"]["min"], fb["level"]["max"]
    gueltige_level = {f["key"] for f in fb["level"]["fragen"]}
    gueltige_attr = set(attribut_keys(fall["position"], fb))
    gueltige_prognosen = {p["key"] for p in fb["prognosen"]}
    smin, smax = fb["bewertung"]["skala"]["min"], fb["bewertung"]["skala"]["max"]

    sauber_l = {}
    for k, v in (level or {}).items():
        if k not in gueltige_level or v is None or v == "":
            continue
        iv = int(v)
        if not lmin <= iv <= lmax:
            raise Fehler(f"Level '{k}' liegt außerhalb der Skala {lmin}–{lmax}.")
        sauber_l[k] = iv

    sauber_a = {}
    for k, v in (antworten or {}).items():
        if v is None or v == "":
            continue
        if k not in gueltige_attr:
            raise Fehler(f"Attribut '{k}' gehört nicht zum Set dieser Position.")
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
        for was, fehlend in (
                ("Level-Einschätzungen", sorted(gueltige_level - set(sauber_l))),
                ("Bewertungen", sorted(gueltige_attr - set(sauber_a))),
                ("Prognosen", sorted(gueltige_prognosen - set(sauber_p)))):
            if fehlend:
                raise Fehler(f"Vor der Abgabe fehlen noch {was}: "
                             + ", ".join(fehlend))

    vorher = con.execute(
        "SELECT abgegeben FROM bewertungen WHERE scout_id = ? AND fall_id = ?",
        (scout["id"], fall_id)).fetchone()
    if vorher and vorher["abgegeben"]:
        raise Fehler("Dieser Fall ist bereits abgegeben und bleibt gesperrt.", 409)

    notiz = (notiz or "")[: fb["notiz"]["max_zeichen"]]
    with con:
        con.execute(
            """INSERT INTO bewertungen
                 (scout_id, fall_id, level_json, antworten_json, prognosen_json,
                  notiz, sekunden, abgegeben, geaendert_am)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(scout_id, fall_id) DO UPDATE SET
                 level_json     = excluded.level_json,
                 antworten_json = excluded.antworten_json,
                 prognosen_json = excluded.prognosen_json,
                 notiz          = excluded.notiz,
                 sekunden       = excluded.sekunden,
                 abgegeben      = excluded.abgegeben,
                 geaendert_am   = excluded.geaendert_am""",
            (scout["id"], fall_id, json.dumps(sauber_l), json.dumps(sauber_a),
             json.dumps(sauber_p), notiz, int(sekunden or 0),
             1 if abgeben else 0, db.jetzt()))
        db.protokoll(con, scout["id"],
                     "abgabe" if abgeben else "zwischenstand", str(fall_id))

    if not abgeben:
        return {"gespeichert": True, "abgegeben": False}

    modell = json.loads(fall["modell_json"])
    eigene = {"level": sauber_l, "antworten": sauber_a, "prognosen": sauber_p}
    return {
        "gespeichert": True,
        "abgegeben": True,
        "modell": modell,
        "rueckmeldung": rueckmeldung(con, fall, eigene, modell, fb),
    }


# --------------------------------------------------------------- Rohdatenlader
def _rohdaten(con, pack_slug=None):
    if pack_slug:
        faelle = con.execute(
            """SELECT f.* FROM faelle f JOIN packs p ON p.id = f.pack_id
               WHERE p.slug = ?""", (pack_slug,)).fetchall()
    else:
        faelle = con.execute("SELECT * FROM faelle").fetchall()
    faelle = {f["id"]: f for f in faelle}
    modelle = {i: json.loads(f["modell_json"]) for i, f in faelle.items()}
    bew = [b for b in con.execute(
        "SELECT * FROM bewertungen WHERE abgegeben = 1") if b["fall_id"] in faelle]
    aufl = {(r["fall_id"], r["frage"]): r["ergebnis"]
            for r in con.execute("SELECT * FROM aufloesungen")
            if r["fall_id"] in faelle}
    return faelle, modelle, bew, aufl


def _abgaben_je_scout(faelle, modelle, bew, fb):
    """Bewertungen in die Form bringen, die metriken.scout_metriken erwartet -
    Level und Attribute zusammen, Modell daneben."""
    leit = leitfrage(fb)
    je_scout = {}
    for b in bew:
        fall = faelle[b["fall_id"]]
        lvl = json.loads(b["level_json"])
        antw = json.loads(b["antworten_json"])
        modell = modelle.get(b["fall_id"], {})
        keys = attribut_keys(fall["position"], fb)
        attr = [float(antw[k]) for k in keys if antw.get(k) is not None]
        je_scout.setdefault(b["scout_id"], []).append({
            "fall_id": b["fall_id"],
            "position": fall["position"],
            "gruppe": positionsgruppe(fall["position"], fb),
            "level": lvl,
            "antworten": {**antw, **{leit: lvl.get(leit)}} if lvl.get(leit) is not None
                         else dict(antw),
            "attribut_mittel": metriken.mittel(attr) if attr else None,
            "prognosen": json.loads(b["prognosen_json"]),
            "modell": {"bewertung": (modell.get("bewertung") or {}),
                       "prognose": (modell.get("prognose") or {}),
                       "level": (modell.get("level") or {})},
        })
    return je_scout


def _audit_kennzahlen(abgaben, fb):
    """Halo, Entkopplung und Zentraltendenz fuer einen einzelnen Scout."""
    leit = leitfrage(fb)
    andere = [f["key"] for f in fb["level"]["fragen"] if f["key"] != leit]
    zweit = andere[0] if andere else None

    paare = [(a["level"].get(leit), a["attribut_mittel"]) for a in abgaben]
    paare = [(float(x), float(y)) for x, y in paare
             if x is not None and y is not None]
    h = metriken.halo([x for x, _ in paare], [y for _, y in paare])

    e = None
    if zweit:
        lp = [(a["level"].get(leit), a["level"].get(zweit)) for a in abgaben]
        lp = [(float(x), float(y)) for x, y in lp
              if x is not None and y is not None]
        e = metriken.entkopplung([x for x, _ in lp], [y for _, y in lp])

    return {
        "halo": round(h, 2) if h is not None else None,
        "entkopplung": round(e, 2) if e is not None else None,
        "zentraltendenz": metriken.zentraltendenz(
            [a["level"].get(leit) for a in abgaben]),
    }


# ----------------------------------------------------------------- Leaderboard
def leaderboard(con, pack_slug=None):
    fb = fragebogen()
    leit = leitfrage(fb)
    faelle, modelle, bew, aufl = _rohdaten(con, pack_slug)
    scouts = {r["id"]: r for r in con.execute("SELECT * FROM scouts")}
    je_scout = _abgaben_je_scout(faelle, modelle, bew, fb)

    kohorte = {}
    for sid, abgaben in je_scout.items():
        for a in abgaben:
            v = a["level"].get(leit)
            if v is not None:
                kohorte.setdefault(a["fall_id"], {}).setdefault(
                    leit, []).append(float(v))

    raten = metriken.basisraten(aufl)
    zeilen = []
    for sid, abgaben in je_scout.items():
        s = scouts.get(sid)
        if s is None:
            continue
        # Das Modell liefert die Leitfrage im level-Block, nicht im
        # bewertung-Block - fuer die Trennschaerfe zusammenfuehren.
        fuer_metrik = [{**a, "modell": {**a["modell"],
                        "bewertung": {**a["modell"]["bewertung"],
                                      **{leit: a["modell"]["level"].get(leit)}}}}
                       for a in abgaben]
        m = metriken.scout_metriken(fuer_metrik, kohorte, aufl, leitfrage=leit)
        m["brier_skill"] = metriken.skill_gesamt(m.pop("_paare_je_frage"), raten)
        m.pop("kalibrierungskurve", None)
        m.update(_audit_kennzahlen(abgaben, fb))
        m["scout_id"] = sid
        m["name"] = s["name"]
        zeilen.append(m)

    kohorten_sd = _median([z["spreizung"] for z in zeilen
                           if z["spreizung"] is not None])
    for z in zeilen:
        z["spreizungs_index"] = metriken.spreizungs_index(
            z["spreizung"], kohorten_sd)

    aufgeloest = any(z["n_aufgeloest"] for z in zeilen)
    if aufgeloest:
        zeilen.sort(key=lambda z: (
            -(z["brier_skill"] if z["brier_skill"] is not None else -9),
            z["brier"] if z["brier"] is not None else 9))
    else:
        zeilen.sort(key=lambda z: (
            -(z["trennschaerfe"] if z["trennschaerfe"] is not None else -9),
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
                    "Noch keine Prognose aufgelöst — die Rangfolge ist "
                    "vorläufig und sortiert nach Trennschärfe gegen das Modell."),
    }


def profil(con, scout, pack_slug=None):
    fb = fragebogen()
    leit = leitfrage(fb)
    faelle, modelle, bew, aufl = _rohdaten(con, pack_slug)
    je_scout = _abgaben_je_scout(faelle, modelle, bew, fb)
    abgaben = je_scout.get(scout["id"], [])

    kohorte = {}
    for _sid, liste in je_scout.items():
        for a in liste:
            v = a["level"].get(leit)
            if v is not None:
                kohorte.setdefault(a["fall_id"], {}).setdefault(
                    leit, []).append(float(v))

    fuer_metrik = [{**a, "modell": {**a["modell"],
                    "bewertung": {**a["modell"]["bewertung"],
                                  **{leit: a["modell"]["level"].get(leit)}}}}
                   for a in abgaben]
    m = metriken.scout_metriken(fuer_metrik, kohorte, aufl, leitfrage=leit)
    m["brier_skill"] = metriken.skill_gesamt(m.pop("_paare_je_frage"),
                                             metriken.basisraten(aufl))
    m.update(_audit_kennzahlen(abgaben, fb))
    m["name"] = scout["name"]

    verteilung = {str(i): 0 for i in range(fb["level"]["min"],
                                           fb["level"]["max"] + 1)}
    for a in abgaben:
        v = a["level"].get(leit)
        if v is not None:
            verteilung[str(int(v))] += 1
    m["verteilung"] = verteilung
    m["schwellen"] = fb["schwellen"]
    return m


# ------------------------------------------------------------ Kalibrier-Report
def kalibrier_report(con, pack_slug=None):
    """Der Scout Rating Audit, fortlaufend statt einmalig.

    Dieselben fuenf Diagnosen, die der Audit im Juni auf 187 Bewertungen
    gerechnet hat - hier auf allem, was die Liga bisher abgegeben hat. Plus die
    Konfliktliste, die der Audit als wertvollste Review-Liste bezeichnet.
    """
    fb = fragebogen()
    leit = leitfrage(fb)
    schwellen = fb["schwellen"]
    faelle, modelle, bew, _aufl = _rohdaten(con, pack_slug)
    scouts = {r["id"]: r for r in con.execute("SELECT * FROM scouts")}
    je_scout = _abgaben_je_scout(faelle, modelle, bew, fb)
    alle = [a for liste in je_scout.values() for a in liste]

    if not alle:
        return {"n_bewertungen": 0, "warnungen": [],
                "hinweis": "Noch keine Abgaben."}

    # 1 Zentraltendenz je Level-Frage
    zentral = {}
    for f in fb["level"]["fragen"]:
        z = metriken.zentraltendenz([a["level"].get(f["key"]) for a in alle])
        if z:
            z["label"] = f["label"]
            z["ueber_ziel"] = z["anteil"] > schwellen["zentraltendenz_max"]
            zentral[f["key"]] = z

    # 2 Rater-Strenge auf der Leitfrage
    strenge_roh = {scouts[sid]["name"]: [a["level"].get(leit) for a in liste]
                   for sid, liste in je_scout.items() if sid in scouts}
    strenge = metriken.rater_strenge(strenge_roh)

    # 3 Halo und Entkopplung, gesamt und je Scout
    gesamt_audit = _audit_kennzahlen(alle, fb)
    je_scout_audit = {scouts[sid]["name"]: _audit_kennzahlen(liste, fb)
                      for sid, liste in je_scout.items() if sid in scouts}

    # 4 Attribut-Trennschaerfe, je Positionsgruppe getrennt
    attribute = {}
    for gruppe in fb["bewertung"]["positionen"]:
        werte = {}
        treffer = [a for a in alle if a["gruppe"] == gruppe]
        if not treffer:
            continue
        for a in treffer:
            for k, v in a["antworten"].items():
                if k != leit:
                    werte.setdefault(k, []).append(v)
        attribute[gruppe] = metriken.attribut_trennschaerfe(
            werte, schwellen["tote_attribute_sigma"])

    # 5 Scout gegen Modell, gesamt und je Positionsgruppe
    def rho(liste):
        paare = [(a["level"].get(leit), a["modell"]["level"].get(leit))
                 for a in liste]
        paare = [(float(x), float(y)) for x, y in paare
                 if x is not None and y is not None]
        if len(paare) < 3:
            return None
        r = metriken.spearman([x for x, _ in paare], [y for _, y in paare])
        return round(r, 2) if r is not None else None

    # Die Rangkorrelation je Gruppe braucht mehrere *Faelle* in dieser Gruppe -
    # neun Bewertungen zu einem einzigen Spieler ergeben keine Rangfolge, weil
    # das Modell-Level dann konstant ist. Deshalb beide Zahlen ausweisen.
    gruppen = sorted({a["gruppe"] for a in alle})
    scout_vs_modell = {
        "gesamt": rho(alle),
        "je_gruppe": {g: rho([a for a in alle if a["gruppe"] == g])
                      for g in gruppen},
        "n_je_gruppe": {g: sum(1 for a in alle if a["gruppe"] == g)
                        for g in gruppen},
        "n_faelle_je_gruppe": {
            g: len({a["fall_id"] for a in alle if a["gruppe"] == g})
            for g in gruppen},
        "mindest_faelle": 3,
    }

    # 6 Konfliktliste
    konflikte = []
    for sid, liste in je_scout.items():
        for a in liste:
            k = metriken.konflikt(a["level"].get(leit),
                                  a["modell"]["level"].get(leit),
                                  schwellen["konflikt_level_abstand"])
            if k:
                konflikte.append({
                    "fall_id": a["fall_id"],
                    "spieler": faelle[a["fall_id"]]["name"],
                    "position": a["position"],
                    "scout": scouts[sid]["name"] if sid in scouts else "?",
                    "scout_level": a["level"].get(leit),
                    "modell_level": a["modell"]["level"].get(leit),
                    **k,
                })
    konflikte.sort(key=lambda k: -abs(k["differenz"]))

    warnungen = []
    genug = len(alle) >= schwellen.get("mindest_faelle_diagnose", 5)
    if not genug:
        warnungen.append(
            f"Erst {len(alle)} Bewertungen — die Diagnosen unten sind noch "
            f"Momentaufnahmen und werden ab "
            f"{schwellen.get('mindest_faelle_diagnose', 5)} Bewertungen "
            f"belastbar.")
    for key, z in zentral.items():
        if genug and z["ueber_ziel"]:
            warnungen.append(
                f"Zentraltendenz bei „{z['label']}“: {round(z['anteil'] * 100)} % "
                f"entfallen auf Level {z['modalwert']} — Ziel sind höchstens "
                f"{round(schwellen['zentraltendenz_max'] * 100)} %.")
    if genug and strenge.get("spanne") and strenge["spanne"] >= 1.0:
        warnungen.append(
            f"Rater-Strenge: {strenge['spanne']} Level zwischen "
            f"{strenge['strengster']} (streng) und {strenge['mildester']} "
            f"(mild) — eine Kalibrier-Session an gemeinsamen Referenzspielern "
            f"schließt diese Lücke.")
    if genug and (gesamt_audit["halo"] or 0) >= schwellen["halo_warnung"]:
        warnungen.append(
            f"Halo: das Level folgt dem Attribut-Mittel mit r = "
            f"{gesamt_audit['halo']} — das Gesamturteil trägt kaum eigene "
            f"Information.")
    if genug and (gesamt_audit["entkopplung"] or 0) >= schwellen["entkopplung_warnung"]:
        warnungen.append(
            f"Entkopplung: bewiesenes Niveau und Ceiling laufen mit r = "
            f"{gesamt_audit['entkopplung']} gleich — das Ceiling wird als "
            f"Aufschlag vergeben, nicht eigenständig geschätzt.")
    tote = sorted({k for g in attribute.values()
                   for k, v in g.items() if v["tot"]})
    if genug and tote:
        warnungen.append(
            f"Tote Attribute (σ < {schwellen['tote_attribute_sigma']}): "
            + ", ".join(tote)
            + " — entweder mit schärferen Ankern versehen oder streichen.")

    return {
        "n_bewertungen": len(alle),
        "n_scouts": len(je_scout),
        "leitfrage": leit,
        "zentraltendenz": zentral,
        "rater_strenge": strenge,
        "halo": {"gesamt": gesamt_audit["halo"], "je_scout":
                 {n: v["halo"] for n, v in je_scout_audit.items()}},
        "entkopplung": {"gesamt": gesamt_audit["entkopplung"], "je_scout":
                        {n: v["entkopplung"] for n, v in je_scout_audit.items()}},
        "attribute": attribute,
        "scout_vs_modell": scout_vs_modell,
        "konflikte": konflikte,
        "schwellen": schwellen,
        "warnungen": warnungen,
    }


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
