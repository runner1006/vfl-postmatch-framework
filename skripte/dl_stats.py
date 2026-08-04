"""Schritt 2: Team-Match- und Spieler-Match-Statistiken laden.

Die Query-API begrenzt 'in'-Filter auf 100 Werte und Ergebnisse auf 500 Zeilen.
Daher: Batches von match_ids, parallel ueber einen ThreadPool.
"""
import sys
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import wyclient as w
from config import TEAM_COLS, PLAYER_COLS, DATA


def fetch_batch(table, cols, ids):
    """Alle Zeilen fuer eine Liste von match_ids, mit Paginierung."""
    out, offset = [], 0
    while True:
        batch = w.query(
            table, select=cols,
            filters=[{"column": "match_id", "op": "in", "value": ids}],
            limit=500, offset=offset,
        )
        out.extend(batch)
        if len(batch) < 500:
            return out
        offset += 500


def download(table, cols, ids, batch_size, workers, name):
    chunks = [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]
    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(lambda c: fetch_batch(table, cols, c), chunks):
            rows.extend(res)
            done += 1
            if done % 20 == 0:
                print(f"  {name}: {done}/{len(chunks)} Batches, {len(rows)} Zeilen",
                      flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    m = pd.read_csv(f"{DATA}/matches.csv")
    ids = m.loc[m["meta_match_data_downloaded"] == True, "match_id"].tolist()  # noqa: E712
    print(f"{len(ids)} Spiele mit Daten", flush=True)

    if what in ("team", "both"):
        df = download("wyscout_match_team_stats_sync", TEAM_COLS, ids, 100, 8, "team")
        df.to_csv(f"{DATA}/team_stats.csv", index=False)
        print(f"TEAM: {len(df)} Zeilen, {df['match_id'].nunique()} Spiele -> team_stats.csv")

    if what in ("player", "both"):
        df = download("wyscout_match_player_stats_sync", PLAYER_COLS, ids, 15, 8, "player")
        df.to_csv(f"{DATA}/player_stats.csv", index=False)
        print(f"PLAYER: {len(df)} Zeilen, {df['match_id'].nunique()} Spiele -> player_stats.csv")
