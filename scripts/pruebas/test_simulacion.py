import random
import unittest

from motor.simulacion import simular_fila


def modelo_minuto_a_minuto(llegadas, frecuencia, capacidad):
    """Referencia lenta, fuera del motor: simula cada bus uno por uno."""
    esperas = []
    frente = 0
    salida = 0
    while frente < len(llegadas):
        subidos = 0
        while frente < len(llegadas) and subidos < capacidad and llegadas[frente] <= salida:
            esperas.append(salida - llegadas[frente])
            frente += 1
            subidos += 1
        salida += frecuencia
    return esperas


class SimulacionTests(unittest.TestCase):
    def test_ejemplo_de_la_guia(self):
        # Salidas (0, 5, 5, 10) para llegadas (0, 1, 5, 5).
        esperas = simular_fila([0, 1, 5, 5], 5, 2)
        self.assertEqual(esperas, [0, 4, 0, 5])
        self.assertEqual(sum(esperas), 9)
        self.assertEqual(sum(esperas) / len(esperas), 2.25)

    def test_vacia(self):
        self.assertEqual(simular_fila([], 5, 2), [])

    def test_llegada_igual_a_salida_alcanza_el_bus(self):
        self.assertEqual(simular_fila([5], 5, 1), [0])
        self.assertEqual(simular_fila([6], 5, 1), [4])

    def test_simultaneas_y_capacidad_uno(self):
        self.assertEqual(simular_fila([0, 0, 0], 3, 1), [0, 3, 6])
        self.assertEqual(simular_fila([2, 2, 2, 2], 3, 3), [1, 1, 1, 4])

    def test_intervalos_grandes_no_simula_buses_vacios(self):
        self.assertEqual(simular_fila([0, 1_000_000_001], 10, 1), [0, 9])

    def test_frecuencia_uno(self):
        self.assertEqual(simular_fila([0, 0, 1, 7], 1, 1), [0, 1, 1, 0])

    def test_fila_que_se_acumula(self):
        # Cada bus sale lleno y el siguiente recoge a quien quedó.
        self.assertEqual(simular_fila([0, 0, 0, 4, 4], 4, 2), [0, 0, 4, 0, 4])

    def test_aleatorio_contra_modelo(self):
        azar = random.Random(42)
        for _ in range(300):
            n = azar.randint(0, 40)
            actual = 0
            llegadas = []
            for _ in range(n):
                actual += azar.randint(0, 6)
                llegadas.append(actual)
            frecuencia = azar.randint(1, 9)
            capacidad = azar.randint(1, 5)
            with self.subTest(llegadas=llegadas, f=frecuencia, c=capacidad):
                self.assertEqual(
                    simular_fila(llegadas, frecuencia, capacidad),
                    modelo_minuto_a_minuto(llegadas, frecuencia, capacidad),
                )

    def test_no_modifica_la_entrada_y_devuelve_lista_nueva(self):
        llegadas = [0, 1, 5, 5]
        primera = simular_fila(llegadas, 5, 2)
        primera.append(99)
        self.assertEqual(llegadas, [0, 1, 5, 5])
        self.assertEqual(simular_fila(llegadas, 5, 2), [0, 4, 0, 5])

    def test_entradas_invalidas(self):
        casos = [
            ([3, 1], 5, 2),        # sin ordenar
            ([-1], 5, 2),          # negativa
            ([0], 0, 2),           # frecuencia cero
            ([0], 5, 0),           # capacidad cero
            ([0], -5, 2),
            ([0.5], 5, 2),         # no entero
            ([True], 5, 2),        # booleano
            ([0], 5, True),
            ([0], "5", 2),
            (None, 5, 2),
        ]
        for llegadas, frecuencia, capacidad in casos:
            with self.subTest(llegadas=llegadas, f=frecuencia, c=capacidad):
                with self.assertRaises(ValueError):
                    simular_fila(llegadas, frecuencia, capacidad)


if __name__ == "__main__":
    unittest.main()
