"""Schritt 7: Gegneranpassung.

Je Liga-Saison und je KPI ein additives Zwei-Wege-Modell mit Shrinkage:

    y_ij = mu + alpha_i (Erzeugung Team i) + beta_j (Zulassung Gegner j)
                + gamma * heim + eps

Geschaetzt als Ridge; die Team- und Gegnereffekte werden bestraft, Intercept und
Heimeffekt nicht. Entscheidend: ROLLIEREND — die Effekte fuer ein Spiel am
Spieltag g stammen ausschliesslich aus den Spieltagen < g derselben Saison.
Damit kann kein Wissen aus dem bewerteten Spiel in die Erwartung zurueckfliessen.

Vor Spieltag MIN_GW liegt zu wenig Information vor; dort ist die Erwartung das
bis dahin beobachtete Ligamittel plus Heimeffekt, und die Zeile wird mit
'genug_historie = False' markiert.
"""
import warnings
import numpy as np
import pandas as pd
from config import DATA, OUT
from kpis import REGISTRY, CC

# numpy 2.0 meldet auf macOS/Accelerate spurious FP-Warnungen in matmul.
# Gegengeprueft: np.linalg.solve und ein einsum-Pfad stimmen auf 4e-16 ueberein,
# keine NaN/inf in den Koeffizienten. Die Warnungen sind daher unterdrueckt.
warnings.filterwarnings("ignore", message=".*encountered in matmul.*",
                        category=RuntimeWarning)

MIN_GW = 6
LAMBDAS = (2.0, 5.0, 10.0, 20.0, 50.0)
TARGETS = list(REGISTRY) + CC


def ridge_fit(y, teams, opps, home, n_team, lam):
    n = len(y)
    X = np.zeros((n, 2 + 2 * n_team))
    X[:, 0] = 1.0
    X[:, 1] = home
    X[np.arange(n), 2 + teams] = 1.0
    X[np.arange(n), 2 + n_team + opps] = 1.0
    pen = np.full(2 + 2 * n_team, lam)
    pen[:2] = 0.0
    A = X.T @ X + np.diag(pen)
    return np.linalg.solve(A, X.T @ y)


def ridge_predict(w, teams, opps, home, n_team):
    return (w[0] + w[1] * home + w[2 + teams]
            + w[2 + n_team + opps])


def rolling_for_season(g, target, lam):
    """Rollierende Erwartungswerte fuer eine Liga-Saison und einen KPI."""
    g = g.sort_values(["gameweek", "match_id"]).copy()
    teams = sorted(set(g["team_id"]) | set(g["opponent_id"].dropna().astype(int)))
    tix = {t: i for i, t in enumerate(teams)}
    nt = len(teams)

    g["_t"] = g["team_id"].map(tix)
    g["_o"] = g["opponent_id"].astype(int).map(tix)
    g["_h"] = g["is_home"].astype(float)
    ok = g[target].notna()

    exp = np.full(len(g), np.nan)
    enough = np.zeros(len(g), bool)
    gws = sorted(g["gameweek"].dropna().unique())

    for gw in gws:
        cur = (g["gameweek"] == gw).to_numpy()
        prev = ((g["gameweek"] < gw) & ok).to_numpy()
        if prev.sum() < max(20, 2 * nt):
            base = g.loc[prev, target].mean() if prev.sum() else g.loc[ok, target].mean()
            exp[cur] = base
            continue
        sub = g[prev]
        w = ridge_fit(sub[target].to_numpy(float), sub["_t"].to_numpy(int),
                      sub["_o"].to_numpy(int), sub["_h"].to_numpy(float), nt, lam)
        c = g[cur]
        exp[cur] = ridge_predict(w, c["_t"].to_numpy(int), c["_o"].to_numpy(int),
                                 c["_h"].to_numpy(float), nt)
        enough[cur] = gw >= MIN_GW

    out = pd.DataFrame({"match_id": g["match_id"].to_numpy(),
                        "team_id": g["team_id"].to_numpy(),
                        f"exp_{target}": exp,
                        f"hist_{target}": enough})
    return out


def choose_lambda(d, target):
    """Lambda ueber den rollierenden Vorhersagefehler waehlen (kein Leakage).

    Die Probe-Saisons werden je KPI nach Datendichte gewaehlt: bei den physischen
    KPIs existieren nur wenige Saisons ueberhaupt, eine feste Probe wuerde dort
    auf nahezu leeren Daten kalibrieren.
    """
    best, best_rmse = LAMBDAS[0], np.inf
    dens = (d.groupby("liga_saison")[target].apply(lambda s: s.notna().sum())
             .sort_values(ascending=False))
    probe = d[d["liga_saison"].isin(dens.head(3).index)]
    for lam in LAMBDAS:
        errs = []
        for _, g in probe.groupby("liga_saison"):
            r = rolling_for_season(g, target, lam).merge(
                g[["match_id", "team_id", target, "gameweek"]], on=["match_id", "team_id"])
            r = r[(r["gameweek"] >= MIN_GW) & r[target].notna() & r[f"exp_{target}"].notna()]
            errs.append((r[target] - r[f"exp_{target}"]).to_numpy())
        if errs:
            e = np.concatenate(errs)
            rmse = float(np.sqrt(np.mean(e ** 2)))
            if rmse < best_rmse:
                best, best_rmse = lam, rmse
    return best, best_rmse


def main():
    d = pd.read_csv(f"{DATA}/kpi_z.csv", parse_dates=["date_utc"])
    d = d[d["opponent_id"].notna()].copy()
    d["opponent_id"] = d["opponent_id"].astype(int)

    params, pieces = [], []
    for target in TARGETS:
        lam, rmse = choose_lambda(d, target)
        parts = [rolling_for_season(g, target, lam)
                 for _, g in d.groupby("liga_saison")]
        res = pd.concat(parts, ignore_index=True)
        pieces.append(res.set_index(["match_id", "team_id"]))
        sd = d[target].std()
        params.append({"kpi": target, "lambda": lam, "rmse_rollierend": round(rmse, 5),
                       "sd_roh": round(float(sd), 5),
                       "erklaerte_streuung": round(1 - (rmse / sd) ** 2, 3) if sd else np.nan})
        print(f"  {target:28s} lambda={lam:5.1f}  RMSE={rmse:.4f}  "
              f"erklaerte Streuung={1-(rmse/sd)**2:.3f}", flush=True)

    exp = pd.concat(pieces, axis=1).reset_index()
    d = d.merge(exp, on=["match_id", "team_id"], how="left")

    # Gegnerbereinigtes Residuum, in Standardabweichungen der Liga-Saison
    for target in TARGETS:
        resid = d[target] - d[f"exp_{target}"]
        d[f"adj_{target}"] = resid / d.groupby("liga_saison")[target].transform(
            lambda s: s.std(ddof=0))

    pd.DataFrame(params).to_csv(f"{OUT}/opponent_model_params.csv", index=False)
    d.to_csv(f"{DATA}/kpi_adjusted.csv", index=False)
    print(f"\nkpi_adjusted.csv: {len(d)} Zeilen")
    share = d[[f"hist_{t}" for t in TARGETS[:1]]].iloc[:, 0].mean()
    print(f"Anteil Zeilen mit ausreichender Historie (ab Spieltag {MIN_GW}): {share*100:.1f} %")
    return d


if __name__ == "__main__":
    main()
