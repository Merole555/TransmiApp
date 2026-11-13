import unittest
from types import SimpleNamespace

from motor.viajes import RankingEstaciones, indexar_horarios, viaje
from test_viajes import TablaPrueba


class RedPrueba:
    def __init__(self, recorridos):
        self.ocurrencias = {}
        self.abiertas = set()
        for ruta, recorrido in recorridos:
            siguiente = None
            for nombre in reversed(recorrido):
                nodo = SimpleNamespace(estacion=nombre, siguiente=siguiente)
                self.ocurrencias.setdefault(nombre, []).append((ruta, nodo))
                self.abiertas.add(nombre)
                siguiente = nodo

    def estado(self, nombre):
        return nombre in self.ocurrencias, nombre in self.abiertas

    def salidas(self, nombre):
        return self.ocurrencias.get(nombre, ())


class ViajeTests(unittest.TestCase):
    def setUp(self):
        self.red = RedPrueba([
            ("T1", ["A", "B", "C"]),
            ("T2", ["B", "D"]),
        ])

    def test_directo_transbordo_y_sentido(self):
        self.assertEqual(viaje(self.red, "A", "C"), (2, [("T1", "A", "C")]))
        self.assertEqual(viaje(self.red, "A", "D"), (
            2, [("T1", "A", "B"), ("T2", "B", "D")],
        ))
        self.assertIsNone(viaje(self.red, "D", "A"))

    def test_cerrada_cuenta_como_salto(self):
        self.red.abiertas.remove("B")
        self.assertEqual(viaje(self.red, "A", "C"), (2, [("T1", "A", "C")]))
        self.assertIsNone(viaje(self.red, "A", "D"))
        self.assertIsNone(viaje(self.red, "B", "B"))
        self.assertEqual(viaje(self.red, "A", "A"), (0, []))

    def test_transbordo_mas_corto_con_ocurrencias_repetidas(self):
        red = RedPrueba([
            ("LARGO", ["A", "X", "Y", "W", "D"]),
            ("T1", ["A", "X", "A", "B"]),
            ("T2", ["D", "B", "D"]),
        ])
        self.assertEqual(viaje(red, "A", "D"), (
            2, [("T1", "A", "B"), ("T2", "B", "D")],
        ))

    def test_desempates_y_limite_de_transbordos(self):
        red = RedPrueba([
            ("Z", ["A", "B", "C"]),
            ("Y", ["A", "B", "C"]),
            ("T0", ["A", "B"]),
            ("T1", ["B", "C"]),
        ])
        self.assertEqual(viaje(red, "A", "C"), (2, [("Y", "A", "C")]))
        red = RedPrueba([
            ("T0", ["A", "B"]), ("T1", ["B", "C"]), ("T2", ["C", "D"]),
        ])
        self.assertIsNone(viaje(red, "A", "D"))


class ArbolPrueba:
    def __init__(self):
        self.claves = set()

    def insertar(self, clave):
        assert clave not in self.claves
        self.claves.add(clave)

    def eliminar(self, clave):
        self.claves.remove(clave)

    def ascendente(self):
        return iter(sorted(self.claves))


class RankingTests(unittest.TestCase):
    def test_conteos_empates_y_mutaciones(self):
        horarios = indexar_horarios(TablaPrueba(), [
            ("T1", "A", "08:00"), ("T1", "B", "08:01"),
            ("T2", "B", "08:02"), ("T2", "B", "08:02"),
        ])
        indice = RankingEstaciones(TablaPrueba(), ArbolPrueba(), horarios)
        for estacion in ("A", "B", "C"):
            indice.registrar(estacion)
        for ruta, estacion in (("T1", "A"), ("T1", "B"), ("T2", "B")):
            indice.cambiar_membresia(ruta, estacion, True)
        self.assertEqual(indice.consultar(5), [("B", 3), ("A", 1), ("C", 0)])
        self.assertEqual(indice.consultar(0), [])
        self.assertEqual(indice.consultar(-1), [])
        indice.cambiar_apertura("B", False)
        self.assertEqual(indice.consultar(1), [("A", 1)])
        indice.cambiar_membresia("T2", "B", False)
        indice.cambiar_apertura("B", True)
        self.assertEqual(indice.consultar(2), [("A", 1), ("B", 1)])
        indice.cambiar_membresia("T2", "B", True)
        salida = indice.consultar(1)
        self.assertEqual(salida, [("B", 3)])
        salida.clear()
        self.assertEqual(indice.consultar(1), [("B", 3)])
