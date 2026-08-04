"""Schritt 4: Referenzkohorte, Korridoranker und Konstruktvalidierung.

Ausgabe:
  ergebnisse/corridors.json                Anker L0/L1/U1/U0 je KPI
  ergebnisse/reference_cohort_profile.csv  Trennschaerfe je KPI und Referenzteam
  daten/kpi_z.csv                          kpi_raw + z je Liga-Saison + orientierter Wert
"""
import json
import numpy as np
import pandas as pd
from scipy import stats
from config import DATA, OUT, REFERENCE, REFERENCE_LABEL, VFL_SEASON
from kpis import REGISTRY, NORMATIVE_CORRIDOR, PHASE_LABEL

RNG = np.random.default_rng(20260801)
N_BOOT = 2000
KONSISTENZ_SCHWELLE = 0.15


def wquantile(values, weights, q):
    v = np.asarray(values, float)
    w = np.asarray(weights, float)
    ok = ~np.isnan(v)
    v, w = v[ok], w[ok]
    if len(v) == 0:
        return np.nan
    i = np.argsort(v)
    v, w = v[i], w[i]
    cw = (np.cumsum(w) - 0.5 * w) / np.sum(w)
    return float(np.interp(q, cw, v))


def cliffs_delta(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 3 or len(b) < 3:
        return np.nan
    u = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(2.0 * u / (len(a) * len(b)) - 1.0)


def hedges_g(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    n1, n2 = len(a), len(b)
    if n1 < 3 or n2 < 3:
        return np.nan
    sp = np.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    if sp == 0:
        return np.nan
    return float((a.mean() - b.mean()) / sp * (1 - 3 / (4 * (n1 + n2) - 9)))


def boot_ci(a, b, fn, n=N_BOOT):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return (np.nan, np.nan)
    vals = [fn(RNG.choice(a, len(a), True), RNG.choice(b, len(b), True)) for _ in range(n)]
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def tag_reference(d):
    d = d.copy()
    d["ref_key"] = None
    d["ref_weight"] = 0.0
    for key, coach, team, seasons, weight in REFERENCE:
        m = ((d["coach_id"] == coach) & (d["team_id"] == team)
             & (d["season_id"].isin(seasons)))
        d.loc[m, "ref_key"] = key
        d.loc[m, "ref_weight"] = weight
    d["is_ref"] = d["ref_key"].notna()
    return d


def add_z(d, kohorte_mitte=None):
    """z je Liga-Saison, orientierter Wert v und Guete g.

    g vereinheitlicht beide KPI-Formen zu einer monoton in Identitaetskonformitaet
    steigenden Groesse:
      einseitig  g = v
      Korridor   g = -|v - m|   mit m = Median der Referenzkohorte
    Damit laesst sich auf beide dieselbe Drei-Punkt-Ankerung anwenden.
    """
    for k in REGISTRY:
        orient, shape = REGISTRY[k][0], REGISTRY[k][1]
        z = d.groupby("liga_saison")[k].transform(
            lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) > 0 else np.nan)
        d[f"z_{k}"] = z
        d[f"v_{k}"] = orient * z
        if shape == "band":
            m = 0.0 if kohorte_mitte is None else kohorte_mitte.get(k, 0.0)
            d[f"g_{k}"] = -(d[f"v_{k}"] - m).abs()
        else:
            d[f"g_{k}"] = d[f"v_{k}"]
    return d


def dreipunkt_anker(g_liga, g_kohorte, gewichte=None, normativ=False):
    """Drei Anker auf der Guete-Verteilung.

        Score   0 = Liga-P5
        Score  50 = Liga-Median
        Score 100 = P90 der Referenzkohorte (bei normativen KPIs: Liga-P90)

    Damit bedeutet 50 auf jedem KPI exakt Ligaschnitt. Die frueher extrem
    ungleiche Saettigung (Median 100 bei OT1, Median 46 bei D2) verschwindet
    per Konstruktion.
    """
    a0 = float(np.nanpercentile(g_liga, 5))
    a50 = float(np.nanmedian(g_liga))
    if normativ or g_kohorte is None or np.isfinite(g_kohorte).sum() < 20:
        a100 = float(np.nanpercentile(g_liga, 90))
    else:
        a100 = wquantile(g_kohorte, gewichte, 0.90)
    # Monotonie erzwingen, falls die Kohorte unter dem Ligamedian liegt
    if not np.isfinite(a100) or a100 <= a50:
        a100 = max(a50 + 1e-6, float(np.nanpercentile(g_liga, 90)))
    if a50 <= a0:
        a0 = a50 - 1e-6
    return a0, a50, a100


def score_dreipunkt(g, a0, a50, a100):
    """Stueckweise lineare Abbildung der Guete auf 0..100."""
    g = np.asarray(g, float)
    s = np.full(g.shape, np.nan)
    ok = ~np.isnan(g)
    unten = ok & (g < a50)
    oben = ok & (g >= a50)
    s[unten] = 50.0 * (g[unten] - a0) / (a50 - a0)
    s[oben] = 50.0 + 50.0 * (g[oben] - a50) / (a100 - a50)
    return np.clip(s, 0, 100)


def main():
    d = tag_reference(pd.read_csv(f"{DATA}/kpi_raw.csv", parse_dates=["date_utc"]))
    # Erster Durchlauf ohne Kohortenmitte, um sie zu bestimmen; danach endgueltig.
    d = add_z(d)
    mitte = {k: float(d.loc[d["is_ref"], f"v_{k}"].median())
             for k in REGISTRY if REGISTRY[k][1] == "band"}
    d = add_z(d, kohorte_mitte=mitte)
    d.to_csv(f"{DATA}/kpi_z.csv", index=False)

    ref = d[d["is_ref"]]
    print(f"Referenzkohorte: {len(ref)} Team-Match-Zeilen")
    print(ref.groupby("ref_key").agg(spiele=("match_id", "size"),
                                     saisons=("liga_saison", "nunique")).to_string())
    print()

    corridors, profile = {}, []
    for k, (orient, shape, _, phase, weight) in REGISTRY.items():
        vcol, gcol = f"v_{k}", f"g_{k}"
        rv, rw = ref[vcol].to_numpy(float), ref["ref_weight"].to_numpy(float)
        valid_ls = d.loc[d[vcol].notna(), "liga_saison"].unique()
        league = d.loc[d["liga_saison"].isin(valid_ls), vcol].to_numpy(float)
        g_liga = d.loc[d["liga_saison"].isin(valid_ls), gcol].to_numpy(float)
        g_koh = ref[gcol].to_numpy(float)

        normativ = k in NORMATIVE_CORRIDOR
        a0, a50, a100 = dreipunkt_anker(g_liga, g_koh, rw, normativ)
        quelle = ("NORMATIV: 100 = Liga-P90, 50 = Liga-Median, 0 = Liga-P5. "
                  "Die Referenzkohorte traegt diesen KPI nicht."
                  if normativ else
                  "Drei-Punkt-Ankerung: 100 = P90 der Referenzkohorte, "
                  "50 = Liga-Median, 0 = Liga-P5")

        base = d.loc[d["season_id"] == VFL_SEASON, k]
        mu, sd = float(base.mean()), float(base.std(ddof=0))
        mitte_v = mitte.get(k, 0.0) if shape == "band" else None

        def v_to_raw(v):
            return None if v is None or not np.isfinite(v) else round(mu + orient * v * sd, 5)

        # Guete zurueck in Rohwerte: bei 'up' direkt, bei 'band' zwei Raender
        def g_to_raw(gv):
            if not np.isfinite(gv):
                return None
            if shape == "band":
                return [v_to_raw(mitte_v + gv), v_to_raw(mitte_v - gv)]   # gv <= 0
            return v_to_raw(gv)

        corridors[k] = {
            "phase": phase, "phase_label": PHASE_LABEL[phase],
            "gewicht_in_phase": weight, "orientierung": orient, "form": shape,
            "quelle_korridor": quelle,
            "anker_guete": {"a0": round(a0, 4), "a50": round(a50, 4),
                            "a100": round(a100, 4)},
            "einheiten_2bl_2526": {
                "score0": g_to_raw(a0), "score50": g_to_raw(a50), "score100": g_to_raw(a100),
                "liga_mittel": round(mu, 5), "liga_sd": round(sd, 5),
                "kohorte_mitte": v_to_raw(mitte_v) if mitte_v is not None else None},
            "kohorte_n": int(np.isfinite(rv).sum()),
        }

        # ------------------------------------------------ Konstruktvalidierung
        rest = d[(~d["is_ref"]) & d["liga_saison"].isin(valid_ls)][vcol]
        row = {"kpi": k, "phase": PHASE_LABEL[phase], "form": shape,
               "n_kohorte": int(ref[vcol].notna().sum()),
               "n_ligarest": int(rest.notna().sum()),
               "median_kohorte_z": round(float(np.nanmedian(rv)), 4),
               "delta_gesamt": round(cliffs_delta(rv, rest), 4),
               "g_gesamt": round(hedges_g(rv, rest), 4)}
        lo, hi = boot_ci(rv, rest, cliffs_delta)
        row["delta_ci_lo"], row["delta_ci_hi"] = round(lo, 4), round(hi, 4)

        pos = tot = 0
        for key, coach, team, seasons, _ in REFERENCE:
            sub = d[(d["coach_id"] == coach) & (d["team_id"] == team)
                    & (d["season_id"].isin(seasons)) & d[vcol].notna()]
            if len(sub) < 15:
                row[f"delta_{key}"] = np.nan
                continue
            own = d[(~d["is_ref"]) & d["liga_saison"].isin(sub["liga_saison"].unique())][vcol]
            dd = cliffs_delta(sub[vcol], own)
            row[f"delta_{key}"] = round(dd, 4)
            tot += 1
            pos += dd > KONSISTENZ_SCHWELLE
        row["konsistenz"] = f"{pos}/{tot}"

        # Sensitivitaet: Kohorte ohne RB Leipzig (abweichender Archetyp)
        no_lp = ref[ref["ref_key"] != "leipzig_werner"]
        row["delta_ohne_leipzig"] = round(cliffs_delta(no_lp[vcol], rest), 4)

        if k in NORMATIVE_CORRIDOR:
            row["urteil"] = "normativ gesetzt (keine Vorbild-Evidenz)"
        elif pos >= 3:
            row["urteil"] = "stark (>=3/4 Referenzen)"
        elif pos == 2:
            row["urteil"] = "gemischt (2/4 Referenzen)"
        else:
            row["urteil"] = "schwach - Datengrenze, siehe Limitation"
        profile.append(row)

    corridors["_meta"] = {
        "konsistenz_schwelle_cliffs_delta": KONSISTENZ_SCHWELLE,
        "kohorte": {REFERENCE_LABEL[k]: {"gewicht": w, "saisons": list(s)}
                    for k, c, t, s, w in REFERENCE},
        "hinweis": ("Korridore leben im z-Raum je Liga-Saison. Die Werte unter "
                    "'einheiten_2bl_2526' sind fuer die Darstellung in die Skala der "
                    "2. Bundesliga 2025/26 zurueckgerechnet."),
    }
    with open(f"{OUT}/corridors.json", "w") as f:
        json.dump(corridors, f, indent=2, ensure_ascii=False)

    prof = pd.DataFrame(profile)
    prof.to_csv(f"{OUT}/reference_cohort_profile.csv", index=False)
    print("KONSTRUKTVALIDIERUNG (Cliff's delta Kohorte vs. Ligarest, orientiert)")
    print(prof[["kpi", "n_kohorte", "delta_gesamt", "delta_ci_lo", "delta_ci_hi",
                "delta_leipzig_werner", "delta_sturm_ilzer", "delta_hoffenheim_ilzer",
                "delta_schalke_muslic", "delta_ohne_leipzig", "konsistenz", "urteil"]]
          .to_string(index=False))
    return prof


if __name__ == "__main__":
    main()
