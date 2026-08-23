"""SQLite-Schicht der Scout League.

Eine Datei, keine Migrationen: `schema()` ist idempotent und laeuft bei jedem
Serverstart. Verbindungen werden pro Request geoeffnet und geschlossen - bei
zehn Usern kostet das nichts und erspart jedes Thread-Locking.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

PFAD = os.environ.get(
    "SCOUTLEAGUE_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoutleague.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS scouts (
  id          INTEGER PRIMARY KEY,
  code        TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  rolle       TEXT NOT NULL DEFAULT 'scout',
  aktiv       INTEGER NOT NULL DEFAULT 1,
  angelegt_am TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packs (
  id           INTEGER PRIMARY KEY,
  slug         TEXT UNIQUE NOT NULL,
  titel        TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'offen',
  schliesst_am TEXT,
  angelegt_am  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS faelle (
  id            INTEGER PRIMARY KEY,
  pack_id       INTEGER NOT NULL REFERENCES packs(id) ON DELETE CASCADE,
  ext_id        TEXT NOT NULL DEFAULT '',
  name          TEXT NOT NULL,
  position      TEXT NOT NULL DEFAULT '',
  jahrgang      INTEGER,
  verein        TEXT NOT NULL DEFAULT '',
  liga          TEXT NOT NULL DEFAULT '',
  fuss          TEXT NOT NULL DEFAULT '',
  video_url     TEXT NOT NULL DEFAULT '',
  indizes_json  TEXT NOT NULL DEFAULT '{}',
  modell_json   TEXT NOT NULL DEFAULT '{}',
  parameter_json TEXT NOT NULL DEFAULT '{}',
  reihenfolge   INTEGER NOT NULL DEFAULT 0,
  UNIQUE(pack_id, ext_id)
);

CREATE TABLE IF NOT EXISTS bewertungen (
  id             INTEGER PRIMARY KEY,
  scout_id       INTEGER NOT NULL REFERENCES scouts(id) ON DELETE CASCADE,
  fall_id        INTEGER NOT NULL REFERENCES faelle(id) ON DELETE CASCADE,
  level_json     TEXT NOT NULL DEFAULT '{}',
  antworten_json TEXT NOT NULL DEFAULT '{}',
  prognosen_json TEXT NOT NULL DEFAULT '{}',
  notiz          TEXT NOT NULL DEFAULT '',
  sekunden       INTEGER NOT NULL DEFAULT 0,
  abgegeben      INTEGER NOT NULL DEFAULT 0,
  geaendert_am   TEXT NOT NULL,
  UNIQUE(scout_id, fall_id)
);

CREATE TABLE IF NOT EXISTS aufloesungen (
  id            INTEGER PRIMARY KEY,
  fall_id       INTEGER NOT NULL REFERENCES faelle(id) ON DELETE CASCADE,
  frage         TEXT NOT NULL,
  ergebnis      INTEGER NOT NULL,
  quelle        TEXT NOT NULL DEFAULT '',
  aufgeloest_am TEXT NOT NULL,
  UNIQUE(fall_id, frage)
);

CREATE TABLE IF NOT EXISTS ereignisse (
  id       INTEGER PRIMARY KEY,
  ts       TEXT NOT NULL,
  scout_id INTEGER,
  art      TEXT NOT NULL,
  detail   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_bew_fall  ON bewertungen(fall_id);
CREATE INDEX IF NOT EXISTS idx_bew_scout ON bewertungen(scout_id);
CREATE INDEX IF NOT EXISTS idx_faelle_pack ON faelle(pack_id);
"""


def jetzt():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def verbinden(pfad=None):
    con = sqlite3.connect(pfad or PFAD, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


# Nachtraeglich hinzugekommene Spalten. SQLite kennt kein "ADD COLUMN IF NOT
# EXISTS", deshalb erst nachsehen, dann anlegen.
NACHTRAEGLICH = [
    ("bewertungen", "level_json", "TEXT NOT NULL DEFAULT '{}'"),
]


def schema(pfad=None):
    con = verbinden(pfad)
    with con:
        con.executescript(SCHEMA)
        for tabelle, spalte, typ in NACHTRAEGLICH:
            vorhanden = {r["name"] for r in
                         con.execute(f"PRAGMA table_info({tabelle})")}
            if spalte not in vorhanden:
                con.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {typ}")
    con.close()


def protokoll(con, scout_id, art, detail=""):
    con.execute(
        "INSERT INTO ereignisse (ts, scout_id, art, detail) VALUES (?,?,?,?)",
        (jetzt(), scout_id, art, detail),
    )


# ------------------------------------------------------------------- Lesehilfen
def scout_per_code(con, code):
    if not code:
        return None
    row = con.execute(
        "SELECT * FROM scouts WHERE code = ? AND aktiv = 1", (code.strip().upper(),)
    ).fetchone()
    return row


def aktives_pack(con, slug=None):
    if slug:
        return con.execute("SELECT * FROM packs WHERE slug = ?", (slug,)).fetchone()
    return con.execute(
        "SELECT * FROM packs WHERE status = 'offen' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def faelle_von(con, pack_id):
    return con.execute(
        "SELECT * FROM faelle WHERE pack_id = ? ORDER BY reihenfolge, id", (pack_id,)
    ).fetchall()


def fall_dict(row, nach_abgabe=False):
    """Fall fuer die Scout-Ansicht.

    Die Trennlinie laeuft zwischen beschreibendem Kontext und bewertenden
    Daten. Position, Jahrgang, Verein sagen *wer* jemand ist, nicht *wie gut* -
    sie bleiben sichtbar. Die Liga muss sichtbar bleiben, sie ist der Anker der
    Level-Frage: das Level ist die Liga-Stufe, um hoechstens eine Stufe
    verschoben, und ohne die Liga waere die Frage nicht zu beantworten.

    Indizes und Modellerwartung liegen dagegen hinter der Abgabe. Die Indizes
    sind nicht Beiwerk zum Modell - das Modell wird aus ihnen gerechnet. Wer
    sie vorher sieht, liest die Antwort ab, und dann misst die Trennschaerfe
    nur noch, ob jemand Balken in Noten uebersetzen kann. Die Konfliktliste,
    laut Audit die wertvollste Review-Liste, bliebe leer, weil niemand Grund
    haette zu widersprechen.
    """
    d = {
        "id": row["id"],
        "ext_id": row["ext_id"],
        "name": row["name"],
        "position": row["position"],
        "jahrgang": row["jahrgang"],
        "verein": row["verein"],
        "liga": row["liga"],
        "fuss": row["fuss"],
        "video_url": row["video_url"],
        # Die Schwelle gehoert zur Prognosefrage, nicht zu den Belegen -
        # ohne sie waere "Marktwert ueber X" nicht beantwortbar.
        "parameter": json.loads(row["parameter_json"]),
    }
    if nach_abgabe:
        d["indizes"] = json.loads(row["indizes_json"])
        d["modell"] = json.loads(row["modell_json"])
    return d
