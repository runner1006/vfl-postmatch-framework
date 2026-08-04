"""Schritt 5: Outcome Alignment.

Shot-Level-xG existiert nicht. Die Schussliste wird aus der Spielerebene
rekonstruiert: je Spieler n Schuesse mit je xG = Spieler-xG / n. Daraus exakte
Poisson-Binomial-Faltung (keine Simulation noetig, n ~ 5-25 Schuesse).

Bekannte Verzerrung: die Varianz der Schussqualitaet INNERHALB eines Spielers
geht verloren. Die Verteilung wird dadurch minimal zu eng.
"""
import numpy as np
import pandas as pd
from config import DATA, OUT

P = "wy_per_90_"
PENALTY_XG = 0.76


def shot_vectors(pl):
    """(match_id, team_id) -> Liste der Einzelschuss-Wahrscheinlichkeiten."""
    pl = pl.copy()
    f = pd.to_numeric(pl["wy_totals_minutes_on_field"], errors="coerce").fillna(0) / 90
    pl["n"] = (pd.to_numeric(pl[P + "shots"], errors="coerce") * f).round()
    pl["x"] = pd.to_numeric(pl[P + "xg_shot"], errors="coerce") * f
    pl["pen"] = (pd.to_numeric(pl[P + "penalties"], errors="coerce") * f).round()
    pl = pl[(pl["n"] > 0) & pl["x"].notna()]

    out = {}
    for (mid, tid), g in pl.groupby(["match_id", "team_id"]):
        vec = []
        for n, x, pen in zip(g["n"], g["x"], g["pen"].fillna(0)):
            n, pen = int(n), int(min(pen, n))
            x_open = max(x - pen * PENALTY_XG, 0.0)
            n_open = n - pen
            if n_open > 0:
                vec.extend([x_open / n_open] * n_open)
            vec.extend([PENALTY_XG] * pen)
        out[(mid, tid)] = np.clip(np.array(vec, float), 0.0, 0.99)
    return out


def poisson_binomial(p, kmax):
    """Exakte Verteilung der Trefferzahl per Faltung."""
    dist = np.zeros(kmax + 1)
    dist[0] = 1.0
    for pi in p:
        nd = dist * (1 - pi)
        nd[1:] += dist[:-1] * pi
        dist = nd
    return dist


def match_outcome(pa, pb, kmax=None):
    # kmax = Anzahl Schuesse des schussstaerkeren Teams -> keine Trunkierung.
    # Bei festem kmax=12 verlor ein Spiel mit 33 Schuessen 0,34 % Masse.
    if kmax is None:
        kmax = max(len(pa), len(pb), 12)
    da, db = poisson_binomial(pa, kmax), poisson_binomial(pb, kmax)
    joint = np.outer(da, db)
    idx = np.arange(kmax + 1)
    win = joint[idx[:, None] > idx[None, :]].sum()
    draw = np.trace(joint)
    loss = joint[idx[:, None] < idx[None, :]].sum()
    return da, db, float(win), float(draw), float(loss), joint


def klassifikation(delta):
    if delta > 0.90:
        return "Ergebnis deutlich besser als die Leistung"
    if delta > 0.30:
        return "Ergebnis leicht besser als die Leistung"
    if delta >= -0.30:
        return "Ergebnis entspricht klar der Leistung"
    if delta >= -0.90:
        return "Ergebnis leicht schlechter als die Leistung"
    return "Ergebnis deutlich schlechter als die Leistung"


def main():
    pl = pd.read_csv(f"{DATA}/player_stats.csv")
    d = pd.read_csv(f"{DATA}/kpi_raw.csv", parse_dates=["date_utc"])
    vecs = shot_vectors(pl)

    rows = []
    for r in d.itertuples(index=False):
        pa = vecs.get((r.match_id, r.team_id), np.array([]))
        pb = vecs.get((r.match_id, r.opponent_id), np.array([]))
        da, db, win, draw, loss, joint = match_outcome(pa, pb)
        xp = 3 * win + draw
        tore, geg = int(r.tore), int(r.gegentore)
        delta = r.punkte - xp

        # Perzentil des tatsaechlichen Ergebnisses in der Verteilung der Tordifferenz
        kmax = len(da) - 1
        diff = np.arange(kmax + 1)[:, None] - np.arange(kmax + 1)[None, :]
        obs = tore - geg
        p_below = joint[diff < obs].sum()
        p_equal = joint[diff == obs].sum()

        top = np.dstack(np.unravel_index(np.argsort(joint.ravel())[::-1][:5], joint.shape))[0]
        rows.append({
            "match_id": r.match_id, "team_id": r.team_id, "opponent_id": r.opponent_id,
            "liga_saison": r.liga_saison, "date_utc": r.date_utc, "is_home": r.is_home,
            "tore": tore, "gegentore": geg, "punkte": r.punkte,
            "n_schuesse": len(pa), "n_schuesse_gegner": len(pb),
            "npxg": round(float(pa.sum()), 4), "npxg_gegner": round(float(pb.sum()), 4),
            "schussvektor": ";".join(f"{v:.3f}" for v in np.sort(pa)[::-1]),
            "p_0_tore": round(float(da[0]), 4), "p_1_tor": round(float(da[1]), 4),
            "p_2_tore": round(float(da[2]), 4), "p_3plus_tore": round(float(da[3:].sum()), 4),
            "p_sieg": round(win, 4), "p_remis": round(draw, 4), "p_niederlage": round(loss, 4),
            "xpoints": round(xp, 4),
            "delta_punkte": round(delta, 4),
            "erwartete_tordifferenz": round(float(pa.sum() - pb.sum()), 4),
            "tatsaechliche_tordifferenz": obs,
            "ergebnis_perzentil": round(float(p_below + 0.5 * p_equal), 4),
            "top_ergebnisse": " | ".join(
                f"{a}:{b} {joint[a, b]*100:.1f}%" for a, b in top),
            "klassifikation": klassifikation(delta),
        })

    out = pd.DataFrame(rows)
    out.to_csv(f"{OUT}/outcome_alignment.csv", index=False)

    print(f"outcome_alignment.csv: {len(out)} Zeilen")
    print("\nKALIBRIERUNGSPRUEFUNG (ueber alle 8.620 Team-Match-Zeilen)")
    print(f"  Summe xPoints:            {out['xpoints'].sum():10.1f}")
    print(f"  Summe tatsaechl. Punkte:  {out['punkte'].sum():10.1f}")
    print(f"  Abweichung:               {out['xpoints'].sum() - out['punkte'].sum():+10.1f} "
          f"({(out['xpoints'].sum()/out['punkte'].sum()-1)*100:+.2f} %)")
    print(f"  Korrelation xP ~ Punkte:  {out['xpoints'].corr(out['punkte']):.3f}")
    print(f"  Mittleres npxG je Team:   {out['npxg'].mean():.3f}")
    print("\n  Verteilung der Klassifikationen:")
    print(out["klassifikation"].value_counts().to_string())
    return out


if __name__ == "__main__":
    main()
