"""Abschliessende Verifikation. Prueft die im Plan festgelegten Kriterien."""
import json
import numpy as np
import pandas as pd
from config import DATA, OUT, VFL_TEAM, VFL_SEASON
from kpis import REGISTRY, CC, SECONDARY
import gegnermodell as gm

ok_all = True


def check(name, ok, detail=""):
    global ok_all
    ok_all &= bool(ok)
    print(f"  [{'OK ' if ok else 'FEHL'}] {name}{('  — ' + detail) if detail else ''}")


print("1. EXTRAKTIONSINTEGRITAET")
m = pd.read_csv(f"{DATA}/matches.csv")
t = pd.read_csv(f"{DATA}/team_stats.csv")
k = pd.read_csv(f"{DATA}/kpi_raw.csv")
check("Genau 2 Team-Zeilen je Spiel",
      (t.groupby("match_id").size() == 2).all(),
      f"{t.match_id.nunique()} Spiele, {len(t)} Zeilen")
check("Alle Spiele mit Daten auch in team_stats",
      set(m.loc[m.meta_match_data_downloaded, "match_id"]) == set(t.match_id))
nulls = k[list(REGISTRY)[:12]].isna().mean().max()
check("Nicht-physische KPIs < 1 % NULL", nulls < 0.01, f"max {nulls*100:.2f} %")

print("\n2. AGGREGATIONSKONTROLLE (Spielersumme vs. Teamwert)")
dsh = (k["sum_shots_player"] - k["wy_totals_general_shots"]).abs()
dxg = (k["sum_xg_player"] - k["wy_totals_general_xg"]).abs()
check("Schussanzahl exakt in > 99 %", (dsh < 0.5).mean() > 0.99,
      f"{(dsh < 0.5).mean()*100:.2f} %")
check("xG-Abweichung Median < 0.01", dxg.median() < 0.01, f"Median {dxg.median():.4f}")

print("\n3. LABEL-PLAUSIBILISIERUNG")
tab = pd.read_csv(f"{OUT}/abschlusstabellen_2bl.csv")
real = {"2017/18": ["Fortuna Düsseldorf", "Nürnberg"], "2018/19": ["Köln", "Paderborn"],
        "2019/20": ["Arminia Bielefeld", "Stuttgart"], "2020/21": ["Bochum", "Greuther Fürth"],
        "2021/22": ["Schalke 04", "Werder Bremen"], "2022/23": ["Heidenheim", "Darmstadt 98"],
        "2023/24": ["St. Pauli", "Holstein Kiel"], "2024/25": ["Köln", "Hamburger SV"]}
bad = []
for s, teams in real.items():
    got = sorted(tab[(tab.saison == s) & (tab.aufsteiger == 1)]["team"].tolist())
    if got != sorted(teams):
        bad.append(f"{s}: {got} statt {sorted(teams)}")
check("Aufsteiger 2017/18–2024/25 stimmen mit der Realitaet", not bad, "; ".join(bad))
check("18 Team-Saisons als Aufsteiger markiert", tab.aufsteiger.sum() == 18,
      f"{tab.aufsteiger.sum()}")

print("\n4. KEIN LEAKAGE IM GEGNERMODELL")
# Erwartungswert fuer Spieltag g darf sich nicht aendern, wenn alle Spieltage > g
# geloescht werden.
d = pd.read_csv(f"{DATA}/kpi_adjusted.csv", parse_dates=["date_utc"])
g_full = d[d.liga_saison == "2BL 2025/26"].copy()
g_full["opponent_id"] = g_full["opponent_id"].astype(int)
GW, TGT = 20, "D1_pressingdruck"
full = gm.rolling_for_season(g_full, TGT, 5.0)
trunc = gm.rolling_for_season(g_full[g_full.gameweek <= GW].copy(), TGT, 5.0)
mrg = full.merge(trunc, on=["match_id", "team_id"], suffixes=("_f", "_t"))
mrg = mrg.merge(g_full[["match_id", "team_id", "gameweek"]], on=["match_id", "team_id"])
sel = mrg[mrg.gameweek == GW]
diff = (sel[f"exp_{TGT}_f"] - sel[f"exp_{TGT}_t"]).abs().max()
check(f"Erwartung an Spieltag {GW} unabhaengig von spaeteren Spielen",
      diff < 1e-9, f"max Abweichung {diff:.2e}")

print("\n5. LOSO — BAROMETER-BASIS IST DAS BESTE NICHT-ZIRKULAERE FEATURE-SET")
lo = pd.read_csv(f"{OUT}/loso_validation.csv").set_index("featureset")
cc = lo.loc["CC-Set (6 KPIs)", "auc_mittel"]
bl = lo.loc["Baseline npxG-Differenz", "auc_mittel"]
nz = lo.drop(index="Baseline Tordifferenz (quasi-zirkulaer)")
check("npxG-Differenz ist bestes nicht-zirkulaeres Set",
      nz["auc_mittel"].idxmax() == "Baseline npxG-Differenz",
      f"AUC {bl:.3f}; das 6-KPI-CC-Set liegt mit {cc:.3f} darunter — "
      f"deshalb ist das Barometer auf die npxG-Differenz gestellt")

print("\n6. TRENNSCHAERFE TEIL A / TEIL B")
teil_a = set(REGISTRY)
teil_b = set(CC) | {"npxg_diff", "adj_npxg_diff"}
check("Keine Ueberschneidung der KPI-Mengen", not (teil_a & teil_b))
xg_begriffe = ("xg", "npxg", "shot", "schuesse", "tore", "goal")
verdacht = [x for x in teil_a if any(w in x.lower() for w in xg_begriffe)]
check("Kein Teil-A-KPI enthaelt xG/Schuss/Tor-Begriffe", not verdacht, str(verdacht))
# Rev. 3: die Formeln stehen in kpi_varianten.json, also wird die Spezifikation
# selbst geprueft statt des Quelltextes.
from kpis import AKTIVES_SET as _AS
_verboten = ("general_xg", "general_shots", "general_goals", "xg_per_shot")
_treffer = []
for _n, _sp in _AS.items():
    for _feld in ("zaehler", "nenner", "ereignisse"):
        _v = _sp.get(_feld)
        if _v and any(w in str(_v.get("spalte", "")) for w in _verboten):
            _treffer.append(f"{_n}.{_feld}")
check("Teil-A-Spezifikation verwendet keine xG-/Schuss-/Tor-Spalten",
      not _treffer, str(_treffer))

print("\n6b. SKALA (Rev. 3: Drei-Punkt-Ankerung)")
sc = pd.read_csv(f"{OUT}/kpi_match_level.csv")
med = {k: sc[f"score_{k}"].median() for k in REGISTRY}
check("Median jedes KPI-Scores in 50 +/- 3",
      all(abs(v - 50) <= 3 for v in med.values()),
      f"Spanne {min(med.values()):.1f}-{max(med.values()):.1f}")
saett = {k: max((sc[f"score_{k}"] <= 0.5).mean(), (sc[f"score_{k}"] >= 99.5).mean())
         for k in REGISTRY}
check("Saettigung je Rand unter 15 %", max(saett.values()) < 0.15,
      f"max {max(saett.values())*100:.1f} % ({max(saett, key=saett.get)})")
g = sc["gesamtscore_spielstil"]
check("Gesamtscore-Median in 50 +/- 3", abs(g.median() - 50) <= 3, f"{g.median():.1f}")
check("Gesamtscore-P90 ueber 75", g.quantile(0.90) > 75, f"P90 = {g.quantile(0.90):.0f}")

print("\n6c. TRENNUNG BLEIBT ERHALTEN")
kz = pd.read_csv(f"{DATA}/kpi_z.csv", usecols=["match_id", "team_id", "is_ref"])
sc2 = sc.merge(kz, on=["match_id", "team_id"], how="left")
a = sc2.loc[sc2.is_ref == True, "gesamtscore_spielstil"].dropna()      # noqa: E712
b = sc2.loc[sc2.is_ref != True, "gesamtscore_spielstil"].dropna()      # noqa: E712
from korridore import cliffs_delta
dl = cliffs_delta(a, b)
check("Kohorte weiterhin klar ueber dem Ligarest", dl > 0.20,
      f"Cliff's delta {dl:+.3f} · Kohorte {a.mean():.1f} vs Liga {b.mean():.1f} "
      f"(Abstand {a.mean()-b.mean():.1f} Punkte, Rev. 2: 7,9)")

print("\n6d. AKTIVES KPI-SET")
from kpis import VARIANTEN, AKTIVES_SET
prof2 = pd.read_csv(f"{OUT}/reference_cohort_profile.csv").set_index("kpi")
kons = sum(int(prof2.loc[k, "konsistenz"].split("/")[0]) for k in REGISTRY)
check(f"Aktives Set '{VARIANTEN['aktiv']}' hat 15 KPIs", len(AKTIVES_SET) == 15)
check("Konsistenzsumme mindestens 29", kons >= 29, f"{kons}/60 (Rev. 2: 28)")
nullkpi = [k for k in REGISTRY if prof2.loc[k, "konsistenz"].startswith("0/")]
check("Hoechstens ein KPI mit 0/4", len(nullkpi) <= 1, str(nullkpi))

print("\n6e. EREIGNIS-CONFIDENCE")
from scipy import stats as _st
kk = "OT1_konterrate"
rho = _st.spearmanr(sc[f"n_{kk}"], sc[f"conf_{kk}"], nan_policy="omit").statistic
check("Confidence folgt der Ereigniszahl monoton", rho > 0.99, f"Spearman {rho:.4f}")
nullkonter = sc[sc[f"n_{kk}"] == 0]
check("Spiele ohne Konter haben Confidence 0",
      bool((nullkonter[f"conf_{kk}"] == 0).all()), f"{len(nullkonter)} Spiele")

print("\n7. REDUNDANZ")
cm = pd.read_csv(f"{OUT}/redundancy_matrix.csv", index_col=0)
kk = list(REGISTRY)
viol = [(a, b) for i, a in enumerate(kk) for b in kk[i+1:] if abs(cm.loc[a, b]) > 0.60]
check("Kein KPI-Paar mit |r| > 0.60", not viol, str(viol))

print("\n8. SCORING-INTEGRITAET")
s = pd.read_csv(f"{OUT}/kpi_match_level.csv")
sc = s[[f"score_{x}" for x in REGISTRY]]
check("Alle Scores in [0, 100]",
      bool(((sc >= 0) | sc.isna()).all().all() and ((sc <= 100) | sc.isna()).all().all()))
check("Gesamtscore nur NaN wenn alle Phasen fehlen",
      bool((s.gesamtscore_spielstil.isna() == (s.phasen_ohne_daten == 5)).all()))
b = s[(s.team_id == VFL_TEAM) & (s.saison == "2025/26") & (s.liga == "2BL")]
check("34 Bochum-Spiele 2025/26 gescort", len(b) == 34, f"{len(b)}")
check("Physik-Zeilen ohne Daten haben NaN statt 0",
      s.loc[s.P1_laufvolumen_hi.isna(), "phase_physisch"].isna().all())

print("\n9. OUTCOME-KALIBRIERUNG")
oc = pd.read_csv(f"{OUT}/outcome_alignment.csv")
dev = oc.xpoints.sum() / oc.punkte.sum() - 1
check("Summe xPoints innerhalb 3 % der tatsaechlichen Punkte", abs(dev) < 0.03,
      f"{dev*100:+.2f} %")
psum = (oc.p_sieg + oc.p_remis + oc.p_niederlage - 1).abs()
check("Wahrscheinlichkeiten summieren auf 1 (Toleranz = Rundung auf 4 Stellen)",
      (psum < 2e-4).all(), f"max Abweichung {psum.max():.1e}")

print("\n10. KORRIDORE")
co = json.load(open(f"{OUT}/corridors.json"))
check("Alle 15 KPIs haben Korridoranker",
      all(x in co for x in REGISTRY), f"{len([x for x in co if x != '_meta'])}")
check("Anker monoton (a0 < a50 < a100) bei jedem KPI",
      all(co[x]["anker_guete"]["a0"] < co[x]["anker_guete"]["a50"]
          < co[x]["anker_guete"]["a100"] for x in REGISTRY))

print("\n11. CONFIDENCE UND TRENNSCHAERFE (Rev. 4)")
from scoring import CONF_SCHWELLE
from kpis import PHASE_WEIGHTS, PHASE_LABEL
for ph in PHASE_WEIGHTS:
    check(f"Trennschaerfe {PHASE_LABEL[ph]} ist ueber alle Spiele konstant",
          s[f"guete_{ph}"].nunique() == 1, f"{s[f'guete_{ph}'].nunique()} Werte")
hat = s["phase_off_umschalten"].notna()
quote = float((hat & (s["conf_off_umschalten"] < CONF_SCHWELLE)).sum() / hat.sum() * 100)
check("Offensives Umschalten in hoechstens 8 % der Spiele ausgeblendet",
      quote <= 8.0, f"{quote:.1f} % bei Schwelle {CONF_SCHWELLE}")
andere = [p for p in PHASE_WEIGHTS if p != "off_umschalten"]
maxq = max(float((s[f"phase_{p}"].notna() & (s[f"conf_{p}"] < CONF_SCHWELLE)).sum()
                 / max(s[f"phase_{p}"].notna().sum(), 1) * 100) for p in andere)
check("Alle uebrigen Phasen nie ausgeblendet", maxq == 0.0, f"max {maxq:.1f} %")
check("Confidence enthaelt die Trennschaerfe nicht mehr",
      float(s.loc[hat, "conf_off_umschalten"].median()) > 0.30,
      f"Median {s.loc[hat, 'conf_off_umschalten'].median():.2f}, vorher 0,15 mit Guete-Faktor")

print("\n12. BEIDSEITIGE EFFIZIENZ (Rev. 4)")
gg = s[["match_id", "team_id", "npg"]].rename(
    columns={"team_id": "opponent_id", "npg": "npg_gegen"})
e = s.merge(gg, on=["match_id", "opponent_id"], how="left")
check("Gegentore ohne Elfmeter fuer jede Zeile bestimmbar", bool(e.npg_gegen.notna().all()),
      f"{int(e.npg_gegen.isna().sum())} fehlend")
eff_off = e.npg - e.CC1_npxg
eff_def = e.CC1d_npxg_gegen - e.npg_gegen
netto = eff_off + eff_def
ident = (e.npg - e.npg_gegen) - (e.CC1_npxg - e.CC1d_npxg_gegen)
check("Netto == tatsaechliche minus erwartete Tordifferenz",
      bool((netto - ident).abs().max() < 1e-9), f"max {float((netto - ident).abs().max()):.1e}")
check("Ligamittel der Nettoeffizienz ist 0 (Symmetrie der Definition)",
      abs(float(netto.mean())) < 1e-9, f"{float(netto.mean()):+.2e}")
check("Beide Seiten sind praktisch unkorreliert (|r| < 0,15)",
      abs(float(eff_off.corr(eff_def))) < 0.15, f"r = {float(eff_off.corr(eff_def)):+.3f}")
up = e[(e.liga == "2BL") & (e.ist_aufsteiger_saison == 1)]
uo, ud = float((up.npg - up.CC1_npxg).mean()), float((up.CC1d_npxg_gegen - up.npg_gegen).mean())
check("Aufsteiger-Referenz reproduziert (+0,079 / +0,180 / +0,259)",
      abs(uo - 0.079) < 5e-4 and abs(ud - 0.180) < 5e-4 and abs(uo + ud - 0.259) < 1e-3,
      f"{uo:+.3f} / {ud:+.3f} / {uo + ud:+.3f}")
md = json.load(open(f"{OUT}/dashboard_matches.json"))
check("Dashboard-Schwelle stimmt mit scoring.py ueberein",
      md["conf_schwelle"] == CONF_SCHWELLE, f"{md['conf_schwelle']} vs {CONF_SCHWELLE}")
check("Jedes Dashboard-Spiel traegt Trennschaerfe und beide Torgroessen",
      all(x.get("ph_guete") and x.get("npg") is not None and x.get("npg_geg") is not None
          for t in md["teams"] for x in t["spiele"]))

print(f"\n{'=' * 62}\nGESAMT: {'ALLE PRUEFUNGEN BESTANDEN' if ok_all else 'MIT ABWEICHUNGEN — siehe oben'}")
