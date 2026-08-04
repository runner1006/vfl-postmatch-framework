"""Client for the wyscoutdb MCP server (direct HTTP JSON-RPC).

Der Zugangstoken steht in der Umgebungsvariable WYSCOUT_MCP_TOKEN, nicht im Code:

    export WYSCOUT_MCP_TOKEN='<Token von Strykerlabs>'

Geprueft wird erst beim ersten Serveraufruf, nicht beim Import. Die Auswertungs- und
Darstellungsschritte (build_dashboard, validate_palette) sollen ohne Zugangsdaten laufen.
"""
import json
import os
import time
import requests

URL = "https://mcpapi.datasync.strykerlabsdev.com/mcp"

_session = None


def _sess():
    """Session beim ersten Aufruf aufbauen - und erst dann den Token verlangen."""
    global _session
    if _session is None:
        token = os.environ.get("WYSCOUT_MCP_TOKEN")
        if not token:
            raise SystemExit(
                "WYSCOUT_MCP_TOKEN ist nicht gesetzt - ohne Token kein Zugriff auf den "
                "Wyscout-MCP-Server.\n"
                "  export WYSCOUT_MCP_TOKEN='<Token von Strykerlabs>'\n"
                "Nur die Download-Schritte brauchen ihn; das Dashboard laesst sich mit "
                "build_dashboard.py auch ohne bauen.")
        _session = requests.Session()
        _session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
    return _session


def _parse_sse(text):
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)


def call_tool(name, arguments, retries=5):
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    last_err = None
    for attempt in range(retries):
        try:
            r = _sess().post(URL, json=body, timeout=300)
            if r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            # Der Server deklariert kein charset; requests faellt sonst auf
            # ISO-8859-1 zurueck und verstuemmelt Umlaute in Team-/Spielernamen.
            msg = _parse_sse(r.content.decode("utf-8"))
            if "error" in msg:
                raise RuntimeError(f"JSON-RPC error: {msg['error']}")
            content = msg["result"]["content"][0]["text"]
            if msg["result"].get("isError"):
                raise RuntimeError(f"tool error: {content[:500]}")
            return json.loads(content)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"call_tool failed after {retries} tries: {last_err}")


def query(table, select=None, filters=None, sort=None, limit=1000, offset=0):
    args = {"table": table, "limit": limit, "offset": offset}
    if select:
        args["select"] = select
    if filters:
        args["filters"] = filters
    if sort:
        args["sort"] = sort
    res = call_tool("wyscout_query_table", args)
    return res["rows"]


def query_all(table, select=None, filters=None, sort=None, page=500,
              max_rows=None, progress=None):
    rows = []
    offset = 0
    while True:
        batch = query(table, select, filters, sort, limit=page, offset=offset)
        rows.extend(batch)
        if progress and (offset // page) % 10 == 0:
            print(f"  {table}: {len(rows)} rows...", flush=True)
        if len(batch) < page:
            break
        offset += page
        if max_rows and len(rows) >= max_rows:
            break
    return rows


def count_rows(table, filters=None):
    """Binary search for total row count via offset probing."""
    lo, hi = 0, 1
    while query(table, select=None, filters=filters, limit=1, offset=hi):
        lo, hi = hi, hi * 4
        if hi > 200_000_000:
            break
    while lo < hi:
        mid = (lo + hi) // 2
        if query(table, select=None, filters=filters, limit=1, offset=mid):
            lo = mid + 1
        else:
            hi = mid
    return lo
