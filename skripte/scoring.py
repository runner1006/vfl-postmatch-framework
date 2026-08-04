"""Schritt 8: Scoring, Aufstiegsbarometer und visualisierungsfertige Ausgabe.

Erzeugt:
  ergebnisse/kpi_match_level.csv     alle 8.620 Team-Match-Zeilen, voll aufbereitet
  ergebnisse/bochum_2526_scored.csv  die 34 Bochum-Spiele der Saison 2025/26
  ergebnisse/redundancy_matrix.csv   paarweise Korrelationen aller 15 KPIs
"""
import json
import numpy as np
import pandas as pd
from config import DATA, OUT, VFL_TEAM, VFL_SEASON
from kpis import REGISTRY, PHASE_WEIGHTS, PHASE_LABEL, SECONDARY, CC
from korridore import score_dreipunkt

CONF_VON_URTEIL = {
    "stark (>=3/4 Referenzen)": 1.0,
    "gemischt (2/4 Referenzen)": 0.7,
    "normativ gesetzt (keine Vorbild-Evidenz)": 0.5,
    "schwach - Datengrenze, siehe Limitation": 0.4,
}

K_CONF = 6          # Halbwertspunkt der Ereignis-Confidence: n/(n+6)
CONF_SCHWELLE = 0.20   # Rev. 4: nur noch echte Extremfaelle werden ausgegraut


def zweite_stufe(werte, ist_ref):
    """Drei-Punkt-Ankerung auf einem fertigen Aggregat (Phasen-/Gesamtscore).

    Ohne diese zweite Stufe bleibt der Gesamtwert gestaucht: Das Mitteln ueber
    15 teilunabhaengige Dimensionen zieht zur Mitte, weil kein Team auf allen
    gleichzeitig stark ist.
    """
    w = np.asarray(werte, float)
    ok = ~np.isnan(w)
    if ok.sum() < 50:
        return w
    a0 = float(np.nanpercentile(w[ok], 5))
    a50 = float(np.nanmedian(w[ok]))
    koh = None
    if ist_ref is not None:
        koh = w[ok & np.asarray(ist_ref, bool)]
    a100 = (float(np.nanpercentile(koh, 90)) if koh is not None and len(koh) >= 20
            else float(np.nanpercentile(w[ok], 90)))
    if a100 <= a50:
        a100 = max(a50 + 1e-6, float(np.nanpercentile(w[ok], 90)))
    if a50 <= a0:
        a0 = a50 - 1e-6
    s = np.full(w.shape, np.nan)
    unten, oben = ok & (w < a50), ok & (w >= a50)
    s[unten] = 50.0 * (w[unten] - a0) / (a50 - a0)
    s[oben] = 50.0 + 50.0 * (w[oben] - a50) / (a100 - a50)
    return np.clip(s, 0, 100)


def main():
    d = pd.read_csv(f"{DATA}/kpi_adjusted.csv", parse_dates=["date_utc"])
    corr = json.load(open(f"{OUT}/corridors.json"))
    prof = pd.read_csv(f"{OUT}/reference_cohort_profile.csv").set_index("kpi")
    oc = pd.read_csv(f"{OUT}/outcome_alignment.csv")
    names = pd.read_csv(f"{DATA}/team_names.csv").set_index("team_id")["name"].to_dict()
    tab = pd.read_csv(f"{OUT}/abschlusstabellen_2bl.csv")

    kpis = list(REGISTRY)

    # ------------------------------- Stufe 1: KPI-Score aus der Guete-Ankerung
    for k in kpis:
        a = corr[k]["anker_guete"]
        d[f"score_{k}"] = score_dreipunkt(d[f"g_{k}"], a["a0"], a["a50"], a["a100"])
        # Ereignis-Confidence: ein Wert auf Basis von 1 Konter ist keine Aussage
        n = pd.to_numeric(d.get(f"n_{k}"), errors="coerce")
        d[f"conf_{k}"] = np.where(d[f"score_{k}"].isna(), np.nan, n / (n + K_CONF))

    # ------------------------------------------------ Phasen- und Gesamtscore
    phase_of = {k: REGISTRY[k][3] for k in kpis}
    weight_of = {k: REGISTRY[k][4] for k in kpis}
    guete_of = {k: CONF_VON_URTEIL.get(prof.loc[k, "urteil"], 0.5) for k in kpis}
    ist_ref = d["is_ref"].to_numpy(bool) if "is_ref" in d else None

    for ph in PHASE_WEIGHTS:
        ks = [k for k in kpis if phase_of[k] == ph]
        sc = d[[f"score_{k}" for k in ks]].to_numpy(float)
        w = np.array([weight_of[k] for k in ks])
        mask = ~np.isnan(sc)
        wsum = (mask * w).sum(axis=1)
        roh = np.where(wsum > 0,
                       np.nansum(np.nan_to_num(sc) * w, axis=1) / np.where(wsum > 0, wsum, 1),
                       np.nan)
        d[f"phase_roh_{ph}"] = roh
        # Stufe 2: dieselbe Ankerung auf dem Aggregat
        d[f"phase_{ph}"] = zweite_stufe(roh, ist_ref)

        # Rev. 4: zwei getrennte Groessen statt eines Produkts.
        #   guete_<phase> = strukturelle Trennschaerfe der KPIs. Eigenschaft des KPI-Sets,
        #     ueber alle Spiele konstant -> gehoert nicht in eine spielweise Ausblendung.
        #   conf_<phase>  = Belastbarkeit DIESES Spiels, allein aus der Ereigniszahl.
        # Vorher waren beide multipliziert; dadurch konnte eine Phase aus drei schwachen
        # KPIs die Schwelle nie erreichen und war in 100 % der Spiele ausgegraut.
        cn = d[[f"conf_{k}" for k in ks]].to_numpy(float)
        gk = np.array([guete_of[k] for k in ks])
        d[f"conf_{ph}"] = np.where(
            wsum > 0, (np.nan_to_num(cn) * w * mask).sum(axis=1) / np.where(wsum > 0, wsum, 1),
            np.nan) * (mask.sum(axis=1) / len(ks))
        d[f"guete_{ph}"] = float(np.average(gk, weights=w))

    ph_cols = [f"phase_{p}" for p in PHASE_WEIGHTS]
    PW = np.array([PHASE_WEIGHTS[p] for p in PHASE_WEIGHTS])
    M = d[ph_cols].to_numpy(float)
    ok = ~np.isnan(M)
    wsum = (ok * PW).sum(axis=1)
    gesamt_roh = np.where(wsum > 0,
                          np.nansum(np.nan_to_num(M) * PW, axis=1) / np.where(wsum > 0, wsum, 1),
                          np.nan)
    d["gesamtscore_roh"] = gesamt_roh
    d["gesamtscore_spielstil"] = zweite_stufe(gesamt_roh, ist_ref)
    C = d[[f"conf_{p}" for p in PHASE_WEIGHTS]].to_numpy(float)
    d["confidence_gesamt"] = np.nansum(np.where(ok, np.nan_to_num(C) * PW, 0), axis=1) / np.where(
        wsum > 0, wsum, 1)
    G = d[[f"guete_{p}" for p in PHASE_WEIGHTS]].to_numpy(float)
    d["guete_gesamt"] = np.nansum(np.where(ok, np.nan_to_num(G) * PW, 0), axis=1) / np.where(
        wsum > 0, wsum, 1)
    d["phasen_ohne_daten"] = (~ok).sum(axis=1)

    # --------------------------------------------------------- Warnhinweise
    # Kleine Nenner destabilisieren Raten - bleibt als eigener Hinweis erhalten,
    # zusaetzlich zur feineren Ereignis-Confidence je KPI.
    klein = ((d["wy_totals_possession_possession_number"] < 60)
             | (d["wy_totals_transitions_recoveries_total"] < 30)
             | (d["wy_totals_transitions_losses_total"] < 40)
             | (d["eff_min"] < 40))
    lp25_aufbau = d.groupby("liga_saison")["S_aufbaukontrolle"].transform(
        lambda s: s.quantile(0.25))
    a_o1 = corr["O1_vertikalitaet"]["anker_guete"]
    flags = []
    for r in d.itertuples(index=False):
        f = []
        if pd.notna(r.v_O1_vertikalitaet) and r.v_O1_vertikalitaet > 1.0:
            f.append("DIREKT_UNKONTROLLIERT?")
        if (pd.notna(r.score_D1_pressingdruck) and pd.notna(r.score_D3_gegner_progression)
                and r.score_D1_pressingdruck >= 80 and r.score_D2_ballgewinnhoehe >= 80
                and r.score_D3_gegner_progression <= 40):
            f.append("MUTIG_UNGESICHERT")
        if r.rote_karten and r.rote_karten > 0:
            f.append("UNTERZAHL")
        if r.rote_karten_gegner and r.rote_karten_gegner > 0:
            f.append("UEBERZAHL")
        if np.isnan(r.P1_laufvolumen_hi):
            f.append("PHYSIK_FEHLT")
        flags.append(";".join(f))
    d["warnflags"] = flags
    # Der Aufbaukontroll-Check laesst sich erst nach dem Loop vektorisiert setzen
    m = (d["warnflags"].str.contains("DIREKT_UNKONTROLLIERT\\?", regex=True)
         & (d["S_aufbaukontrolle"] >= lp25_aufbau))
    d.loc[m, "warnflags"] = d.loc[m, "warnflags"].str.replace(
        "DIREKT_UNKONTROLLIERT\\?;?", "", regex=True).str.strip(";")
    d["warnflags"] = d["warnflags"].str.replace("DIREKT_UNKONTROLLIERT\\?",
                                                "DIREKT_UNKONTROLLIERT", regex=True)
    d.loc[klein, "warnflags"] = (d.loc[klein, "warnflags"] + ";KLEINE_NENNER").str.strip(";")

    # ---------------------------------------------------- Aufstiegsbarometer
    # Referenz: alle Team-Match-Zeilen der 18 direkten Aufsteiger (2. Bundesliga).
    up = tab[tab["aufsteiger"] == 1][["saison", "team_id"]].assign(_up=1)
    d = d.merge(up, on=["saison", "team_id"], how="left")
    d["ist_aufsteiger_saison"] = d["_up"].fillna(0).astype(int)
    d = d.drop(columns="_up")

    d["npxg_diff"] = d["CC1_npxg"] - d["CC1d_npxg_gegen"]
    d["adj_npxg_diff"] = d["adj_CC1_npxg"] - d["adj_CC1d_npxg_gegen"]
    ref = d[(d["liga"] == "2BL") & (d["ist_aufsteiger_saison"] == 1)]

    def perzentil_gegen(series, referenz):
        r = np.sort(referenz.dropna().to_numpy())
        return np.where(series.isna(), np.nan,
                        np.searchsorted(r, series.to_numpy(), "left") / max(len(r), 1) * 100)

    d["barometer_gesamt"] = perzentil_gegen(d["adj_npxg_diff"], ref["adj_npxg_diff"])
    d["barometer_offensiv"] = perzentil_gegen(d["adj_CC1_npxg"], ref["adj_CC1_npxg"])
    d["barometer_defensiv"] = perzentil_gegen(-d["adj_CC1d_npxg_gegen"],
                                              -ref["adj_CC1d_npxg_gegen"])
    d["barometer_roh"] = perzentil_gegen(d["npxg_diff"], ref["npxg_diff"])

    # ------------------------------------------------- Chancenverwertung
    d["npg"] = d["tore"] - d["n_penalties"].fillna(0)
    d["verwertung_vfl"] = d["npg"] - d["CC1_npxg"]
    d["verwertung_gegner"] = (d["gegentore"] - d["CC1d_npxg_gegen"])
    d["torhueter_effekt"] = d["gk_xg_save"] - d["gegentore"]

    d = d.merge(oc[["match_id", "team_id", "xpoints", "p_sieg", "p_remis", "p_niederlage",
                    "delta_punkte", "klassifikation", "ergebnis_perzentil",
                    "top_ergebnisse", "schussvektor"]],
                on=["match_id", "team_id"], how="left")
    d["team"] = d["team_id"].map(names)
    d["gegner"] = d["opponent_id"].map(names)

    # ------------------------------------------------------------- Ausgabe
    base_cols = ["match_id", "team_id", "team", "opponent_id", "gegner", "liga", "saison",
                 "liga_saison", "date_utc", "gameweek", "is_home", "tore", "gegentore",
                 "punkte", "rote_karten", "rote_karten_gegner", "eff_min",
                 "ist_aufsteiger_saison"]
    kpi_cols = []
    for k in kpis:
        kpi_cols += [k, f"z_{k}", f"v_{k}", f"g_{k}", f"n_{k}", f"conf_{k}",
                     f"exp_{k}", f"adj_{k}", f"score_{k}"]
    score_cols = ph_cols + [f"phase_roh_{p}" for p in PHASE_WEIGHTS] \
        + [f"conf_{p}" for p in PHASE_WEIGHTS] + [f"guete_{p}" for p in PHASE_WEIGHTS] + [
        "gesamtscore_spielstil", "gesamtscore_roh", "confidence_gesamt", "guete_gesamt",
        "phasen_ohne_daten", "warnflags"]
    b_cols = ["CC1_npxg", "CC1d_npxg_gegen", "npxg_diff", "adj_npxg_diff",
              "CC2_box_zugriffsrate", "CC2d_box_zugriffsrate_gegen",
              "CC3_abschlussqualitaet", "CC3d_abschlussqualitaet_gegen",
              "adj_CC1_npxg", "adj_CC1d_npxg_gegen", "adj_CC2_box_zugriffsrate",
              "barometer_gesamt", "barometer_offensiv", "barometer_defensiv", "barometer_roh",
              "npg", "verwertung_vfl", "verwertung_gegner", "torhueter_effekt",
              "xpoints", "p_sieg", "p_remis", "p_niederlage", "delta_punkte",
              "klassifikation", "ergebnis_perzentil", "top_ergebnisse", "schussvektor"]
    out_cols = base_cols + kpi_cols + score_cols + SECONDARY + b_cols

    d[out_cols].to_csv(f"{OUT}/kpi_match_level.csv", index=False)

    b = d[(d["team_id"] == VFL_TEAM) & (d["season_id"] == VFL_SEASON)].sort_values("date_utc")
    b[out_cols].to_csv(f"{OUT}/bochum_2526_scored.csv", index=False)

    # ------------------------------------------------------ Redundanzmatrix
    Z = d[[f"v_{k}" for k in kpis]].rename(columns={f"v_{k}": k for k in kpis})
    cm = Z.corr(min_periods=200).round(3)
    cm.to_csv(f"{OUT}/redundancy_matrix.csv")
    viol = [(a, b_, cm.loc[a, b_]) for i, a in enumerate(kpis) for b_ in kpis[i + 1:]
            if abs(cm.loc[a, b_]) > 0.60]

    print(f"kpi_match_level.csv:    {len(d)} Zeilen, {len(out_cols)} Spalten")
    print(f"bochum_2526_scored.csv: {len(b)} Spiele")
    print(f"\nRedundanz: Paare mit |r| > 0.60 -> {len(viol)}")
    for a, b_, r in viol:
        print(f"   {a} / {b_}: r={r:+.2f}")

    print("\n\nVfL BOCHUM 2025/26 — SAISONUEBERBLICK")
    print(f"  Spiele: {len(b)}   Punkte: {int(b['punkte'].sum())}   "
          f"Tore {int(b['tore'].sum())}:{int(b['gegentore'].sum())}")
    print(f"  Platz laut gerechneter Tabelle: "
          f"{int(tab[(tab.saison=='2025/26') & (tab.team_id==VFL_TEAM)]['platz'].iloc[0])}")
    print(f"  Gesamtscore Spielstiltreue:  {b['gesamtscore_spielstil'].mean():.1f} "
          f"(Median {b['gesamtscore_spielstil'].median():.1f}, "
          f"Spanne {b['gesamtscore_spielstil'].min():.0f}-{b['gesamtscore_spielstil'].max():.0f})")
    print(f"  Aufstiegsbarometer:          {b['barometer_gesamt'].mean():.1f}")
    print(f"  xPoints Summe:               {b['xpoints'].sum():.1f} "
          f"(tatsaechlich {int(b['punkte'].sum())})")
    print("\n  Phasen-Scores im Saisonmittel:")
    for p in PHASE_WEIGHTS:
        print(f"    {PHASE_LABEL[p]:24s} {b[f'phase_{p}'].mean():5.1f}   "
              f"(Confidence {b[f'conf_{p}'].mean():.2f})")
    return d, b


if __name__ == "__main__":
    main()
