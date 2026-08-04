"""Schritt 3b: Kandidaten-Screening.

Fuer jedes taktische Prinzip werden mehrere Operationalisierungen gerechnet und
danach beurteilt, ob sie die vier Referenzmannschaften ueberhaupt vom jeweiligen
Ligarest trennen. Erst danach wird das finale 15er-Set gewaehlt.

Wichtig: Die Auswahl erfolgt gegen die IDENTITAET (Referenzteams), nicht gegen
Ergebnisse. Schutz gegen Ueberanpassung ist die Konsistenzforderung: ein KPI muss
in mehreren der vier Referenzen in dieselbe Richtung zeigen, nicht nur gepoolt.
"""
import numpy as np
import pandas as pd
from config import DATA, OUT, REFERENCE, REFERENCE_LABEL
from kpis import player_aggregates
from korridore import cliffs_delta, boot_ci, tag_reference

T = "wy_totals_"


def safe(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    return a / b.where(b > 0)


def build_wide():
    m = pd.read_csv(f"{DATA}/matches.csv", parse_dates=["date_utc"])
    t = pd.read_csv(f"{DATA}/team_stats.csv")
    pl = pd.read_csv(f"{DATA}/player_stats.csv")

    d = t.merge(m[["match_id", "liga", "saison", "season_id", "date_utc",
                   "home_team_id", "away_team_id", "home_team_coach_id",
                   "away_team_coach_id"]], on="match_id")
    d["is_home"] = d["team_id"] == d["home_team_id"]
    d["opponent_id"] = np.where(d["is_home"], d["away_team_id"], d["home_team_id"])
    d["coach_id"] = np.where(d["is_home"], d["home_team_coach_id"], d["away_team_coach_id"])
    d["liga_saison"] = d["liga"] + " " + d["saison"]

    # alle Team-Statistikspalten auch als Gegnerwert
    stat_cols = [c for c in t.columns if c not in ("match_id", "team_id")]
    opp = d[["match_id", "team_id"] + stat_cols].rename(
        columns={"team_id": "opponent_id", **{c: "O_" + c for c in stat_cols}})
    d = d.merge(opp, on=["match_id", "opponent_id"], how="left")

    d = d.merge(player_aggregates(pl), on=["match_id", "team_id"], how="left")
    d["eff_min"] = (pd.to_numeric(d[T + "possession_total_time_seconds"], errors="coerce")
                    - pd.to_numeric(d[T + "possession_dead_time_seconds"], errors="coerce")) / 60
    return d


def candidates(d):
    """name -> (Serie, Orientierung +1/-1, Prinzip)."""
    c = {}
    A = lambda n: d[T + n]          # eigener Wert          # noqa: E731
    O = lambda n: d["O_" + T + n]   # Gegnerwert            # noqa: E731

    poss = A("possession_possession_number")
    rec = A("transitions_recoveries_total")
    loss = A("transitions_losses_total")
    halfr = A("possession_reaching_opponent_half")
    boxr = A("possession_reaching_opponent_box")
    fl = A("flanks_left_flank_attacks") + A("flanks_right_flank_attacks")
    flc = fl + A("flanks_center_attacks")

    # ---- RP3 Vertikalitaet / Forward Mindset
    c["v_fwd_share"] = (safe(A("passes_forward_passes_successful"),
                             A("passes_passes_successful")), +1, "RP3 Vertikalitaet")
    c["v_fwd_attempt_share"] = (safe(A("passes_forward_passes"), A("passes_passes")),
                                +1, "RP3 Vertikalitaet")
    c["v_vertical_share"] = (safe(A("passes_vertical_passes_successful"),
                                  A("passes_passes_successful")), +1, "RP3 Vertikalitaet")
    c["v_prog_share"] = (safe(A("passes_progressive_passes"), A("passes_passes")),
                         +1, "RP3 Vertikalitaet")
    c["v_back_share"] = (safe(A("passes_back_passes"), A("passes_passes")),
                         -1, "RP3 Vertikalitaet")
    c["v_pass_len"] = (pd.to_numeric(d["wy_average_passes_avg_pass_length"],
                                     errors="coerce"), +1, "RP3 Vertikalitaet")
    c["v_tempo"] = (pd.to_numeric(A("passes_match_tempo"), errors="coerce"),
                    +1, "RP3 Vertikalitaet")
    c["v_poss_dauer"] = (pd.to_numeric(d["wy_average_possession_avg_possession_duration_seconds"],
                                       errors="coerce"), -1, "RP3 Vertikalitaet")

    # ---- Progression
    c["p_prog_per_poss"] = (safe(A("passes_progressive_passes_successful"), poss),
                            +1, "Progression")
    c["p_runs_per_poss"] = (safe(A("general_progressive_runs"), poss), +1, "Progression")
    c["p_halfreach_rate"] = (safe(halfr, poss), +1, "Progression")
    c["p_boxreach_per_half"] = (safe(boxr, halfr), +1, "Progression")
    c["p_final_third_per_poss"] = (safe(A("passes_pass_to_final_thirds_successful"), poss),
                                   +1, "Progression")
    c["p_deep_per_poss"] = (safe(A("passes_deep_completed_passes_successful"), poss),
                            +1, "Progression")
    c["p_through_per_half"] = (safe(A("passes_through_passes_successful"), halfr),
                               +1, "Progression")

    # ---- RP4 Fluegelfokus
    c["f_fluegelanteil"] = (safe(fl, flc), +1, "RP4 Fluegel")
    c["f_crosses_per_poss"] = (safe(A("passes_crosses_total"), poss), +1, "RP4 Fluegel")
    c["f_crosses_succ_per_poss"] = (safe(A("passes_crosses_successful"), poss),
                                    +1, "RP4 Fluegel")
    c["f_crosses_per_fluegelatt"] = (safe(A("passes_crosses_total"), fl), +1, "RP4 Fluegel")
    c["f_cross_acc"] = (safe(A("passes_crosses_successful"), A("passes_crosses_total")),
                        +1, "RP4 Fluegel")
    c["f_cutback_share"] = (safe(A("passes_crosses_low"), A("passes_crosses_total")),
                            +1, "RP4 Fluegel")
    c["f_boxpass_per_poss"] = (safe(A("passes_pass_to_penalty_areas_successful"), poss),
                               +1, "RP4 Fluegel")
    c["f_boxdelivery_per_boxreach"] = (
        safe(A("passes_crosses_successful") + A("passes_pass_to_penalty_areas_successful"),
             boxr), +1, "RP4 Fluegel")
    c["f_touchbox_per_boxreach"] = (safe(A("general_touches_in_box"), boxr),
                                    +1, "RP4 Fluegel")

    # ---- Off. Umschalten
    c["u_konter_per_rec"] = (safe(A("attacks_counter_attacks"), rec), +1, "Umschalten off")
    c["u_konter_share_att"] = (safe(A("attacks_counter_attacks"), A("attacks_total")),
                               +1, "Umschalten off")
    c["u_runs_per_rec"] = (safe(A("general_progressive_runs"), rec), +1, "Umschalten off")
    c["u_deep_per_rec"] = (safe(A("passes_deep_completed_passes_successful"), rec),
                           +1, "Umschalten off")
    c["u_attacks_per_rec"] = (safe(A("attacks_total"), rec), +1, "Umschalten off")
    c["u_dangrec_share"] = (safe(d["sum_dang_opp_rec"], rec), +1, "Umschalten off")

    # ---- RP1 Pressing / Vorwaertsverteidigen
    c["d_pdda"] = (pd.to_numeric(A("defence_pdda"), errors="coerce"), -1, "RP1 Pressing")
    c["d_rec_high_share"] = (safe(A("transitions_recoveries_high"), rec), +1, "RP1 Pressing")
    c["d_rec_high_per_min"] = (safe(A("transitions_recoveries_high"), d["eff_min"]),
                               +1, "RP1 Pressing")
    c["d_opphalf_rec_share"] = (safe(A("transitions_opponent_half_recoveries"), rec),
                                +1, "RP1 Pressing")
    c["d_challenge_int"] = (pd.to_numeric(A("duels_challenge_intensity"), errors="coerce"),
                            +1, "RP1 Pressing")
    c["d_defduels_per_oppposs"] = (safe(A("duels_defensive_duels"),
                                        O("possession_possession_number")),
                                   +1, "RP1 Pressing")
    c["d_opp_ownhalf_loss_share"] = (safe(O("transitions_own_half_losses"),
                                          O("transitions_losses_total")),
                                     +1, "RP1 Pressing")

    # ---- Defensive Struktur
    c["s_box_zugriff_zugel"] = (safe(O("possession_reaching_opponent_box"),
                                     O("possession_reaching_opponent_half")),
                                -1, "Defensive Struktur")
    c["s_halfreach_zugel"] = (safe(O("possession_reaching_opponent_half"),
                                   O("possession_possession_number")),
                              -1, "Defensive Struktur")
    c["s_opp_prog_zugel"] = (safe(O("passes_progressive_passes_successful"),
                                  O("possession_possession_number")),
                             -1, "Defensive Struktur")
    c["s_opp_deep_zugel"] = (safe(O("passes_deep_completed_passes_successful"),
                                  O("possession_possession_number")),
                             -1, "Defensive Struktur")
    c["s_aerial_win"] = (safe(A("duels_aerial_duels_successful"), A("duels_aerial_duels")),
                         +1, "Defensive Struktur")

    # ---- Def. Umschalten / Gegenpressing
    c["g_counterpress_per_loss"] = (safe(d["sum_counterpress"], loss), +1, "Gegenpressing")
    c["g_counterpress_per_highloss"] = (safe(d["sum_counterpress"],
                                             A("transitions_losses_high")),
                                        +1, "Gegenpressing")
    c["g_dangloss_share"] = (safe(d["sum_dang_loss"], loss), -1, "Restverteidigung")
    c["g_highloss_share"] = (safe(A("transitions_losses_high"), loss), +1, "Restverteidigung")
    c["g_opp_konter_per_loss"] = (safe(O("attacks_counter_attacks"), loss),
                                  -1, "Restverteidigung")
    c["g_rec_per_loss"] = (safe(rec, loss), +1, "Gegenpressing")

    # ---- RP2 Physik
    c["y_hidist_per_min"] = (safe(d["sum_hi_dist"], d["eff_min"]), +1, "RP2 Physik")
    c["y_dist_per_min"] = (safe(d["sum_dist"], d["eff_min"]), +1, "RP2 Physik")
    c["y_counthi_per_min"] = (safe(d["sum_count_hi"], d["eff_min"]), +1, "RP2 Physik")
    c["y_sprint_per_min"] = (safe(d["sum_sprint"], d["eff_min"]), +1, "RP2 Physik")
    c["y_accdec_per_min"] = (safe(d["sum_acc"] + d["sum_dec"], d["eff_min"]),
                             +1, "RP2 Physik")
    c["y_acc_per_min"] = (safe(d["sum_acc"], d["eff_min"]), +1, "RP2 Physik")
    c["y_dec_per_min"] = (safe(d["sum_dec"], d["eff_min"]), +1, "RP2 Physik")
    c["y_maxspeed_top5"] = (pd.to_numeric(d["max_speed_top5"], errors="coerce"),
                            +1, "RP2 Physik")
    return c


def screen(d, cands):
    d = tag_reference(d)
    rows = []
    for name, (series, orient, prinzip) in cands.items():
        d["_raw"] = pd.to_numeric(series, errors="coerce")
        z = d.groupby("liga_saison")["_raw"].transform(
            lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else np.nan)
        d["_v"] = orient * z
        valid_ls = d.loc[d["_v"].notna(), "liga_saison"].unique()
        ref = d[d["is_ref"] & d["_v"].notna()]
        rest = d[(~d["is_ref"]) & d["liga_saison"].isin(valid_ls)]["_v"]
        if len(ref) < 30:
            continue
        dl = cliffs_delta(ref["_v"], rest)
        lo, hi = boot_ci(ref["_v"], rest, cliffs_delta, n=800)
        row = {"kandidat": name, "prinzip": prinzip, "orientierung": orient,
               "n_kohorte": len(ref), "median_z": round(float(ref["_v"].median()), 3),
               "delta": round(dl, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3)}
        pos = tot = 0
        for key, coach, team, seasons, _ in REFERENCE:
            sub = d[(d["coach_id"] == coach) & (d["team_id"] == team)
                    & (d["season_id"].isin(seasons)) & d["_v"].notna()]
            if len(sub) < 15:
                row[f"d_{key}"] = np.nan
                continue
            own = d[(~d["is_ref"]) & d["liga_saison"].isin(sub["liga_saison"].unique())]["_v"]
            dd = cliffs_delta(sub["_v"], own)
            row[f"d_{key}"] = round(dd, 3)
            tot += 1
            pos += dd > 0.15
        row["konsistenz"] = f"{pos}/{tot}"
        row["n_pos"] = pos
        row["n_test"] = tot
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["prinzip", "n_pos", "delta"],
                                          ascending=[True, False, False])


if __name__ == "__main__":
    d = build_wide()
    # zusaetzliches Spieler-Aggregat fuer u_dangrec_share
    pl = pd.read_csv(f"{DATA}/player_stats.csv")
    pl["_f"] = pd.to_numeric(pl["wy_totals_minutes_on_field"], errors="coerce").fillna(0) / 90
    pl["_x"] = pd.to_numeric(pl["wy_per_90_dangerous_opponent_half_recoveries"],
                             errors="coerce") * pl["_f"]
    agg = pl.groupby(["match_id", "team_id"])["_x"].sum(min_count=1).rename("sum_dang_opp_rec")
    d = d.merge(agg, on=["match_id", "team_id"], how="left")

    res = screen(d, candidates(d))
    res.to_csv(f"{OUT}/kandidaten_screening.csv", index=False)

    cols = ["kandidat", "n_kohorte", "median_z", "delta", "ci_lo", "ci_hi",
            "d_leipzig_werner", "d_sturm_ilzer", "d_hoffenheim_ilzer",
            "d_schalke_muslic", "konsistenz"]
    for prinzip, grp in res.groupby("prinzip", sort=False):
        print(f"\n=== {prinzip} ===")
        print(grp[cols].to_string(index=False))
