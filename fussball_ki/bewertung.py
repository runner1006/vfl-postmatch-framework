"""Bewertung einer Hypothese: rechnen, kreuzvalidieren, mit Benchmarks messen.

Zwei Mengen, streng getrennt:

  Lernmenge   Kreuzvalidierung, auf der die Schleife Hypothesen auswaehlt.
              spiel: die zeitlich fruehesten 80 % der Spiele, 2 x 5 Falten
              mit festem Seed (jede Hypothese sieht dieselben Falten).
              aufstieg: Leave-one-season-out ueber die Saisons bis 2024/25.
  Pruefmenge  spiel: die spaetesten 20 % der Spiele. aufstieg: 2025/26.
              Wird je Experiment mitgerechnet, aber dem Forscher NICHT
              gezeigt - sonst waehlt er darauf aus, und sie ist wertlos.

Hauptmetrik ist in beiden Aufgaben der Log-Loss (kleiner ist besser), weil
er als Proper Scoring Rule Kalibrierung und Trennschaerfe zugleich misst.
"""
import math
import random
import time

from .daten import formel_auswerten
from .modelle import (Standardisierer, auc, brier, log_loss, modell_bauen,
                      modell_aus_dict, trefferquote)

FALTEN = {"k": 5, "seeds": (7, 11)}
PRUEF_ANTEIL = 0.2


# ---------------------------------------------------------- Merkmalsmatrix
def merkmalsnamen(hyp):
    return list(hyp["merkmale"]) + [a["name"] for a in hyp["abgeleitet"]]


def merkmalszeile(hyp, werte):
    """Basis- und abgeleitete Merkmale fuer ein Merkmalsdict berechnen."""
    w = dict(werte)
    for a in hyp["abgeleitet"]:
        w[a["name"]] = formel_auswerten(a["formel"], w)
    return [w.get(n) for n in merkmalsnamen(hyp)]


def merkmalsmatrix(tabelle, hyp):
    return [merkmalszeile(hyp, z["merkmale"]) for z in tabelle.zeilen]


# ------------------------------------------------------------- Aufteilung
def lern_und_pruefmenge(tabelle):
    n = len(tabelle)
    if tabelle.aufgabe == "aufstieg":
        gruppen = sorted({z["gruppe"] for z in tabelle.zeilen})
        letzte = gruppen[-1]
        lern = [i for i, z in enumerate(tabelle.zeilen) if z["gruppe"] != letzte]
        pruef = [i for i, z in enumerate(tabelle.zeilen) if z["gruppe"] == letzte]
        return lern, pruef
    schnitt = int(round(n * (1 - PRUEF_ANTEIL)))
    return list(range(schnitt)), list(range(schnitt, n))


def falten(tabelle, lern):
    """Liste von (Trainingsindizes, Testindizes) - fest, nicht hypothesenabhaengig."""
    if tabelle.aufgabe == "aufstieg":
        gruppen = sorted({tabelle.zeilen[i]["gruppe"] for i in lern})
        out = []
        for g in gruppen:
            test = [i for i in lern if tabelle.zeilen[i]["gruppe"] == g]
            train = [i for i in lern if tabelle.zeilen[i]["gruppe"] != g]
            out.append((train, test))
        return out
    out = []
    for seed in FALTEN["seeds"]:
        idx = list(lern)
        random.Random(seed).shuffle(idx)
        for f in range(FALTEN["k"]):
            test = idx[f::FALTEN["k"]]
            ts = set(test)
            train = [i for i in lern if i not in ts]
            out.append((train, test))
    return out


# ---------------------------------------------------------- Standardisieren
def _standardisieren(X, gruppen, train, test, modus):
    """Gibt (X_train_z, X_test_z, Standardisierer-Beschreibung) zurueck."""
    if modus == "gruppe":
        std_je_gruppe = {}
        for g in set(gruppen):
            rows = [X[i] for i in range(len(X)) if gruppen[i] == g]
            std_je_gruppe[g] = Standardisierer().fit(rows)
        def z(i):
            return std_je_gruppe[gruppen[i]].transform([X[i]])[0]
        return [z(i) for i in train], [z(i) for i in test], {
            "modus": "gruppe", "gruppen": {g: s.als_dict() for g, s in std_je_gruppe.items()}}
    std = Standardisierer().fit([X[i] for i in train])
    return (std.transform([X[i] for i in train]), std.transform([X[i] for i in test]),
            {"modus": "global", **std.als_dict()})


def _fit_predict(hyp, Xtr, ytr, Xte, K, seed):
    m = modell_bauen(hyp["modell"], seed=seed).fit(Xtr, ytr, K)
    return m, m.predict_proba(Xte)


def _basis(ytr, K):
    n = len(ytr)
    return [(sum(1 for v in ytr if v == k) + 1.0) / (n + K) for k in range(K)]


# ---------------------------------------------------------------- Metriken
def _metriken_spiel(tabelle, idx, y, p, p_basis):
    out = {"logloss": log_loss(y, p), "brier": brier(y, p), "treffer": trefferquote(y, p),
           "logloss_basis": log_loss(y, p_basis)}
    pf, yf, pm = [], [], []
    for i, yi, pi in zip(idx, y, p):
        f = tabelle.zeilen[i]["extra"].get("p_framework")
        if f and all(v is not None for v in f):
            pf.append(f)
            yf.append(yi)
            pm.append(pi)
    if pf:
        out["logloss_framework"] = log_loss(yf, pf)
        out["logloss_auf_frameworkzeilen"] = log_loss(yf, pm)
    return out


def _metriken_aufstieg(tabelle, idx, y, p, p_basis, je_falte):
    p1 = [pi[1] for pi in p]
    out = {"logloss": log_loss(y, p), "brier": brier(y, p),
           "logloss_basis": log_loss(y, p_basis), "auc_gesamt": auc(y, p1)}
    aucs, treffer, von = [], 0, 0
    for (fi, fy, fp) in je_falte:
        a = auc(fy, [q[1] for q in fp])
        if a is not None:
            aucs.append(a)
        rang = sorted(range(len(fp)), key=lambda j: -fp[j][1])[:3]
        treffer += sum(1 for j in rang if fy[j] == 1)
        von += 3
    if aucs:
        out["auc_mittel"] = sum(aucs) / len(aucs)
        out["auc_min"] = min(aucs)
    out["top3_treffer"] = treffer
    out["top3_von"] = von
    return out


def _runde(d, stellen=4):
    return {k: (round(v, stellen) if isinstance(v, float) else v) for k, v in d.items()}


# -------------------------------------------------------------- Bewertung
def bewerten(tabelle, hyp):
    """Kreuzvalidierung auf der Lernmenge plus stille Pruefung auf der Pruefmenge."""
    start = time.time()
    X = merkmalsmatrix(tabelle, hyp)
    y = tabelle.labels()
    K = len(tabelle.klassen)
    gruppen = [z["gruppe"] for z in tabelle.zeilen]
    namen = merkmalsnamen(hyp)
    warnungen = []
    for j, n in enumerate(namen):
        fehlt = sum(1 for r in X if r[j] is None) / len(X)
        if fehlt > 0.5:
            warnungen.append("%s fehlt in %.0f%% der Zeilen" % (n, 100 * fehlt))

    lern, pruef = lern_und_pruefmenge(tabelle)
    falt = falten(tabelle, lern)
    if tabelle.aufgabe == "spiel":
        # je Wiederholung gepoolte Out-of-fold-Vorhersagen, dann gemittelt
        k = FALTEN["k"]
        metr = []
        for w in range(len(falt) // k):
            idx, yy, pp, pb = [], [], [], []
            for f, (train, test) in enumerate(falt[w * k:(w + 1) * k]):
                Xtr, Xte, _ = _standardisieren(X, gruppen, train, test, hyp["standardisierung"])
                ytr = [y[i] for i in train]
                _, p = _fit_predict(hyp, Xtr, ytr, Xte, K, seed=f)
                basis = _basis(ytr, K)
                idx += test
                yy += [y[i] for i in test]
                pp += p
                pb += [basis] * len(test)
            metr.append(_metriken_spiel(tabelle, idx, yy, pp, pb))
        cv = {k2: sum(m[k2] for m in metr) / len(metr) for k2 in metr[0] if all(k2 in m for m in metr)}
    else:
        idx, yy, pp, pb, je_falte = [], [], [], [], []
        for f, (train, test) in enumerate(falt):
            Xtr, Xte, _ = _standardisieren(X, gruppen, train, test, hyp["standardisierung"])
            ytr = [y[i] for i in train]
            _, p = _fit_predict(hyp, Xtr, ytr, Xte, K, seed=f)
            basis = _basis(ytr, K)
            idx += test
            fy = [y[i] for i in test]
            yy += fy
            pp += p
            pb += [basis] * len(test)
            je_falte.append((f, fy, p))
        cv = _metriken_aufstieg(tabelle, idx, yy, pp, pb, je_falte)

    # stille Pruefung: auf der ganzen Lernmenge fitten, auf der Pruefmenge messen
    Xtr, Xte, _ = _standardisieren(X, gruppen, lern, pruef, hyp["standardisierung"])
    ytr = [y[i] for i in lern]
    yte = [y[i] for i in pruef]
    _, p = _fit_predict(hyp, Xtr, ytr, Xte, K, seed=99)
    basis = _basis(ytr, K)
    if tabelle.aufgabe == "spiel":
        pr = _metriken_spiel(tabelle, pruef, yte, p, [basis] * len(pruef))
    else:
        pr = _metriken_aufstieg(tabelle, pruef, yte, p, [basis] * len(pruef), [(0, yte, p)])

    return {"hauptmetrik": round(cv["logloss"], 4), "richtung": "min",
            "metriken": _runde(cv), "pruef": _runde(pr),
            "n_lern": len(lern), "n_pruef": len(pruef), "n_falten": len(falt),
            "merkmale": namen, "warnungen": warnungen,
            "dauer_s": round(time.time() - start, 2)}


# ------------------------------------------------------------- Endmodell
def endmodell(tabelle, hyp):
    """Auf allen Zeilen fitten - das Modell, das `vorhersage` benutzt."""
    X = merkmalsmatrix(tabelle, hyp)
    y = tabelle.labels()
    K = len(tabelle.klassen)
    gruppen = [z["gruppe"] for z in tabelle.zeilen]
    alle = list(range(len(X)))
    Xz, _, std = _standardisieren(X, gruppen, alle, [], hyp["standardisierung"])
    m = modell_bauen(hyp["modell"], seed=0).fit(Xz, y, K)
    out = {"aufgabe": tabelle.aufgabe, "hypothese": hyp, "merkmale": merkmalsnamen(hyp),
           "klassen": tabelle.klassen, "standardisierer": std, "modell": m.als_dict()}
    if m.typ == "logit":
        out["koeffizienten"] = koeffizienten(out)
    return out


def koeffizienten(endm):
    """Standardisierte Logit-Koeffizienten je Klasse (Referenz: letzte Klasse).
    Im binaeren Fall aus Sicht der positiven Klasse, weil das so gelesen wird."""
    B = endm["modell"]["B"]
    namen = ["achse"] + endm["merkmale"]
    klassen = endm["klassen"]
    if len(klassen) == 2:
        return {klassen[1]: dict(zip(namen, [round(-v, 4) for v in B[0]]))}
    return {klassen[k]: dict(zip(namen, [round(v, 4) for v in bk])) for k, bk in enumerate(B)}


def vorhersagen(endm, werte, gruppe=None):
    """Klassenwahrscheinlichkeiten fuer ein Merkmalsdict aus dem Endmodell."""
    hyp = endm["hypothese"]
    x = merkmalszeile(hyp, werte)
    std = endm["standardisierer"]
    if std["modus"] == "gruppe":
        if gruppe not in std["gruppen"]:
            raise ValueError("Gruppe %r unbekannt; bekannt: %s" % (gruppe, ", ".join(sorted(std["gruppen"]))))
        s = Standardisierer.aus_dict(std["gruppen"][gruppe])
    else:
        s = Standardisierer.aus_dict(std)
    m = modell_aus_dict(endm["modell"])
    p = m.predict_proba(s.transform([x]))[0]
    return dict(zip(endm["klassen"], [round(v, 4) for v in p]))
