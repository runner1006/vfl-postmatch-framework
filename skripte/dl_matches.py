"""Schritt 1: alle Spiele der 16 Wettbewerb-Saison-Kombinationen laden."""
import pandas as pd
import wyclient as w
from config import SEASONS, SEASON_COMP, MATCH_COLS, DATA

rows = []
for season_id, (liga, label) in SEASONS.items():
    comp = SEASON_COMP[season_id]
    batch = w.query_all(
        "wyscout_match_sync",
        select=MATCH_COLS,
        filters=[
            {"column": "competition_id", "op": "eq", "value": comp},
            {"column": "season_id", "op": "eq", "value": season_id},
        ],
        page=500,
    )
    for r in batch:
        r["liga"] = liga
        r["saison"] = label
    rows.extend(batch)
    print(f"{liga} {label} (season {season_id}): {len(batch)} Spiele", flush=True)

df = pd.DataFrame(rows)
df = df.rename(columns={"wyscout_id": "match_id"})
df["date_utc"] = pd.to_datetime(df["date_utc"])
df = df.sort_values("date_utc").reset_index(drop=True)
df.to_csv(f"{DATA}/matches.csv", index=False)

print()
print(f"GESAMT {len(df)} Spiele, davon {df['meta_match_data_downloaded'].sum()} mit Daten")
print(df.groupby(["liga", "saison"]).agg(
    spiele=("match_id", "size"),
    mit_daten=("meta_match_data_downloaded", "sum"),
    mit_physik=("meta_match_physical_data_downloaded", "sum"),
).to_string())
