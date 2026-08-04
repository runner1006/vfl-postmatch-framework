"""Schritt 6: Historische Aufstiegsanalyse der 2. Bundesliga (9 Saisons).

 - Abschlusstabellen aus Match-Ergebnissen rechnen (keine Relegationsrunde in der DB)
 - Aufsteiger-Labels: Platz 1-2 direkt, Platz 3 Relegation
 - Effektgroessen je Kandidaten-KPI mit Bootstrap-CI
 - Saisonstabilitaet, Zusammenhang mit PPG / xPoints / Tabellenplatz
 - Leave-One-Season-Out gegen die Baselines Tordifferenz und npxG-Differenz
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from config import DATA, OUT
from korridore import cliffs_delta, hedges_g, boot_ci


# ------------------------------------------------------------------------
# Minimale L2-regularisierte logistische Regression (scipy statt sklearn,
# um keine zusaetzliche Abhaengigkeit einzufuehren).
# ------------------------------------------------------------------------
def fit_logit(X, y, lam=1.0):
    X1 = np.column_stack([np.ones(len(X)), X])

    def nll(w):
        z = np.clip(X1 @ w, -35, 35)
        ll = np.sum(y * z - np.logaddexp(0, z))
        return -ll + lam * np.sum(w[1:] ** 2)

    w0 = np.zeros(X1.shape[1])
    return minimize(nll, w0, method="L-BFGS-B").x


def predict_logit(w, X):
    z = np.clip(np.column_stack([np.ones(len(X)), X]) @ w, -35, 35)
    return 1 / (1 + np.exp(-z))


def roc_auc(y, p):
    y = np.asarray(y)
    r = stats.rankdata(p)
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def brier(y, p):
    return float(np.mean((np.asarray(y) - np.asarray(p)) ** 2))

# Kandidaten VOR der Auswertung fixiert (kein nachtraegliches Erweitern).
KANDIDATEN = {
    "npxg":              ("CC1_npxg", +1, "Chance Creation offensiv"),
    "npxg_gegen":        ("CC1d_npxg_gegen", -1, "Chance Creation defensiv"),
    "npxg_differenz":    ("npxg_diff", +1, "Chance Creation kombiniert"),
    "box_zugriffsrate":  ("CC2_box_zugriffsrate", +1, "Prozesskette offensiv"),
    "box_zugriff_gegen": ("CC2d_box_zugriffsrate_gegen", -1, "Prozesskette defensiv"),
    "abschlussqualitaet": ("CC3_abschlussqualitaet", +1, "Abschlussqualitaet offensiv"),
    "abschlussqual_gegen": ("CC3d_abschlussqualitaet_gegen", -1, "Abschlussqualitaet defensiv"),
    "schuesse":          ("wy_totals_general_shots", +1, "Volumen offensiv"),
    "schuesse_gegen":    ("schuesse_gegen", -1, "Volumen defensiv"),
    "xpoints":           ("xpoints", +1, "Gesamtleistung"),
}


def tabellen(d):
    """Abschlusstabelle je 2.-BL-Saison aus Match-Ergebnissen."""
    z = d[d["liga"] == "2BL"]
    t = z.groupby(["saison", "team_id"]).agg(
        spiele=("match_id", "size"), punkte=("punkte", "sum"),
        tore=("tore", "sum"), gegentore=("gegentore", "sum")).reset_index()
    t["tordifferenz"] = t["tore"] - t["gegentore"]
    t["ppg"] = t["punkte"] / t["spiele"]
    t = t.sort_values(["saison", "punkte", "tordifferenz", "tore"],
                      ascending=[True, False, False, False])
    t["platz"] = t.groupby("saison").cumcount() + 1
    t["aufsteiger"] = (t["platz"] <= 2).astype(int)
    t["relegation"] = (t["platz"] == 3).astype(int)
    t["top3"] = (t["platz"] <= 3).astype(int)
    t["top6"] = (t["platz"] <= 6).astype(int)
    return t


def main():
    d = pd.read_csv(f"{DATA}/kpi_z.csv", parse_dates=["date_utc"])
    oc = pd.read_csv(f"{OUT}/outcome_alignment.csv")[
        ["match_id", "team_id", "xpoints", "npxg", "npxg_gegner"]]
    d = d.merge(oc, on=["match_id", "team_id"], how="left")
    d["npxg_diff"] = d["CC1_npxg"] - d["CC1d_npxg_gegen"]

    tab = tabellen(d)
    nm = pd.read_csv(f"{DATA}/team_names.csv").set_index("team_id")["name"].to_dict()
    tab["team"] = tab["team_id"].map(nm)
    tab.to_csv(f"{OUT}/abschlusstabellen_2bl.csv", index=False)
    print("ABSCHLUSSTABELLEN — Top 3 je Saison (aus Match-Ergebnissen gerechnet)")
    for s, g in tab.groupby("saison"):
        top = g.nsmallest(3, "platz")
        print(f"  {s}: " + " | ".join(
            f"{int(r.platz)}. {r.team} ({int(r.punkte)} Pkt, {int(r.tordifferenz):+d})"
            for r in top.itertuples()))

    # Saisonmittel je Team fuer alle Kandidaten
    cols = [c for c, _, _ in KANDIDATEN.values()]
    ts = (d[d["liga"] == "2BL"].groupby(["saison", "team_id"])[cols]
          .mean().reset_index())
    ts = ts.merge(tab, on=["saison", "team_id"])
    ts.to_csv(f"{OUT}/team_season_stats.csv", index=False)

    # z je Saison, damit Ligadrift die Vergleiche nicht verzerrt
    for c in cols:
        ts[f"z_{c}"] = ts.groupby("saison")[c].transform(
            lambda s: (s - s.mean()) / s.std(ddof=0))

    rows = []
    for name, (col, orient, familie) in KANDIDATEN.items():
        v = orient * ts[f"z_{col}"]
        up = v[ts["aufsteiger"] == 1]
        rest = v[ts["aufsteiger"] == 0]
        t3 = v[ts["top3"] == 1]
        dl = cliffs_delta(up, rest)
        lo, hi = boot_ci(up, rest, cliffs_delta)
        glo, ghi = boot_ci(up, rest, hedges_g)

        # Saisonstabilitaet: Anteil Saisons, in denen die Top-3 ueber dem Rest liegen.
        # Auf Top-3 statt Aufsteiger, weil zwei Aufsteiger je Saison fuer eine
        # verteilungsfreie Effektgroesse zu wenig sind.
        signs = []
        for s, g in ts.groupby("saison"):
            vv = orient * g[f"z_{col}"]
            a, b = vv[g["top3"] == 1], vv[g["top3"] == 0]
            if len(a) >= 3 and len(b) >= 3:
                signs.append(cliffs_delta(a, b))
        stab = float(np.mean([x > 0 for x in signs])) if signs else np.nan

        rows.append({
            "kpi": name, "spalte": col, "familie": familie, "orientierung": orient,
            "aufsteiger_mittel": round(float(ts.loc[ts.aufsteiger == 1, col].mean()), 4),
            "nicht_aufsteiger_mittel": round(float(ts.loc[ts.aufsteiger == 0, col].mean()), 4),
            "aufsteiger_median": round(float(ts.loc[ts.aufsteiger == 1, col].median()), 4),
            "nicht_aufsteiger_median": round(float(ts.loc[ts.aufsteiger == 0, col].median()), 4),
            "aufsteiger_sd": round(float(ts.loc[ts.aufsteiger == 1, col].std()), 4),
            "nicht_aufsteiger_sd": round(float(ts.loc[ts.aufsteiger == 0, col].std()), 4),
            "cliffs_delta": round(dl, 3), "delta_ci_lo": round(lo, 3),
            "delta_ci_hi": round(hi, 3),
            "hedges_g": round(hedges_g(up, rest), 3),
            "g_ci_lo": round(glo, 3), "g_ci_hi": round(ghi, 3),
            "delta_top3": round(cliffs_delta(t3, v[ts["top3"] == 0]), 3),
            "rho_ppg": round(float(stats.spearmanr(v, ts["ppg"]).statistic), 3),
            "rho_xpoints": round(float(stats.spearmanr(v, ts["xpoints"]).statistic), 3),
            "rho_platz": round(float(stats.spearmanr(v, ts["platz"]).statistic), 3),
            "saisonstabilitaet": round(stab, 3),
        })
    res = pd.DataFrame(rows).sort_values("cliffs_delta", ascending=False)

    # ------------------------------------------------- Leave-One-Season-Out
    ts["z_tordifferenz"] = ts.groupby("saison")["tordifferenz"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0))
    ts["box_diff"] = ts["CC2_box_zugriffsrate"] - ts["CC2d_box_zugriffsrate_gegen"]
    ts["z_box_diff"] = ts.groupby("saison")["box_diff"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0))

    featuresets = {
        "CC-Set (6 KPIs)": ["z_CC1_npxg", "z_CC1d_npxg_gegen", "z_CC2_box_zugriffsrate",
                            "z_CC2d_box_zugriffsrate_gegen", "z_CC3_abschlussqualitaet",
                            "z_CC3d_abschlussqualitaet_gegen"],
        "CC-Kern (npxG off+def)": ["z_CC1_npxg", "z_CC1d_npxg_gegen"],
        "npxG-Diff + Box-Diff": ["z_npxg_diff", "z_box_diff"],
        "npxG-Diff + Abschlussqual.": ["z_npxg_diff", "z_CC3_abschlussqualitaet"],
        "Baseline npxG-Differenz": ["z_npxg_diff"],
        "Baseline Tordifferenz (quasi-zirkulaer)": ["z_tordifferenz"],
    }

    loso = []
    for label, feats in featuresets.items():
        aucs, briers, hits = [], [], []
        for s in sorted(ts["saison"].unique()):
            tr, te = ts[ts.saison != s], ts[ts.saison == s]
            X, y = tr[feats].to_numpy(), tr["top3"].to_numpy()
            w = fit_logit(X, y, lam=1.0)
            p = predict_logit(w, te[feats].to_numpy())
            aucs.append(roc_auc(te["top3"].to_numpy(), p))
            briers.append(brier(te["top3"].to_numpy(), p))
            pred_top3 = set(te.iloc[np.argsort(p)[::-1][:3]]["team_id"])
            hits.append(len(pred_top3 & set(te[te.top3 == 1]["team_id"])))
        loso.append({"featureset": label, "n_features": len(feats),
                     "auc_mittel": round(float(np.mean(aucs)), 3),
                     "auc_min": round(float(np.min(aucs)), 3),
                     "brier_mittel": round(float(np.mean(briers)), 4),
                     "top3_treffer_von_27": int(np.sum(hits)),
                     "top3_trefferquote": round(float(np.sum(hits) / (3 * len(aucs))), 3)})
    loso = pd.DataFrame(loso)

    res.to_csv(f"{OUT}/promotion_analysis.csv", index=False)
    loso.to_csv(f"{OUT}/loso_validation.csv", index=False)

    print("\n\nEFFEKTGROESSEN — Aufsteiger (n=18) vs. Nicht-Aufsteiger (n=144)")
    print(res[["kpi", "aufsteiger_mittel", "nicht_aufsteiger_mittel", "cliffs_delta",
               "delta_ci_lo", "delta_ci_hi", "hedges_g", "rho_ppg", "rho_platz",
               "saisonstabilitaet"]].to_string(index=False))
    print("\n\nLEAVE-ONE-SEASON-OUT (Vorhersage Top-3, 9 Folds)")
    print(loso.to_string(index=False))
    return res, loso


if __name__ == "__main__":
    main()
