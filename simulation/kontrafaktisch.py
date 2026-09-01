"""Kontrafaktische Vergleiche: was aendert sich, wenn genau eines anders ist.

Der Zweck der ganzen Engine. Eine einzelne Simulation ist wertlos - sie ist
eine Stichprobe aus einem sehr breiten Zufallsprozess. Aussagekraft entsteht
erst aus dem paarweisen Vergleich vieler Wiederholungen, in denen alles gleich
ist ausser der einen Aenderung.

Gemeinsame Zufallszahlen
------------------------
Basis und Variante laufen je Wiederholung mit **demselben Startwert**. Ohne das
verschwindet jeder realistische Effekt im Rauschen: die Streuung des xG einer
einzelnen Simulation liegt in der Groessenordnung des Effekts, den ein
Spielertausch ueberhaupt haben kann. Mit gemeinsamen Zufallszahlen laufen beide
Arme bis zur ersten wirksamen Abweichung identisch, und die Differenz misst die
Aenderung statt der Wuerfel. Ausgewiesen wird deshalb immer die **gepaarte**
Differenz, nie der Unterschied zweier Mittelwerte.

Was hier nicht behauptet wird
-----------------------------
Das Vertrauensintervall beschreibt die Unsicherheit *innerhalb des Modells*.
Es sagt nichts darueber, ob das Modell die Wirklichkeit trifft. Ein enges
Intervall um einen Effekt von +0.3 xG heisst: das Modell ist sich sicher - nicht:
die Mannschaft gewinnt 0.3 xG. Die Kalibrierungsgrenzen in der README gelten
unveraendert weiter.
"""
import random
import statistics

import raumkontrolle as R
import spiel as S
import spieler as SP
import taktik as T


# ------------------------------------------------------------------ Metriken
def metriken(sp):
    """Auswertbare Groessen eines Laufs, teamweise als (heim, gast)."""
    b = sp.bericht()
    lage = sp.lage
    aus = {
        "tore": tuple(b["tore"]),
        "xg": tuple(b["xg"]),
        "schuesse": tuple(b["schuesse"]),
        "ballbesitz": tuple(b["ballbesitz"]),
        "passquote": tuple(b["passquote"]),
        "paesse_an": tuple(b["paesse_an"]),
        "laufdistanz_km": tuple(b["laufdistanz"]),
        "sprint_m": tuple(b["sprintdistanz"]),
        "energie_ende": tuple(b["energie_ende"]),
    }
    aus.update(sp.raumauswertung())
    return aus


def _bootstrap(werte, n=4000, alpha=0.05, seed=12345):
    """Perzentil-Bootstrap fuer den Mittelwert gepaarter Differenzen."""
    if not werte:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    m = len(werte)
    mittel = sum(werte) / m
    ziehungen = []
    for _ in range(n):
        s = 0.0
        for _ in range(m):
            s += werte[rng.randrange(m)]
        ziehungen.append(s / m)
    ziehungen.sort()
    lo = ziehungen[int(alpha / 2 * n)]
    hi = ziehungen[int((1 - alpha / 2) * n) - 1]
    return (mittel, lo, hi)


# ------------------------------------------------------------------- Vergleich
class Vergleich:
    """Ergebnis eines Zwei-Arm-Vergleichs."""

    def __init__(self, name, basis, variante, n):
        self.name = name
        self.basis = basis            # Liste der Metrikdicts
        self.variante = variante
        self.n = n

    def differenz(self, metrik, team=0):
        paare = []
        for a, b in zip(self.basis, self.variante):
            va, vb = a.get(metrik), b.get(metrik)
            if va is None or vb is None:
                continue
            if isinstance(va, tuple):
                va, vb = va[team], vb[team]
            paare.append(vb - va)
        return paare

    def bericht(self, metriken_liste=None, team=0):
        namen = metriken_liste or [
            "xg", "schuesse", "ballbesitz", "passquote", "abwehrhoehe_m",
            "ppda", "gefahrflaeche", "strafraumeintritte", "laufdistanz_km",
        ]
        zeilen = []
        for m in namen:
            d = self.differenz(m, team)
            if not d:
                continue
            mittel, lo, hi = _bootstrap(d)
            basiswerte = [(a[m][team] if isinstance(a[m], tuple) else a[m])
                          for a in self.basis if m in a]
            zeilen.append(dict(
                metrik=m,
                basis=round(statistics.fmean(basiswerte), 3),
                differenz=round(mittel, 3),
                ki_unten=round(lo, 3),
                ki_oben=round(hi, 3),
                deutlich=(lo > 0.0 or hi < 0.0),
            ))
        return zeilen

    def tabelle(self, metriken_liste=None, team=0):
        zeilen = self.bericht(metriken_liste, team)
        breite = max((len(z["metrik"]) for z in zeilen), default=10)
        kopf = "%-*s %10s %10s %20s %s" % (breite, "Metrik", "Basis",
                                           "Differenz", "95%-Intervall", "")
        out = [self.name, "n = %d gepaarte Wiederholungen" % self.n, "", kopf,
               "-" * len(kopf)]
        for z in zeilen:
            out.append("%-*s %10.3f %+10.3f   [%+8.3f, %+8.3f] %s" % (
                breite, z["metrik"], z["basis"], z["differenz"],
                z["ki_unten"], z["ki_oben"], "  deutlich" if z["deutlich"] else ""))
        return "\n".join(out)


def vergleiche(bauer, aenderung, n=20, dauer=600.0, name="Vergleich",
              startseed=0, fortschritt=None):
    """Zwei Arme gepaart simulieren und die Differenzen auswerten.

    `bauer(seed)` liefert ein fertig aufgestelltes `spiel.Spiel`.
    `aenderung(spiel)` veraendert genau eine Sache daran - Attribute eines
    Spielers, eine Mannschaftsanweisung, eine Formation.

    Beide Arme werden mit demselben `seed` gebaut, damit identische
    Zufallsfolgen entstehen.
    """
    basis, variante = [], []
    for i in range(n):
        seed = startseed + i
        a = bauer(seed)
        a.laufen(dauer)
        basis.append(metriken(a))

        b = bauer(seed)
        aenderung(b)
        b.laufen(dauer)
        variante.append(metriken(b))

        if fortschritt:
            fortschritt(i + 1, n)
    return Vergleich(name, basis, variante, n)


# --------------------------------------------------------- Fertige Fragen
def spielertausch(bauer, team, nummer, neue_attribute, **kw):
    """"Was passiert, wenn Spieler A statt Spieler B spielt?"

    `neue_attribute` ist ein `spieler.Attribute` oder ein Dict von Aenderungen.
    """
    def aendern(sp):
        for s in sp.lage.mannschaft[team]:
            if s.nummer == nummer:
                if isinstance(neue_attribute, SP.Attribute):
                    s.attribute = neue_attribute
                else:
                    s.attribute = s.attribute.kopie(**neue_attribute)
                return
        raise KeyError("Spieler mit Nummer %d nicht in Team %d" % (nummer, team))
    return vergleiche(bauer, aendern, name=kw.pop("name", "Spielertausch"), **kw)


def anweisung_aendern(bauer, team, **kw):
    """"Was passiert, wenn wir hoeher verteidigen / anders pressen?" """
    aenderungen = {k: v for k, v in kw.items()
                   if k in T.Teamanweisung.__slots__}
    rest = {k: v for k, v in kw.items() if k not in aenderungen}

    def aendern(sp):
        sp.lage.anweisung[team] = sp.lage.anweisung[team].kopie(**aenderungen)
        if "formation" in aenderungen:
            sp._grundpositionen_setzen()
    name = rest.pop("name", "Anweisung: " + ", ".join(
        "%s=%s" % (k, v) for k, v in aenderungen.items()))
    return vergleiche(bauer, aendern, name=name, **rest)


def formationswechsel(bauer, team, formation, **kw):
    """"Was passiert, wenn wir statt 4-2-3-1 ein 3-4-3 spielen?" """
    def aendern(sp):
        sp.lage.anweisung[team] = sp.lage.anweisung[team].kopie(formation=formation)
        sp._grundpositionen_setzen()
        sp.aufstellen(anstoss_team=0)
    return vergleiche(bauer, aendern,
                     name=kw.pop("name", "Formation -> %s" % formation), **kw)


# ------------------------------------------------------- Situationsanalyse
def situation_fortschreiben(sp, dauer=10.0, wiederholungen=60, marken=(5.0, 10.0),
                            startseed=0):
    """"Welche Raeume entstehen nach 5 bis 10 Sekunden dieser Situation?"

    Nimmt den aktuellen Zustand als Ausgangslage, laesst ihn `wiederholungen`
    mal mit verschiedenen Zufallsfolgen weiterlaufen und misst an den
    Zeitmarken die Verteilung von Ballort, Raumkontrolle und Gefahr.

    Das ist der Modus, der einer Trainerfrage am naechsten kommt: nicht "wie
    endet das Spiel", sondern "was passiert in den naechsten Sekunden, und wie
    sicher ist das".
    """
    zustand = _zustand_sichern(sp)
    ergebnis = {m: [] for m in marken}
    for w in range(wiederholungen):
        klon = _zustand_laden(sp, zustand, seed=startseed + w)
        for marke in sorted(marken):
            while klon.lage.zeit < zustand["zeit"] + marke:
                klon.schritt()
            ergebnis[marke].append(_momentaufnahme(klon))
    return {m: _verdichten(v) for m, v in ergebnis.items()}


def _zustand_sichern(sp):
    return dict(
        zeit=sp.lage.zeit,
        ball=(sp.lage.ball.pos, sp.lage.ball.v, sp.lage.ball.drall,
              None if sp.lage.ball.traeger is None
              else (sp.lage.ball.traeger.team, sp.lage.ball.traeger.nummer)),
        spieler=[[(s.pos, s.v, s.blick, s.energie) for s in elf]
                 for elf in sp.lage.mannschaft],
        richtung=list(sp.lage.richtung),
        phasenbesitz=sp.lage.phasenbesitz,
    )


def _zustand_laden(sp, zustand, seed):
    """Neues Spiel mit identischer Ausgangslage, aber eigener Zufallsfolge."""
    heim = [_spieler_klon(s) for s in sp.lage.mannschaft[0]]
    gast = [_spieler_klon(s) for s in sp.lage.mannschaft[1]]
    klon = S.Spiel(heim, gast, sp.lage.anweisung[0], sp.lage.anweisung[1],
                   seed=seed, dt=sp.dt, aufzeichnen=sp.aufzeichnen,
                   aufzeichnungsrate=sp.rate)
    klon.lage.richtung = list(zustand["richtung"])
    klon.lage.zeit = zustand["zeit"]
    klon.lage.phasenbesitz = zustand["phasenbesitz"]
    for team, elf in enumerate(klon.lage.mannschaft):
        for s, (pos, v, blick, energie) in zip(elf, zustand["spieler"][team]):
            s.pos, s.v, s.blick, s.energie = pos, v, blick, energie
    klon.lage.ball.pos, klon.lage.ball.v, klon.lage.ball.drall = zustand["ball"][:3]
    klon.standard = None
    tr = zustand["ball"][3]
    if tr is not None:
        for s in klon.lage.mannschaft[tr[0]]:
            if s.nummer == tr[1]:
                klon.lage.ball.traeger = s
                s.am_ball = True
    return klon


def _spieler_klon(s):
    neu = SP.Spieler(s.name, s.nummer, s.team, s.rolle,
                     s.attribute.kopie(), s.ist_torwart)
    neu.pos, neu.v, neu.blick, neu.energie = s.pos, s.v, s.blick, s.energie
    return neu


def _momentaufnahme(sp):
    lage = sp.lage
    h, g = R.kontrollierte_flaeche(lage.mannschaft[0], lage.mannschaft[1],
                                   lage.richtung[0], nx=24, ny=16,
                                   nur_gefaehrlich=True)
    return dict(
        ball_x=lage.ball.pos[0] * lage.richtung[0],
        ball_y=lage.ball.pos[1] * lage.richtung[0],
        besitz=(-1 if lage.phasenbesitz is None else lage.phasenbesitz),
        gefahr_heim=h, gefahr_gast=g,
        xg_heim=sp.statistik["xg"][0], xg_gast=sp.statistik["xg"][1],
    )


def _verdichten(liste):
    aus = {}
    for schluessel in ("ball_x", "ball_y", "gefahr_heim", "gefahr_gast"):
        werte = sorted(d[schluessel] for d in liste)
        n = len(werte)
        aus[schluessel] = dict(
            median=round(werte[n // 2], 3),
            p10=round(werte[int(n * 0.10)], 3),
            p90=round(werte[int(n * 0.90)], 3),
        )
    aus["ballbesitz_heim"] = round(
        sum(1 for d in liste if d["besitz"] == 0) / len(liste), 3)
    aus["n"] = len(liste)
    return aus
