from .simulacion import simular_fila

try:
    from .red import Red
except ImportError:
    # red.py todavía no está en main
    Red = None
