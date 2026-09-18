"""Bewertung einer Hypothese: Vorwaertsvalidierung ueber Saisons.

Prognosen werden so geprueft, wie sie im Ernstfall entstehen: Modell auf allen
Saisons bis S-1 fitten, Saison S vorhersagen, naechste Saison. Zwei Mengen,
streng getrennt:

  Lernmenge   Vorwaertsvalidierung ueber die Testsaisons 2015/16 bis zur
              vorletzten vollstaendigen Saison; darauf waehlt die Schleife aus.
  Pruefsaison die letzte vollstaendige Saison. Wird je Experiment mitgerechnet,
              aber dem Forscher NICHT gezeigt - sonst waehlt er darauf aus.

Die laufende Saison (mit offenen Spielen) gehoert zu keiner der beiden: ihre
gespielten Spiele fliessen nur ins Endmodell, ihre offenen sind die Prognosen.

Hauptmetrik ist der Log-Loss (kleiner ist besser), Proper Scoring Rule fuer
Kalibrierung und Trennschaerfe zugleich. Benchmarks: Basisrate (Klassen-
haeufigkeit der Trainingssaisons) und ein Elo-Logit (elo_diff allein),
beide mit derselben Vorwaertsvalidierung gerechnet.
"""
import time

import numpy as np

from .formeln import auswerten
from .modelle import (Standardisierer, auc, brier, log_loss, modell_bauen,
                      modell_aus_dict, trefferquote)

ERSTE_TESTSAISON = "2015-16"
MIN_TRAININGSSAISONS = 3


# ---------------------------------------------------------- Merkmalsmatrix
def merkmalsnamen(hyp):
    return list(hyp["merkmale"]) + [a["name"] for a in hyp["abgeleitet"]]


def merkmalszeile(hyp, werte):
    w = dict(werte)
    for a in hyp["abgeleitet"]:
        w[a["name"]] = auswerten(a["formel"], w)
    return [w.get(n) for n in merkmalsnamen(hyp)]


def merkmalsmatrix(zeilen, hyp):
    X = np.array([[np.nan if v is None else float(v) for v in merkmalszeile(hyp, z["merkmale"])]
                  for z in zeilen], dtype=float)
    return X.reshape(len(zeilen), -1)


# ------------------------------------------------------------- Aufteilung
def saisonplan(tabelle):
    """(Testsaisons der Lernmenge, Pruefsaison, laufende Saison oder None)."""
    alle = tabelle.saisons()
    offen = {z["gruppe"] for z in tabelle.offen}
    laufend = alle[-1] if alle[-1] in offen else None   # nur die juengste Saison gilt als laufend
    voll = alle[:-1] if laufend else alle
    pruef = voll[-1]
    tests = [s for s in voll[:-1] if s >= ERSTE_TESTSAISON]
    return tests, pruef, laufend


def _idx(tabelle, bedingung):
    return np.array([i for i, z in enumerate(tabelle.zeilen) if bedingung(z["gruppe"])], dtype=int)


def falten(tabelle):
    """Vorwaertsfalten: (Trainingsindizes, Testindizes, Testsaison)."""
    tests, _, _ = saisonplan(tabelle)
    out = []
    for s in tests:
        train = _idx(tabelle, lambda g, s=s: g < s)
        test = _idx(tabelle, lambda g, s=s: g == s)
        if len({tabelle.zeilen[i]["gruppe"] for i in train}) >= MIN_TRAININGSSAISONS and len(test):
            out.append((train, test, s))
    return out


# ---------------------------------------------------------- Standardisieren
def _standardisieren(X, gruppen, train, test, modus):
    if modus == "gruppe":
        gr = np.asarray(gruppen)
        stds = {g: Standardisierer().fit(X[gr == g]) for g in set(gruppen)}
        Z = np.zeros_like(X)
        for g, s in stds.items():
            maske = gr == g
            Z[maske] = s.transform(X[maske])
        return Z[train], Z[test], {"modus": "gruppe", "gruppen": {g: s.als_dict() for g, s in stds.items()}}
    std = Standardisierer().fit(X[train])
    return std.transform(X[train]), (std.transform(X[test]) if len(test) else X[test]), {"modus": "global", **std.als_dict()}


def _fit(hyp, Xtr, ytr, K, tore, seed):
    m = modell_bauen(hyp["modell"], seed=seed)
    m.fit(Xtr, ytr, K, tore=tore)
    return m


def _basis(ytr, K):
    ytr = np.asarray(ytr)
    return np.array([(np.sum(ytr == k) + 1.0) / (len(ytr) + K) for k in range(K)])


def _metriken(y, P, P_basis, K):
    y = np.asarray(y)
    out = {"logloss": log_loss(y, P), "brier": brier(y, P), "treffer": trefferquote(y, P),
           "logloss_basis": log_loss(y, P_basis)}
    if K == 2:
        out["auc"] = auc(y, P[:, 1])
    return out


def _runde(d, stellen=4):
    return {k: (round(v, stellen) if isinstance(v, float) else v) for k, v in d.items()}


# -------------------------------------------------------------- Bewertung
def _durchlauf(tabelle, hyp, X, y, tore, gruppen, falt, seed0=0):
    """Vorhersagen ueber alle Falten; gibt (idx, P, P_basis, je_saison) zurueck."""
    K = len(tabelle.klassen)
    idx, PP, PB, je_saison = [], [], [], {}
    for f, (train, test, saison) in enumerate(falt):
        Xtr, Xte, _ = _standardisieren(X, gruppen, train, test, hyp["standardisierung"])
        ytr = y[train]
        m = _fit(hyp, Xtr, ytr, K, tore[train] if tore is not None else None, seed=seed0 + f)
        P = m.predict_proba(Xte)
        basis = np.tile(_basis(ytr, K), (len(test), 1))
        idx.append(test)
        PP.append(P)
        PB.append(basis)
        je_saison[saison] = round(log_loss(y[test], P), 4)
    idx = np.concatenate(idx)
    return idx, np.vstack(PP), np.vstack(PB), je_saison


def bewerten(tabelle, hyp):
    start = time.time()
    X = merkmalsmatrix(tabelle.zeilen, hyp)
    y = np.array(tabelle.labels(), dtype=int)
    tore = np.array([z["extra"]["tore"] for z in tabelle.zeilen], dtype=float)
    gruppen = [z["gruppe"] for z in tabelle.zeilen]
    K = len(tabelle.klassen)
    namen = merkmalsnamen(hyp)
    warnungen = []
    for j, n in enumerate(namen):
        fehlt = float(np.mean(np.isnan(X[:, j])))
        if fehlt > 0.5:
            warnungen.append("%s fehlt in %.0f%% der Zeilen" % (n, 100 * fehlt))

    falt = falten(tabelle)
    idx, P, PB, je_saison = _durchlauf(tabelle, hyp, X, y, tore, gruppen, falt)
    cv = _metriken(y[idx], P, PB, K)
    if tabelle.benchmark.get("elo_logloss_je_saison"):
        cv["logloss_elo"] = float(np.mean([tabelle.benchmark["elo_logloss_je_saison"][s] for s in je_saison
                                           if s in tabelle.benchmark["elo_logloss_je_saison"]]))
    cv["logloss_je_saison"] = je_saison

    # stille Pruefung: alle Saisons vor der Pruefsaison -> Pruefsaison
    _, pruefsaison, _ = saisonplan(tabelle)
    train = _idx(tabelle, lambda g: g < pruefsaison)
    test = _idx(tabelle, lambda g: g == pruefsaison)
    Xtr, Xte, _ = _standardisieren(X, gruppen, train, test, hyp["standardisierung"])
    m = _fit(hyp, Xtr, y[train], K, tore[train], seed=99)
    Pp = m.predict_proba(Xte)
    pr = _metriken(y[test], Pp, np.tile(_basis(y[train], K), (len(test), 1)), K)
    if tabelle.benchmark.get("pruef_logloss_elo") is not None:
        pr["logloss_elo"] = tabelle.benchmark["pruef_logloss_elo"]

    return {"hauptmetrik": round(cv["logloss"], 4), "richtung": "min",
            "metriken": _runde(cv), "pruef": _runde(pr),
            "n_lern": int(len(idx)), "n_pruef": int(len(test)), "n_falten": len(falt),
            "testsaisons": [s for _, _, s in falt], "pruefsaison": pruefsaison,
            "merkmale": namen, "warnungen": warnungen, "dauer_s": round(time.time() - start, 2)}


def benchmarks(tabelle):
    """Basisrate und Elo-Logit mit derselben Vorwaertsvalidierung; fuellt tabelle.benchmark."""
    hyp = {"merkmale": ["elo_diff"], "abgeleitet": [], "modell": {"typ": "logit", "l2": 1.0},
           "standardisierung": "global"}
    tabelle.benchmark = {}
    erg = bewerten(tabelle, hyp)
    tabelle.benchmark = {
        "quelle": "Elo-Logit (elo_diff allein) und Basisrate, gleiche Vorwaertsvalidierung",
        "logloss_basis": erg["metriken"]["logloss_basis"],
        "logloss_elo": erg["metriken"]["logloss"],
        "elo_logloss_je_saison": erg["metriken"]["logloss_je_saison"],
        "pruef_logloss_basis": erg["pruef"]["logloss_basis"],
        "pruef_logloss_elo": erg["pruef"]["logloss"],
        "testsaisons": erg["testsaisons"], "pruefsaison": erg["pruefsaison"],
    }
    return tabelle.benchmark


# ------------------------------------------------------------- Endmodell
def endmodell(tabelle, hyp):
    """Auf allen gespielten Spielen fitten - das Modell fuer `vorhersage`."""
    X = merkmalsmatrix(tabelle.zeilen, hyp)
    y = np.array(tabelle.labels(), dtype=int)
    tore = np.array([z["extra"]["tore"] for z in tabelle.zeilen], dtype=float)
    gruppen = [z["gruppe"] for z in tabelle.zeilen]
    K = len(tabelle.klassen)
    alle = np.arange(len(X))
    Xz, _, std = _standardisieren(X, gruppen, alle, np.array([], dtype=int), hyp["standardisierung"])
    m = _fit(hyp, Xz, y, K, tore, seed=0)
    out = {"aufgabe": tabelle.aufgabe, "hypothese": hyp, "merkmale": merkmalsnamen(hyp),
           "klassen": tabelle.klassen, "standardisierer": std, "modell": m.als_dict(),
           "stand": max(z["extra"]["datum"] for z in tabelle.zeilen), "n": int(len(X))}
    if m.typ == "logit":
        out["koeffizienten"] = koeffizienten(out)
    elif m.typ == "poisson":
        namen = ["achse"] + out["merkmale"]
        out["koeffizienten"] = {"Heimtore (log-Rate)": dict(zip(namen, [round(v, 4) for v in m.beta_heim])),
                                "Gasttore (log-Rate)": dict(zip(namen, [round(v, 4) for v in m.beta_gast]))}
    return out


def koeffizienten(endm):
    B = endm["modell"]["B"]
    namen = ["achse"] + endm["merkmale"]
    klassen = endm["klassen"]
    if len(klassen) == 2:
        return {klassen[1]: dict(zip(namen, [round(-v, 4) for v in B[0]]))}
    return {klassen[k]: dict(zip(namen, [round(v, 4) for v in bk])) for k, bk in enumerate(B)}


def vorhersagen(endm, werte, gruppe=None):
    """Klassenwahrscheinlichkeiten fuer ein Merkmalsdict aus dem Endmodell."""
    hyp = endm["hypothese"]
    x = np.array([[np.nan if v is None else float(v) for v in merkmalszeile(hyp, werte)]], dtype=float)
    std = endm["standardisierer"]
    if std["modus"] == "gruppe":
        if gruppe not in std["gruppen"]:
            gruppe = sorted(std["gruppen"])[-1]   # unbekannte Saison: juengste Statistik
        s = Standardisierer.aus_dict(std["gruppen"][gruppe])
    else:
        s = Standardisierer.aus_dict(std)
    m = modell_aus_dict(endm["modell"])
    p = m.predict_proba(s.transform(x))[0]
    out = dict(zip(endm["klassen"], [round(float(v), 4) for v in p]))
    if m.typ == "poisson":
        lh, lg = m.predict_tore(s.transform(x))
        out["_tore_erwartet"] = (round(float(lh[0]), 2), round(float(lg[0]), 2))
    return out
