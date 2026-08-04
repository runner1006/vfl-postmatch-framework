"""Schritt 3: KPI-Berechnung auf Team-Match-Ebene (Rev. 3).

Das aktive KPI-Set steht NICHT mehr im Code, sondern in `kpi_varianten.json`.
Dort liegen auch alle geprueften Alternativen samt Trennschaerfe und den
Redundanz-Blockaden. Ein Tausch heisst: JSON aendern, Pipeline neu laufen lassen.

REGISTRY wird aus dem aktiven Set aufgebaut:
  name -> (orient, shape, shrink_k, phase, gewicht_in_phase)
  orient  +1 = hoher Rohwert entspricht der Spielidee, -1 = niedriger
  shape   'up'   = mehr Identitaet ist beliebig gut
          'band' = zweiseitiger Korridor

Zusaetzlich wird je KPI eine Ereigniszahl `n_<KPI>` mitgeschrieben. Sie ist die
Grundlage der spielweisen Confidence (scoring.py): ein Wert, der auf einem
einzigen Konter beruht, wird als unsicher ausgewiesen statt als harte Aussage.
"""
import json
import os
import numpy as np
import pandas as pd
from config import DATA

T = "wy_totals_"
P = "wy_per_90_"
PENALTY_XG = 0.76
PHYS_MIN_COVERAGE = 0.80

_VARIANTEN_PFAD = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "kpi_varianten.json")
with open(_VARIANTEN_PFAD) as _f:
    VARIANTEN = json.load(_f)

AKTIVES_SET = VARIANTEN["sets"][VARIANTEN["aktiv"]]

REGISTRY = {
    name: (spec["orient"], spec["form"], spec.get("shrink"),
           spec["phase"], spec["gewicht"])
    for name, spec in AKTIVES_SET.items()
}

# Korridor normativ statt aus der Referenzkohorte (Kohorte traegt ihn nicht).
NORMATIVE_CORRIDOR = {n for n, s in AKTIVES_SET.items() if s.get("normativ")}

PHASE_WEIGHTS = {
    "defensiv": 0.25, "def_umschalten": 0.20, "offensiv": 0.20,
    "off_umschalten": 0.20, "physisch": 0.15,
}

PHASE_LABEL = {
    "offensiv": "Offensiv", "off_umschalten": "Offensives Umschalten",
    "defensiv": "Defensiv", "def_umschalten": "Defensives Umschalten",
    "physisch": "Physisch",
}

SECONDARY = [
    "S_fluegelanteil", "S_flankenpraezision", "S_cutback_proxy",
    "S_aufbaukontrolle", "S_through_tiefe", "S_prog_pass_per_poss",
    "S_prog_runs_per_poss", "S_hohe_verluste_anteil", "S_ballbesitz",
    "S_sprintdichte", "S_hi_count_dichte", "S_laufdistanz", "S_dezeleration",
]

CC = ["CC1_npxg", "CC2_box_zugriffsrate", "CC3_abschlussqualitaet",
      "CC1d_npxg_gegen", "CC2d_box_zugriffsrate_gegen",
      "CC3d_abschlussqualitaet_gegen"]


def _safe(num, den):
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    return num / den.where(den > 0)


def _spec_wert(d, spec):
    """Loest eine Spaltenreferenz aus kpi_varianten.json auf."""
    if spec is None:
        return None
    q = spec["quelle"]
    if q == "eff_min":
        return d["eff_min"]
    if q == "gegner":
        return d["O_" + spec["spalte"]]
    return d[spec["spalte"]]          # team | aggregat | direkt


def _spec_serie(d, zaehler, nenner, shrink_k, gruppe):
    """Baut die KPI-Serie aus Zaehler/Nenner-Spezifikation."""
    z = _spec_wert(d, zaehler)
    if nenner is None:                # 'direkt': Spalte ist selbst der KPI-Wert
        return pd.to_numeric(z, errors="coerce")
    n = _spec_wert(d, nenner)
    if shrink_k:
        return shrink(z, n, shrink_k, gruppe)
    return _safe(z, n)


def shrink(num, den, k, group):
    """Empirical-Bayes-Glaettung zum Mittel der Liga-Saison."""
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    mu = (num / den.where(den > 0)).groupby(group).transform("mean")
    return (num + k * mu) / (den + k)


def player_aggregates(pl):
    """Spieler-Match -> Team-Match. Per-90-Werte mit Minuten zurueckrechnen.

    Summen ueber ausschliesslich fehlende Werte bleiben NaN (min_count=1),
    sonst wuerde 'keine Physikdaten' als 'null Laufleistung' gelesen.
    Physik wird zusaetzlich verworfen, wenn weniger als PHYS_MIN_COVERAGE der
    Feldspielerminuten abgedeckt sind.
    """
    pl = pl.copy()
    mins = pd.to_numeric(pl["wy_totals_minutes_on_field"], errors="coerce").fillna(0)
    pl["_f"] = mins / 90.0
    pl["minutes"] = mins
    pl["is_gk"] = pl["wy_role_1_code"].astype(str).str.lower().eq("gk")

    def tot(col):
        return pd.to_numeric(pl[col], errors="coerce") * pl["_f"]

    pl["n_counterpress"] = tot(P + "counterpressing_recoveries")
    pl["n_dang_loss"] = tot(P + "dangerous_own_half_losses")
    pl["n_dang_opp_rec"] = tot(P + "dangerous_opponent_half_recoveries")
    pl["n_xg"] = tot(P + "xg_shot")
    pl["n_shots"] = tot(P + "shots")
    pl["n_pens"] = tot(P + "penalties")
    pl["n_hi_dist"] = tot(P + "physical_hi_distance")
    pl["n_dist"] = tot(P + "physical_distance")
    pl["n_count_hi"] = tot(P + "physical_count_hi")
    pl["n_sprint"] = tot(P + "physical_count_sprint")
    pl["n_acc"] = tot(P + "physical_count_high_acceleration")
    pl["n_dec"] = tot(P + "physical_count_high_deceleration")
    pl["n_xg_save"] = np.where(pl["is_gk"], tot(P + "xg_save"), np.nan)
    pl["n_conceded"] = np.where(pl["is_gk"], tot(P + "gk_conceded_goals"), np.nan)

    field = pl[~pl["is_gk"]].copy()
    g = pl.groupby(["match_id", "team_id"])
    gf = field.groupby(["match_id", "team_id"])

    out = pd.DataFrame({
        "sum_counterpress": g["n_counterpress"].sum(min_count=1),
        "sum_dang_loss": g["n_dang_loss"].sum(min_count=1),
        "sum_dang_opp_rec": g["n_dang_opp_rec"].sum(min_count=1),
        "sum_xg_player": g["n_xg"].sum(min_count=1),
        "sum_shots_player": g["n_shots"].sum(min_count=1),
        "n_penalties": g["n_pens"].sum(min_count=1),
        "gk_xg_save": g["n_xg_save"].sum(min_count=1),
        "gk_conceded": g["n_conceded"].sum(min_count=1),
        "sum_hi_dist": gf["n_hi_dist"].sum(min_count=1),
        "sum_dist": gf["n_dist"].sum(min_count=1),
        "sum_count_hi": gf["n_count_hi"].sum(min_count=1),
        "sum_sprint": gf["n_sprint"].sum(min_count=1),
        "sum_acc": gf["n_acc"].sum(min_count=1),
        "sum_dec": gf["n_dec"].sum(min_count=1),
        "n_field": gf.size(),
        "field_minutes": gf["minutes"].sum(),
    })

    ms = field.dropna(subset=["wy_totals_physical_max_speed"])
    out["max_speed_top5"] = (
        ms.sort_values("wy_totals_physical_max_speed", ascending=False)
          .groupby(["match_id", "team_id"])["wy_totals_physical_max_speed"]
          .apply(lambda s: s.head(5).mean()))

    tot_min = gf["minutes"].sum()
    for src, name in ((P + "physical_count_hi", "phys_minutes_cov"),
                      (P + "physical_count_high_deceleration", "dec_minutes_cov")):
        okmin = (field.assign(_m=field["minutes"].where(field[src].notna(), 0))
                      .groupby(["match_id", "team_id"])["_m"].sum())
        out[name] = okmin / tot_min.replace(0, np.nan)

    bad = out["phys_minutes_cov"].fillna(0) < PHYS_MIN_COVERAGE
    out.loc[bad, ["sum_hi_dist", "sum_dist", "sum_count_hi", "sum_sprint",
                  "sum_acc", "max_speed_top5"]] = np.nan
    out.loc[out["dec_minutes_cov"].fillna(0) < PHYS_MIN_COVERAGE, "sum_dec"] = np.nan
    return out.reset_index()


def build():
    m = pd.read_csv(f"{DATA}/matches.csv", parse_dates=["date_utc"])
    t = pd.read_csv(f"{DATA}/team_stats.csv")
    pl = pd.read_csv(f"{DATA}/player_stats.csv")

    d = t.merge(m[["match_id", "liga", "saison", "season_id", "date_utc", "gameweek",
                   "home_team_id", "away_team_id", "home_team_score", "away_team_score",
                   "home_team_score_half_time", "away_team_score_half_time",
                   "home_team_coach_id", "away_team_coach_id"]], on="match_id")

    d["is_home"] = d["team_id"] == d["home_team_id"]
    d["opponent_id"] = np.where(d["is_home"], d["away_team_id"], d["home_team_id"])
    d["coach_id"] = np.where(d["is_home"], d["home_team_coach_id"], d["away_team_coach_id"])
    d["tore"] = np.where(d["is_home"], d["home_team_score"], d["away_team_score"])
    d["gegentore"] = np.where(d["is_home"], d["away_team_score"], d["home_team_score"])
    d["punkte"] = np.where(d["tore"] > d["gegentore"], 3,
                           np.where(d["tore"] == d["gegentore"], 1, 0))
    d["hz_tore"] = np.where(d["is_home"], d["home_team_score_half_time"],
                            d["away_team_score_half_time"])
    d["hz_gegentore"] = np.where(d["is_home"], d["away_team_score_half_time"],
                                 d["home_team_score_half_time"])
    d["liga_saison"] = d["liga"] + " " + d["saison"]

    stat_cols = [c for c in t.columns if c not in ("match_id", "team_id")]
    opp = d[["match_id", "team_id"] + stat_cols].rename(
        columns={"team_id": "opponent_id", **{c: "O_" + c for c in stat_cols}})
    d = d.merge(opp, on=["match_id", "opponent_id"], how="left")
    d = d.merge(player_aggregates(pl), on=["match_id", "team_id"], how="left")

    d["eff_min"] = (pd.to_numeric(d[T + "possession_total_time_seconds"], errors="coerce")
                    - pd.to_numeric(d[T + "possession_dead_time_seconds"], errors="coerce")) / 60

    g = d["liga_saison"]
    A = lambda n: d[T + n]           # noqa: E731
    O = lambda n: d["O_" + T + n]    # noqa: E731
    poss, rec, loss = (A("possession_possession_number"),
                       A("transitions_recoveries_total"),
                       A("transitions_losses_total"))

    # ---------------- Die 15 Stil-KPIs aus dem aktiven Set (kpi_varianten.json)
    for name, spec in AKTIVES_SET.items():
        d[name] = _spec_serie(d, spec["zaehler"], spec.get("nenner"),
                              spec.get("shrink"), g)
        d["n_" + name] = pd.to_numeric(_spec_wert(d, spec["ereignisse"]),
                                       errors="coerce")

    # ------------------------------------------------------------ Sekundaer
    fl = A("flanks_left_flank_attacks") + A("flanks_right_flank_attacks")
    d["S_fluegelanteil"] = _safe(fl, fl + A("flanks_center_attacks"))
    d["S_flankenpraezision"] = _safe(A("passes_crosses_successful"), A("passes_crosses_total"))
    d["S_cutback_proxy"] = _safe(A("passes_crosses_low"), A("passes_crosses_total"))
    d["S_aufbaukontrolle"] = 1 - _safe(A("openplay_long") + A("openplay_very_long"),
                                       A("openplay_total"))
    d["S_through_tiefe"] = _safe(A("passes_through_passes_successful"),
                                 A("possession_reaching_opponent_half"))
    d["S_prog_pass_per_poss"] = _safe(A("passes_progressive_passes_successful"), poss)
    d["S_prog_runs_per_poss"] = _safe(A("general_progressive_runs"), poss)
    d["S_hohe_verluste_anteil"] = _safe(A("transitions_losses_high"), loss)
    d["S_ballbesitz"] = pd.to_numeric(d["wy_percent_possession_possession_percent"],
                                      errors="coerce")
    d["S_sprintdichte"] = _safe(d["sum_sprint"], d["eff_min"])
    d["S_hi_count_dichte"] = _safe(d["sum_count_hi"], d["eff_min"])
    d["S_laufdistanz"] = _safe(d["sum_dist"], d["eff_min"])
    d["S_dezeleration"] = _safe(d["sum_dec"], d["eff_min"])

    # --------------------------------------------------------- Teil B: CC
    d["n_penalties"] = d["n_penalties"].fillna(0).round()
    d["CC1_npxg"] = (pd.to_numeric(A("general_xg"), errors="coerce")
                     - PENALTY_XG * d["n_penalties"]).clip(lower=0)
    d["CC2_box_zugriffsrate"] = _safe(A("possession_reaching_opponent_box"), poss)
    d["CC3_abschlussqualitaet"] = pd.to_numeric(A("general_xg_per_shot"), errors="coerce")
    oppcc = d[["match_id", "team_id", "CC1_npxg", "CC2_box_zugriffsrate"]].rename(
        columns={"team_id": "opponent_id", "CC1_npxg": "CC1d_npxg_gegen",
                 "CC2_box_zugriffsrate": "CC2d_box_zugriffsrate_gegen"})
    d = d.merge(oppcc, on=["match_id", "opponent_id"], how="left")
    d["CC3d_abschlussqualitaet_gegen"] = pd.to_numeric(
        A("general_xg_per_shot_against"), errors="coerce")

    d["schuesse_gegen"] = O("general_shots")
    d["sot_gegen"] = O("general_shots_on_target")
    d["rote_karten"] = A("general_red_cards")
    d["rote_karten_gegner"] = O("general_red_cards")
    d["gegner_xg"] = O("general_xg")
    return d


KEEP_META = [
    "match_id", "team_id", "opponent_id", "coach_id", "liga", "saison", "liga_saison",
    "season_id", "date_utc", "gameweek", "is_home", "tore", "gegentore", "punkte",
    "hz_tore", "hz_gegentore", "rote_karten", "rote_karten_gegner", "eff_min",
    "sum_xg_player", "sum_shots_player", "n_penalties", "gk_xg_save", "gk_conceded",
    "schuesse_gegen", "sot_gegen", "gegner_xg", "phys_minutes_cov", "dec_minutes_cov",
    "n_field", T + "general_xg", T + "general_shots", T + "general_shots_on_target",
    T + "transitions_recoveries_total", T + "transitions_losses_total",
    T + "possession_possession_number", T + "possession_reaching_opponent_half",
]

if __name__ == "__main__":
    d = build()
    cols = KEEP_META + list(REGISTRY) + ["n_" + k for k in REGISTRY] + SECONDARY + CC
    d[cols].to_csv(f"{DATA}/kpi_raw.csv", index=False)
    print(f"Aktives Set: '{VARIANTEN['aktiv']}'")
    print(f"kpi_raw.csv: {len(d)} Zeilen, {len(cols)} Spalten")
    print("\nVollstaendigkeit der 15 primaeren KPIs je Liga (Prozent nicht-NULL):")
    print((d.groupby("liga")[list(REGISTRY)].apply(lambda x: x.notna().mean()).T * 100)
          .round(1).to_string())
    print("\nEreigniszahlen je KPI (Basis der spielweisen Confidence):")
    ev = pd.DataFrame({
        "Median": [d["n_" + k].median() for k in REGISTRY],
        "Anteil_0": [(d["n_" + k].fillna(0) == 0).mean() * 100 for k in REGISTRY],
        "Anteil_unter3": [(d["n_" + k].fillna(0) < 3).mean() * 100 for k in REGISTRY],
    }, index=list(REGISTRY)).round(1)
    print(ev.to_string())
