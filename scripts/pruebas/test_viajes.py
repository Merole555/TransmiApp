import unittest
from types import SimpleNamespace

from motor.viajes import indexar_horarios, proximo_bus


class TablaPrueba(dict):
    obtener = dict.get
    asignar = dict.__setitem__


class ProximoBusTests(unittest.TestCase):
    def setUp(self):
        horarios = indexar_horarios(TablaPrueba(), [
            ("T1", "B", "23:59"),
            ("T1", "B", "08:05"),
            ("T1", "B", "08:05"),
            ("T1", "B", "00:00"),
            ("T2", "B", "08:12"),
        ])
        self.abiertas = {"A", "B"}
        self.paradas = {("T1", "A"), ("T1", "B"), ("T2", "B")}
        self.red = SimpleNamespace(
            horarios=horarios,
            estado=lambda nombre: (nombre in {"A", "B"}, nombre in self.abiertas),
            tiene_parada=lambda ruta, nombre: (ruta, nombre) in self.paradas,
        )

    def test_horas_ordenadas_y_duplicados(self):
        self.assertEqual(self.red.horarios["T1", "B"], [0, 485, 485, 1439])
        for consulta, esperada in [
            ("00:00", "00:00"), ("08:00", "08:05"), ("08:05", "08:05"),
            ("08:06", "23:59"), ("23:59", "23:59"),
        ]:
            with self.subTest(consulta=consulta):
                self.assertEqual(proximo_bus(self.red, "B", "T1", consulta), esperada)

    def test_ausencias(self):
        for estacion, ruta, hora in [
            ("B", "T2", "08:13"), ("A", "T1", "00:00"),
            ("X", "T1", "00:00"), ("B", "X", "00:00"),
        ]:
            with self.subTest(estacion=estacion, ruta=ruta, hora=hora):
                self.assertIsNone(proximo_bus(self.red, estacion, ruta, hora))

    def test_cierre_y_membresia(self):
        self.abiertas.remove("B")
        self.assertIsNone(proximo_bus(self.red, "B", "T1", "08:05"))
        self.abiertas.add("B")
        self.paradas.remove(("T1", "B"))
        self.assertIsNone(proximo_bus(self.red, "B", "T1", "08:05"))
        self.paradas.add(("T1", "B"))
        self.assertEqual(proximo_bus(self.red, "B", "T1", "08:05"), "08:05")

    def test_hora_invalida_aun_si_no_hay_estacion(self):
        for hora in ("8:05", "24:00", "08:60", "08-05", "０８:０５", None):
            with self.subTest(hora=hora), self.assertRaises(ValueError):
                proximo_bus(self.red, "X", "T1", hora)
