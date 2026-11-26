"""R7, R8 y R9: edición de recorridos, cierres e historial (miembro 3).

Estado que usa (lo crea miembro 1 en red.py):
- red.rutas:    TablaHash ruta -> [cabeza, cola] de una lista doblemente enlazada.
- red.paradas:  TablaHash estacion -> lista de [ruta, nodo] (una por ocurrencia).
- red.estaciones / red.abiertas / red.indice_ranking: los mantiene
  estaciones.retirar_abierta / reinsertar_abierta (R1-R3 y R6).

Estado propio (se crea la primera vez que se muta, en red.estado_ops):
- ocurrencias: TablaHash (ruta, estacion) -> [cantidad, nodo]. Permite
  localizar el ancla o el nodo a quitar sin recorrer la ruta y detectar
  anclas ambiguas (estación repetida en una ruta cargada del CSV).
- deshacer / rehacer: dos pilas (Pila, de estructuras.py) de Registro.
"""

from . import estaciones
from .estructuras import Nodo, Pila, TablaHash


class Registro:
    """Lo mínimo para revertir un cambio (no se copia la red)."""

    def __init__(self, accion, estacion, ruta=None, nodo=None, anterior=None, siguiente=None):
        self.accion = accion          # "agregar", "quitar", "cerrar" o "reabrir"
        self.estacion = estacion
        self.ruta = ruta
        self.nodo = nodo              # nodo agregado o quitado
        self.anterior = anterior      # vecinos exactos del nodo en la ruta
        self.siguiente = siguiente
        self.posicion = None          # lugar que ocupaba en red.paradas[estacion]

    def texto(self):
        """Descripción corta para mostrar el historial en la interfaz."""
        if self.accion == "agregar":
            return f"Agregar {self.estacion} después de {self.anterior.estacion} en {self.ruta}"
        if self.accion == "quitar":
            return f"Quitar {self.estacion} de {self.ruta}"
        if self.accion == "cerrar":
            return f"Cerrar {self.estacion}"
        return f"Reabrir {self.estacion}"


class EstadoOperaciones:
    def __init__(self, red):
        self.deshacer = Pila()
        self.rehacer = Pila()
        self.ocurrencias = TablaHash()
        for ruta in red.nombres_rutas:
            nodo = red.rutas.obtener(ruta)[0]
            while nodo is not None:
                clave = (ruta, nodo.estacion)
                actual = self.ocurrencias.obtener(clave)
                if actual is None:
                    self.ocurrencias.asignar(clave, [1, nodo])
                else:
                    actual[0] += 1
                nodo = nodo.siguiente


def preparar(red):
    """Devuelve el estado de operaciones, creándolo la primera vez (O(total de paradas))."""
    estado = getattr(red, "estado_ops", None)
    if estado is None:
        estado = EstadoOperaciones(red)
        red.estado_ops = estado
    return estado


# ---------------------------------------------------------------- rutinas internas

def _enlazar(red, estado, registro):
    """Mete registro.nodo entre registro.anterior y registro.siguiente."""
    nodo = registro.nodo
    ruta = registro.ruta
    extremos = red.rutas.obtener(ruta)
    nodo.anterior = registro.anterior
    nodo.siguiente = registro.siguiente
    if registro.anterior is None:
        extremos[0] = nodo
    else:
        registro.anterior.siguiente = nodo
    if registro.siguiente is None:
        extremos[1] = nodo
    else:
        registro.siguiente.anterior = nodo

    salidas = red.paradas.obtener(registro.estacion)
    if salidas is None:
        salidas = []
        red.paradas.asignar(registro.estacion, salidas)
    entrada = [ruta, nodo]
    if registro.posicion is None or registro.posicion >= len(salidas):
        salidas.append(entrada)
    else:
        salidas.insert(registro.posicion, entrada)

    estado.ocurrencias.asignar((ruta, registro.estacion), [1, nodo])
    red.indice_ranking.cambiar_membresia(ruta, registro.estacion, True)


def _desenlazar(red, estado, ruta, nodo):
    """Saca el nodo de la ruta. Devuelve la posición que ocupaba en red.paradas."""
    extremos = red.rutas.obtener(ruta)
    if nodo.anterior is None:
        extremos[0] = nodo.siguiente
    else:
        nodo.anterior.siguiente = nodo.siguiente
    if nodo.siguiente is None:
        extremos[1] = nodo.anterior
    else:
        nodo.siguiente.anterior = nodo.anterior

    salidas = red.paradas.obtener(nodo.estacion)
    posicion = 0
    while posicion < len(salidas) and salidas[posicion][1] is not nodo:
        posicion += 1
    salidas.pop(posicion)

    estado.ocurrencias.eliminar((ruta, nodo.estacion))
    red.indice_ranking.cambiar_membresia(ruta, nodo.estacion, False)
    return posicion


def _aplicar(red, estado, registro):
    if registro.accion == "agregar":
        _enlazar(red, estado, registro)
    elif registro.accion == "quitar":
        registro.posicion = _desenlazar(red, estado, registro.ruta, registro.nodo)
    elif registro.accion == "cerrar":
        estaciones.retirar_abierta(red, registro.estacion)
    else:
        estaciones.reinsertar_abierta(red, registro.estacion)


def _invertir(red, estado, registro):
    if registro.accion == "agregar":
        registro.posicion = _desenlazar(red, estado, registro.ruta, registro.nodo)
    elif registro.accion == "quitar":
        _enlazar(red, estado, registro)
    elif registro.accion == "cerrar":
        estaciones.reinsertar_abierta(red, registro.estacion)
    else:
        estaciones.retirar_abierta(red, registro.estacion)


def _registrar(estado, registro):
    """Una mutación nueva y exitosa apila en deshacer y vacía rehacer."""
    estado.deshacer.apilar(registro)
    estado.rehacer.vaciar()


# ---------------------------------------------------------------- R7

def recorrido(red, ruta, al_reves=False):
    """Lista nueva con el trazado físico (incluye estaciones cerradas)."""
    resultado = []
    extremos = red.rutas.obtener(ruta)
    if extremos is None:
        return resultado
    if al_reves:
        nodo = extremos[1]
        while nodo is not None:
            resultado.append(nodo.estacion)
            nodo = nodo.anterior
    else:
        nodo = extremos[0]
        while nodo is not None:
            resultado.append(nodo.estacion)
            nodo = nodo.siguiente
    return resultado


def agregar_parada(red, ruta, nueva, despues_de):
    if red.rutas.obtener(ruta) is None or not red.estaciones.contiene(nueva):
        return False
    estado = preparar(red)
    if estado.ocurrencias.contiene((ruta, nueva)):
        return False                       # ya figura en el recorrido
    ancla = estado.ocurrencias.obtener((ruta, despues_de))
    if ancla is None or ancla[0] != 1:
        return False                       # no existe o es ambigua
    if ancla[1].siguiente is None:
        return False                       # sin sucesora
    registro = Registro("agregar", nueva, ruta, Nodo(nueva), ancla[1], ancla[1].siguiente)
    _enlazar(red, estado, registro)
    _registrar(estado, registro)
    return True


def quitar_parada(red, ruta, estacion):
    extremos = red.rutas.obtener(ruta)
    if extremos is None:
        return False
    estado = preparar(red)
    entrada = estado.ocurrencias.obtener((ruta, estacion))
    if entrada is None or entrada[0] != 1:
        return False                       # no está o es ambigua
    if extremos[0] is extremos[1]:
        return False                       # la ruta debe conservar una parada
    nodo = entrada[1]
    registro = Registro("quitar", estacion, ruta, nodo, nodo.anterior, nodo.siguiente)
    registro.posicion = _desenlazar(red, estado, ruta, nodo)
    _registrar(estado, registro)
    return True


# ---------------------------------------------------------------- R8

def cerrar(red, nombre):
    if not estaciones.retirar_abierta(red, nombre):
        return False
    _registrar(preparar(red), Registro("cerrar", nombre))
    return True


def reabrir(red, nombre):
    if not estaciones.reinsertar_abierta(red, nombre):
        return False
    _registrar(preparar(red), Registro("reabrir", nombre))
    return True


# ---------------------------------------------------------------- R9

def deshacer(red):
    estado = preparar(red)
    if len(estado.deshacer) == 0:
        return False
    registro = estado.deshacer.desapilar()
    _invertir(red, estado, registro)
    estado.rehacer.apilar(registro)
    return True


def rehacer(red):
    estado = preparar(red)
    if len(estado.rehacer) == 0:
        return False
    registro = estado.rehacer.desapilar()
    _aplicar(red, estado, registro)
    estado.deshacer.apilar(registro)
    return True


# ---------------------------------------------------------------- consultas para la interfaz

LIMITE_HISTORIAL = 20


def _ordenar(nombres):
    """Mergesort de cadenas (no se puede usar sorted)."""
    if len(nombres) < 2:
        return nombres
    mitad = len(nombres) // 2
    izquierda = _ordenar(nombres[:mitad])
    derecha = _ordenar(nombres[mitad:])
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


def listar_cerradas(red):
    """Estaciones cerradas en orden alfabético. O(n + k log k)."""
    cerradas = []
    for nombre in red.estaciones.claves():
        if red.estaciones.obtener(nombre) is False:
            cerradas.append(nombre)
    return _ordenar(cerradas)


def _textos(pila):
    resultado = []
    indice = len(pila.datos) - 1
    while indice >= 0 and len(resultado) < LIMITE_HISTORIAL:
        resultado.append(pila.datos[indice].texto())
        indice -= 1
    return resultado


def historial(red):
    """(acciones que se pueden deshacer, acciones que se pueden rehacer), la más reciente primero."""
    estado = preparar(red)
    return _textos(estado.deshacer), _textos(estado.rehacer)
