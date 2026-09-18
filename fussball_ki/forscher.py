"""Die Forscher: wer Hypothesen vorschlaegt und wer die Erkenntnisse fortschreibt.

Beide haben dieselbe Schnittstelle:

    vorschlagen(kontext)  -> Liste von Hypothesen-Vorschlaegen (Dicts)
    reflektieren(kontext) -> neuer Text fuer wissen/erkenntnisse.md

ClaudeForscher   ruft ein Claude-Modell ueber das Anthropic-SDK. Der Forscher
                 bekommt seine eigenen Erkenntnisse aus der Vorrunde vorgelegt
                 und schreibt sie am Ende der Runde neu - das Sprachmodell lernt
                 so seine eigenen Anweisungen. Braucht ANTHROPIC_API_KEY.
OfflineForscher  evolutionaere Suche plus regelbasierte Destillation. Kein
                 Netz, deterministisch bei gleichem Seed. Dient als Ersatz,
                 wenn der Online-Forscher ausfaellt, und als Pruefstand.
"""
import json
import random

from .hypothese import SCHEMA, startpaket

STANDARD_MODELL = "claude-opus-5"


class ForscherFehler(RuntimeError):
    pass


# ================================================================ Offline
class OfflineForscher:
    name = "offline"

    def __init__(self, seed=0):
        self.rnd = random.Random(seed)

    # ------------------------------------------------------------ vorschlagen
    def vorschlagen(self, kontext):
        n = kontext["anzahl"]
        tabelle = kontext["tabelle"]
        rang = kontext["rangliste"]
        bekannt = set(kontext["kennungen"])
        if not rang:
            return startpaket(tabelle.aufgabe)[:n]
        eltern = [e["hypothese"] for e in rang[:3]]
        out = []
        versuche = 0
        from .hypothese import pruefen
        while len(out) < n and versuche < 60:
            versuche += 1
            basis = self.rnd.choice(eltern)
            kind, was = self._mutieren(basis, tabelle)
            hyp, fehler = pruefen(kind, tabelle)
            if fehler or hyp["kennung"] in bekannt:
                continue
            bekannt.add(hyp["kennung"])
            kind["begruendung"] = "Offline-Suche, Runde %s: %s (Elternteil: %s)" % (
                kontext["runde"], was, basis["name"])
            out.append(kind)
        return out

    @staticmethod
    def _kurzname(name):
        """Suffixe frueherer Mutationen abstreifen, damit Namen lesbar bleiben."""
        import re
        n = re.sub(r"\s*\((l2[^)]*|global-z|gruppe-z)\)", "", name)
        n = re.sub(r"\s+als (MLP|Logit)$", "", n)
        return n.strip()[:60]

    def _mutieren(self, basis, tabelle):
        kind = json.loads(json.dumps(basis))
        kind.pop("kennung", None)
        basis = dict(basis, name=self._kurzname(basis["name"]))
        frei = [m for m in tabelle.merkmale if m not in kind["merkmale"]]
        ops = ["dazu", "dazu", "weg", "l2", "abgeleitet", "typ", "standardisierung"]
        op = self.rnd.choice(ops)
        if op == "dazu" and frei:
            m = self.rnd.choice(frei)
            kind["merkmale"].append(m)
            kind["name"] = "%s + %s" % (basis["name"], m)
            return kind, "Merkmal %s hinzugefuegt" % m
        if op == "weg" and len(kind["merkmale"]) + len(kind["abgeleitet"]) > 1:
            if kind["merkmale"] and (not kind["abgeleitet"] or self.rnd.random() < 0.7):
                m = kind["merkmale"].pop(self.rnd.randrange(len(kind["merkmale"])))
            else:
                m = kind["abgeleitet"].pop(self.rnd.randrange(len(kind["abgeleitet"])))["name"]
            kind["name"] = "%s - %s" % (basis["name"], m)
            return kind, "Merkmal %s entfernt" % m
        if op == "l2":
            f = self.rnd.choice([0.1, 0.3, 3.0, 10.0])
            kind["modell"]["l2"] = round(kind["modell"].get("l2", 1.0) * f, 4)
            kind["name"] = "%s (l2=%s)" % (basis["name"], kind["modell"]["l2"])
            return kind, "Regularisierung mal %s" % f
        if op == "abgeleitet":
            namen = list(kind["merkmale"]) + [a["name"] for a in kind["abgeleitet"]]
            pool = namen if len(namen) >= 2 else namen + frei
            if len(pool) >= 2:
                a, b = self.rnd.sample(pool, 2)
                art = self.rnd.choice(["diff", "prod", "quot"])
                formel = {"diff": "%s - %s", "prod": "%s * %s", "quot": "%s / (abs(%s) + 0.1)"}[art] % (a, b)
                an = "%s_%s_%s" % (art, a, b)
                kind["abgeleitet"].append({"name": an[:60], "formel": formel})
                kind["name"] = "%s + %s" % (basis["name"], an[:30])
                return kind, "abgeleitetes Merkmal %s = %s" % (an[:60], formel)
        if op == "typ":
            if kind["modell"]["typ"] == "logit":
                kind["modell"] = {"typ": "mlp", "l2": 0.01, "versteckt": self.rnd.choice([4, 6, 8, 12]),
                                  "epochen": 150, "lernrate": 0.02}
                kind["name"] = "%s als MLP" % basis["name"]
                return kind, "Modelltyp auf MLP gewechselt"
            kind["modell"] = {"typ": "logit", "l2": 1.0}
            kind["name"] = "%s als Logit" % basis["name"]
            return kind, "Modelltyp auf Logit gewechselt"
        if op == "standardisierung":
            kind["standardisierung"] = "gruppe" if kind["standardisierung"] == "global" else "global"
            kind["name"] = "%s (%s-z)" % (basis["name"], kind["standardisierung"])
            return kind, "Standardisierung auf %s" % kind["standardisierung"]
        # Rueckfall: Regularisierung leicht aendern
        kind["modell"]["l2"] = round(kind["modell"].get("l2", 1.0) * 0.5, 4)
        kind["name"] = "%s (l2 halbiert)" % basis["name"]
        return kind, "Regularisierung halbiert"

    # ----------------------------------------------------------- reflektieren
    def reflektieren(self, kontext):
        teile = ["# Erkenntnisse", "",
                 "Automatisch destilliert vom Offline-Forscher nach Runde %d. Aussagen sind "
                 "Mittelwerte ueber alle bisherigen Experimente, keine Kausalbefunde." % kontext["runde"], ""]
        for aufgabe, k in kontext["je_aufgabe"].items():
            rang = k["rangliste"]
            teile.append("## Aufgabe %s" % aufgabe)
            if not rang:
                teile.append("Noch keine erfolgreichen Experimente.")
                teile.append("")
                continue
            best = rang[0]
            r = best["ergebnis"]["metriken"]
            teile.append("**Bestes Modell:** %s (Log-Loss CV %s, Basisrate %s%s)." % (
                best["hypothese"]["name"], best["ergebnis"]["hauptmetrik"], r.get("logloss_basis"),
                (", Framework %s" % r["logloss_framework"]) if "logloss_framework" in r else ""))
            if k.get("benchmark"):
                teile.append("Benchmark des Frameworks: %s" % json.dumps(k["benchmark"], ensure_ascii=False))
            teile.append("")
            teile.append("### Was traegt")
            for m, delta, n in self._merkmalseffekte(rang)[:6]:
                if delta < 0:
                    teile.append("- %s: Modelle mit diesem Merkmal im Mittel %.4f besser (n=%d)" % (m, -delta, n))
            teile.append("")
            teile.append("### Was nicht traegt")
            for m, delta, n in reversed(self._merkmalseffekte(rang)[-6:]):
                if delta > 0:
                    teile.append("- %s: Modelle mit diesem Merkmal im Mittel %.4f schlechter (n=%d)" % (m, delta, n))
            teile.append("")
            typen = {}
            for e in rang:
                typen.setdefault(e["hypothese"]["modell"]["typ"], []).append(e["ergebnis"]["hauptmetrik"])
            teile.append("### Modelltypen")
            for t, werte in typen.items():
                teile.append("- %s: bestes %.4f, Mittel %.4f ueber %d Experimente" % (
                    t, min(werte), sum(werte) / len(werte), len(werte)))
            teile.append("")
            teile.append("### Regeln fuer die naechste Runde")
            oben = best["hypothese"]["merkmale"][:5]
            teile.append("- Vom besten Modell ausgehen; Kern behalten: %s." % ", ".join(oben))
            teile.append("- Merkmale aus 'Was nicht traegt' nur mit neuer Begruendung erneut pruefen.")
            teile.append("- Je Runde mindestens eine Hypothese, die etwas Neues prueft "
                         "(anderer Modelltyp, abgeleitetes Merkmal, andere Standardisierung).")
            teile.append("")
        return "\n".join(teile)

    @staticmethod
    def _merkmalseffekte(rang):
        """(Merkmal, Delta Hauptmetrik mit minus ohne, n mit) - negativ heisst hilfreich."""
        alle = set()
        for e in rang:
            alle.update(e["hypothese"]["merkmale"])
        out = []
        for m in alle:
            mit = [e["ergebnis"]["hauptmetrik"] for e in rang if m in e["hypothese"]["merkmale"]]
            ohne = [e["ergebnis"]["hauptmetrik"] for e in rang if m not in e["hypothese"]["merkmale"]]
            if len(mit) >= 2 and len(ohne) >= 2:
                out.append((m, sum(mit) / len(mit) - sum(ohne) / len(ohne), len(mit)))
        return sorted(out, key=lambda t: t[1])


# ================================================================= Claude
SYSTEM_FORSCHER = """Du bist der Forscher einer selbstlernenden Fussball-KI. Du baust keine Modelle
selbst - du schlaegst Hypothesen vor, ein Rechenkern prueft sie an echten Daten und
traegt die Ergebnisse in eine Rangliste ein. Deine Erkenntnisse aus frueheren Runden
hast du selbst geschrieben; sie sind dein einziges Gedaechtnis ueber die Rangliste hinaus.

Regeln:
- Nur Merkmale aus dem Katalog. Abgeleitete Merkmale als Formel ueber Katalognamen:
  Arithmetik (+ - * / **), Klammern, Zahlen und die Funktionen abs, sqrt, log, log1p, exp,
  min, max. Keine anderen Namen, keine Zuweisungen.
- Modelltypen: "logit" (multinomiales Logit, Newton, L2 = l2) oder "mlp" (ein verstecktes
  tanh-Layer mit `versteckt` Neuronen, Adam, `epochen`, `lernrate`, L2 = l2). Fuer logit
  trotzdem alle Felder fuellen (versteckt, epochen, lernrate werden ignoriert).
- Standardisierung "global" (z ueber die Trainingsmenge) oder "gruppe" (z je Gruppe:
  Saison bei aufstieg, Mannschaft bei spiel - loescht Mannschaftsniveau-Unterschiede).
- Hoechstens 25 Merkmale je Hypothese. Fehlende Werte werden auf das Trainingsmittel gesetzt.
- Keine Hypothese wiederholen, die in der Rangliste schon steht. Kleine, gezielte
  Aenderungen am besten Modell sind erwuenscht, aber mindestens eine Hypothese je Runde
  soll etwas grundsaetzlich Neues pruefen.
- Merkmale, die das Ergebnis selbst sind (Tore, Punkte), gibt es im Katalog absichtlich nicht.
- Jede Hypothese traegt eine fussballfachliche Begruendung und eine pruefbare Erwartung.
- Hauptmetrik ist der Log-Loss der Kreuzvalidierung (kleiner ist besser). Zum Vergleich
  stehen die Basisrate (Klassenhaeufigkeit) und der Framework-Benchmark in der Rangliste.

Antworte ausschliesslich mit dem JSON-Objekt nach Schema.
"""

SYSTEM_LEHRER = """Du bist der Lehrer einer selbstlernenden Fussball-KI. Nach jeder Runde schreibst du
die Datei erkenntnisse.md neu. Sie ist das einzige Langzeitgedaechtnis des Forschers und
wird ihm in der naechsten Runde woertlich vorgelegt - du schreibst also die Anweisungen,
mit denen das naechste Sprachmodell arbeitet.

Regeln:
- Nur belegte Aussagen mit Zahlen aus der Rangliste; Vermutungen ausdruecklich als solche.
- Bewaehrte Regeln der alten Fassung behalten, widerlegte streichen, nichts Doppeltes.
- Struktur (Markdown): # Erkenntnisse, dann je Aufgabe ## Aufgabe <name> mit
  ### Was traegt, ### Was nicht traegt, ### Offene Fragen, ### Regeln fuer die naechste Runde.
- Hoechstens etwa 700 Woerter. Deutsch. Keine Einleitung, keine Hoeflichkeiten.
"""


class ClaudeForscher:
    def __init__(self, modell=None, client=None, effort="high"):
        self.modell = modell or STANDARD_MODELL
        self.effort = effort
        self.name = "claude:" + self.modell
        self._client = client
        self.letzte_nutzung = None

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ForscherFehler("Das Paket 'anthropic' fehlt: pip install anthropic")
            self._client = anthropic.Anthropic()
        return self._client

    # -------------------------------------------------------------- Anfrage
    def _anfrage(self, system, nutzer, schema=None, max_tokens=16000):
        try:
            import anthropic
        except ImportError:
            anthropic = None
        output_config = {"effort": self.effort}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        try:
            antwort = self.client.beta.messages.create(
                model=self.modell,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": nutzer}],
                output_config=output_config,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except Exception as e:  # in eine Fehlerkette uebersetzen, die der Aufrufer versteht
            if anthropic is not None:
                if isinstance(e, anthropic.AuthenticationError):
                    raise ForscherFehler("Anthropic: Schluessel ungueltig oder fehlt (ANTHROPIC_API_KEY)")
                if isinstance(e, anthropic.RateLimitError):
                    raise ForscherFehler("Anthropic: Ratenlimit erreicht - spaeter erneut versuchen")
                if isinstance(e, anthropic.APIStatusError):
                    raise ForscherFehler("Anthropic: HTTP %s - %s" % (e.status_code, e.message))
                if isinstance(e, anthropic.APIConnectionError):
                    raise ForscherFehler("Anthropic: keine Verbindung - %s" % e)
            raise ForscherFehler("Anthropic: %s" % e)
        if antwort.stop_reason == "refusal":
            grund = getattr(antwort, "stop_details", None)
            raise ForscherFehler("Anthropic: Anfrage abgelehnt (%s)" % (
                getattr(grund, "category", None) or "ohne Kategorie"))
        if antwort.stop_reason == "max_tokens":
            raise ForscherFehler("Anthropic: Antwort abgeschnitten (max_tokens=%d)" % max_tokens)
        self.letzte_nutzung = getattr(antwort, "usage", None)
        return "".join(b.text for b in antwort.content if getattr(b, "type", "") == "text")

    # ---------------------------------------------------------- vorschlagen
    def vorschlagen(self, kontext):
        tabelle = kontext["tabelle"]
        system = SYSTEM_FORSCHER + "\n\nMerkmalskatalog fuer Aufgabe %s:\n%s\n" % (
            tabelle.aufgabe, kontext["katalog"])
        nutzer = "\n".join([
            "Runde %d, Aufgabe: %s" % (kontext["runde"], tabelle.aufgabe),
            "Frage: %s" % tabelle.frage,
            "Klassen: %s" % ", ".join(tabelle.klassen),
            "Zeilen: %d (davon Kreuzvalidierung auf %d)" % (len(tabelle), kontext.get("n_lern", len(tabelle))),
            "Framework-Benchmark: %s" % json.dumps(tabelle.benchmark, ensure_ascii=False),
            "",
            "Deine Erkenntnisse aus frueheren Runden:",
            kontext["erkenntnisse"],
            "",
            "Rangliste bisheriger Experimente:",
            kontext["rangliste_text"],
            "",
            "Schlage genau %d neue Hypothesen vor." % kontext["anzahl"],
        ])
        text = self._anfrage(system, nutzer, schema=SCHEMA)
        try:
            daten = json.loads(text)
        except json.JSONDecodeError as e:
            raise ForscherFehler("Anthropic: Antwort ist kein JSON (%s)" % e)
        hyps = daten.get("hypothesen") if isinstance(daten, dict) else None
        if not isinstance(hyps, list):
            raise ForscherFehler("Anthropic: Antwort ohne 'hypothesen'")
        return hyps[:kontext["anzahl"]]

    # --------------------------------------------------------- reflektieren
    def reflektieren(self, kontext):
        teile = ["Runde %d ist gerechnet." % kontext["runde"], "",
                 "Bisherige Fassung der Erkenntnisse:", kontext["erkenntnisse_alt"], ""]
        for aufgabe, k in kontext["je_aufgabe"].items():
            teile += ["## Aufgabe %s" % aufgabe,
                      "Framework-Benchmark: %s" % json.dumps(k.get("benchmark", {}), ensure_ascii=False),
                      "Rangliste (Lernmenge):", k["rangliste_text"], ""]
            if k.get("neu"):
                teile.append("In dieser Runde neu gerechnet:")
                for e in k["neu"]:
                    if e.get("status") == "ok":
                        teile.append("- %s -> Log-Loss %s (Erwartung war: %s)" % (
                            e["hypothese"]["name"], e["ergebnis"]["hauptmetrik"],
                            e["hypothese"].get("erwartung", "-")))
                    else:
                        teile.append("- %s -> %s: %s" % (e.get("name", "?"), e.get("status"),
                                                         "; ".join(e.get("fehler", []))))
                teile.append("")
        teile.append("Schreibe die Datei erkenntnisse.md jetzt vollstaendig neu.")
        text = self._anfrage(SYSTEM_LEHRER, "\n".join(teile))
        if not text.strip():
            raise ForscherFehler("Anthropic: leere Reflexion")
        return text.strip()


def forscher_waehlen(offline=False, modell=None, seed=0):
    """Online, wenn ein Schluessel da ist und nicht ausdruecklich offline gewuenscht."""
    import os
    profil = os.path.isdir(os.path.expanduser("~/.config/anthropic"))  # `ant auth login`
    schluessel = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if offline or not (schluessel or profil):
        return OfflineForscher(seed=seed)
    return ClaudeForscher(modell=modell)
