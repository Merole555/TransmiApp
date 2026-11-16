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


def viaje(red, origen, destino):
    if not red.estado(origen)[1] or not red.estado(destino)[1]:
        return None
    if origen == destino:
        return 0, []

    mejor = None
    for ruta, salida in red.salidas(origen):
        nodo = salida.siguiente
        saltos = 1
        while nodo is not None:
            if mejor is not None and saltos > mejor[0]:
                break
            nombre = nodo.estacion
            tramo = (ruta, origen, nombre)
            if nombre == destino:
                candidato = (saltos, 1, (tramo,))
                if mejor is None or candidato < mejor:
                    mejor = candidato
                break
            if red.estado(nombre)[1] and (mejor is None or saltos < mejor[0]):
                mejor = _evaluar_transbordos(red, tramo, destino, saltos, mejor)
            nodo = nodo.siguiente
            saltos += 1

    if mejor is None:
        return None
    return mejor[0], list(mejor[2])


def _evaluar_transbordos(red, tramo, destino, saltos, mejor):
    ruta, _, cambio = tramo
    for otra_ruta, salida in red.salidas(cambio):
        if otra_ruta == ruta:
            continue
        nodo = salida.siguiente
        total = saltos + 1
        while nodo is not None and (mejor is None or total <= mejor[0]):
            if nodo.estacion == destino:
                candidato = (total, 2, (tramo, (otra_ruta, cambio, destino)))
                if mejor is None or candidato < mejor:
                    mejor = candidato
                break
            nodo = nodo.siguiente
            total += 1
    return mejor


class RankingEstaciones:
    """Mantiene el conteo activo y las claves ordenadas de las abiertas."""

    def __init__(self, estaciones, abiertas, horarios):
        self._estaciones = estaciones
        self._abiertas = abiertas
        self._horarios = horarios

    def registrar(self, estacion):
        self._estaciones.asignar(estacion, (0, True))
        self._abiertas.insertar((0, estacion))

    def cambiar_apertura(self, estacion, abierta):
        cantidad, anterior = self._estaciones.obtener(estacion)
        if abierta == anterior:
            return
        clave = (-cantidad, estacion)
        if abierta:
            self._abiertas.insertar(clave)
        else:
            self._abiertas.eliminar(clave)
        self._estaciones.asignar(estacion, (cantidad, abierta))

    def cambiar_membresia(self, ruta, estacion, activa):
        """Recibe únicamente transiciones efectivas de la pareja completa."""
        minutos = self._horarios.obtener((ruta, estacion))
        if not minutos:
            return
        cantidad, abierta = self._estaciones.obtener(estacion)
        if abierta:
            self._abiertas.eliminar((-cantidad, estacion))
        cantidad += len(minutos) if activa else -len(minutos)
        self._estaciones.asignar(estacion, (cantidad, abierta))
        if abierta:
            self._abiertas.insertar((-cantidad, estacion))

    def consultar(self, k):
        resultado = []
        if k <= 0:
            return resultado
        for negativo, estacion in self._abiertas.ascendente():
            resultado.append((estacion, -negativo))
            if len(resultado) == k:
                break
        return resultado


def ranking(red, k):
    return red.indice_ranking.consultar(k)
