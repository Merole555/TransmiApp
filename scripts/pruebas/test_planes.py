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
        return "NO_EXISTE" if nombre not in self.ocurrencias else ("ABIERTA" if nombre in self.abiertas else "CERRADA")

    def salidas(self, nombre):
        return self.ocurrencias.get(nombre, ())


class ViajeTests(unittest.TestCase):
    def setUp(self):
        self.red = RedPrueba([
            ("T1", ["A", "B", "C"]),
            ("T2", ["B", "D"]),
        ])

    def test_directo_transbordo_y_sentido(self):
        self.assertEqual(viaje(self.red, "A", "C"), ("DIRECTO", 2, [("T1", "A", "C")]))
        self.assertEqual(viaje(self.red, "A", "D"), (
            "TRANSBORDO", 2, [("T1", "A", "B"), ("T2", "B", "D")],
        ))
        self.assertIsNone(viaje(self.red, "D", "A"))

    def test_cerrada_cuenta_como_salto(self):
        self.red.abiertas.remove("B")
        self.assertEqual(viaje(self.red, "A", "C"), ("DIRECTO", 2, [("T1", "A", "C")]))
        self.assertIsNone(viaje(self.red, "A", "D"))
        self.assertIsNone(viaje(self.red, "B", "B"))
        self.assertEqual(viaje(self.red, "A", "A"), ("DIRECTO", 0, []))

    def test_transbordo_mas_corto_con_ocurrencias_repetidas(self):
        red = RedPrueba([
            ("LARGO", ["A", "X", "Y", "W", "D"]),
            ("T1", ["A", "X", "A", "B"]),
            ("T2", ["D", "B", "D"]),
        ])
        self.assertEqual(viaje(red, "A", "D"), (
            "TRANSBORDO", 2, [("T1", "A", "B"), ("T2", "B", "D")],
        ))

    def test_desempates_y_limite_de_transbordos(self):
        red = RedPrueba([
            ("Z", ["A", "B", "C"]),
            ("Y", ["A", "B", "C"]),
            ("T0", ["A", "B"]),
            ("T1", ["B", "C"]),
        ])
        self.assertEqual(viaje(red, "A", "C"), ("DIRECTO", 2, [("Y", "A", "C")]))
        red = RedPrueba([
            ("T0", ["A", "B"]), ("T1", ["B", "C"]), ("T2", ["C", "D"]),
        ])
        self.assertIsNone(viaje(red, "A", "D"))


    def test_empate_lexicografico_independiente_de_orden_de_carga(self):
        for recorridos in (
            [("Z99", ["A", "B", "D"]), ("B74", ["A", "C", "D"])],
            [("B74", ["A", "C", "D"]), ("Z99", ["A", "B", "D"])],
        ):
            with self.subTest(recorridos=recorridos):
                red = RedPrueba(recorridos)
                self.assertEqual(viaje(red, "A", "D"), (
                    "DIRECTO", 2, [("B74", "A", "D")],
                ))

    def test_empate_directo_prefiere_sin_transbordo(self):
        red = RedPrueba([
            ("Z99", ["A", "B", "D"]),
            ("A01", ["A", "B"]),
            ("A02", ["B", "D"]),
        ])
        self.assertEqual(viaje(red, "A", "D"), (
            "DIRECTO", 2, [("Z99", "A", "D")],
        ))

    def test_empate_entre_puntos_de_transbordo(self):
        red = RedPrueba([
            ("T1", ["A", "B", "C"]),
            ("T2", ["B", "E", "D"]),
            ("T3", ["C", "D"]),
        ])
        self.assertEqual(viaje(red, "A", "D"), (
            "TRANSBORDO", 3, [("T1", "A", "B"), ("T2", "B", "D")],
        ))
        red.abiertas.remove("B")
        self.assertEqual(viaje(red, "A", "D"), (
            "TRANSBORDO", 3, [("T1", "A", "C"), ("T3", "C", "D")],
        ))

    def test_transbordo_mas_corto_gana_a_directo_y_sentido_unico(self):
        red = RedPrueba([
            ("DIREC", ["A", "X", "Y", "D"]),
            ("T1", ["A", "B"]),
            ("T2", ["B", "D"]),
        ])
        self.assertEqual(viaje(red, "A", "D"), (
            "TRANSBORDO", 2, [("T1", "A", "B"), ("T2", "B", "D")],
        ))
        self.assertIsNone(viaje(red, "D", "A"))

    def test_ocurrencias_repetidas_busca_salida_posterior_mas_corta(self):
        red = RedPrueba([("T1", ["A", "X", "A", "D"])])
        self.assertEqual(viaje(red, "A", "D"), (
            "DIRECTO", 1, [("T1", "A", "D")],
        ))


class RankingTests(unittest.TestCase):
    def test_conteos_empates_y_mutaciones(self):
        horarios = indexar_horarios(TablaPrueba(), [
            ("T1", "A", "08:00"), ("T1", "B", "08:01"),
            ("T2", "B", "08:02"), ("T2", "B", "08:02"),
        ])
        indice = RankingEstaciones(TablaPrueba(), None, horarios)
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
        # Repetir eventos o registros no puede duplicar claves ni contabilizar
        # buses dos veces: los avisos son transiciones de estado.
        indice.registrar("B")
        indice.cambiar_membresia("T2", "B", True)
        self.assertEqual(indice.consultar(5), [("B", 3), ("A", 1), ("C", 0)])
        indice.cambiar_membresia("T2", "B", False)
        indice.cambiar_membresia("T2", "B", False)
        self.assertEqual(indice.consultar(5), [("A", 1), ("B", 1), ("C", 0)])
        indice.cambiar_membresia("T2", "B", True)
        self.assertEqual(indice.consultar(5), [("B", 3), ("A", 1), ("C", 0)])
        salida = indice.consultar(1)
        self.assertEqual(salida, [("B", 3)])
        salida.clear()
        self.assertEqual(indice.consultar(1), [("B", 3)])
