"""Sichere Formelauswertung fuer abgeleitete Merkmale.

Das Sprachmodell darf Formeln ueber Katalognamen vorschlagen, aber nichts
ausfuehren: der Syntaxbaum wird selbst abgelaufen, erlaubt sind Zahlen,
Merkmalsnamen, + - * / **, Klammern und wenige Funktionen. Kein eval.
"""
import ast
import math

FUNKTIONEN = {
    "abs": abs, "sqrt": math.sqrt, "log": math.log, "log1p": math.log1p,
    "exp": math.exp, "min": min, "max": max,
}
_OPERATOREN = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b,
}


class FormelFehler(ValueError):
    pass


def pruefen(formel, erlaubte_namen):
    """Statische Pruefung; gibt die benutzten Merkmalsnamen zurueck."""
    try:
        baum = ast.parse(str(formel).strip(), mode="eval")
    except SyntaxError as e:
        raise FormelFehler("Syntaxfehler in %r: %s" % (formel, e))
    benutzt = set()

    def gehe(k):
        if isinstance(k, ast.Expression):
            gehe(k.body)
        elif isinstance(k, ast.Constant) and isinstance(k.value, (int, float)) and not isinstance(k.value, bool):
            pass
        elif isinstance(k, ast.Name):
            if k.id not in erlaubte_namen:
                raise FormelFehler("unbekanntes Merkmal %r in %r" % (k.id, formel))
            benutzt.add(k.id)
        elif isinstance(k, ast.BinOp) and type(k.op) in _OPERATOREN:
            gehe(k.left)
            gehe(k.right)
        elif isinstance(k, ast.UnaryOp) and isinstance(k.op, (ast.USub, ast.UAdd)):
            gehe(k.operand)
        elif isinstance(k, ast.Call):
            if not isinstance(k.func, ast.Name) or k.func.id not in FUNKTIONEN:
                raise FormelFehler("Funktion nicht erlaubt in %r" % formel)
            if k.keywords:
                raise FormelFehler("Schluesselwortargumente nicht erlaubt in %r" % formel)
            for a in k.args:
                gehe(a)
        else:
            raise FormelFehler("nicht erlaubter Ausdruck in %r" % formel)

    gehe(baum)
    return benutzt


def auswerten(formel, werte):
    """Formel gegen ein Merkmalsdict; Rechenfehler und fehlende Eingaben -> None."""
    baum = ast.parse(str(formel).strip(), mode="eval")

    def gehe(k):
        if isinstance(k, ast.Expression):
            return gehe(k.body)
        if isinstance(k, ast.Constant):
            return float(k.value)
        if isinstance(k, ast.Name):
            v = werte.get(k.id)
            if v is None:
                raise FormelFehler("fehlt")
            return float(v)
        if isinstance(k, ast.BinOp):
            return _OPERATOREN[type(k.op)](gehe(k.left), gehe(k.right))
        if isinstance(k, ast.UnaryOp):
            v = gehe(k.operand)
            return -v if isinstance(k.op, ast.USub) else v
        if isinstance(k, ast.Call):
            return float(FUNKTIONEN[k.func.id](*[gehe(a) for a in k.args]))
        raise FormelFehler("nicht erlaubter Ausdruck")

    try:
        v = gehe(baum)
    except (FormelFehler, ZeroDivisionError, ValueError, OverflowError, TypeError):
        return None
    if isinstance(v, complex) or math.isnan(v) or math.isinf(v):
        return None
    return v
