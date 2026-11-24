import random
import unittest

from motor.simulacion import simular_fila


def simular_lento(llegadas, frecuencia, capacidad):
    """Versión lenta que revisa bus por bus, solo para comparar."""
    esperas = []
    i = 0
    bus = 0
    while i < len(llegadas):
        subieron = 0
        while i < len(llegadas) and subieron < capacidad and llegadas[i] <= bus:
            esperas.append(bus - llegadas[i])
            i += 1
            subieron += 1
        bus += frecuencia
    return esperas


class SimulacionTests(unittest.TestCase):
    def test_ejemplo_guia(self):
        esperas = simular_fila([0, 1, 5, 5], 5, 2)
        self.assertEqual(esperas, [0, 4, 0, 5])
        self.assertEqual(sum(esperas), 9)
        self.assertEqual(max(esperas), 5)

    def test_fila_vacia(self):
        self.assertEqual(simular_fila([], 5, 2), [])

    def test_llega_justo_cuando_sale(self):
        self.assertEqual(simular_fila([5], 5, 1), [0])
        self.assertEqual(simular_fila([6], 5, 1), [4])

    def test_capacidad_uno_y_simultaneas(self):
        self.assertEqual(simular_fila([0, 0, 0], 3, 1), [0, 3, 6])
        self.assertEqual(simular_fila([2, 2, 2, 2], 3, 3), [1, 1, 1, 4])

    def test_intervalo_grande(self):
        self.assertEqual(simular_fila([0, 1000000001], 10, 1), [0, 9])

    def test_contra_version_lenta(self):
        azar = random.Random(42)
        for _ in range(200):
            llegadas = []
            actual = 0
            for _ in range(azar.randint(0, 30)):
                actual += azar.randint(0, 6)
                llegadas.append(actual)
            frecuencia = azar.randint(1, 9)
            capacidad = azar.randint(1, 5)
            self.assertEqual(
                simular_fila(llegadas, frecuencia, capacidad),
                simular_lento(llegadas, frecuencia, capacidad),
            )

    def test_entradas_invalidas(self):
        for llegadas, frecuencia, capacidad in [
            ([3, 1], 5, 2), ([-1], 5, 2), ([0], 0, 2), ([0], 5, 0),
            ([0.5], 5, 2), ([True], 5, 2), ([0], "5", 2), (None, 5, 2),
        ]:
            with self.subTest(llegadas=llegadas), self.assertRaises(ValueError):
                simular_fila(llegadas, frecuencia, capacidad)
