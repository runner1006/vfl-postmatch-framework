"""Erzeugt ergebnisse/dashboard_matches.json — Datenbasis fuer den Spielbericht
und die Parameterdokumentation.

Wichtig: Es werden ROHGROESSEN abgelegt (npxG, Tore, Modellerwartung, Ligamittel,
Gegner-Saisonstaerke), nicht fertige Scores. Die Normalisierung und die Zielwerte
werden erst im Dashboard gerechnet und sind dort austauschbar.
"""
import json
import numpy as np
import pandas as pd
from config import DATA, OUT, REFERENCE, REFERENCE_LABEL, VFL_TEAM, VFL_SEASON
from kpis import REGISTRY, PHASE_LABEL, PHASE_WEIGHTS, NORMATIVE_CORRIDOR
from scoring import CONF_SCHWELLE

PHASES = list(PHASE_WEIGHTS)


def n(x, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


# --------------------------------------------------------------------------
# Parameterdokumentation: drei Ebenen
# --------------------------------------------------------------------------
KPI_DOC = {
    "O1_vertikalitaet": dict(
        name="Vertikalität", mgmt="„Nach vorne gespielt“", rp="RP3 Forward Mindset",
        prinzip="Vorwärtsgerichtetes Passspiel als Grundhaltung, nicht als Notlösung",
        definition="Anteil der erfolgreichen Vorwärtspässe an allen erfolgreichen Pässen",
        formel="passes_forward_passes_successful / passes_passes_successful",
        zaehler="wy_totals_passes_forward_passes_successful",
        nenner="wy_totals_passes_passes_successful",
        tabelle="wyscout_match_team_stats_sync", norm="Anteil (0–1)", shrink=None,
        limit="Vorwärtsrichtung ist providerdefiniert; sagt nichts über Raumgewinn"),
    "O2_boxzugang": dict(
        name="Boxzugang", mgmt="„Bis in die Box durchgekommen“",
        rp="Ursprungsbriefing: kontrollierte Progression",
        prinzip="Aus der gegnerischen Hälfte wird auch ein Box-Zugriff",
        definition="Anteil der Ballbesitze in der gegnerischen Hälfte, die bis in die Box führen",
        formel="possession_reaching_opponent_box / possession_reaching_opponent_half",
        zaehler="wy_totals_possession_reaching_opponent_box",
        nenner="wy_totals_possession_reaching_opponent_half",
        tabelle="wyscout_match_team_stats_sync", norm="je Hälften-Erreichung", shrink=None,
        limit="Rev. 3: ersetzt Deep Completed Passes je Ballbesitz — jener korrelierte "
              "zu r = 0,97 mit dem neuen OT2"),
    "O3_fluegel_boxzuspiel": dict(
        name="Flügel-Boxzuspiel", mgmt="„Von außen gefährlich geworden“",
        rp="RP4 Flügelfokus",
        prinzip="Chancen aus der Außenspur, Flanken auf den Zielspieler",
        definition="Erfolgreiche Flanken je Ballbesitz",
        formel="passes_crosses_successful / possession_possession_number",
        zaehler="wy_totals_passes_crosses_successful",
        nenner="wy_totals_possession_possession_number",
        tabelle="wyscout_match_team_stats_sync", norm="je Ballbesitz", shrink=None,
        limit="KORRIDOR NORMATIV — keine der vier Referenzmannschaften spielt "
              "flügellastig. Cut-Backs nur über flache Flanken annäherbar."),
    "OT1_konterrate": dict(
        name="Konterrate", mgmt="„Umgeschaltet“", rp="Umschaltmoment genutzt",
        prinzip="Nach Ballgewinn entsteht ein direkter Angriff",
        definition="Konterangriffe je Ballgewinn, empirisch-bayesianisch geglättet",
        formel="attacks_counter_attacks / transitions_recoveries_total  (Shrinkage k=12)",
        zaehler="wy_totals_attacks_counter_attacks",
        nenner="wy_totals_transitions_recoveries_total",
        tabelle="wyscout_match_team_stats_sync", norm="je Ballgewinn", shrink=12,
        limit="Einzige providerseitig transitionsgetaggte Größe — trennt die "
              "Referenzteams dennoch nicht (0/4)"),
    "OT2_tiefenertrag": dict(
        name="Tiefenertrag je Ballgewinn", mgmt="„Aus Ballgewinnen Tiefe erzeugt“",
        rp="Ertrag des Ballgewinns",
        prinzip="Aus dem Ballgewinn entsteht ein Pass in die Zone vor dem Tor",
        definition="Erfolgreiche Deep Completed Passes je Ballgewinn",
        formel="passes_deep_completed_passes_successful / transitions_recoveries_total",
        zaehler="wy_totals_passes_deep_completed_passes_successful",
        nenner="wy_totals_transitions_recoveries_total",
        tabelle="wyscout_match_team_stats_sync", norm="je Ballgewinn", shrink=None,
        limit="Nicht transitionsisoliert — Spielsumme, kein Zeitfenster. Rev. 3: ersetzt "
              "Angriffe je Ballgewinn (r = 0,65 zum neuen DT3)"),
    "OT3_ballgewinnqualitaet": dict(
        name="Ballgewinnqualität", mgmt="„Gefährlich erobert“",
        rp="Voraussetzung für gefährliches Umschalten",
        prinzip="Ballgewinne entstehen in aussichtsreichen Zonen",
        definition="Gefährliche Ballgewinne in der gegnerischen Hälfte je Ballgewinn",
        formel="Σ_Spieler dangerous_opponent_half_recoveries / transitions_recoveries_total",
        zaehler="wy_per_90_dangerous_opponent_half_recoveries × Minuten/90 (Spielerebene)",
        nenner="wy_totals_transitions_recoveries_total",
        tabelle="wyscout_match_player_stats_sync → Team", norm="je Ballgewinn", shrink=None,
        limit="Gefährlichkeitsschwelle providerintern"),
    "D1_pressingdruck": dict(
        name="Pressingdruck", mgmt="„Druck gemacht“", rp="RP1 hohes Anlaufen",
        prinzip="Aggressives, hohes Anlaufen des gegnerischen Aufbaus",
        definition="Gegnerische Pässe je eigener Defensivaktion (PPDA)",
        formel="defence_pdda   — Orientierung −1: niedriger = aggressiver",
        zaehler="wy_totals_defence_pdda", nenner="—",
        tabelle="wyscout_match_team_stats_sync",
        norm="je gegnerischer Aufbauaktion", shrink=None,
        limit="Sinkt mechanisch auch durch viele tiefe Defensivaktionen — nie allein lesen"),
    "D2_ballgewinnhoehe": dict(
        name="Ballgewinnhöhe", mgmt="„Hoch erobert“", rp="RP1 Vorwärtsverteidigen",
        prinzip="Der Ball wird weit vom eigenen Tor erobert",
        definition="Hohe Ballgewinne je effektiver Spielminute",
        formel="transitions_recoveries_high / eff_min",
        zaehler="wy_totals_transitions_recoveries_high",
        nenner="(possession_total_time_seconds − possession_dead_time_seconds) / 60",
        tabelle="wyscout_match_team_stats_sync", norm="je effektiver Spielminute", shrink=None,
        limit="Zonendefinition providerintern"),
    "D3_gegner_progression": dict(
        name="Zugelassene gegnerische Progression", mgmt="„Den Gegner nicht spielen lassen“",
        rp="RP1 Absicherung",
        prinzip="Der Gegner kommt nicht in kontrollierte Vorwärtsbewegung",
        definition="Erfolgreiche progressive Pässe des Gegners je gegnerischem Ballbesitz",
        formel="Gegner.passes_progressive_passes_successful / "
               "Gegner.possession_possession_number — Orientierung −1",
        zaehler="wy_totals_passes_progressive_passes_successful (Gegnerzeile)",
        nenner="wy_totals_possession_possession_number (Gegnerzeile)",
        tabelle="wyscout_match_team_stats_sync (Gegnerzeile)",
        norm="je gegnerischem Ballbesitz", shrink=None,
        limit="Rev. 3: ersetzt die zugelassene Hälften-Erreichung — jene korrelierte "
              "zu r = 0,70 mit dem neuen DT3"),
    "DT1_gegenpressing": dict(
        name="Gegenpressing-Quote", mgmt="„Sofort zurückerobert“",
        rp="Ursprungsbriefing: unmittelbares Gegenpressing",
        prinzip="Nach Ballverlust folgt sofortiger Zugriff",
        definition="Erfolgreiche Gegenpressing-Rückeroberungen je Ballverlust",
        formel="Σ_Spieler counterpressing_recoveries / transitions_losses_total",
        zaehler="wy_per_90_counterpressing_recoveries × Minuten/90 (Spielerebene)",
        nenner="wy_totals_transitions_losses_total",
        tabelle="wyscout_match_player_stats_sync → Team", norm="je Ballverlust", shrink=None,
        limit="Misst nur ERFOLGE. Gegenpressing-Versuche brauchen Event-Zeitstempel."),
    "DT2_gefaehrl_verluste": dict(
        name="Gefährlichkeit der Verluste", mgmt="„Sauber verloren“", rp="Restverteidigung",
        prinzip="Ballverluste passieren nicht in gefährlichen Zonen",
        definition="Anteil gefährlicher Ballverluste in der eigenen Hälfte",
        formel="Σ_Spieler dangerous_own_half_losses / transitions_losses_total "
               "— Orientierung −1",
        zaehler="wy_per_90_dangerous_own_half_losses × Minuten/90 (Spielerebene)",
        nenner="wy_totals_transitions_losses_total",
        tabelle="wyscout_match_player_stats_sync → Team", norm="je Ballverlust", shrink=None,
        limit="Gefährlichkeitsschwelle providerintern"),
    "DT3_hohe_verluste": dict(
        name="Höhe der Ballverluste", mgmt="„Weit weg vom eigenen Tor verloren“",
        rp="Restverteidigung",
        prinzip="Ballverluste passieren hoch, nicht in der eigenen Gefahrenzone",
        definition="Anteil der eigenen Ballverluste, die im hohen Drittel passieren",
        formel="transitions_losses_high / transitions_losses_total",
        zaehler="wy_totals_transitions_losses_high",
        nenner="wy_totals_transitions_losses_total",
        tabelle="wyscout_match_team_stats_sync", norm="je Ballverlust", shrink=None,
        limit="Rev. 3: ersetzt die zugelassenen Konter (0/4 Konsistenz, 29 % Nullzähler). "
              "Der Tausch erzwang die Wechsel bei D3 und OT2."),
    "P1_laufvolumen_hi": dict(
        name="Intensives Laufvolumen", mgmt="„Intensität gehalten“", rp="RP2 Laufvolumen",
        prinzip="Hohe Laufintensität als Voraussetzung des Spielstils",
        definition="Hochintensive Laufdistanz der Feldspieler je effektiver Spielminute",
        formel="Σ_Feldspieler physical_hi_distance / eff_min",
        zaehler="wy_per_90_physical_hi_distance × Minuten/90 (ohne Torwart)",
        nenner="effektive Spielzeit in Minuten",
        tabelle="wyscout_match_player_stats_sync → Team",
        norm="Meter je effektiver Spielminute", shrink=None,
        limit="Nur wenn ≥ 80 % der Feldspielerminuten abgedeckt sind, sonst NaN. "
              "Kein Ballbesitzkontext (SkillCorner fehlt)."),
    "P2_explosivitaet": dict(
        name="Explosivität", mgmt="„Explosiv geblieben“", rp="RP2 Explosivität",
        prinzip="Beschleunigungen für Pressing, Absicherung und Hinterlaufen",
        definition="Hohe Beschleunigungen der Feldspieler je effektiver Spielminute",
        formel="Σ_Feldspieler physical_count_high_acceleration / eff_min",
        zaehler="wy_per_90_physical_count_high_acceleration × Minuten/90 (ohne Torwart)",
        nenner="effektive Spielzeit in Minuten",
        tabelle="wyscout_match_player_stats_sync → Team",
        norm="Aktionen je effektiver Spielminute", shrink=None,
        limit="Decelerations korrelieren zu r = 0,82 und sind deshalb sekundär"),
    "P3_endgeschwindigkeit": dict(
        name="Endgeschwindigkeit", mgmt="„Spitze abgerufen“", rp="RP2 Endgeschwindigkeit",
        prinzip="Spitzengeschwindigkeit im Spiel tatsächlich abgerufen",
        definition="Mittel der fünf höchsten Maximalgeschwindigkeiten der Feldspieler",
        formel="mean(Top-5 physical_max_speed der Feldspieler)",
        zaehler="wy_totals_physical_max_speed", nenner="—",
        tabelle="wyscout_match_player_stats_sync → Team",
        norm="Team-Aggregat (Top-5-Mittel)", shrink=None,
        limit="Einzelspitzen; unabhängig von P1/P2 (r ≤ 0,44)"),
}

PHASE_DOC = {
    "offensiv": dict(
        frage="Baut der VfL kontrolliert auf, wird er vorwärtsgerichtet gefährlich?",
        rp="Referenzpunkte 3 (Forward Mindset) und 4 (Flügelfokus)"),
    "off_umschalten": dict(
        frage="Reagiert die Mannschaft nach Ballgewinn zielgerichtet?",
        rp="Ursprungsbriefing; keine eigene Referenzpunkt-Zuordnung"),
    "defensiv": dict(
        frage="Verteidigt der VfL aktiv, hoch und trotzdem abgesichert?",
        rp="Referenzpunkt 1 (aggressiv, hohes Anlaufen, Vorwärtsverteidigen)"),
    "def_umschalten": dict(
        frage="Folgt nach Ballverlust sofortiger Zugriff, bleibt die Restverteidigung stabil?",
        rp="Ursprungsbriefing: unmittelbares Gegenpressing"),
    "physisch": dict(
        frage="War die Mannschaft körperlich in der Lage, diesen Stil zu spielen?",
        rp="Referenzpunkt 2 (Laufvolumen, Explosivität, Endgeschwindigkeit)"),
}


T = "wy_totals_"

# Kontextgroessen, die im Spielbericht einsehbar sind. Jede wird zusaetzlich als
# Perzentil ihrer Liga-Saison ausgewiesen, damit "viel" oder "wenig" einordbar ist.
KONTEXT = [
    ("geg_ballbesitz", "Ballbesitz Gegner", "%", "gegner", "wy_percent_possession_possession_percent"),
    ("geg_pdda", "PPDA Gegner (hoch = läuft nicht an)", "", "gegner", T + "defence_pdda"),
    ("geg_recov_hoch", "Ballgewinnhöhe Gegner", "Anteil", "quotient_gegner",
     (T + "transitions_recoveries_high", T + "transitions_recoveries_total")),
    ("geg_fwd_anteil", "Vorwärtspass-Anteil Gegner", "Anteil", "quotient_gegner",
     (T + "passes_forward_passes_successful", T + "passes_passes_successful")),
    ("geg_haelfte_rate", "Gegner erreicht unsere Hälfte", "Anteil", "quotient_gegner",
     (T + "possession_reaching_opponent_half", T + "possession_possession_number")),
    ("geg_box_rate", "Gegner erreicht unsere Box", "Anteil", "quotient_gegner",
     (T + "possession_reaching_opponent_box", T + "possession_possession_number")),
    ("geg_konter", "Konter des Gegners", "Anzahl", "gegner", T + "attacks_counter_attacks"),
    ("eig_ballgewinne", "Eigene Ballgewinne (Nenner)", "Anzahl", "team",
     T + "transitions_recoveries_total"),
    ("eig_ballverluste", "Eigene Ballverluste (Nenner)", "Anzahl", "team",
     T + "transitions_losses_total"),
    ("eig_ballbesitze", "Eigene Ballbesitze (Nenner)", "Anzahl", "team",
     T + "possession_possession_number"),
    ("eig_eff_min", "Effektive Spielzeit", "Minuten", "roh", "eff_min"),
]


def kontext_frame(d, team_stats):
    """Kontextgroessen je Team-Match plus Perzentil in der Liga-Saison."""
    o = team_stats.rename(columns={"team_id": "opponent_id",
                                   **{c: "O_" + c for c in team_stats.columns
                                      if c not in ("match_id", "team_id")}})
    x = d[["match_id", "team_id", "opponent_id", "liga_saison", "eff_min"]].merge(
        o, on=["match_id", "opponent_id"], how="left").merge(
        team_stats, on=["match_id", "team_id"], how="left")
    out = pd.DataFrame(index=x.index)
    for key, _, _, art, spalte in KONTEXT:
        if art == "roh":
            v = pd.to_numeric(x[spalte], errors="coerce")
        elif art == "gegner":
            v = pd.to_numeric(x["O_" + spalte], errors="coerce")
        elif art == "team":
            v = pd.to_numeric(x[spalte], errors="coerce")
        else:                                     # quotient_gegner
            z, nn = spalte
            v = (pd.to_numeric(x["O_" + z], errors="coerce")
                 / pd.to_numeric(x["O_" + nn], errors="coerce").where(
                     pd.to_numeric(x["O_" + nn], errors="coerce") > 0))
        out[key] = v
        out[key + "_p"] = v.groupby(x["liga_saison"]).rank(pct=True) * 100
    # Blockhoehe des Gegners: je Liga-Saison standardisiert, hoch = presst hoch
    zp = -pd.to_numeric(x["O_" + T + "defence_pdda"], errors="coerce")
    zr = out["geg_recov_hoch"]
    zz = lambda s: s.groupby(x["liga_saison"]).transform(          # noqa: E731
        lambda t: (t - t.mean()) / t.std(ddof=0))
    out["geg_blockhoehe"] = zz(zp) + zz(zr)
    out["geg_blockhoehe_p"] = out["geg_blockhoehe"].groupby(x["liga_saison"]).rank(pct=True) * 100
    out["match_id"] = x["match_id"].values
    out["team_id"] = x["team_id"].values
    return out


def main():
    d = pd.read_csv(f"{OUT}/kpi_match_level.csv", parse_dates=["date_utc"])
    meta = pd.read_csv(f"{DATA}/kpi_adjusted.csv",
                       usecols=["match_id", "team_id", "coach_id", "season_id",
                                "exp_CC1_npxg", "exp_CC1d_npxg_gegen"])
    d = d.merge(meta, on=["match_id", "team_id"], how="left")
    d = d.merge(kontext_frame(d, pd.read_csv(f"{DATA}/team_stats.csv")),
                on=["match_id", "team_id"], how="left")
    prof = pd.read_csv(f"{OUT}/reference_cohort_profile.csv").set_index("kpi")
    corr = json.load(open(f"{OUT}/corridors.json"))

    # npg (Tore ohne Elfmeter) kommt bereits aus kpi_match_level.csv. Die frueher hier
    # stehende Ersatzrechnung hat sie mit den Gesamttoren ueberschrieben, weil die Spalte
    # n_penalties nie existiert hat - die Elfmeter waeren so in die Effizienz eingegangen.
    if "npg" not in d:
        d["npg"] = d["tore"] - d.get("n_penalties", 0)

    # Gegentore ohne Elfmeter = npG der Gegnerzeile desselben Spiels. Damit stehen auf
    # beiden Seiten dieselben Groessen (npG gegen npxG); das Ligamittel der Nettoeffizienz
    # ist dann konstruktionsbedingt exakt 0 und die Skala bleibt lesbar.
    d = d.merge(d[["match_id", "team_id", "npg"]].rename(
        columns={"team_id": "opponent_id", "npg": "npg_gegen"}),
        on=["match_id", "opponent_id"], how="left")

    # ---------------------------------------------- Gegnerstaerke je Liga-Saison
    # Saisonmittel je Team: erzeugtes und zugelassenes npxG. Basis fuer die
    # einfache Normalisierungsvariante im Dashboard.
    ts = (d.groupby(["liga_saison", "team_id"])
            .agg(npxg_off=("CC1_npxg", "mean"), npxg_def=("CC1d_npxg_gegen", "mean"),
                 spiele=("match_id", "size")).reset_index())
    ls_mean = (d.groupby("liga_saison")
                 .agg(npxg=("CC1_npxg", "mean"), sd=("CC1_npxg", "std"),
                      tore=("tore", "mean")).reset_index())

    staerke = {}
    for r in ts.itertuples(index=False):
        staerke.setdefault(r.liga_saison, {})[str(int(r.team_id))] = {
            "off": n(r.npxg_off), "def": n(r.npxg_def), "n": int(r.spiele)}
    ligamittel = {r.liga_saison: {"npxg": n(r.npxg), "sd": n(r.sd), "tore": n(r.tore)}
                  for r in ls_mean.itertuples(index=False)}

    # ---------------------------------------------------------- Teams und Spiele
    teams = []
    reihen = [("bochum", "VfL Bochum", None, VFL_TEAM, (VFL_SEASON,))]
    reihen += [(k, REFERENCE_LABEL[k], c, t, s) for k, c, t, s, _ in REFERENCE]

    for key, label, coach, team, seasons in reihen:
        sub = d[(d.team_id == team) & (d.season_id.isin(seasons))]
        if coach is not None:
            sub = sub[sub.coach_id == coach]
        sub = sub.sort_values("date_utc")
        spiele = []
        for i, r in enumerate(sub.itertuples(index=False)):
            spiele.append({
                "i": i, "id": int(r.match_id), "gw": int(r.gameweek) if pd.notna(r.gameweek) else i + 1,
                "datum": str(r.date_utc.date()), "ls": r.liga_saison,
                "geg": r.gegner if isinstance(r.gegner, str) else "?",
                "geg_id": int(r.opponent_id), "heim": bool(r.is_home),
                "tore": int(r.tore), "gt": int(r.gegentore), "pkt": int(r.punkte),
                # Stil
                "score": n(r.gesamtscore_spielstil, 1),
                "ph": {p: n(getattr(r, f"phase_{p}"), 1) for p in PHASES},
                "kpi": {k: n(getattr(r, f"score_{k}"), 1) for k in REGISTRY},
                "kpi_roh": {k: n(getattr(r, k), 4) for k in REGISTRY},
                "kpi_n": {k: n(getattr(r, f"n_{k}"), 1) for k in REGISTRY},
                "kpi_conf": {k: n(getattr(r, f"conf_{k}"), 2) for k in REGISTRY},
                "ph_conf": {p: n(getattr(r, f"conf_{p}"), 2) for p in PHASES},
                "ph_guete": {p: n(getattr(r, f"guete_{p}"), 2) for p in PHASES},
                "npg": n(r.npg, 2), "npg_geg": n(r.npg_gegen, 2),
                "tw_effekt": n(r.torhueter_effekt, 3),
                "kontext": {key: n(getattr(r, key), 3) for key, *_ in KONTEXT},
                "kontext_p": {key: n(getattr(r, key + "_p"), 0) for key, *_ in KONTEXT},
                "blockhoehe": n(r.geg_blockhoehe, 2),
                "blockhoehe_p": n(r.geg_blockhoehe_p, 0),
                "conf": n(r.confidence_gesamt, 2),
                "flags": r.warnflags if isinstance(r.warnflags, str) else "",
                # Rohgroessen fuer die rechte Seite
                "npxg": n(r.CC1_npxg), "npxg_geg": n(r.CC1d_npxg_gegen),
                "exp_npxg": n(r.exp_CC1_npxg), "exp_npxg_geg": n(r.exp_CC1d_npxg_gegen),
                "xp": n(r.xpoints, 2), "dpkt": n(r.delta_punkte, 2),
                "psieg": n(r.p_sieg, 3), "premis": n(r.p_remis, 3),
                "pnied": n(r.p_niederlage, 3),
                "klasse": r.klassifikation if isinstance(r.klassifikation, str) else "",
            })
        teams.append({"key": key, "label": label, "n": len(spiele),
                      "saisons": sorted(sub.liga_saison.unique().tolist()),
                      "spiele": spiele})

    # -------------------------------------------------- Aufsteiger-Benchmark
    up = d[(d.liga == "2BL") & (d.ist_aufsteiger_saison == 1)]
    b_off, b_def = float(up.CC1_npxg.mean()), float(up.CC1d_npxg_gegen.mean())

    # Wie oft erreichen die Aufsteiger selbst ihr eigenes, gegnerbereinigtes Niveau?
    # Dieselbe additive Verschiebung wie im Dashboard: Benchmark + Abweichung des
    # Gegners vom Ligamittel. Dient als Vergleichslinie fuer die Saisonzeile.
    z = d[d.liga == "2BL"].merge(
        ts.rename(columns={"team_id": "opponent_id", "npxg_off": "g_off",
                           "npxg_def": "g_def"})[["liga_saison", "opponent_id",
                                                  "g_off", "g_def"]],
        on=["liga_saison", "opponent_id"], how="left")
    z = z.merge(ls_mean[["liga_saison", "npxg"]].rename(columns={"npxg": "lm"}),
                on="liga_saison", how="left")
    ziel_diff = ((b_off + (z.g_def - z.lm)) - (b_def + (z.g_off - z.lm)))
    ist_diff = z.CC1_npxg - z.CC1d_npxg_gegen
    z["ueber_ziel"] = ist_diff >= ziel_diff
    anteil_up = float(z.loc[z.ist_aufsteiger_saison == 1, "ueber_ziel"].mean() * 100)
    anteil_liga = float(z["ueber_ziel"].mean() * 100)

    benchmark = {
        "npxg_erzeugt": n(b_off), "npxg_zugelassen": n(b_def),
        "npxg_diff": n(b_off - b_def),
        "tore": n(up.tore.mean()), "gegentore": n(up.gegentore.mean()),
        "n": int(len(up)),
        "anteil_ueber_ziel": n(anteil_up, 1),
        "anteil_ueber_ziel_liga": n(anteil_liga, 1),
        # Rev. 4: beidseitige Effizienz auf npG-Basis (Tore ohne Elfmeter),
        # damit die Referenz zur npxG-Groesse passt.
        "eff_offensiv": n(float((up.npg - up.CC1_npxg).mean())),
        "eff_defensiv": n(float((up.CC1d_npxg_gegen - up.npg_gegen).mean())),
        "eff_netto": n(float(((up.npg - up.CC1_npxg)
                              + (up.CC1d_npxg_gegen - up.npg_gegen)).mean())),
        "tw_effekt": n(float(up.torhueter_effekt.mean())),
    }

    # ------------------------------------------------ Parameterdokumentation
    doc_phasen = [{
        "key": p, "label": PHASE_LABEL[p], "gewicht": PHASE_WEIGHTS[p],
        "frage": PHASE_DOC[p]["frage"], "rp": PHASE_DOC[p]["rp"],
        "kpis": [k for k in REGISTRY if REGISTRY[k][3] == p],
    } for p in PHASES]

    doc_kpis = []
    for k, (orient, shape, sk, phase, gew) in REGISTRY.items():
        c = corr[k]
        e = c["einheiten_2bl_2526"]
        doc_kpis.append({
            "key": k, "kurz": k.split("_")[0], "phase": phase,
            "phase_label": PHASE_LABEL[phase], "gewicht": gew,
            "orient": orient, "form": shape, "shrink": sk,
            "urteil": prof.loc[k, "urteil"], "delta": n(prof.loc[k, "delta_gesamt"]),
            "konsistenz": prof.loc[k, "konsistenz"],
            "normativ": k in NORMATIVE_CORRIDOR,
            "quelle_korridor": c["quelle_korridor"],
            "anker": {"score0": e["score0"], "score50": e["score50"],
                      "score100": e["score100"], "liga_mittel": e["liga_mittel"],
                      "liga_sd": e["liga_sd"], "kohorte_mitte": e.get("kohorte_mitte")},
            "anker_guete": c["anker_guete"],
            **KPI_DOC[k],
        })

    # ---------------------------------------------------- Kontextdefinitionen
    kontext_def = [{"key": k, "label": lab, "einheit": e} for k, lab, e, *_ in KONTEXT]
    kontext_def.append({"key": "blockhoehe", "label": "Blockhöhe des Gegners",
                        "einheit": "z (hoch = presst hoch)"})

    # Hypothesen, vorab gerechnet ueber alle erfassten Spiele
    alle = pd.concat([pd.DataFrame(t["spiele"]).assign(team=t["label"]) for t in teams])
    def korr(xk, yk, yph=None):
        x = alle["blockhoehe"] if xk == "blockhoehe" else alle["kontext"].apply(lambda c: c.get(xk))
        y = (alle["ph"].apply(lambda c: c.get(yph)) if yph
             else alle["kpi"].apply(lambda c: c.get(yk)))
        m = x.notna() & y.notna()
        return (n(float(np.corrcoef(x[m], y[m])[0, 1]), 3), int(m.sum())) if m.sum() > 30 else (None, 0)

    hyp = []
    for lab, xk, yk, yph in [
        ("Tiefer Gegnerblock → weniger Umschaltertrag", "blockhoehe", None, "off_umschalten"),
        ("Tiefer Gegnerblock → weniger Konter", "blockhoehe", "OT1_konterrate", None),
        ("Gegner-Ballbesitz → eigener Boxzugang", "geg_ballbesitz", "O2_boxzugang", None),
        ("Mehr Ballgewinne → höherer Umschaltscore", "eig_ballgewinne", None, "off_umschalten"),
        ("Gegner läuft hoch an → eigene Vertikalität", "geg_pdda", "O1_vertikalitaet", None),
    ]:
        r_, nn = korr(xk, yk, yph)
        hyp.append({"label": lab, "x": xk, "y": yph or yk, "y_ist_phase": bool(yph),
                    "r": r_, "n": nn,
                    "urteil": ("trägt nicht" if r_ is not None and abs(r_) < 0.25
                               else "schwach" if r_ is not None and abs(r_) < 0.45
                               else "deutlich" if r_ is not None else "—")})

    out = {"teams": teams, "staerke": staerke, "ligamittel": ligamittel,
           "benchmark": benchmark, "doc_phasen": doc_phasen, "doc_kpis": doc_kpis,
           "phase_labels": PHASE_LABEL, "kontext_def": kontext_def, "hypothesen": hyp,
           "conf_schwelle": CONF_SCHWELLE}

    with open(f"{OUT}/dashboard_matches.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"dashboard_matches.json — {len(json.dumps(out))/1024:.0f} KB")
    for t in teams:
        print(f"  {t['label']:26s} {t['n']:4d} Spiele  {t['saisons']}")
    print(f"  Aufsteiger-Benchmark: {benchmark}")


if __name__ == "__main__":
    main()
