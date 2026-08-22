#!/usr/bin/env python3
"""Modellerwartung aus einem NOVA-Export ableiten.

Der Case Pack braucht drei Dinge je Spieler: ein Level 1-10, eine Erwartung je
Attribut auf der 1-5-Skala und Prognosewahrscheinlichkeiten. Bisher kamen die
von Hand. Hier entstehen sie aus Daten - so weit die Daten reichen, und keinen
Schritt weiter.

Was sich rechnen laesst und was nicht:

  Perzentil im Positionspool   rechnen. Braucht den vollen Pool der Liga,
                               >= 400 Minuten, sonst ist der Rang wertlos.
  Level heute                  rechnen, SOBALD das Liga-Niveau bekannt ist.
                               Perzentil verschiebt es um hoechstens eine Stufe
                               (die Bruecke aus Kapitel 9 des Audits).
  Liga-Niveau                  NICHT rechenbar. Ein Perzentil sagt, wie gut
                               jemand in seiner Liga ist, nie wie stark die
                               Liga ist. Steht in liga_level.json.
  Attributerwartung            rechnen, wo eine Kennzahl auf das Attribut
                               zeigt. Wo keine zeigt: leer lassen.
  Ceiling                      nicht beobachtbar. Was hier steht, ist eine
                               offen deklarierte Heuristik aus Alter und
                               Verlauf, kein gefittetes Modell - es gibt keine
                               Outcome-Historie, auf die man fitten koennte.
  Prognosen                    brauchen Basisraten aus aufgeloesten Faellen.
                               Ohne die bleibt das Feld leer.

Der Grundsatz durchgehend: eine Luecke ausweisen ist billiger als eine Zahl
erfinden. Eine erfundene Modellerwartung macht Trennschaerfe, Konfliktliste und
Sofort-Rueckmeldung unbrauchbar, ohne dass es jemandem auffaellt.
"""
import csv
import io
import json
import os
import re
import unicodedata

HIER = os.path.dirname(os.path.abspath(__file__))
REGISTER = os.path.join(HIER, "liga_level.json")

MIN_MINUTEN = 400          # Methodikregel: Raenge nur gegen Pools ab 400 Minuten
POOL_KLEIN = 15            # darunter ist ein Perzentil eine Meinung mit Nachkomma


# ------------------------------------------------------------------ Einlesen
def _entkleiden(text):
    """Auf einen Vergleichskern reduzieren: klein, ohne Akzente, ohne Beiwerk."""
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


def zahl(wert):
    """Robust gegen deutsche Kommazahlen, Prozentzeichen und leere Zellen."""
    if wert is None:
        return None
    s = str(wert).strip().replace("%", "").replace(" ", "")
    if not s or s in {"-", "--", "N/A", "n/a", "NA"}:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")   # 1.234,5
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def export_lesen(pfad):
    """CSV einlesen, ohne das Trennzeichen zu raten zu muessen.

    Die Exporte sind semikolongetrennt und utf-8-sig, aber ein Export, der
    einmal durch Excel gelaufen ist, kann alles sein. Deshalb sniffen.
    """
    with open(pfad, encoding="utf-8-sig", newline="") as f:
        probe = f.read(8192)
        f.seek(0)
        try:
            trenner = csv.Sniffer().sniff(probe, delimiters=";,\t").delimiter
        except csv.Error:
            trenner = ";"
        return list(csv.DictReader(f, delimiter=trenner))


# -------------------------------------------------------------- Spaltensuche
# Logischer Name -> Kandidaten. Gesucht wird auf dem entkleideten Kern, damit
# "xG Assist", "xg_assist" und "XG-ASSIST" dieselbe Spalte treffen.
SPALTEN = {
    "spieler":   ["player", "spieler", "name", "playername"],
    "position":  ["position", "pos", "primaryposition"],
    "team":      ["team", "club", "currentclub", "verein"],
    "liga":      ["competition", "league", "liga", "wettbewerb"],
    "saison":    ["season", "saison"],
    "minuten":   ["minutesplayed", "minutes", "min", "minuten"],
    "geburt":    ["birthday", "dateofbirth", "dob", "geburtsdatum", "birthdate"],
    "alter":     ["age", "alter"],
    "index":     ["defaultindex", "index", "novaindex", "profileindex",
                  "overallindex"],
}


def spalten_finden(kopf, zusatz=None):
    """Logische Namen auf die tatsaechlichen Spalten des Exports abbilden.

    Zuerst exakte Treffer auf dem Kern, dann Teilstring-Treffer. Ein Export
    mit unbekannten Spaltennamen soll nicht scheitern, sondern melden, was er
    nicht gefunden hat.
    """
    karte = dict(SPALTEN)
    karte.update(zusatz or {})
    kerne = {_entkleiden(k): k for k in kopf}
    gefunden, fehlt = {}, []
    for logisch, kandidaten in karte.items():
        treffer = next((kerne[_entkleiden(c)] for c in kandidaten
                        if _entkleiden(c) in kerne), None)
        if treffer is None:
            for kern, echt in kerne.items():
                if any(_entkleiden(c) and _entkleiden(c) in kern
                       for c in kandidaten):
                    treffer = echt
                    break
        if treffer:
            gefunden[logisch] = treffer
        else:
            fehlt.append(logisch)
    return gefunden, fehlt


def index_spalten(kopf):
    """Alle Spalten, die nach einem Index oder Sub-Index aussehen.

    NOVA-Indizes kommen als 0-1-Floats. Welche Sub-Indizes ein Export
    mitbringt, wechselt - deshalb nicht hart verdrahten, sondern finden.
    """
    aus = {}
    for spalte in kopf:
        kern = _entkleiden(spalte)
        if "index" in kern or kern.endswith("score"):
            aus[spalte] = kern
    return aus


# -------------------------------------------------------------- Poolpruefung
def pool_pruefen(zeilen, spalten, min_minuten=MIN_MINUTEN):
    """Taugt dieser Pool als Vergleichsbasis?

    Die Methodikregel lautet: Raenge nur gegen den vollen Positionspool einer
    Liga ab 400 Minuten. Ein handverlesener Export mit zwoelf Namen erzeugt
    Perzentile, die wie Messwerte aussehen und keine sind. Lieber laut sagen.
    """
    m_spalte = spalten.get("minuten")
    gesamt = len(zeilen)
    mit_minuten = [z for z in zeilen
                   if m_spalte and (zahl(z.get(m_spalte)) or 0) >= min_minuten]
    kurz = [z for z in zeilen
            if m_spalte and 0 < (zahl(z.get(m_spalte)) or 0) < 60]

    gruende = []
    if not m_spalte:
        gruende.append("keine Minutenspalte gefunden - der 400-Minuten-Filter "
                       "greift nicht")
    if len(mit_minuten) < POOL_KLEIN:
        gruende.append(f"nur {len(mit_minuten)} Zeilen ab {min_minuten} Minuten "
                       f"- zu wenig fuer ein belastbares Perzentil")
    if kurz:
        gruende.append(f"{len(kurz)} Zeilen unter 60 Minuten - sieht nach einem "
                       f"handverlesenen Export aus, nicht nach einem Ligapool")
    ligen = {z.get(spalten.get("liga", ""), "") for z in zeilen}
    ligen.discard("")
    if len(ligen) > 3:
        gruende.append(f"{len(ligen)} verschiedene Wettbewerbe im Pool - ein "
                       f"Perzentil ueber Ligagrenzen hinweg vergleicht nichts")

    return {
        "zeilen_gesamt": gesamt,
        "zeilen_im_pool": len(mit_minuten),
        "min_minuten": min_minuten,
        "ligen": sorted(ligen),
        "brauchbar": not gruende,
        "gruende": gruende,
    }


# ---------------------------------------------------------------- Perzentile
def perzentil(wert, pool):
    """Rang in Prozent, Bindungen mittig (midrank) - dieselbe Konvention wie
    in den Reports. 0-100, hoeher ist besser."""
    werte = [w for w in pool if w is not None]
    if wert is None or len(werte) < 2:
        return None
    kleiner = sum(1 for w in werte if w < wert)
    gleich = sum(1 for w in werte if w == wert)
    return round(100.0 * (kleiner + 0.5 * gleich) / len(werte), 1)


# Perzentilbaender auf die 1-5-Attributskala. Bewusst breit an den Raendern:
# das Modell ist die Referenz, gegen die Trennschaerfe gemessen wird - eine
# Referenz, die nie 1 oder 5 sagt, kann keine Spreizung pruefen.
BAENDER = [(10, 1), (35, 2), (65, 3), (90, 4), (101, 5)]


def perzentil_zu_note(p):
    if p is None:
        return None
    for grenze, note in BAENDER:
        if p < grenze:
            return note
    return 5


# ------------------------------------------------------------- Liga -> Level
def register_laden(pfad=REGISTER):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def liga_aufloesen(name, register=None):
    """Liganame aus dem Export auf einen Registereintrag abbilden.

    Rueckgabe: (kanonischer Name, Level oder None, Eintrag oder None).
    Ein unbekannter Name ist kein Fehler - er ist eine offene Frage, und die
    gehoert ins Methodenblatt, nicht in eine geratene Zahl.
    """
    register = register or register_laden()
    roh = (name or "").strip()
    kanonisch = register["aliasse"].get(roh, roh)
    if kanonisch not in register["ligen"]:
        kerne = {_entkleiden(k): k for k in register["ligen"]}
        kanonisch = kerne.get(_entkleiden(roh), kanonisch)
    eintrag = register["ligen"].get(kanonisch)
    return kanonisch, (eintrag or {}).get("level"), eintrag


# --------------------------------------------------------- Level und Ceiling
def level_heute(liga_stufe, perzentil_wert):
    """Bewiesenes Niveau: die Liga, in der real gespielt wurde, verschoben um
    hoechstens eine Stufe durch das Perzentil im Positionspool."""
    import metriken
    return metriken.perzentil_zu_level(perzentil_wert, liga_stufe)


# Alterszuschlag aufs Ceiling. Kein gefittetes Modell - dafuer fehlt jede
# Outcome-Historie. Eine offen deklarierte Heuristik: Entwicklungsspielraum
# nimmt mit dem Alter ab, jenseits der Peakjahre kippt er ins Negative.
#
# Bewusst zurueckhaltend kalibriert. Das haeufigste Ergebnis ueber zwei bis
# drei Jahre ist, dass ein Spieler auf seinem Niveau bleibt; Spruenge um zwei
# Stufen sind selten. Ein systematisch optimistisches Modell waere hier
# doppelt teuer: es ist die Referenz, gegen die Scouts gemessen werden, also
# liesse es das ganze Feld pessimistisch aussehen und wuerde einen Bias
# ausweisen, der keiner ist.
ALTERSZUSCHLAG = [(18, 1.5), (20, 1.0), (22, 0.5), (26, 0.0),
                  (29, 0.0), (99, -0.5)]
MAX_ZUWACHS = 2.0


def ceiling(level_jetzt, alter, trend=None):
    """Realistisches Niveau in zwei bis drei Jahren.

    Zwei Eingaenge, beide beobachtbar: Alter und Verlauf des Index zwischen
    den letzten beiden Saisons. Was daraus wird, ist eine Setzung - sie steht
    hier, damit sie diskutierbar ist, statt in einem Kopf zu stecken.
    """
    if level_jetzt is None or alter is None:
        return None
    zuschlag = next(z for grenze, z in ALTERSZUSCHLAG if alter <= grenze)
    if trend is not None:
        zuschlag += 0.5 if trend > 0.05 else (-0.5 if trend < -0.05 else 0.0)
    if alter < 27:
        zuschlag = max(zuschlag, 0.0)   # junge Spieler faellt man nicht ab
    zuschlag = min(zuschlag, MAX_ZUWACHS)
    return max(1.0, min(10.0, round(level_jetzt + zuschlag, 1)))


def alter_aus(zeile, spalten, stichjahr=None):
    a = zahl(zeile.get(spalten.get("alter", "")))
    if a and 14 <= a <= 45:
        return int(a)
    roh = str(zeile.get(spalten.get("geburt", ""), ""))
    jahr = re.search(r"(19|20)\d{2}", roh)
    if jahr and stichjahr:
        return stichjahr - int(jahr.group(0))
    return None


# ------------------------------------------------------------- Zusammenbauen
def spieler_modell(zeilen_spieler, pool_werte, liga_stufe, attribut_quellen,
                   gesamt_perzentil=None, alter=None, trend=None):
    """Modellerwartung fuer einen Spieler.

    zeilen_spieler    seine Zeilen aus dem Export (eine je getaggter Saison)
    pool_werte        {Kennzahlenspalte: [Werte des Positionspools]}
    liga_stufe        1-10 aus dem Register, oder None
    attribut_quellen  {Attributschluessel: Kennzahlenspalte} - nur was
                      tatsaechlich zugeordnet ist; der Rest bleibt leer
    gesamt_perzentil  Perzentil des Gesamtindex im Pool. Treibt das Level und
                      wird ausdruecklich uebergeben, nicht aus den Attributen
                      geraten - ein Level aus einem Teilaspekt waere falsch.
    """
    def mittel(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    bewertung, perzentile, ohne_daten = {}, {}, []
    for attribut, spalte in attribut_quellen.items():
        eigen = mittel([zahl(z.get(spalte)) for z in zeilen_spieler])
        p = perzentil(eigen, pool_werte.get(spalte, []))
        perzentile[attribut] = p
        note = perzentil_zu_note(p)
        if note is None:
            ohne_daten.append(attribut)
        else:
            bewertung[attribut] = note

    return {
        "bewertung": bewertung,
        "attribut_perzentile": perzentile,
        "attribute_ohne_daten": ohne_daten,
        "liga_stufe": liga_stufe,
        "gesamt_perzentil": gesamt_perzentil,
        "level_heute": level_heute(liga_stufe, gesamt_perzentil),
        "level_ceiling": ceiling(level_heute(liga_stufe, gesamt_perzentil),
                                 alter, trend),
        "alter": alter,
        "trend": trend,
    }


def bericht(pruefung, register_luecken, ohne_daten, ohne_prognose):
    """Das Methodenblatt: was gerechnet wurde, was gesetzt, was fehlt.

    Gehoert neben jeden Case Pack. Ein Modell ohne diesen Zettel ist nicht
    nachpruefbar, und ein nicht nachpruefbares Modell ist als Referenz fuer
    Trennschaerfe wertlos.
    """
    zeilen = []
    zeilen.append("## Datengrundlage")
    zeilen.append(f"- Pool: {pruefung['zeilen_im_pool']} von "
                  f"{pruefung['zeilen_gesamt']} Zeilen ab "
                  f"{pruefung['min_minuten']} Minuten")
    if pruefung["ligen"]:
        zeilen.append(f"- Wettbewerbe: {', '.join(pruefung['ligen'])}")
    if not pruefung["brauchbar"]:
        zeilen.append("- **Pool nicht belastbar:**")
        zeilen += [f"  - {g}" for g in pruefung["gruende"]]

    zeilen.append("\n## Gesetzt statt gerechnet")
    zeilen.append("- Liga-Niveau kommt aus `liga_level.json`, nicht aus dem "
                  "Export. Ein Perzentil misst den Rang in der Liga, nie die "
                  "Liga.")
    zeilen.append("- Das Ceiling ist eine Heuristik aus Alter und Indexverlauf, "
                  "kein gefittetes Modell. Es gibt keine Outcome-Historie, auf "
                  "die man fitten koennte.")
    if register_luecken:
        zeilen.append("- **Ohne Liga-Niveau, also ohne Level:** "
                      + ", ".join(sorted(register_luecken)))

    zeilen.append("\n## Luecken")
    zeilen.append(f"- Attribute ohne Datenzuordnung: "
                  + (", ".join(sorted(ohne_daten)) if ohne_daten else "keine"))
    zeilen.append(f"- Prognosen ohne Basisrate: "
                  + (", ".join(sorted(ohne_prognose)) if ohne_prognose
                     else "keine"))
    zeilen.append("\nLeere Felder sind Absicht. Eine erfundene Modellerwartung "
                  "macht Trennschaerfe, Konfliktliste und Sofort-Rueckmeldung "
                  "unbrauchbar, ohne dass es jemandem auffaellt.")
    return "\n".join(zeilen)


# ------------------------------------------------------------------- Basisraten
def basisraten_aus_liga(con):
    """Prognosewahrscheinlichkeiten aus bereits aufgeloesten Faellen.

    Solange nichts aufgeloest ist, gibt es keine Basisrate - und dann bleibt
    das Feld leer, statt eine 0.5 hinzuschreiben, die nach Wissen aussieht.
    """
    import metriken
    aufl = {(r["fall_id"], r["frage"]): r["ergebnis"]
            for r in con.execute("SELECT * FROM aufloesungen")}
    if not aufl:
        return {}
    return {f: round(v, 3) for f, v in metriken.basisraten(aufl).items()}


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, HIER)

    p = argparse.ArgumentParser(
        description="Export ansehen: welche Spalten, welcher Pool, welche Liga?")
    p.add_argument("--export", required=True)
    a = p.parse_args()

    zeilen = export_lesen(a.export)
    if not zeilen:
        raise SystemExit("Export ist leer.")
    kopf = list(zeilen[0])
    spalten, fehlt = spalten_finden(kopf)
    pruefung = pool_pruefen(zeilen, spalten)

    print(f"{len(zeilen)} Zeilen, {len(kopf)} Spalten\n")
    print("Erkannt:")
    for k, v in sorted(spalten.items()):
        print(f"  {k:<10} -> {v}")
    if fehlt:
        print("Nicht gefunden:", ", ".join(fehlt))
    print("\nIndexspalten:", ", ".join(sorted(index_spalten(kopf))) or "keine")
    print(f"\nPool: {pruefung['zeilen_im_pool']}/{pruefung['zeilen_gesamt']} "
          f"ab {MIN_MINUTEN} Minuten, brauchbar: {pruefung['brauchbar']}")
    for g in pruefung["gruende"]:
        print("  !", g)
    for liga in pruefung["ligen"]:
        name, stufe, _ = liga_aufloesen(liga)
        print(f"  Liga '{liga}' -> {name}: "
              + (f"Level {stufe}" if stufe else "NICHT eingeordnet"))
