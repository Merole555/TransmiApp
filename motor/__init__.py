"""Import público del motor: ``from motor import Red, simular_fila``."""

from .simulacion import simular_fila

try:
    from .red import Red
except ImportError:  # red.py lo integra el miembro 1; mientras tanto R10 funciona solo.
    Red = None

__all__ = ["Red", "simular_fila"]
