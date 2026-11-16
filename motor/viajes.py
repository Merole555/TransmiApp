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
    if minutos >= 60:
        raise ValueError("La hora debe tener minutos entre 00 y 59")
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


def _abierta(red, nombre):
    """Comprueba el estado definido por el contrato público de R1."""
    return red.estado(nombre) == "ABIERTA"


def proximo_bus(red, estacion, ruta, hora):
    objetivo = minuto_del_dia(hora)
    if not _abierta(red, estacion) or not red.tiene_parada(ruta, estacion):
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
    if not _abierta(red, origen) or not _abierta(red, destino):
        return None
    if origen == destino:
        return "DIRECTO", 0, []

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
            if _abierta(red, nombre) and (mejor is None or saltos < mejor[0]):
                mejor = _evaluar_transbordos(red, tramo, destino, saltos, mejor)
            nodo = nodo.siguiente
            saltos += 1

    if mejor is None:
        return None
    return ("DIRECTO" if mejor[1] == 1 else "TRANSBORDO"), mejor[0], list(mejor[2])


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
    """Índice de ranking ordenado por (-buses, nombre), sin árbol externo.

    Las consultas leen directamente la lista ordenada; cada edición actualiza
    la clave afectada. Se usa búsqueda binaria manual para encontrar su lugar.
    """

    def __init__(self, estaciones, abiertas, horarios):
        self._estaciones = estaciones
        self._orden = []
        self._horarios = horarios

    def _posicion(self, clave):
        inicio = 0
        fin = len(self._orden)
        while inicio < fin:
            medio = (inicio + fin) // 2
            if self._orden[medio] < clave:
                inicio = medio + 1
            else:
                fin = medio
        return inicio

    def _insertar(self, clave):
        self._orden.insert(self._posicion(clave), clave)

    def _quitar(self, clave):
        posicion = self._posicion(clave)
        if posicion < len(self._orden) and self._orden[posicion] == clave:
            self._orden.pop(posicion)

    def registrar(self, estacion):
        self._estaciones.asignar(estacion, (0, True))
        self._insertar((0, estacion))

    def cambiar_apertura(self, estacion, abierta):
        cantidad, anterior = self._estaciones.obtener(estacion)
        if abierta == anterior:
            return
        clave = (-cantidad, estacion)
        if abierta:
            self._insertar(clave)
        else:
            self._quitar(clave)
        self._estaciones.asignar(estacion, (cantidad, abierta))

    def cambiar_membresia(self, ruta, estacion, activa):
        """Actualiza la contribución al pasar entre 0 y >=1 ocurrencias."""
        minutos = self._horarios.obtener((ruta, estacion))
        if not minutos:
            return
        cantidad, abierta = self._estaciones.obtener(estacion)
        if abierta:
            self._quitar((-cantidad, estacion))
        cantidad += len(minutos) if activa else -len(minutos)
        self._estaciones.asignar(estacion, (cantidad, abierta))
        if abierta:
            self._insertar((-cantidad, estacion))

    def consultar(self, k):
        resultado = []
        if k <= 0:
            return resultado
        indice = 0
        while indice < len(self._orden) and len(resultado) < k:
            negativo, estacion = self._orden[indice]
            resultado.append((estacion, -negativo))
            indice += 1
        return resultado


def ranking(red, k):
    return red.indice_ranking.consultar(k)
