"""Die Rechnung hinter dem Leaderboard.

Zwei Bloecke, die bewusst getrennt bleiben statt zu einer Note zu verschmelzen:

  Sofort      - verfuegbar in der Sekunde der Abgabe, misst *wie* jemand
                bewertet: Spreizung, Bias, Naehe zum Modell, Trennschaerfe.
  Verzoegert  - verfuegbar erst nach Auefloesung, misst *ob* jemand recht
                hatte: Brier-Score, Brier-Skill, Kalibrierungsfehler.

Der Sofort-Block ist der eigentliche Zweck von Stufe 0. Scouts geben laut
Diagnose gefuehlt gleiche Bewertungen ab; Spreizung und Trennschaerfe machen
genau das sichtbar, lange bevor die erste Prognose aufloest.

Dazu kommt der Audit-Block (Scout Rating Audit, Juni 2026): Zentraltendenz,
Rater-Strenge, Halo, Entkopplung und Attribut-Trennschaerfe. Das sind genau
die fuenf Groessen, die der Audit einmalig auf 187 Bewertungen gerechnet hat -
hier laufen sie fortlaufend auf den Abgaben der Liga mit.

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


def pearson(xs, ys):
    """Produkt-Moment-Korrelation. Der Audit misst Halo und Entkopplung damit;
    None, wenn eine Seite konstant ist - ein Scout ohne Streuung hat keinen
    messbaren Halo, und 0 waere die falsche Auskunft."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx, my = mittel(xs), mittel(ys)
    zx = sum((a - mx) ** 2 for a in xs)
    zy = sum((b - my) ** 2 for b in ys)
    if zx == 0 or zy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / math.sqrt(zx * zy)


def z_werte(xs):
    """Werte relativ zum eigenen Mittel und der eigenen Streuung. Der
    Strenge-Gap von 0,56 Notenpunkten zwischen zwei Scouts verschwindet
    dadurch; was bleibt, ist die Rangfolge innerhalb des Scouts."""
    s = stdabw(xs)
    if s is None or s == 0:
        return None
    m = mittel(xs)
    return [(x - m) / s for x in xs]


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


# ------------------------------------------------------------------ Audit-Block
# Die fuenf Diagnosen aus dem Scout Rating Audit, fortlaufend statt einmalig.

def zentraltendenz(werte):
    """Anteil des haeufigsten Werts. Der Audit fand 58 % Dreier auf der
    1-6-Skala und setzt als Ziel: keine Auspraegung ueber 35 %."""
    werte = [w for w in werte if w is not None]
    if not werte:
        return None
    haeufigkeit = {}
    for w in werte:
        haeufigkeit[w] = haeufigkeit.get(w, 0) + 1
    modal, n = max(haeufigkeit.items(), key=lambda kv: (kv[1], -kv[0]))
    return {
        "n": len(werte),
        "modalwert": modal,
        "anteil": round(n / len(werte), 3),
        "genutzte_stufen": len(haeufigkeit),
    }


def rater_strenge(werte_je_scout):
    """Mittelwert je Scout und die Spannweite dazwischen. Der Audit misst hier
    0,56 Notenpunkte zwischen Zoran und Miguel - bei identischer Skala."""
    mittel_je = {s: mittel(w) for s, w in werte_je_scout.items()
                 if [x for x in w if x is not None]}
    if len(mittel_je) < 2:
        return {"je_scout": {s: round(m, 2) for s, m in mittel_je.items()},
                "spanne": None}
    werte = list(mittel_je.values())
    return {
        "je_scout": {s: round(m, 2) for s, m in mittel_je.items()},
        "spanne": round(max(werte) - min(werte), 2),
        "strengster": min(mittel_je, key=mittel_je.get),
        "mildester": max(mittel_je, key=mittel_je.get),
    }


def halo(leitwerte, attribut_mittel):
    """Korrelation zwischen dem Leiturteil und dem Mittel der Attribute. Nahe 1
    heisst: das Gesamturteil ist nur ein Echo der Einzelnoten und traegt keine
    eigene Information. Der Audit misst r = 0,78."""
    return pearson(leitwerte, attribut_mittel)


def entkopplung(heute, ceiling):
    """Korrelation zwischen bewiesenem Niveau und Ceiling. Beide sollen
    Verschiedenes messen; der Audit findet r = 0,55 Gleichlauf."""
    return pearson(heute, ceiling)


def attribut_trennschaerfe(werte_je_attribut, sigma_grenze=0.4):
    """Streuung je Attribut ueber alle bewerteten Spieler. Unter der Grenze ist
    ein Attribut tot: es kostet Zeit und liefert keine Unterscheidung."""
    aus = {}
    for key, werte in werte_je_attribut.items():
        werte = [w for w in werte if w is not None]
        s = stdabw(werte)
        aus[key] = {
            "n": len(werte),
            "sigma": round(s, 2) if s is not None else None,
            "mittel": round(mittel(werte), 2) if werte else None,
            "tot": bool(s is not None and s < sigma_grenze),
        }
    return aus


def konflikt(scout_level, modell_level, abstand=2):
    """Scout und Modell sind sich uneinig. Der Audit nennt diese Faelle die
    wertvollste Review-Liste - dort steckt der meiste Erkenntnisgewinn."""
    if scout_level is None or modell_level is None:
        return None
    d = float(scout_level) - float(modell_level)
    if abs(d) < abstand:
        return None
    return {"differenz": round(d, 1),
            "richtung": "scout_hoeher" if d > 0 else "modell_hoeher"}


def perzentil_zu_level(perzentil, basis_level):
    """Die Bruecke aus dem Audit: das Daten-Perzentil verschiebt das bewiesene
    Liga-Niveau um hoechstens eine Stufe nach oben oder unten.

    Ausgangspunkt bleibt die Liga, in der der Spieler real gespielt hat -
    das Perzentil sagt nur, ob er dort ueber oder unter dem Schnitt liegt.
    """
    if perzentil is None or basis_level is None:
        return None
    p = float(perzentil)
    if p >= 90:
        v = 1.0
    elif p >= 70:
        v = 0.5
    elif p >= 50:
        v = 0.0
    elif p >= 30:
        v = -0.5
    else:
        v = -1.0
    return max(1.0, min(10.0, round(float(basis_level) + v, 1)))
