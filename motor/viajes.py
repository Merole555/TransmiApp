"""Consultas de viajes y mantenimiento de sus índices."""


def minuto_del_dia(hora):
    if (
        not isinstance(hora, str)
        or len(hora) != 5
        or hora[2] != ":"
        or not all("0" <= digito <= "9" for digito in hora[:2] + hora[3:])
    ):
        raise ValueError("La hora debe tener formato HH:MM")
    horas = int(hora[:2])
    minutos = int(hora[3:])
    if horas >= 24 or minutos >= 60:
        raise ValueError("La hora debe estar entre 00:00 y 23:59")
    return horas * 60 + minutos


def _ordenar_minutos(minutos):
    if len(minutos) < 2:
        return minutos
    mitad = len(minutos) // 2
    izquierda = _ordenar_minutos(minutos[:mitad])
    derecha = _ordenar_minutos(minutos[mitad:])
    resultado = []
    i = j = 0
    while i < len(izquierda) and j < len(derecha):
        if izquierda[i] <= derecha[j]:
            resultado.append(izquierda[i])
            i += 1
        else:
            resultado.append(derecha[j])
            j += 1
    resultado.extend(izquierda[i:])
    resultado.extend(derecha[j:])
    return resultado


def indexar_horarios(tabla, filas):
    """Carga una tabla propia vacía. Cada fila contiene ruta, estación y hora."""
    pares = []
    for ruta, estacion, hora in filas:
        minuto = minuto_del_dia(hora)
        par = (ruta, estacion)
        minutos = tabla.obtener(par)
        if minutos is None:
            minutos = []
            tabla.asignar(par, minutos)
            pares.append(par)
        minutos.append(minuto)
    for par in pares:
        tabla.asignar(par, _ordenar_minutos(tabla.obtener(par)))
    return tabla


def proximo_bus(red, estacion, ruta, hora):
    objetivo = minuto_del_dia(hora)
    if not red.estado(estacion)[1] or not red.tiene_parada(ruta, estacion):
        return None
    minutos = red.horarios.obtener((ruta, estacion))
    if not minutos:
        return None

    inicio = 0
    fin = len(minutos)
    while inicio < fin:
        medio = (inicio + fin) // 2
        if minutos[medio] < objetivo:
            inicio = medio + 1
        else:
            fin = medio
    if inicio == len(minutos):
        return None
    horas, resto = divmod(minutos[inicio], 60)
    return f"{horas:02d}:{resto:02d}"
