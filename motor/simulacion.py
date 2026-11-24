"""R10: simulación de la fila para subir al bus."""


def _es_entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def simular_fila(llegadas, frecuencia, capacidad):
    """Devuelve la espera de cada persona en el orden en que llegó.

    Sale un bus en el minuto 0 y en cada múltiplo de la frecuencia.
    Si alguien llega justo cuando sale el bus, alcanza a subir.
    """
    if not isinstance(llegadas, (list, tuple)):
        raise ValueError("Las llegadas deben ser una lista")
    if not _es_entero(frecuencia) or frecuencia <= 0:
        raise ValueError("La frecuencia debe ser un entero positivo")
    if not _es_entero(capacidad) or capacidad <= 0:
        raise ValueError("La capacidad debe ser un entero positivo")
    anterior = 0
    for llegada in llegadas:
        if not _es_entero(llegada) or llegada < 0:
            raise ValueError("Cada llegada debe ser un entero no negativo")
        if llegada < anterior:
            raise ValueError("Las llegadas deben estar ordenadas")
        anterior = llegada

    esperas = []
    i = 0          # primera persona de la fila que no ha subido
    bus = -1       # minuto en que salió el último bus
    while i < len(llegadas):
        # siguiente bus que alcanza a recoger a la persona del frente
        siguiente = ((llegadas[i] + frecuencia - 1) // frecuencia) * frecuencia
        if siguiente <= bus:
            siguiente = bus + frecuencia
        bus = siguiente

        subieron = 0
        while i < len(llegadas) and subieron < capacidad and llegadas[i] <= bus:
            esperas.append(bus - llegadas[i])
            i += 1
            subieron += 1
    return esperas
