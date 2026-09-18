"""Modelle und Metriken - reine Standardbibliothek.

Die Datenmengen sind klein (298 bzw. 162 Zeilen), darum lohnt kein numpy:
ein multinomiales Logit-Modell wird mit Newton-Schritten in Sekundenbruchteilen
gefittet, ein kleines neuronales Netz mit Adam in wenigen Sekunden.

Alle Modelle nehmen standardisierte Merkmale (Standardisierer) und liefern
Klassenwahrscheinlichkeiten. Gewichte lassen sich als JSON ablegen und wieder
laden, damit `vorhersage` ohne Neurechnung auskommt.
"""
import math
import random


# ---------------------------------------------------------------- Metriken
def log_loss(y, p, eps=1e-12):
    """Mittlere negative Log-Likelihood. p: Liste von Wahrscheinlichkeitsvektoren."""
    s = 0.0
    for yi, pi in zip(y, p):
        s -= math.log(min(max(pi[yi], eps), 1.0))
    return s / len(y)


def brier(y, p):
    """Mehrklassen-Brier-Score (Summe der quadrierten Abweichungen je Zeile)."""
    s = 0.0
    for yi, pi in zip(y, p):
        s += sum((pk - (1.0 if k == yi else 0.0)) ** 2 for k, pk in enumerate(pi))
    return s / len(y)


def trefferquote(y, p):
    richtig = sum(1 for yi, pi in zip(y, p) if max(range(len(pi)), key=pi.__getitem__) == yi)
    return richtig / len(y)


def auc(y, score):
    """Flaeche unter der ROC-Kurve, rangbasiert mit Bindungskorrektur. y in {0,1}."""
    paare = sorted(zip(score, y))
    n = len(paare)
    raenge = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and paare[j + 1][0] == paare[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            raenge[k] = r
        i = j + 1
    n_pos = sum(1 for _, yi in paare if yi == 1)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    r_pos = sum(r for r, (_, yi) in zip(raenge, paare) if yi == 1)
    return (r_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def softmax(z):
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]


# --------------------------------------------------------- Standardisierer
class Standardisierer:
    """z-Standardisierung je Spalte; fehlende Werte (None) werden mit dem
    Trainingsmittel ersetzt, also auf z = 0 gesetzt."""

    def __init__(self, mittel=None, sd=None):
        self.mittel = mittel
        self.sd = sd

    def fit(self, X):
        d = len(X[0])
        self.mittel, self.sd = [], []
        for j in range(d):
            werte = [z[j] for z in X if z[j] is not None]
            if not werte:
                self.mittel.append(0.0)
                self.sd.append(1.0)
                continue
            mu = sum(werte) / len(werte)
            var = sum((v - mu) ** 2 for v in werte) / max(len(werte) - 1, 1)
            sd = math.sqrt(var)
            self.mittel.append(mu)
            self.sd.append(sd if sd > 1e-12 else 1.0)
        return self

    def transform(self, X):
        out = []
        for z in X:
            out.append([0.0 if v is None else (v - m) / s
                        for v, m, s in zip(z, self.mittel, self.sd)])
        return out

    def als_dict(self):
        return {"mittel": self.mittel, "sd": self.sd}

    @classmethod
    def aus_dict(cls, d):
        return cls(d["mittel"], d["sd"])


# ------------------------------------------------------ lineare Algebra
def loese(A, b):
    """Gauss-Elimination mit Spaltenpivot. A wird kopiert."""
    n = len(A)
    M = [zeile[:] + [b[i]] for i, zeile in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-14:
            M[c][c] += 1e-8  # numerische Stuetze bei Kollinearitaet
            piv = c
        M[c], M[piv] = M[piv], M[c]
        pz = M[c]
        for r in range(c + 1, n):
            f = M[r][c] / pz[c]
            if f == 0.0:
                continue
            zr = M[r]
            for k in range(c, n + 1):
                zr[k] -= f * pz[k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))
        x[r] = s / M[r][r]
    return x


# ------------------------------------------------------------------ Logit
class Logit:
    """Multinomiales Logit (K Klassen, letzte Klasse Referenz), L2-regularisiert,
    Newton-Verfahren mit Schrittweitenhalbierung. K = 2 ist der binaere Fall."""

    typ = "logit"

    def __init__(self, l2=1.0, max_iter=30, tol=1e-7):
        self.l2 = max(float(l2), 1e-3)
        self.max_iter = int(max_iter)
        self.tol = tol
        self.B = None      # (K-1) x (d+1), Spalte 0 = Achsenabschnitt
        self.K = None
        self.iterationen = 0

    # ---- Hilfen
    def _logits(self, x):
        return [sum(b * v for b, v in zip(bk, x)) for bk in self.B] + [0.0]

    def _ziel(self, Xe, y):
        s = 0.0
        for x, yi in zip(Xe, y):
            p = softmax(self._logits(x))
            s -= math.log(max(p[yi], 1e-300))
        s += 0.5 * self.l2 * sum(b * b for bk in self.B for b in bk[1:])
        return s

    def fit(self, X, y, K=None):
        self.K = K or (max(y) + 1)
        Xe = [[1.0] + list(x) for x in X]
        p_dim = len(Xe[0])
        Kr = self.K - 1
        self.B = [[0.0] * p_dim for _ in range(Kr)]
        ziel = self._ziel(Xe, y)
        for it in range(self.max_iter):
            self.iterationen = it + 1
            # Gradient und Hesse-Matrix
            g = [[0.0] * p_dim for _ in range(Kr)]
            H = [[0.0] * (Kr * p_dim) for _ in range(Kr * p_dim)]
            for x, yi in zip(Xe, y):
                p = softmax(self._logits(x))
                for k in range(Kr):
                    r = p[k] - (1.0 if yi == k else 0.0)
                    gk = g[k]
                    for j in range(p_dim):
                        gk[j] += r * x[j]
                xx = [[xj * xm for xm in x] for xj in x]
                for k in range(Kr):
                    for l in range(k, Kr):
                        w = p[k] * ((1.0 if k == l else 0.0) - p[l])
                        if w == 0.0:
                            continue
                        for j in range(p_dim):
                            Hz = H[k * p_dim + j]
                            xxj = xx[j]
                            base = l * p_dim
                            for m in range(p_dim):
                                Hz[base + m] += w * xxj[m]
            # Symmetrie und L2
            for k in range(Kr):
                for l in range(k + 1, Kr):
                    for j in range(p_dim):
                        for m in range(p_dim):
                            H[l * p_dim + m][k * p_dim + j] = H[k * p_dim + j][l * p_dim + m]
            for k in range(Kr):
                for j in range(1, p_dim):
                    g[k][j] += self.l2 * self.B[k][j]
                    H[k * p_dim + j][k * p_dim + j] += self.l2
            gv = [v for gk in g for v in gk]
            schritt = loese(H, gv)
            if max(abs(v) for v in schritt) < self.tol:
                break
            # Schrittweitenhalbierung
            alt = [bk[:] for bk in self.B]
            t = 1.0
            for _ in range(12):
                for k in range(Kr):
                    for j in range(p_dim):
                        self.B[k][j] = alt[k][j] - t * schritt[k * p_dim + j]
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
        return [softmax(self._logits([1.0] + list(x))) for x in X]

    def als_dict(self):
        return {"typ": self.typ, "l2": self.l2, "K": self.K, "B": self.B}

    @classmethod
    def aus_dict(cls, d):
        m = cls(l2=d["l2"])
        m.K = d["K"]
        m.B = d["B"]
        return m


# -------------------------------------------------------------------- MLP
class MLP:
    """Ein verstecktes tanh-Layer, Softmax-Ausgang, Adam, L2. Vollbatch."""

    typ = "mlp"

    def __init__(self, versteckt=8, l2=0.01, lernrate=0.02, epochen=200, seed=0):
        self.h = max(int(versteckt), 1)
        self.l2 = max(float(l2), 0.0)
        self.lr = float(lernrate)
        self.epochen = int(epochen)
        self.seed = seed
        self.W1 = self.b1 = self.W2 = self.b2 = None
        self.K = None

    def _vorwaerts(self, x):
        hid = [math.tanh(b + sum(w * v for w, v in zip(wz, x))) for wz, b in zip(self.W1, self.b1)]
        z = [b + sum(w * v for w, v in zip(wz, hid)) for wz, b in zip(self.W2, self.b2)]
        return hid, softmax(z)

    def fit(self, X, y, K=None):
        self.K = K or (max(y) + 1)
        d = len(X[0])
        rnd = random.Random(self.seed)
        s1 = 1.0 / math.sqrt(d)
        s2 = 1.0 / math.sqrt(self.h)
        self.W1 = [[rnd.uniform(-s1, s1) for _ in range(d)] for _ in range(self.h)]
        self.b1 = [0.0] * self.h
        self.W2 = [[rnd.uniform(-s2, s2) for _ in range(self.h)] for _ in range(self.K)]
        self.b2 = [0.0] * self.K
        params = [self.W1, self.b1, self.W2, self.b2]
        # Adam-Zustand in derselben Form wie die Parameter
        def nullen(p):
            return [nullen(v) if isinstance(v, list) else 0.0 for v in p]
        m = [nullen(p) for p in params]
        v = [nullen(p) for p in params]
        b1, b2, eps = 0.9, 0.999, 1e-8
        n = len(X)
        for ep in range(1, self.epochen + 1):
            gW1 = [[0.0] * d for _ in range(self.h)]
            gb1 = [0.0] * self.h
            gW2 = [[0.0] * self.h for _ in range(self.K)]
            gb2 = [0.0] * self.K
            for x, yi in zip(X, y):
                hid, p = self._vorwaerts(x)
                dz = [(pk - (1.0 if k == yi else 0.0)) / n for k, pk in enumerate(p)]
                dh = [0.0] * self.h
                for k in range(self.K):
                    gb2[k] += dz[k]
                    gz = gW2[k]
                    wz = self.W2[k]
                    for j in range(self.h):
                        gz[j] += dz[k] * hid[j]
                        dh[j] += dz[k] * wz[j]
                for j in range(self.h):
                    da = dh[j] * (1.0 - hid[j] * hid[j])
                    gb1[j] += da
                    gj = gW1[j]
                    for i in range(d):
                        gj[i] += da * x[i]
            for j in range(self.h):
                for i in range(d):
                    gW1[j][i] += self.l2 * self.W1[j][i]
            for k in range(self.K):
                for j in range(self.h):
                    gW2[k][j] += self.l2 * self.W2[k][j]
            grads = [gW1, gb1, gW2, gb2]
            korr1 = 1 - b1 ** ep
            korr2 = 1 - b2 ** ep
            for P, G, M, V in zip(params, grads, m, v):
                if isinstance(P[0], list):
                    for r in range(len(P)):
                        Pr, Gr, Mr, Vr = P[r], G[r], M[r], V[r]
                        for c in range(len(Pr)):
                            Mr[c] = b1 * Mr[c] + (1 - b1) * Gr[c]
                            Vr[c] = b2 * Vr[c] + (1 - b2) * Gr[c] * Gr[c]
                            Pr[c] -= self.lr * (Mr[c] / korr1) / (math.sqrt(Vr[c] / korr2) + eps)
                else:
                    for c in range(len(P)):
                        M[c] = b1 * M[c] + (1 - b1) * G[c]
                        V[c] = b2 * V[c] + (1 - b2) * G[c] * G[c]
                        P[c] -= self.lr * (M[c] / korr1) / (math.sqrt(V[c] / korr2) + eps)
        return self

    def predict_proba(self, X):
        return [self._vorwaerts(list(x))[1] for x in X]

    def als_dict(self):
        return {"typ": self.typ, "versteckt": self.h, "l2": self.l2, "lernrate": self.lr,
                "epochen": self.epochen, "K": self.K,
                "W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2}

    @classmethod
    def aus_dict(cls, d):
        m = cls(versteckt=d["versteckt"], l2=d["l2"], lernrate=d["lernrate"], epochen=d["epochen"])
        m.K = d["K"]
        m.W1, m.b1, m.W2, m.b2 = d["W1"], d["b1"], d["W2"], d["b2"]
        return m


MODELLTYPEN = {"logit": Logit, "mlp": MLP}


def modell_bauen(spez, seed=0):
    """Modell aus einer Hypothesen-Spezifikation ({"typ": ..., ...})."""
    typ = spez.get("typ", "logit")
    if typ == "logit":
        return Logit(l2=spez.get("l2", 1.0))
    if typ == "mlp":
        return MLP(versteckt=spez.get("versteckt", 8), l2=spez.get("l2", 0.01),
                   lernrate=spez.get("lernrate", 0.02), epochen=spez.get("epochen", 200),
                   seed=seed)
    raise ValueError("unbekannter Modelltyp %r" % typ)


def modell_aus_dict(d):
    return MODELLTYPEN[d["typ"]].aus_dict(d)
