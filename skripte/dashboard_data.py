"""Erzeugt ergebnisse/dashboard_data.json — kompakte Datenbasis fuer das HTML-Dashboard."""
import json
import numpy as np
import pandas as pd
from config import DATA, OUT, REFERENCE, REFERENCE_LABEL, VFL_TEAM, VFL_SEASON
from kpis import REGISTRY, PHASE_LABEL, PHASE_WEIGHTS

PHASES = list(PHASE_WEIGHTS)


def jnum(x, nd=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


def main():
    d = pd.read_csv(f"{OUT}/kpi_match_level.csv", parse_dates=["date_utc"])
    meta = pd.read_csv(f"{DATA}/kpi_adjusted.csv",
                       usecols=["match_id", "team_id", "coach_id", "season_id"])
    d = d.merge(meta, on=["match_id", "team_id"], how="left")
    prof = pd.read_csv(f"{OUT}/reference_cohort_profile.csv")
    loso = pd.read_csv(f"{OUT}/loso_validation.csv")
    prom = pd.read_csv(f"{OUT}/promotion_analysis.csv")
    tab = pd.read_csv(f"{OUT}/abschlusstabellen_2bl.csv")

    # ------------------------------------------------------ Kohorte markieren
    d["ref_key"] = None
    for key, coach, team, seasons, _ in REFERENCE:
        m = (d.coach_id == coach) & (d.team_id == team) & (d.season_id.isin(seasons))
        d.loc[m, "ref_key"] = key
    koh = d[d.ref_key.notna()]
    boc = d[(d.team_id == VFL_TEAM) & (d.season_id == VFL_SEASON)].sort_values("date_utc")
    liga = d[d.liga == "2BL"]

    out = {}

    # -------------------------------------------------------------- Eckdaten
    out["meta"] = {
        "stand": "04.08.2026",
        "spiele": int(d.match_id.nunique()),
        "teamzeilen": int(len(d)),
        "ligasaisons": int(d.liga_saison.nunique()),
        "kohorte_spiele": int(len(koh)),
        "bochum_platz": int(tab[(tab.saison == "2025/26") & (tab.team_id == VFL_TEAM)]
                            .platz.iloc[0]),
    }

    # ------------------------------------------------ Nutzbarkeit: je KPI
    urteil_map = {"stark (>=3/4 Referenzen)": "stark",
                  "gemischt (2/4 Referenzen)": "gemischt",
                  "normativ gesetzt (keine Vorbild-Evidenz)": "normativ",
                  "schwach - Datengrenze, siehe Limitation": "schwach"}
    out["kpi_trennschaerfe"] = [{
        "kpi": r.kpi,
        "label": r.kpi.split("_", 1)[1].replace("_", " "),
        "kurz": r.kpi.split("_")[0],
        "phase": r.phase,
        "delta": jnum(r.delta_gesamt, 3),
        "lo": jnum(r.delta_ci_lo, 3), "hi": jnum(r.delta_ci_hi, 3),
        "konsistenz": r.konsistenz,
        "urteil": urteil_map.get(r.urteil, "schwach"),
        "je_team": {k: jnum(getattr(r, f"delta_{k}"), 3) for k, *_ in REFERENCE},
    } for r in prof.itertuples(index=False)]

    # ----------------------------------------- Phasenvergleich mit Confidence
    out["phasen"] = [{
        "phase": p, "label": PHASE_LABEL[p], "gewicht": PHASE_WEIGHTS[p],
        "bochum": jnum(boc[f"phase_{p}"].mean(), 1),
        "kohorte": jnum(koh[f"phase_{p}"].mean(), 1),
        "liga": jnum(liga[f"phase_{p}"].mean(), 1),
        "confidence": jnum(boc[f"conf_{p}"].mean(), 2),
        "spanne_bochum": [jnum(boc[f"phase_{p}"].min(), 0), jnum(boc[f"phase_{p}"].max(), 0)],
    } for p in PHASES]

    out["gesamt"] = {
        "bochum": jnum(boc.gesamtscore_spielstil.mean(), 1),
        "kohorte": jnum(koh.gesamtscore_spielstil.mean(), 1),
        "liga": jnum(liga.gesamtscore_spielstil.mean(), 1),
        "aufsteiger": jnum(liga[liga.ist_aufsteiger_saison == 1]
                           .gesamtscore_spielstil.mean(), 1),
        "barometer_bochum": jnum(boc.barometer_gesamt.mean(), 1),
        "barometer_kohorte": jnum(koh.barometer_gesamt.mean(), 1),
        "barometer_liga": jnum(liga.barometer_gesamt.mean(), 1),
    }

    # ------------------------------------------------- Verlauf: letzte Saison
    def verlauf(sub, label, liga_saison):
        sub = sub.sort_values("date_utc")
        return {
            "team": label, "liga_saison": liga_saison, "n": int(len(sub)),
            "punkte": int(sub.punkte.sum()), "xpoints": jnum(sub.xpoints.sum(), 1),
            "mittel": jnum(sub.gesamtscore_spielstil.mean(), 1),
            "spiele": [{
                "gw": int(g) if pd.notna(g) else i + 1,
                "datum": str(dt)[:10],
                "gegner": geg if isinstance(geg, str) else "",
                "heim": bool(h),
                "erg": f"{int(t)}:{int(gt)}",
                "score": jnum(s, 1),
                "barometer": jnum(b, 0),
                "phasen": {p: jnum(v, 0) for p, v in zip(PHASES, ph)},
            } for i, (g, dt, geg, h, t, gt, s, b, *ph) in enumerate(zip(
                sub.gameweek, sub.date_utc.dt.date, sub.gegner, sub.is_home,
                sub.tore, sub.gegentore, sub.gesamtscore_spielstil,
                sub.barometer_gesamt, *[sub[f"phase_{p}"] for p in PHASES]))],
        }

    reihen = [verlauf(boc, "VfL Bochum", "2. BL 2025/26")]
    for key, coach, team, seasons, _ in REFERENCE:
        sub = d[(d.coach_id == coach) & (d.team_id == team) & (d.season_id.isin(seasons))]
        # letzte Saison mit mindestens 15 Spielen unter diesem Trainer
        gr = sub.groupby("liga_saison").size()
        gr = gr[gr >= 15]
        ls = sub[sub.liga_saison.isin(gr.index)].sort_values("date_utc").liga_saison.iloc[-1]
        reihen.append(verlauf(sub[sub.liga_saison == ls], REFERENCE_LABEL[key], ls))
    out["verlauf"] = reihen

    # ------------------------------------ Alle Spiele je Referenzteam (Streifen)
    out["alle_spiele"] = []
    for key, coach, team, seasons, _ in REFERENCE:
        sub = (d[(d.coach_id == coach) & (d.team_id == team)
                 & (d.season_id.isin(seasons))].sort_values("date_utc"))
        out["alle_spiele"].append({
            "team": REFERENCE_LABEL[key], "n": int(len(sub)),
            "von": str(sub.date_utc.dt.date.iloc[0]), "bis": str(sub.date_utc.dt.date.iloc[-1]),
            "saisons": sorted(sub.liga_saison.unique().tolist()),
            "scores": [jnum(x, 1) for x in sub.gesamtscore_spielstil],
        })
    out["alle_spiele"].append({
        "team": "VfL Bochum", "n": int(len(boc)),
        "von": str(boc.date_utc.dt.date.iloc[0]), "bis": str(boc.date_utc.dt.date.iloc[-1]),
        "saisons": ["2BL 2025/26"],
        "scores": [jnum(x, 1) for x in boc.gesamtscore_spielstil],
    })

    # -------------------------------------------------------- Validierungen
    out["loso"] = [{"set": r.featureset, "n": int(r.n_features),
                    "auc": jnum(r.auc_mittel, 3), "treffer": int(r.top3_treffer_von_27),
                    "zirkulaer": "zirkul" in r.featureset}
                   for r in loso.itertuples(index=False)]
    out["aufstieg"] = [{"kpi": r.kpi, "auf": jnum(r.aufsteiger_mittel, 3),
                        "rest": jnum(r.nicht_aufsteiger_mittel, 3),
                        "delta": jnum(r.cliffs_delta, 3),
                        "lo": jnum(r.delta_ci_lo, 3), "hi": jnum(r.delta_ci_hi, 3)}
                       for r in prom.itertuples(index=False)]

    oc = pd.read_csv(f"{OUT}/outcome_alignment.csv")
    out["kalibrierung"] = {
        "xp_summe": jnum(oc.xpoints.sum(), 0), "punkte_summe": int(oc.punkte.sum()),
        "abweichung_pct": jnum((oc.xpoints.sum() / oc.punkte.sum() - 1) * 100, 2),
        "schuesse_exakt_pct": jnum(
            ((pd.read_csv(f"{DATA}/kpi_raw.csv")["sum_shots_player"]
              - pd.read_csv(f"{DATA}/kpi_raw.csv")["wy_totals_general_shots"]).abs()
             < 0.5).mean() * 100, 2),
        "aufsteiger_korrekt": "9 von 9 Saisons",
        "redundanz_verletzungen": 0,
    }

    # ------------------------------------------------- Bochum: Saisonverlauf B
    boc = boc.copy()
    boc["kum_punkte"] = boc.punkte.cumsum()
    boc["kum_xpoints"] = boc.xpoints.cumsum()
    out["bochum_punkte"] = [{
        "gw": int(g), "gegner": geg, "erg": f"{int(t)}:{int(gt)}",
        "p": int(kp), "xp": jnum(kx, 1), "delta": jnum(dl, 2), "klasse": kl}
        for g, geg, t, gt, kp, kx, dl, kl in zip(
            boc.gameweek, boc.gegner, boc.tore, boc.gegentore,
            boc.kum_punkte, boc.kum_xpoints, boc.delta_punkte, boc.klassifikation)]

    with open(f"{OUT}/dashboard_data.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"dashboard_data.json geschrieben — {len(json.dumps(out))/1024:.0f} KB")
    print(f"  Verlaufsreihen: {[(r['team'], r['liga_saison'], r['n']) for r in out['verlauf']]}")


if __name__ == "__main__":
    main()
