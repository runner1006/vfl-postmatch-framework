#!/usr/bin/env python3
"""Scout League - HTTP-Server.

Nur Standardbibliothek: ein `python3 serve.py` genuegt, kein Build, kein
Paketmanager, keine Cloud-Abhaengigkeit. Fuer zehn User in einer Closed Beta
ist ThreadingHTTPServer mit SQLite reichlich dimensioniert.

    export SCOUTLEAGUE_ADMIN_TOKEN='...'      # sonst ist /admin gesperrt
    python3 scoutleague/serve.py --port 8080

Authentifizierung ist bewusst duenn: ein persoenlicher Scout-Code je User,
uebergeben als Header `X-Scout-Code`. Das reicht fuer einen internen Kreis
hinter einem geteilten Link und ist ausdruecklich kein Ersatz fuer echte
Accounts, sobald die Liga oeffentlich wird (Stufe 2).
"""
import argparse
import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

import db          # noqa: E402
import logik       # noqa: E402
import export      # noqa: E402

STATIC = os.path.join(HIER, "static")
ADMIN_TOKEN = os.environ.get("SCOUTLEAGUE_ADMIN_TOKEN", "")


class Handler(BaseHTTPRequestHandler):
    server_version = "ScoutLeague/0.1"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------- Hilfsmittel
    def _senden(self, status, koerper, typ="application/json; charset=utf-8",
                extra=None):
        if isinstance(koerper, (dict, list)):
            koerper = json.dumps(koerper, ensure_ascii=False).encode("utf-8")
        elif isinstance(koerper, str):
            koerper = koerper.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(koerper)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(koerper)

    def _fehler(self, status, text):
        self._senden(status, {"fehler": text})

    def _koerper(self):
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge <= 0:
            return {}
        if laenge > 256 * 1024:
            raise logik.Fehler("Anfrage zu groß.", 413)
        try:
            return json.loads(self.rfile.read(laenge).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise logik.Fehler("Ungültiges JSON.")

    def _scout(self, con):
        s = db.scout_per_code(con, self.headers.get("X-Scout-Code", ""))
        if s is None:
            raise logik.Fehler("Unbekannter oder gesperrter Scout-Code.", 401)
        return s

    def _admin(self):
        if not ADMIN_TOKEN:
            raise logik.Fehler(
                "Admin ist deaktiviert: SCOUTLEAGUE_ADMIN_TOKEN nicht gesetzt.", 503)
        if self.headers.get("X-Admin-Token", "") != ADMIN_TOKEN:
            raise logik.Fehler("Admin-Token falsch.", 401)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s  %s\n" % (self.log_date_time_string(), fmt % args))

    # ------------------------------------------------------------------ Routing
    def do_GET(self):
        self._route("GET")

    def do_HEAD(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _route(self, methode):
        pfad = urlparse(self.path).path
        frage = parse_qs(urlparse(self.path).query)
        con = None
        try:
            if methode == "GET" and not pfad.startswith("/api/"):
                return self._statisch(pfad)
            con = db.verbinden()
            antwort = self._api(methode, pfad, frage, con)
            if antwort is None:
                return self._fehler(404, "Unbekannter Endpunkt.")
            if isinstance(antwort, tuple):          # (koerper, typ, extra)
                return self._senden(200, *antwort)
            return self._senden(200, antwort)
        except logik.Fehler as e:
            self._fehler(e.status, e.text)
        except BrokenPipeError:
            pass
        except Exception:                            # noqa: BLE001
            traceback.print_exc()
            self._fehler(500, "Interner Fehler \u2014 Details stehen im Serverlog.")
        finally:
            if con is not None:
                con.close()

    def _api(self, methode, pfad, frage, con):
        slug = (frage.get("pack") or [None])[0]

        if pfad == "/api/anmelden" and methode == "POST":
            code = (self._koerper().get("code") or "").strip().upper()
            s = db.scout_per_code(con, code)
            if s is None:
                raise logik.Fehler("Unbekannter oder gesperrter Scout-Code.", 401)
            with con:
                db.protokoll(con, s["id"], "anmeldung")
            return {"name": s["name"], "code": s["code"], "rolle": s["rolle"]}

        if pfad == "/api/fragebogen" and methode == "GET":
            return logik.fragebogen()

        if pfad == "/api/pack" and methode == "GET":
            return logik.pack_fuer_scout(con, self._scout(con), slug)

        if pfad == "/api/bewertung" and methode == "POST":
            k = self._koerper()
            if "fall_id" not in k:
                raise logik.Fehler("fall_id fehlt.")
            return logik.bewertung_speichern(
                con, self._scout(con), int(k["fall_id"]), k.get("level"),
                k.get("antworten"), k.get("prognosen"), k.get("notiz"),
                k.get("sekunden"), bool(k.get("abgeben")))

        if pfad == "/api/leaderboard" and methode == "GET":
            self._scout(con)
            return logik.leaderboard(con, slug)

        if pfad == "/api/profil" and methode == "GET":
            return logik.profil(con, self._scout(con), slug)

        # ------------------------------------------------------------ Admin
        if pfad == "/api/admin/uebersicht" and methode == "GET":
            self._admin()
            return export.uebersicht(con, slug)

        if pfad == "/api/admin/aufloesen" and methode == "POST":
            self._admin()
            k = self._koerper()
            return export.aufloesen(con, int(k["fall_id"]), k["frage"],
                                    int(k["ergebnis"]), k.get("quelle", ""))

        if pfad == "/api/admin/pack_status" and methode == "POST":
            self._admin()
            k = self._koerper()
            status = k.get("status")
            if status not in ("offen", "geschlossen"):
                raise logik.Fehler("status muss 'offen' oder 'geschlossen' sein.")
            with con:
                con.execute("UPDATE packs SET status = ? WHERE slug = ?",
                            (status, k["slug"]))
            return {"slug": k["slug"], "status": status}

        if pfad == "/api/admin/kalibrierung" and methode == "GET":
            self._admin()
            return logik.kalibrier_report(con, slug)

        if pfad == "/api/admin/export.csv" and methode == "GET":
            self._admin()
            csv = export.bewertungen_csv(con, slug)
            return (csv, "text/csv; charset=utf-8",
                    {"Content-Disposition": 'attachment; filename="scoutleague.csv"'})

        return None

    def _statisch(self, pfad):
        if pfad in ("/", ""):
            pfad = "/index.html"
        if pfad == "/admin":
            pfad = "/admin.html"
        ziel = os.path.normpath(os.path.join(STATIC, pfad.lstrip("/")))
        if not ziel.startswith(STATIC) or not os.path.isfile(ziel):
            return self._fehler(404, "Nicht gefunden.")
        typ = mimetypes.guess_type(ziel)[0] or "application/octet-stream"
        if typ.startswith("text/") or typ in ("application/javascript",
                                              "application/json"):
            typ += "; charset=utf-8"
        with open(ziel, "rb") as f:
            self._senden(200, f.read(), typ, {"Cache-Control": "no-cache"})


def main():
    p = argparse.ArgumentParser(description="Scout League MVP")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    a = p.parse_args()

    db.schema()
    if not ADMIN_TOKEN:
        print("Hinweis: SCOUTLEAGUE_ADMIN_TOKEN ist nicht gesetzt, /admin bleibt "
              "gesperrt.", file=sys.stderr)
    print(f"Scout League laeuft auf http://{a.host}:{a.port}  "
          f"(DB: {db.PFAD})", file=sys.stderr)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
