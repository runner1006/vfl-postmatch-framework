"""Zentrale Konfiguration: Wettbewerbe, Saisons, Referenzkohorte, Spaltenlisten."""
import os

# Pfade relativ zum Repository, damit die Pipeline aus jedem Klon laeuft.
# Ueberschreibbar, wenn Rohdaten oder Ergebnisse woanders liegen.
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- Wettbewerbe
COMP_2BL = 423   # 2. Bundesliga
COMP_BL = 426    # Bundesliga
COMP_AUT = 168   # Oesterreichische Bundesliga

# season_id -> Label
SEASONS = {
    # 2. Bundesliga, 9 Saisons
    181138: ("2BL", "2017/18"),
    185568: ("2BL", "2018/19"),
    185781: ("2BL", "2019/20"),
    186266: ("2BL", "2020/21"),
    187512: ("2BL", "2021/22"),
    188076: ("2BL", "2022/23"),
    188972: ("2BL", "2023/24"),
    189976: ("2BL", "2024/25"),
    191651: ("2BL", "2025/26"),
    # Bundesliga (Ligakontext fuer Leipzig/Werner und Hoffenheim/Ilzer)
    189970: ("BL", "2024/25"),
    191661: ("BL", "2025/26"),
    # Oesterreichische Bundesliga (Ligakontext fuer Sturm Graz/Ilzer)
    186237: ("AUT", "2020/21"),
    187523: ("AUT", "2021/22"),
    188062: ("AUT", "2022/23"),
    188980: ("AUT", "2023/24"),
    189980: ("AUT", "2024/25"),
}

SEASON_COMP = {
    **{s: COMP_2BL for s in (181138, 185568, 185781, 186266, 187512,
                             188076, 188972, 189976, 191651)},
    **{s: COMP_BL for s in (189970, 191661)},
    **{s: COMP_AUT for s in (186237, 187523, 188062, 188980, 189980)},
}

# ---------------------------------------------------------------- VfL Bochum
VFL_TEAM = 2448          # VfL Bochum 1848 (Maenner). NICHT 3030 (Frauen).
VFL_SEASON = 191651      # 2025/26, 2. Bundesliga

# ------------------------------------------------------------ Referenzkohorte
# Vom Verein benannte Vorbilder. Gewicht 0.5 fuer Schalke ("in Abstrichen").
# Filter laeuft ueber coach_id UND team_id UND season_id -> nur Ligaspiele.
REFERENCE = [
    # key,             coach_id, team_id, season_ids,                         weight
    ("leipzig_werner",   454326,    2975, (191661,),                            1.0),
    ("sturm_ilzer",      357755,    8742, (186237, 187523, 188062, 188980,
                                           189980),                             1.0),
    ("hoffenheim_ilzer", 357755,    2482, (189970, 191661),                     1.0),
    ("schalke_muslic",   684312,    2449, (191651,),                            0.5),
]

REFERENCE_LABEL = {
    "leipzig_werner": "RB Leipzig / Werner",
    "sturm_ilzer": "Sturm Graz / Ilzer",
    "hoffenheim_ilzer": "TSG Hoffenheim / Ilzer",
    "schalke_muslic": "Schalke 04 / Muslic",
}

# ------------------------------------------------------- Spalten: Team-Match
TEAM_COLS = [
    "match_id", "team_id",
    # Paesse
    "wy_totals_passes_passes", "wy_totals_passes_passes_successful",
    "wy_totals_passes_forward_passes", "wy_totals_passes_forward_passes_successful",
    "wy_totals_passes_back_passes", "wy_totals_passes_lateral_passes",
    "wy_totals_passes_progressive_passes", "wy_totals_passes_progressive_passes_successful",
    "wy_totals_passes_vertical_passes", "wy_totals_passes_vertical_passes_successful",
    "wy_totals_passes_through_passes", "wy_totals_passes_through_passes_successful",
    "wy_totals_passes_pass_to_penalty_areas", "wy_totals_passes_pass_to_penalty_areas_successful",
    "wy_totals_passes_pass_to_final_thirds", "wy_totals_passes_pass_to_final_thirds_successful",
    "wy_totals_passes_deep_completed_passes", "wy_totals_passes_deep_completed_passes_successful",
    "wy_totals_passes_long_passes", "wy_totals_passes_long_passes_successful",
    "wy_totals_passes_key_passes", "wy_totals_passes_shot_assists",
    "wy_totals_passes_smart_passes", "wy_totals_passes_match_tempo",
    "wy_average_passes_avg_pass_length",
    # Flanken
    "wy_totals_passes_crosses_total", "wy_totals_passes_crosses_successful",
    "wy_totals_passes_crosses_low", "wy_totals_passes_crosses_high",
    "wy_totals_passes_crosses_blocked",
    "wy_totals_passes_crosses_from_left_flank", "wy_totals_passes_crosses_from_right_flank",
    # Aufbau-Passlaengen
    "wy_totals_openplay_short", "wy_totals_openplay_medium",
    "wy_totals_openplay_long", "wy_totals_openplay_very_long",
    "wy_totals_openplay_total",
    # Ballbesitz
    "wy_totals_possession_possession_number",
    "wy_totals_possession_reaching_opponent_half",
    "wy_totals_possession_reaching_opponent_box",
    "wy_totals_possession_total_time_seconds",
    "wy_totals_possession_dead_time_seconds",
    "wy_totals_possession_pure_possession_time_seconds",
    "wy_average_possession_avg_possession_duration_seconds",
    "wy_percent_possession_possession_percent",
    # Uebergaenge
    "wy_totals_transitions_recoveries_high", "wy_totals_transitions_recoveries_medium",
    "wy_totals_transitions_recoveries_low", "wy_totals_transitions_recoveries_total",
    "wy_totals_transitions_losses_high", "wy_totals_transitions_losses_medium",
    "wy_totals_transitions_losses_low", "wy_totals_transitions_losses_total",
    "wy_totals_transitions_opponent_half_recoveries",
    "wy_totals_transitions_own_half_losses",
    # Defensive
    "wy_totals_defence_pdda", "wy_totals_defence_interceptions",
    "wy_totals_defence_tackles", "wy_totals_defence_clearances",
    "wy_totals_duels_challenge_intensity",
    "wy_totals_duels_defensive_duels", "wy_totals_duels_defensive_duels_successful",
    "wy_totals_duels_aerial_duels", "wy_totals_duels_aerial_duels_successful",
    # Abschluesse / xG
    "wy_totals_general_xg", "wy_totals_general_xg_per_shot",
    "wy_totals_general_xg_per_shot_against",
    "wy_totals_general_shots", "wy_totals_general_shots_on_target",
    "wy_totals_general_shots_from_box", "wy_totals_general_shots_from_danger_zone",
    "wy_totals_general_shots_against",
    "wy_totals_general_touches_in_box", "wy_totals_general_progressive_runs",
    "wy_totals_general_goals", "wy_totals_general_red_cards",
    "wy_totals_general_yellow_cards", "wy_totals_general_corners",
    "wy_totals_general_fouls",
    # Angriffe
    "wy_totals_attacks_total", "wy_totals_attacks_with_shots",
    "wy_totals_attacks_counter_attacks",
    "wy_totals_attacks_positional_attack", "wy_totals_attacks_positional_with_shots",
    "wy_totals_attacks_corners", "wy_totals_attacks_free_kicks",
    # Fluegel
    "wy_totals_flanks_left_flank_attacks", "wy_totals_flanks_right_flank_attacks",
    "wy_totals_flanks_center_attacks",
    "wy_totals_flanks_left_flank_xg", "wy_totals_flanks_right_flank_xg",
    "wy_totals_flanks_center_xg",
]

# ----------------------------------------------------- Spalten: Spieler-Match
PLAYER_COLS = [
    "match_id", "player_id", "team_id",
    "wy_totals_minutes_on_field", "wy_role_1_code",
    # Gegenpressing / Restverteidigung
    "wy_per_90_counterpressing_recoveries",
    "wy_per_90_dangerous_own_half_losses",
    "wy_per_90_dangerous_opponent_half_recoveries",
    "wy_per_90_recoveries", "wy_per_90_losses",
    # Abschluss / Torhueter
    "wy_per_90_xg_shot", "wy_per_90_shots", "wy_per_90_goals",
    "wy_per_90_penalties", "wy_per_90_xg_save", "wy_per_90_gk_conceded_goals",
    "wy_per_90_gk_shots_against",
    # Physik (erst ab Okt 2024)
    "wy_per_90_physical_hi_distance", "wy_per_90_physical_distance",
    "wy_per_90_physical_count_hi", "wy_per_90_physical_count_sprint",
    "wy_per_90_physical_count_hsr",
    "wy_per_90_physical_count_high_acceleration",
    "wy_per_90_physical_count_high_deceleration",
    "wy_totals_physical_max_speed",
]

MATCH_COLS = [
    "wyscout_id", "date_utc", "gameweek", "label", "competition_id", "season_id",
    "home_team_id", "away_team_id", "winner_team_id",
    "home_team_score", "away_team_score",
    "home_team_score_half_time", "away_team_score_half_time",
    "home_team_coach_id", "away_team_coach_id",
    "status", "meta_match_data_downloaded", "meta_match_physical_data_downloaded",
]

DATA = os.environ.get("VFL_DATEN", os.path.join(WURZEL, "daten"))
OUT = os.environ.get("VFL_ERGEBNISSE", os.path.join(WURZEL, "ergebnisse"))
