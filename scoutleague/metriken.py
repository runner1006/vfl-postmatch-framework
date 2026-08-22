"""Die Rechnung hinter dem Leaderboard.

Zwei Bloecke, die bewusst getrennt bleiben statt zu einer Note zu verschmelzen:

  Sofort      - verfuegbar in der Sekunde der Abgabe, misst *wie* jemand
                bewertet: Spreizung, Bias, Naehe zum Modell, Trennschaerfe.
  Verzoegert  - verfuegbar erst nach Auefloesung, misst *ob* jemand recht
                hatte: Brier-Score, Brier-Skill, Kalibrierungsfehler.

Der Sofort-Block ist der eigentliche Zweck von Stufe 0. Scouts geben laut
Diagnose gefuehlt gleiche Bewertungen ab; Spreizung und Trennschaerfe machen
genau das sichtbar, lange bevor die erste Prognose aufloest.

Keine externen Abhaengigkeiten - alles Standardbibliothek.
"""
import math

SKALA_MIN, SKALA_MAX = 1.0, 5.0
SPANNE = SKALA_MAX - SKALA_MIN


# ------------------------------------------------------------------ Grundlagen
def mittel(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def stdabw(xs):
    """Stichproben-Standardabweichung. Unter zwei Werten nicht definiert."""
    xs = list(xs)
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def raenge(xs):
    """Raenge mit Mittelwert bei Bindungen - Basis fuer Spearman."""
    paare = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(paare):
        j = i
        while j + 1 < len(paare) and xs[paare[j + 1]] == xs[paare[i]]:
            j += 1
        mittlerer = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[paare[k]] = mittlerer
        i = j + 1
    return r


def spearman(xs, ys):
    """Rangkorrelation. None, wenn zu wenige Punkte oder eine Seite konstant
    ist - bei einem Scout, der ueberall dieselbe 3 vergibt, gibt es keine
    Trennschaerfe zu messen, und 0 waere die falsche Auskunft."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = raenge(xs), raenge(ys)
    mx, my = mittel(rx), mittel(ry)
    zx = sum((a - mx) ** 2 for a in rx)
    zy = sum((b - my) ** 2 for b in ry)
    if zx == 0 or zy == 0:
        return None
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / math.sqrt(zx * zy)


# --------------------------------------------------------------- Sofort-Metrik
def modell_naehe(antworten, modell):
    """0-100. 100 = exakt die Modellerwartung, 0 = maximaler Abstand auf der
    Skala. Gemittelt ueber alle Fragen, zu denen das Modell eine Erwartung hat.
    Ausdruecklich kein Guetemass: naeher am Modell heisst nicht besser, es
    heisst nur weniger eigenstaendig."""
    diffs = [
        abs(float(antworten[k]) - float(v))
        for k, v in (modell or {}).items()
        if k in antworten and antworten[k] is not None
    ]
    if not diffs:
        return None
    return round(100.0 * (1.0 - mittel(diffs) / SPANNE), 1)


def prognose_naehe(prognosen, modell_prognosen):
    """0-100 gegen die Modellwahrscheinlichkeit. Sofortiges Feedback, solange
    die Realitaet noch nicht geantwortet hat."""
    diffs = [
        abs(float(prognosen[k]) - float(v))
        for k, v in (modell_prognosen or {}).items()
        if k in prognosen and prognosen[k] is not None
    ]
    if not diffs:
        return None
    return round(100.0 * (1.0 - mittel(diffs)), 1)


def spreizung(werte):
    """Standardabweichung der Leitfrage ueber alle Faelle eines Scouts."""
    s = stdabw(werte)
    return round(s, 2) if s is not None else None


def spreizungs_index(scout_sd, kohorten_sd):
    """Wie breit bewertet dieser Scout im Vergleich zum Feld? 1.0 = wie der
    Median der Kohorte, 0.5 = halb so breit (alles Mittelfeld), 1.5 = deutlich
    entschiedener."""
    if scout_sd is None or not kohorten_sd:
        return None
    return round(scout_sd / kohorten_sd, 2)


# ----------------------------------------------------------- Verzoegerte Metrik
def brier(paare):
    """Mittlerer quadratischer Fehler ueber (Wahrscheinlichkeit, Ergebnis).
    0 ist perfekt, 0.25 ist Muenzwurf, 1.0 ist maximal daneben."""
    paare = [(float(p), float(o)) for p, o in paare]
    if not paare:
        return None
    return round(sum((p - o) ** 2 for p, o in paare) / len(paare), 4)


def brier_skill(paare, basisrate):
    """Brier gegen die naive Vorhersage 'immer die Basisrate'. Positiv heisst
    besser als die Basisrate zu kennen, negativ heisst schlechter."""
    bs = brier(paare)
    if bs is None or basisrate is None:
        return None
    basis = brier([(basisrate, o) for _, o in paare])
    if not basis:
        return None
    return round(1.0 - bs / basis, 3)


def kalibrierungsfehler(paare, bins=5):
    """Gewichteter Abstand zwischen zugesagter und eingetretener Haeufigkeit
    (ECE). 0 heisst: wer 70 % sagt, liegt in 70 % der Faelle richtig."""
    paare = [(float(p), float(o)) for p, o in paare]
    if not paare:
        return None
    gesamt = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        im_bin = [
            (p, o) for p, o in paare if (p >= lo and (p < hi or (b == bins - 1 and p <= hi)))
        ]
        if not im_bin:
            continue
        gesamt += len(im_bin) * abs(mittel([p for p, _ in im_bin])
                                    - mittel([o for _, o in im_bin]))
    return round(gesamt / len(paare), 3)


def kalibrierungskurve(paare, bins=5):
    """Punkte fuer das Reliability-Diagramm im Scout-Profil."""
    paare = [(float(p), float(o)) for p, o in paare]
    kurve = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        im_bin = [
            (p, o) for p, o in paare if (p >= lo and (p < hi or (b == bins - 1 and p <= hi)))
        ]
        kurve.append({
            "von": round(lo, 2), "bis": round(hi, 2), "n": len(im_bin),
            "gesagt": round(mittel([p for p, _ in im_bin]), 3) if im_bin else None,
            "eingetreten": round(mittel([o for _, o in im_bin]), 3) if im_bin else None,
        })
    return kurve


# --------------------------------------------------------------- Zusammenfuegen
def scout_metriken(abgaben, kohorte, aufloesungen, leitfrage="gesamt"):
    """Alle Kennzahlen eines Scouts.

    abgaben      Liste von {"fall_id", "antworten", "prognosen", "modell"}
                 (modell = {"bewertung": {...}, "prognose": {...}})
    kohorte      {fall_id: {frage: [Werte aller Scouts]}} fuer Bias und
                 Kohorten-Vergleich
    aufloesungen {(fall_id, frage): 0|1}
    """
    leit_scout, leit_modell = [], []
    naehen, prog_naehen = [], []
    bias_diffs = []
    prog_paare = []
    paare_je_frage = {}

    for a in abgaben:
        antw = a.get("antworten") or {}
        prog = a.get("prognosen") or {}
        modell = a.get("modell") or {}
        m_bew = modell.get("bewertung") or {}
        m_prog = modell.get("prognose") or {}

        if antw.get(leitfrage) is not None:
            leit_scout.append(float(antw[leitfrage]))
            if m_bew.get(leitfrage) is not None:
                leit_modell.append(float(m_bew[leitfrage]))
            andere = (kohorte.get(a["fall_id"]) or {}).get(leitfrage) or []
            if len(andere) >= 2:
                bias_diffs.append(float(antw[leitfrage]) - mittel(andere))

        n = modell_naehe(antw, m_bew)
        if n is not None:
            naehen.append(n)
        pn = prognose_naehe(prog, m_prog)
        if pn is not None:
            prog_naehen.append(pn)

        for frage, p in prog.items():
            if p is None:
                continue
            erg = aufloesungen.get((a["fall_id"], frage))
            if erg is None:
                continue
            prog_paare.append((float(p), float(erg)))
            paare_je_frage.setdefault(frage, []).append((float(p), float(erg)))

    sd = spreizung(leit_scout)
    # Trennschaerfe nur, wenn Scout und Modell zu denselben Faellen etwas sagen
    trenn = (spearman(leit_scout, leit_modell)
             if len(leit_scout) == len(leit_modell) else None)

    return {
        "n_faelle": len(abgaben),
        "spreizung": sd,
        "bias": round(mittel(bias_diffs), 2) if bias_diffs else None,
        "modell_naehe": round(mittel(naehen), 1) if naehen else None,
        "prognose_naehe": round(mittel(prog_naehen), 1) if prog_naehen else None,
        "trennschaerfe": round(trenn, 2) if trenn is not None else None,
        "n_aufgeloest": len(prog_paare),
        "brier": brier(prog_paare),
        "kalibrierungsfehler": kalibrierungsfehler(prog_paare),
        "kalibrierungskurve": kalibrierungskurve(prog_paare),
        "_paare_je_frage": paare_je_frage,
    }


def basisraten(alle_aufloesungen):
    """Eintrittshaeufigkeit je Prognosefrage ueber alle aufgeloesten Faelle.
    Referenz fuer den Brier-Skill - ohne sie ist ein Brier von 0.18 eine Zahl
    ohne Massstab."""
    nach_frage = {}
    for (_fall, frage), erg in alle_aufloesungen.items():
        nach_frage.setdefault(frage, []).append(float(erg))
    return {f: mittel(v) for f, v in nach_frage.items()}


def skill_gesamt(paare_je_frage, raten):
    """Brier-Skill ueber alle Fragen, jede gegen ihre eigene Basisrate."""
    zaehler, nenner = 0.0, 0.0
    for frage, paare in paare_je_frage.items():
        rate = raten.get(frage)
        if rate is None or not paare:
            continue
        zaehler += sum((p - o) ** 2 for p, o in paare)
        nenner += sum((rate - o) ** 2 for _, o in paare)
    if nenner <= 0:
        return None
    return round(1.0 - zaehler / nenner, 3)
