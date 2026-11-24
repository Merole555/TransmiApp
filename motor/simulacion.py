"""R10 · Simulación de la fila de abordaje (miembro 4).

Contrato aprobado en el repositorio (backend/INTEGRACION.md):
``simular_fila(llegadas, frecuencia, capacidad)`` devuelve una lista nueva
con la espera de cada persona, en el mismo orden FIFO de ``llegadas``.

Reglas:
- Tiempos en minutos enteros desde 0. Sale un bus en 0 y en cada múltiplo
  de ``frecuencia``; cada bus lleva como máximo ``capacidad`` personas.
- Una persona que llega exactamente cuando sale el bus alcanza a subir.
- ``llegadas`` debe ser no negativa y no decreciente; ``frecuencia`` y
  ``capacidad`` deben ser enteros positivos. Si no, ``ValueError``.

Algoritmo: un cursor recorre ``llegadas`` como frente de la fila (no se
elimina el primer elemento del arreglo). Cuando la fila está vacía se salta
directamente al primer múltiplo de la frecuencia que puede recoger a la
siguiente persona, así no se simulan buses vacíos. Tiempo O(n), espacio
O(n) para la salida y O(1) auxiliar, con n personas.
"""


def _entero(valor):
    # bool es subclase de int, pero True/False no son tiempos válidos.
    return isinstance(valor, int) and not isinstance(valor, bool)


def _validar(llegadas, frecuencia, capacidad):
    if not isinstance(llegadas, (list, tuple)):
        raise ValueError("Las llegadas deben ser una lista de enteros")
    if not _entero(frecuencia) or frecuencia <= 0:
        raise ValueError("La frecuencia debe ser un entero positivo")
    if not _entero(capacidad) or capacidad <= 0:
        raise ValueError("La capacidad debe ser un entero positivo")
    anterior = 0
    for llegada in llegadas:
        if not _entero(llegada):
            raise ValueError("Cada llegada debe ser un entero")
        if llegada < 0:
            raise ValueError("Las llegadas no pueden ser negativas")
        if llegada < anterior:
            raise ValueError("Las llegadas deben estar en orden no decreciente")
        anterior = llegada


def _siguiente_salida(llegada, frecuencia):
    """Primer múltiplo de la frecuencia mayor o igual a la llegada."""
    return ((llegada + frecuencia - 1) // frecuencia) * frecuencia


def simular_fila(llegadas, frecuencia, capacidad):
    _validar(llegadas, frecuencia, capacidad)
    esperas = []
    total = len(llegadas)
    frente = 0          # cursor: primera persona que todavía no sube
    salida = -1         # hora del último bus procesado
    while frente < total:
        # Próximo bus útil: el primero que sale después del último procesado
        # y en o después de la llegada de quien está al frente.
        candidata = _siguiente_salida(llegadas[frente], frecuencia)
        if candidata <= salida:
            candidata = salida + frecuencia
        salida = candidata
        subidos = 0
        while frente < total and subidos < capacidad and llegadas[frente] <= salida:
            esperas.append(salida - llegadas[frente])
            frente += 1
            subidos += 1
    return esperas
