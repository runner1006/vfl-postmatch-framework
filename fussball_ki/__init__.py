"""Selbstlernende Fussball-KI.

Eine KI, die sich selbst weiterbaut: ein Sprachmodell (Claude) schlaegt
Modellhypothesen vor, der Rechenkern prueft sie an echten Spieldaten, und aus
dem Ergebnis schreibt das Sprachmodell seine eigenen Anweisungen fuer die
naechste Runde fort. Gelernt wird also auf zwei Ebenen: die statistischen
Fussballmodelle (Gewichte) und das Wissen, mit dem das Sprachmodell arbeitet.

Reine Standardbibliothek. Das Anthropic-SDK ist nur fuer den Online-Forscher
noetig; ohne Schluessel laeuft dieselbe Schleife mit dem Offline-Forscher.
"""

__version__ = "0.1"
