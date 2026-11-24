"""Clase Red: carga los tres CSV y delega cada requisito a su módulo.

Base del miembro 1 (carga y R1-R3). R4-R6 están en viajes.py (miembro 2),
R7-R9 en operaciones.py (miembro 3) y R10 en simulacion.py (miembro 4).
"""

import csv
from pathlib import Path

from . import estaciones, viajes
from .estructuras import ArbolAVL, Nodo, TablaHash

try:
    from . import operaciones
except ImportError:
    operaciones = None  # todavía no está en main

def _leer_csv(carpeta, archivo):
    """Devuelve una lista de (numero_de_fila, fila) sin la cabecera."""
    ruta = Path(carpeta) / archivo
    if not ruta.is_file():
        raise ValueError(f"No existe {archivo} en {carpeta}")
    filas = []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        lector = csv.reader(f)
        cabecera = next(lector, None)
        esperada = _cabecera(archivo)
        if cabecera != esperada:
            raise ValueError(f"{archivo}: la cabecera debe ser {','.join(esperada)}")
        numero = 1
        for fila in lector:
            numero += 1
            if len(fila) == 0:
                continue
            if len(fila) != len(esperada):
                raise ValueError(f"{archivo}, fila {numero}: se esperaban {len(esperada)} columnas")
            filas.append((numero, fila))
    return filas


def _cabecera(archivo):
    if archivo == "estaciones.csv":
        return ["nombre"]
    if archivo == "rutas.csv":
        return ["ruta", "orden", "estacion"]
    return ["ruta", "estacion", "hora"]


def _ordenar_por_orden(paradas):
    """Mergesort de una lista de (orden, estacion) por el número de orden."""
    if len(paradas) < 2:
        return paradas
    mitad = len(paradas) // 2
    izquierda = _ordenar_por_orden(paradas[:mitad])
    derecha = _ordenar_por_orden(paradas[mitad:])
    resultado = []
    i = j = 0
    while i < len(izquierda) and j < len(derecha):
        if izquierda[i][0] <= derecha[j][0]:
            resultado.append(izquierda[i])
            i += 1
        else:
            resultado.append(derecha[j])
            j += 1
    resultado.extend(izquierda[i:])
    resultado.extend(derecha[j:])
    return resultado


class Red:
    def __init__(self, carpeta):
        carpeta = str(carpeta)
        self.estaciones = TablaHash()    # nombre -> True si está abierta
        self.abiertas = ArbolAVL()       # nombres de las estaciones abiertas
        self.rutas = TablaHash()         # ruta -> [cabeza, cola] de la lista enlazada
        self.nombres_rutas = []          # ids de ruta en el orden en que aparecen
        self.paradas = TablaHash()       # estacion -> lista de [ruta, nodo]
        self.horarios = TablaHash()      # (ruta, estacion) -> minutos ordenados
        self.indice_ranking = viajes.RankingEstaciones(TablaHash(), None, self.horarios)

        self._cargar_estaciones(carpeta)
        self._cargar_rutas(carpeta)
        self._cargar_horarios(carpeta)

    # ------------------------------------------------------------ carga

    def _cargar_estaciones(self, carpeta):
        for numero, fila in _leer_csv(carpeta, "estaciones.csv"):
            nombre = fila[0].strip()
            if nombre == "":
                raise ValueError(f"estaciones.csv, fila {numero}: nombre vacío")
            if self.estaciones.contiene(nombre):
                raise ValueError(f"estaciones.csv, fila {numero}: estación repetida {nombre}")
            self.estaciones.asignar(nombre, True)
            self.abiertas.insertar(nombre)
            self.indice_ranking.registrar(nombre)

    def _cargar_rutas(self, carpeta):
        por_ruta = TablaHash()    # ruta -> lista de (orden, estacion)
        usados = TablaHash()      # (ruta, orden) ya vistos
        for numero, fila in _leer_csv(carpeta, "rutas.csv"):
            ruta, orden, estacion = fila[0].strip(), fila[1].strip(), fila[2].strip()
            if ruta == "":
                raise ValueError(f"rutas.csv, fila {numero}: ruta vacía")
            if not orden.isdigit() or int(orden) < 1:
                raise ValueError(f"rutas.csv, fila {numero}: orden inválido {orden}")
            if not self.estaciones.contiene(estacion):
                raise ValueError(f"rutas.csv, fila {numero}: estación desconocida {estacion}")
            if usados.contiene((ruta, int(orden))):
                raise ValueError(f"rutas.csv, fila {numero}: orden {orden} repetido en {ruta}")
            usados.asignar((ruta, int(orden)), True)
            lista = por_ruta.obtener(ruta)
            if lista is None:
                lista = []
                por_ruta.asignar(ruta, lista)
                self.nombres_rutas.append(ruta)
            lista.append((int(orden), estacion))

        # se construye la lista doblemente enlazada de cada ruta
        for ruta in self.nombres_rutas:
            cabeza = None
            cola = None
            for _, estacion in _ordenar_por_orden(por_ruta.obtener(ruta)):
                nodo = Nodo(estacion)
                if cabeza is None:
                    cabeza = nodo
                else:
                    cola.siguiente = nodo
                    nodo.anterior = cola
                cola = nodo
                salidas = self.paradas.obtener(estacion)
                if salidas is None:
                    salidas = []
                    self.paradas.asignar(estacion, salidas)
                salidas.append([ruta, nodo])
            self.rutas.asignar(ruta, [cabeza, cola])

    def _cargar_horarios(self, carpeta):
        filas = []
        for numero, fila in _leer_csv(carpeta, "horarios.csv"):
            ruta, estacion, hora = fila[0].strip(), fila[1].strip(), fila[2].strip()
            if not self.rutas.contiene(ruta):
                raise ValueError(f"horarios.csv, fila {numero}: ruta desconocida {ruta}")
            if not self.tiene_parada(ruta, estacion):
                raise ValueError(f"horarios.csv, fila {numero}: {estacion} no está en la ruta {ruta}")
            try:
                viajes.minuto_del_dia(hora)
            except ValueError:
                raise ValueError(f"horarios.csv, fila {numero}: hora inválida {hora}") from None
            filas.append((ruta, estacion, hora))
        viajes.indexar_horarios(self.horarios, filas)

        # cada pareja ruta-estación suma sus buses al ranking una sola vez
        vistas = TablaHash()
        for ruta in self.nombres_rutas:
            nodo = self.rutas.obtener(ruta)[0]
            while nodo is not None:
                if not vistas.contiene((ruta, nodo.estacion)):
                    vistas.asignar((ruta, nodo.estacion), True)
                    self.indice_ranking.cambiar_membresia(ruta, nodo.estacion, True)
                nodo = nodo.siguiente

    # --------------------------------------- consultas que usan otros módulos

    def tiene_parada(self, ruta, estacion):
        for actual, _ in self.paradas.obtener(estacion, []):
            if actual == ruta:
                return True
        return False

    def salidas(self, nombre):
        """Pares (ruta, nodo) de cada vez que la estación aparece en una ruta."""
        resultado = []
        for ruta, nodo in self.paradas.obtener(nombre, []):
            resultado.append((ruta, nodo))
        return resultado

    # ------------------------------------------------------------ R1-R3

    def estado(self, nombre):
        return estaciones.estado(self, nombre)

    def autocompletar(self, prefijo, k):
        return estaciones.autocompletar(self, prefijo, k)

    def rango(self, desde, hasta):
        return estaciones.rango(self, desde, hasta)

    # ------------------------------------------------------------ R4-R6

    def proximo_bus(self, estacion, ruta, hora):
        return viajes.proximo_bus(self, estacion, ruta, hora)

    def viaje(self, origen, destino):
        return viajes.viaje(self, origen, destino)

    def ranking(self, k):
        return viajes.ranking(self, k)

    # ------------------------------------------------------------ R7-R9

    def _operaciones(self):
        if operaciones is None:
            raise NotImplementedError("R7-R9 los implementa el miembro 3 en operaciones.py")
        return operaciones

    def agregar_parada(self, ruta, nueva, despues_de):
        return self._operaciones().agregar_parada(self, ruta, nueva, despues_de)

    def quitar_parada(self, ruta, estacion):
        return self._operaciones().quitar_parada(self, ruta, estacion)

    def recorrido(self, ruta, al_reves=False):
        return self._operaciones().recorrido(self, ruta, al_reves)

    def cerrar(self, nombre):
        return self._operaciones().cerrar(self, nombre)

    def reabrir(self, nombre):
        return self._operaciones().reabrir(self, nombre)

    def deshacer(self):
        return self._operaciones().deshacer(self)

    def rehacer(self):
        return self._operaciones().rehacer(self)
