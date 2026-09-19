"""Modelle und Metriken auf numpy.

Drei Modellfamilien, alle mit derselben Schnittstelle (fit / predict_proba /
als_dict / aus_dict), alle auf standardisierten Merkmalen:

  Logit    multinomiales Logit, L2-regularisiert, Newton-Verfahren.
  MLP      ein verstecktes tanh-Layer, Softmax-Ausgang, Adam, L2.
  Poisson  zwei Poisson-Regressionen (Heimtore, Gasttore) mit log-Link;
           Ergebnis- oder Ueber/Unter-Wahrscheinlichkeiten aus der Faltung
           der beiden Torverteilungen. Das fussballnahe Modell: es lernt
           Torraten, nicht Klassen.
"""
import math

import numpy as np


# ---------------------------------------------------------------- Metriken
def log_loss(y, p, eps=1e-12):
    p = np.clip(np.asarray(p, dtype=float), eps, 1.0)
    y = np.asarray(y, dtype=int)
    return float(-np.mean(np.log(p[np.arange(len(y)), y])))


def brier(y, p):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    ziel = np.zeros_like(p)
    ziel[np.arange(len(y)), y] = 1.0
    return float(np.mean(np.sum((p - ziel) ** 2, axis=1)))


def trefferquote(y, p):
    return float(np.mean(np.argmax(np.asarray(p), axis=1) == np.asarray(y)))


def auc(y, score):
    """Flaeche unter der ROC-Kurve, rangbasiert mit Bindungskorrektur."""
    y = np.asarray(y)
    s = np.asarray(score, dtype=float)
    n_pos, n_neg = int(np.sum(y == 1)), int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        return None
    ordnung = np.argsort(s, kind="mergesort")
    raenge = np.empty(len(s), dtype=float)
    sortiert = s[ordnung]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sortiert[j + 1] == sortiert[i]:
            j += 1
        raenge[ordnung[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((raenge[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def softmax(Z):
    Z = Z - Z.max(axis=1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(axis=1, keepdims=True)


# --------------------------------------------------------- Standardisierer
class Standardisierer:
    """z-Standardisierung je Spalte; fehlende Werte (NaN) werden auf das
    Trainingsmittel gesetzt, also auf z = 0."""

    def __init__(self, mittel=None, sd=None):
        self.mittel = None if mittel is None else np.asarray(mittel, dtype=float)
        self.sd = None if sd is None else np.asarray(sd, dtype=float)

    def fit(self, X):
        X = np.asarray(X, dtype=float)
        with np.errstate(invalid="ignore"):
            self.mittel = np.nanmean(X, axis=0)
            self.sd = np.nanstd(X, axis=0, ddof=1) if len(X) > 1 else np.ones(X.shape[1])
        self.mittel = np.where(np.isnan(self.mittel), 0.0, self.mittel)
        self.sd = np.where(np.isnan(self.sd) | (self.sd < 1e-12), 1.0, self.sd)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        Z = (X - self.mittel) / self.sd
        return np.where(np.isnan(Z), 0.0, Z)

    def als_dict(self):
        return {"mittel": self.mittel.tolist(), "sd": self.sd.tolist()}

    @classmethod
    def aus_dict(cls, d):
        return cls(d["mittel"], d["sd"])


def _mit_achse(X):
    X = np.asarray(X, dtype=float)
    return np.hstack([np.ones((len(X), 1)), X])


# ------------------------------------------------------------------ Logit
class Logit:
    """Multinomiales Logit (K Klassen, letzte Klasse Referenz), L2, Newton."""

    typ = "logit"

    def __init__(self, l2=1.0, max_iter=30, tol=1e-7):
        self.l2 = max(float(l2), 1e-3)
        self.max_iter = int(max_iter)
        self.tol = tol
        self.B = None   # (K-1) x (d+1)
        self.K = None
        self.iterationen = 0

    def _proba(self, Xe):
        Z = np.hstack([Xe @ self.B.T, np.zeros((len(Xe), 1))])
        return softmax(Z)

    def _ziel(self, Xe, y):
        P = self._proba(Xe)
        nll = -np.sum(np.log(np.clip(P[np.arange(len(y)), y], 1e-300, None)))
        return nll + 0.5 * self.l2 * np.sum(self.B[:, 1:] ** 2)

    def fit(self, X, y, K=None, **_):
        y = np.asarray(y, dtype=int)
        self.K = int(K or (y.max() + 1))
        Xe = _mit_achse(X)
        n, p = Xe.shape
        Kr = self.K - 1
        self.B = np.zeros((Kr, p))
        Y = np.zeros((n, Kr))
        Y[np.arange(n)[y < Kr], y[y < Kr]] = 1.0
        strafe = np.ones(p) * self.l2
        strafe[0] = 0.0
        ziel = self._ziel(Xe, y)
        for it in range(self.max_iter):
            self.iterationen = it + 1
            P = self._proba(Xe)[:, :Kr]
            G = (P - Y).T @ Xe + strafe * self.B                       # Kr x p
            H = np.zeros((Kr * p, Kr * p))
            for k in range(Kr):
                for l in range(k, Kr):
                    w = P[:, k] * ((1.0 if k == l else 0.0) - P[:, l])
                    blk = (Xe * w[:, None]).T @ Xe
                    H[k * p:(k + 1) * p, l * p:(l + 1) * p] = blk
                    if l != k:
                        H[l * p:(l + 1) * p, k * p:(k + 1) * p] = blk
            H[np.arange(Kr * p), np.arange(Kr * p)] += np.tile(strafe, Kr)
            schritt = np.linalg.solve(H + 1e-9 * np.eye(Kr * p), G.ravel()).reshape(Kr, p)
            if np.max(np.abs(schritt)) < self.tol:
                break
            alt = self.B.copy()
            t = 1.0
            for _ in range(15):
                self.B = alt - t * schritt
                neu = self._ziel(Xe, y)
                if neu <= ziel + 1e-10:
                    break
                t *= 0.5
            else:
                self.B = alt
                break
            if ziel - neu < self.tol * max(1.0, abs(ziel)):
                ziel = neu
                break
            ziel = neu
        return self

    def predict_proba(self, X):
        return self._proba(_mit_achse(X))

    def als_dict(self):
        return {"typ": self.typ, "l2": self.l2, "K": self.K, "B": self.B.tolist()}

    @classmethod
    def aus_dict(cls, d):
        m = cls(l2=d["l2"])
        m.K = d["K"]
        m.B = np.asarray(d["B"], dtype=float)
        return m


# -------------------------------------------------------------------- MLP
class MLP:
    """Ein verstecktes tanh-Layer, Softmax-Ausgang, Adam, L2, Vollbatch."""

    typ = "mlp"

    def __init__(self, versteckt=8, l2=0.01, lernrate=0.02, epochen=200, seed=0):
        self.h = max(int(versteckt), 1)
        self.l2 = max(float(l2), 0.0)
        self.lr = float(lernrate)
        self.epochen = int(epochen)
        self.seed = seed
        self.W1 = self.b1 = self.W2 = self.b2 = None
        self.K = None

    def _vorwaerts(self, X):
        Hid = np.tanh(X @ self.W1 + self.b1)
        return Hid, softmax(Hid @ self.W2 + self.b2)

    def fit(self, X, y, K=None, **_):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        self.K = int(K or (y.max() + 1))
        n, d = X.shape
        rnd = np.random.RandomState(self.seed)
        self.W1 = rnd.uniform(-1, 1, (d, self.h)) / math.sqrt(d)
        self.b1 = np.zeros(self.h)
        self.W2 = rnd.uniform(-1, 1, (self.h, self.K)) / math.sqrt(self.h)
        self.b2 = np.zeros(self.K)
        Y = np.zeros((n, self.K))
        Y[np.arange(n), y] = 1.0
        params = [self.W1, self.b1, self.W2, self.b2]
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        b1, b2, eps = 0.9, 0.999, 1e-8
        for ep in range(1, self.epochen + 1):
            Hid, P = self._vorwaerts(X)
            dZ = (P - Y) / n
            gW2 = Hid.T @ dZ + self.l2 * self.W2
            gb2 = dZ.sum(axis=0)
            dH = (dZ @ self.W2.T) * (1.0 - Hid ** 2)
            gW1 = X.T @ dH + self.l2 * self.W1
            gb1 = dH.sum(axis=0)
            for P_, G_, M_, V_ in zip(params, [gW1, gb1, gW2, gb2], m, v):
                M_ *= b1
                M_ += (1 - b1) * G_
                V_ *= b2
                V_ += (1 - b2) * G_ ** 2
                P_ -= self.lr * (M_ / (1 - b1 ** ep)) / (np.sqrt(V_ / (1 - b2 ** ep)) + eps)
        return self

    def predict_proba(self, X):
        return self._vorwaerts(np.asarray(X, dtype=float))[1]

    def als_dict(self):
        return {"typ": self.typ, "versteckt": self.h, "l2": self.l2, "lernrate": self.lr,
                "epochen": self.epochen, "K": self.K, "W1": self.W1.tolist(), "b1": self.b1.tolist(),
                "W2": self.W2.tolist(), "b2": self.b2.tolist()}

    @classmethod
    def aus_dict(cls, d):
        m = cls(versteckt=d["versteckt"], l2=d["l2"], lernrate=d["lernrate"], epochen=d["epochen"])
        m.K = d["K"]
        m.W1, m.b1 = np.asarray(d["W1"]), np.asarray(d["b1"])
        m.W2, m.b2 = np.asarray(d["W2"]), np.asarray(d["b2"])
        return m


# ---------------------------------------------------------------- Poisson
MAX_TORE = 12


def _poisson_pmf(lam, k_max=MAX_TORE):
    """Wahrscheinlichkeiten 0..k_max je Zeile; der Rest wird auf k_max gelegt."""
    lam = np.asarray(lam, dtype=float)[:, None]
    k = np.arange(k_max + 1)[None, :]
    logp = -lam + k * np.log(np.clip(lam, 1e-12, None)) - np.array([math.lgamma(i + 1) for i in range(k_max + 1)])[None, :]
    P = np.exp(logp)
    P[:, -1] += np.clip(1.0 - P.sum(axis=1), 0.0, 1.0)
    return P


class Poisson:
    """Zwei Poisson-Regressionen mit log-Link (Heimtore, Gasttore), L2, Newton.

    K = 3 liefert Heimsieg / Unentschieden / Auswaertssieg aus der Faltung der
    Torverteilungen, K = 2 liefert unter / ueber 2,5 Tore aus der Summe.
    `fit` braucht die Tore je Spiel (tore=[(heim, gast), ...])."""

    typ = "poisson"

    def __init__(self, l2=1.0, max_iter=30, tol=1e-8):
        self.l2 = max(float(l2), 1e-3)
        self.max_iter = int(max_iter)
        self.tol = tol
        self.beta_heim = self.beta_gast = None
        self.K = None
        self.iterationen = 0

    def _fit_eins(self, Xe, y):
        n, p = Xe.shape
        beta = np.zeros(p)
        beta[0] = math.log(max(float(np.mean(y)), 1e-3))
        strafe = np.ones(p) * self.l2
        strafe[0] = 0.0

        def ziel(b):
            eta = np.clip(Xe @ b, -20, 20)
            return float(np.sum(np.exp(eta) - y * eta) + 0.5 * np.sum(strafe * b ** 2))

        z = ziel(beta)
        for it in range(self.max_iter):
            self.iterationen = it + 1
            lam = np.exp(np.clip(Xe @ beta, -20, 20))
            g = Xe.T @ (lam - y) + strafe * beta
            H = (Xe * lam[:, None]).T @ Xe + np.diag(strafe)
            schritt = np.linalg.solve(H + 1e-9 * np.eye(p), g)
            if np.max(np.abs(schritt)) < self.tol:
                break
            t = 1.0
            for _ in range(15):
                neu_b = beta - t * schritt
                zn = ziel(neu_b)
                if zn <= z + 1e-10:
                    break
                t *= 0.5
            else:
                break
            beta = neu_b
            if z - zn < self.tol * max(1.0, abs(z)):
                z = zn
                break
            z = zn
        return beta

    def fit(self, X, y=None, K=None, tore=None, **_):
        if tore is None:
            raise ValueError("Poisson-Modell braucht tore=[(heim, gast), ...]")
        self.K = int(K or 3)
        Xe = _mit_achse(X)
        T = np.asarray(tore, dtype=float)
        self.beta_heim = self._fit_eins(Xe, T[:, 0])
        self.beta_gast = self._fit_eins(Xe, T[:, 1])
        return self

    def predict_tore(self, X):
        Xe = _mit_achse(X)
        return (np.exp(np.clip(Xe @ self.beta_heim, -20, 20)),
                np.exp(np.clip(Xe @ self.beta_gast, -20, 20)))

    def predict_proba(self, X):
        lh, lg = self.predict_tore(X)
        if self.K == 2:
            P = _poisson_pmf(lh + lg)
            unter = P[:, :3].sum(axis=1)
            return np.stack([unter, 1.0 - unter], axis=1)
        Ph, Pg = _poisson_pmf(lh), _poisson_pmf(lg)
        M = Ph[:, :, None] * Pg[:, None, :]          # n x (h) x (g)
        h_idx, g_idx = np.indices((MAX_TORE + 1, MAX_TORE + 1))
        heim = M[:, h_idx > g_idx].sum(axis=1)
        remis = M[:, h_idx == g_idx].sum(axis=1)
        gast = M[:, h_idx < g_idx].sum(axis=1)
        P = np.stack([heim, remis, gast], axis=1)
        return P / P.sum(axis=1, keepdims=True)

    def als_dict(self):
        return {"typ": self.typ, "l2": self.l2, "K": self.K,
                "beta_heim": self.beta_heim.tolist(), "beta_gast": self.beta_gast.tolist()}

    @classmethod
    def aus_dict(cls, d):
        m = cls(l2=d["l2"])
        m.K = d["K"]
        m.beta_heim = np.asarray(d["beta_heim"])
        m.beta_gast = np.asarray(d["beta_gast"])
        return m


MODELLTYPEN = {"logit": Logit, "mlp": MLP, "poisson": Poisson}


def modell_bauen(spez, seed=0):
    typ = spez.get("typ", "logit")
    if typ == "logit":
        return Logit(l2=spez.get("l2", 1.0))
    if typ == "mlp":
        return MLP(versteckt=spez.get("versteckt", 8), l2=spez.get("l2", 0.01),
                   lernrate=spez.get("lernrate", 0.02), epochen=spez.get("epochen", 200), seed=seed)
    if typ == "poisson":
        return Poisson(l2=spez.get("l2", 1.0))
    raise ValueError("unbekannter Modelltyp %r" % typ)


def modell_aus_dict(d):
    return MODELLTYPEN[d["typ"]].aus_dict(d)
