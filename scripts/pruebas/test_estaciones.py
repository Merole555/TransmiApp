import math
import tempfile
import unittest
from pathlib import Path

from motor import Red
from motor import estaciones
from motor.estructuras import ArbolAVL, TablaHash

ESTACIONES = ["nombre", "A", "B", "C", "D", "E"]
RUTAS = ["ruta,orden,estacion", "T1,1,A", "T1,2,B", "T1,3,C", "T2,1,B", "T2,2,D"]
HORARIOS = ["ruta,estacion,hora", "T1,A,08:00", "T1,B,08:05", "T1,B,08:10",
            "T1,C,08:15", "T2,B,08:12", "T2,D,08:20"]


def escribir_red(carpeta, estaciones_csv=ESTACIONES, rutas_csv=RUTAS, horarios_csv=HORARIOS):
    carpeta = Path(carpeta)
    (carpeta / "estaciones.csv").write_text("\n".join(estaciones_csv) + "\n", encoding="utf-8")
    (carpeta / "rutas.csv").write_text("\n".join(rutas_csv) + "\n", encoding="utf-8")
    (carpeta / "horarios.csv").write_text("\n".join(horarios_csv) + "\n", encoding="utf-8")


class TablaHashTests(unittest.TestCase):
    def test_colisiones_en_el_mismo_cubo(self):
        tabla = TablaHash(64)
        # se buscan dos nombres distintos que caigan en el mismo cubo
        primero = "E0"
        segundo = None
        i = 1
        while segundo is None:
            candidato = f"E{i}"
            if tabla._hash(candidato) % 64 == tabla._hash(primero) % 64:
                segundo = candidato
            i += 1
        tabla.asignar(primero, 1)
        tabla.asignar(segundo, 2)
        self.assertIs(tabla._cubo(primero), tabla._cubo(segundo))
        self.assertEqual(tabla.obtener(primero), 1)
        self.assertEqual(tabla.obtener(segundo), 2)
        self.assertTrue(tabla.eliminar(primero))
        self.assertFalse(tabla.contiene(primero))
        self.assertEqual(tabla.obtener(segundo), 2)

    def test_redimensiona_y_conserva(self):
        tabla = TablaHash(2)
        for i in range(1000):
            tabla.asignar(f"E{i}", i)
        self.assertEqual(len(tabla), 1000)
        self.assertGreater(len(tabla.cubos), 1000)
        for i in range(1000):
            self.assertEqual(tabla.obtener(f"E{i}"), i)

    def test_claves_tupla(self):
        tabla = TablaHash()
        tabla.asignar(("T1", "B"), [485])
        self.assertEqual(tabla.obtener(("T1", "B")), [485])
        self.assertIsNone(tabla.obtener(("T1B", "")))


class ArbolAVLTests(unittest.TestCase):
    def altura_maxima(self, n):
        return 1.45 * math.log2(n + 2)

    def test_insercion_ordenada_queda_balanceada(self):
        arbol = ArbolAVL()
        for i in range(1000):
            arbol.insertar(f"{i:04d}")
        self.assertLessEqual(arbol.raiz.altura, self.altura_maxima(1000))
        self.assertEqual(list(arbol.en_orden()), [f"{i:04d}" for i in range(1000)])

    def test_rotaciones_dobles(self):
        for orden in (["C", "A", "B"], ["A", "C", "B"]):
            arbol = ArbolAVL()
            for clave in orden:
                arbol.insertar(clave)
            self.assertEqual(arbol.raiz.clave, "B")
            self.assertEqual(arbol.raiz.altura, 2)

    def test_eliminar_y_repetidos(self):
        arbol = ArbolAVL()
        for i in range(200):
            self.assertTrue(arbol.insertar(f"{i:03d}"))
        self.assertFalse(arbol.insertar("005"))
        for i in range(0, 200, 2):
            self.assertTrue(arbol.eliminar(f"{i:03d}"))
        self.assertFalse(arbol.eliminar("000"))
        self.assertEqual(len(arbol), 100)
        self.assertEqual(list(arbol.en_orden()), [f"{i:03d}" for i in range(1, 200, 2)])
        self.assertLessEqual(arbol.raiz.altura, self.altura_maxima(100))

    def test_desde_limite_inferior(self):
        arbol = ArbolAVL()
        for clave in ["B", "D", "F", "H"]:
            arbol.insertar(clave)
        self.assertEqual(list(arbol.desde("C")), ["D", "F", "H"])
        self.assertEqual(list(arbol.desde("D")), ["D", "F", "H"])
        self.assertEqual(list(arbol.desde("Z")), [])


class EstacionesTests(unittest.TestCase):
    def setUp(self):
        self.carpeta = self.enterContext(tempfile.TemporaryDirectory())
        escribir_red(self.carpeta)
        self.red = Red(self.carpeta)

    def test_estado(self):
        self.assertEqual(self.red.estado("A"), "ABIERTA")
        self.assertEqual(self.red.estado("Z"), "NO_EXISTE")
        estaciones.retirar_abierta(self.red, "B")
        self.assertEqual(self.red.estado("B"), "CERRADA")

    def test_rango(self):
        self.assertEqual(self.red.rango("B", "D"), ["B", "C", "D"])
        self.assertEqual(self.red.rango("C", "C"), ["C"])
        self.assertEqual(self.red.rango("D", "B"), [])
        self.assertEqual(self.red.rango("BB", "CZ"), ["C"])
        self.assertEqual(self.red.rango("F", "Z"), [])
        estaciones.retirar_abierta(self.red, "B")
        self.assertEqual(self.red.rango("B", "D"), ["C", "D"])
        estaciones.reinsertar_abierta(self.red, "B")
        self.assertEqual(self.red.rango("B", "D"), ["B", "C", "D"])

    def test_autocompletar(self):
        self.assertEqual(self.red.autocompletar("", 2), ["A", "B"])
        self.assertEqual(self.red.autocompletar("C", 5), ["C"])
        self.assertEqual(self.red.autocompletar("X", 5), [])
        self.assertEqual(self.red.autocompletar("A", 0), [])
        self.assertEqual(self.red.autocompletar("A", -1), [])
        self.assertEqual(self.red.autocompletar("", 10), ["A", "B", "C", "D", "E"])

    def test_lista_devuelta_es_nueva(self):
        lista = self.red.rango("A", "E")
        lista.append("ZZZ")
        lista.clear()
        self.assertEqual(self.red.rango("A", "E"), ["A", "B", "C", "D", "E"])

    def test_cerrar_cambia_viaje_y_ranking(self):
        self.assertEqual(self.red.viaje("A", "D"), ("TRANSBORDO", 2, [("T1", "A", "B"), ("T2", "B", "D")]))
        self.assertEqual(self.red.ranking(1), [("B", 3)])
        self.assertTrue(estaciones.retirar_abierta(self.red, "B"))
        self.assertFalse(estaciones.retirar_abierta(self.red, "B"))
        self.assertIsNone(self.red.viaje("A", "D"))
        self.assertIsNone(self.red.proximo_bus("B", "T1", "08:05"))
        self.assertEqual(self.red.viaje("A", "C"), ("DIRECTO", 2, [("T1", "A", "C")]))
        self.assertTrue(estaciones.reinsertar_abierta(self.red, "B"))
        self.assertEqual(self.red.ranking(1), [("B", 3)])


class CargaTests(unittest.TestCase):
    def test_carpeta_con_espacios_y_filas_desordenadas(self):
        with tempfile.TemporaryDirectory() as base:
            carpeta = Path(base) / "red de prueba"
            carpeta.mkdir()
            escribir_red(
                carpeta,
                ["nombre", "E", "C", "A", "D", "B"],
                ["ruta,orden,estacion", "T2,2,D", "T1,3,C", "T1,1,A", "T2,1,B", "T1,2,B"],
                ["ruta,estacion,hora", "T2,D,08:20", "T1,B,08:10", "T1,A,08:00",
                 "T1,B,08:05", "T1,C,08:15", "T2,B,08:12"],
            )
            red = Red(str(carpeta))
            self.assertEqual(red.rango("A", "E"), ["A", "B", "C", "D", "E"])
            self.assertEqual(red.viaje("A", "C"), ("DIRECTO", 2, [("T1", "A", "C")]))
            self.assertEqual(red.proximo_bus("B", "T1", "08:06"), "08:10")

    def test_csv_invalidos_dicen_archivo_y_fila(self):
        casos = [
            ("estaciones.csv, fila 3", ["nombre", "A", "A"], RUTAS[:1], HORARIOS[:1]),
            ("estaciones.csv: la cabecera", ["estacion", "A"], RUTAS[:1], HORARIOS[:1]),
            ("rutas.csv, fila 2", ESTACIONES, ["ruta,orden,estacion", "T1,1,Z"], HORARIOS[:1]),
            ("rutas.csv, fila 3", ESTACIONES, ["ruta,orden,estacion", "T1,1,A", "T1,1,B"], HORARIOS[:1]),
            ("rutas.csv, fila 2", ESTACIONES, ["ruta,orden,estacion", "T1,x,A"], HORARIOS[:1]),
            ("horarios.csv, fila 2", ESTACIONES, RUTAS, ["ruta,estacion,hora", "T1,A,8:00"]),
            ("horarios.csv, fila 2", ESTACIONES, RUTAS, ["ruta,estacion,hora", "T9,A,08:00"]),
            ("horarios.csv, fila 2", ESTACIONES, RUTAS, ["ruta,estacion,hora", "T2,A,08:00"]),
        ]
        for mensaje, est, rut, hor in casos:
            with self.subTest(mensaje=mensaje), tempfile.TemporaryDirectory() as carpeta:
                escribir_red(carpeta, est, rut, hor)
                with self.assertRaises(ValueError) as error:
                    Red(carpeta)
                self.assertIn(mensaje, str(error.exception))

    def test_falta_un_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            escribir_red(carpeta)
            (Path(carpeta) / "horarios.csv").unlink()
            with self.assertRaises(ValueError):
                Red(carpeta)

    def test_red_grande_generada(self):
        n = 3000
        with tempfile.TemporaryDirectory() as carpeta:
            nombres = [f"E{i:05d}" for i in range(n)]
            rutas = ["ruta,orden,estacion"] + [f"R1,{i + 1},{nombres[i]}" for i in range(n)]
            escribir_red(carpeta, ["nombre"] + nombres, rutas, ["ruta,estacion,hora"])
            red = Red(carpeta)
            self.assertEqual(red.autocompletar("E0", 3), ["E00000", "E00001", "E00002"])
            for i in range(0, n, 2):
                estaciones.retirar_abierta(red, nombres[i])
            self.assertEqual(red.rango("E00000", "E00005"), ["E00001", "E00003", "E00005"])
            self.assertEqual(red.viaje(nombres[1], nombres[n - 1])[1], n - 2)
