import random
import tempfile
import unittest

from motor import Red
from test_estaciones import escribir_red

NOMBRES = ("A", "B", "C", "D", "E")
RUTAS_OBS = ("T1", "T2", "T9")
# minutos de horarios.csv de la red compartida
MINUTOS = {
    ("T1", "A"): [480], ("T1", "B"): [485, 490], ("T1", "C"): [495],
    ("T2", "B"): [492], ("T2", "D"): [500],
}


def observar(red):
    """Todo lo visible de R1-R7 para comparar antes y después."""
    return {
        "estados": [red.estado(e) for e in NOMBRES + ("Z",)],
        "autocompletar": red.autocompletar("", 10),
        "rango": red.rango("A", "E"),
        "buses": [red.proximo_bus(e, r, "00:00") for e in NOMBRES for r in RUTAS_OBS],
        "viajes": [red.viaje(o, d) for o in NOMBRES for d in NOMBRES],
        "ranking": red.ranking(10),
        "rutas": [(red.recorrido(r), red.recorrido(r, al_reves=True)) for r in RUTAS_OBS],
    }


TRANSBORDO_AD = ("TRANSBORDO", 2, [("T1", "A", "B"), ("T2", "B", "D")])
RANKING_BASE = [("B", 3), ("A", 1), ("C", 1), ("D", 1), ("E", 0)]


class OperacionesBase(unittest.TestCase):
    def setUp(self):
        self.carpeta = self.enterContext(tempfile.TemporaryDirectory())
        escribir_red(self.carpeta)
        self.red = Red(self.carpeta)


class CierreTests(OperacionesBase):
    def test_cerrar_deshacer_rehacer(self):
        red = self.red
        base = observar(red)
        self.assertEqual(red.viaje("A", "D"), TRANSBORDO_AD)
        self.assertEqual(red.ranking(5), RANKING_BASE)

        self.assertTrue(red.cerrar("B"))
        self.assertFalse(red.cerrar("B"))
        cerrado = observar(red)
        self.assertEqual(red.estado("B"), "CERRADA")
        self.assertEqual(red.autocompletar("", 10), ["A", "C", "D", "E"])
        self.assertEqual(red.rango("A", "E"), ["A", "C", "D", "E"])
        self.assertIsNone(red.proximo_bus("B", "T1", "08:05"))
        self.assertIsNone(red.viaje("A", "D"))
        self.assertEqual(red.viaje("A", "C"), ("DIRECTO", 2, [("T1", "A", "C")]))
        self.assertEqual(red.ranking(5), [("A", 1), ("C", 1), ("D", 1), ("E", 0)])
        self.assertEqual(red.recorrido("T1"), ["A", "B", "C"])   # trazado físico

        self.assertTrue(red.deshacer())
        self.assertEqual(observar(red), base)
        self.assertEqual(red.proximo_bus("B", "T1", "08:05"), "08:05")
        self.assertTrue(red.rehacer())
        self.assertEqual(observar(red), cerrado)
        self.assertTrue(red.deshacer())
        self.assertEqual(observar(red), base)

    def test_cerrar_y_reabrir_validan(self):
        red = self.red
        self.assertFalse(red.reabrir("B"))
        self.assertFalse(red.cerrar("Z"))
        self.assertFalse(red.reabrir("Z"))
        self.assertTrue(red.cerrar("B"))
        self.assertTrue(red.reabrir("B"))
        self.assertEqual(red.estado("B"), "ABIERTA")
        self.assertEqual(red.ranking(1), [("B", 3)])
        self.assertTrue(red.deshacer())      # deshace reabrir
        self.assertEqual(red.estado("B"), "CERRADA")
        self.assertTrue(red.deshacer())      # deshace cerrar
        self.assertEqual(red.estado("B"), "ABIERTA")
        self.assertFalse(red.deshacer())

    def test_historial_vacio(self):
        self.assertFalse(self.red.deshacer())
        self.assertFalse(self.red.rehacer())


class EdicionTests(OperacionesBase):
    def test_agregar_en_medio(self):
        red = self.red
        base = observar(red)
        self.assertTrue(red.agregar_parada("T1", "E", "B"))
        self.assertEqual(red.recorrido("T1"), ["A", "B", "E", "C"])
        self.assertEqual(red.recorrido("T1", al_reves=True), ["C", "E", "B", "A"])
        self.assertEqual(red.viaje("A", "C"), ("DIRECTO", 3, [("T1", "A", "C")]))
        self.assertEqual(red.viaje("A", "E"), ("DIRECTO", 2, [("T1", "A", "E")]))
        self.assertTrue(red.tiene_parada("T1", "E"))
        self.assertIsNone(red.proximo_bus("E", "T1", "00:00"))   # no se inventan horarios
        self.assertEqual(red.ranking(5), RANKING_BASE)           # E aporta cero
        agregado = observar(red)

        self.assertTrue(red.deshacer())
        self.assertEqual(observar(red), base)
        self.assertFalse(red.tiene_parada("T1", "E"))
        self.assertTrue(red.rehacer())
        self.assertEqual(observar(red), agregado)

    def test_agregar_rechazos_no_cambian_nada(self):
        red = self.red
        base = observar(red)
        for ruta, nueva, ancla in [
            ("T9", "E", "B"),    # ruta desconocida
            ("T1", "Z", "B"),    # estación inexistente
            ("T1", "A", "B"),    # ya figura en el recorrido
            ("T1", "E", "X"),    # ancla inexistente
            ("T1", "E", "C"),    # ancla sin sucesora
            ("T2", "A", "D"),    # ancla sin sucesora
        ]:
            with self.subTest(ruta=ruta, nueva=nueva, ancla=ancla):
                self.assertFalse(red.agregar_parada(ruta, nueva, ancla))
        self.assertEqual(observar(red), base)
        self.assertFalse(red.deshacer())

    def test_agregar_con_horarios_previos_al_reinsertar(self):
        red = self.red
        self.assertTrue(red.quitar_parada("T1", "C"))          # C: 1 -> 0
        self.assertEqual(red.ranking(5), [("B", 3), ("A", 1), ("D", 1), ("C", 0), ("E", 0)])
        self.assertTrue(red.agregar_parada("T1", "C", "A"))    # reactiva su horario
        self.assertEqual(red.recorrido("T1"), ["A", "C", "B"])
        self.assertEqual(red.ranking(5), RANKING_BASE)
        self.assertEqual(red.proximo_bus("C", "T1", "08:00"), "08:15")

    def test_quitar_de_otra_ruta(self):
        red = self.red
        base = observar(red)
        self.assertTrue(red.quitar_parada("T2", "B"))
        self.assertEqual(red.recorrido("T2"), ["D"])
        self.assertEqual(red.ranking(5), [("B", 2), ("A", 1), ("C", 1), ("D", 1), ("E", 0)])
        self.assertIsNone(red.proximo_bus("B", "T2", "08:00"))
        self.assertEqual(red.proximo_bus("B", "T1", "08:00"), "08:05")
        self.assertIsNone(red.viaje("A", "D"))
        quitado = observar(red)

        self.assertTrue(red.deshacer())
        self.assertEqual(red.ranking(5), RANKING_BASE)
        self.assertEqual(red.proximo_bus("B", "T2", "08:00"), "08:12")
        self.assertEqual(red.viaje("A", "D"), TRANSBORDO_AD)
        self.assertEqual(observar(red), base)
        self.assertTrue(red.rehacer())
        self.assertEqual(observar(red), quitado)

    def test_quitar_ambos_extremos_y_ultima_parada(self):
        red = self.red
        self.assertTrue(red.quitar_parada("T1", "A"))
        self.assertEqual(red.recorrido("T1"), ["B", "C"])
        self.assertTrue(red.quitar_parada("T1", "C"))
        self.assertEqual(red.recorrido("T1"), ["B"])
        self.assertEqual(red.recorrido("T1", al_reves=True), ["B"])
        self.assertFalse(red.quitar_parada("T1", "B"))        # debe quedar una parada
        self.assertFalse(red.quitar_parada("T1", "A"))        # ya no está
        self.assertTrue(red.deshacer())
        self.assertTrue(red.deshacer())
        self.assertEqual(red.recorrido("T1"), ["A", "B", "C"])
        self.assertEqual(red.recorrido("T1", al_reves=True), ["C", "B", "A"])
        self.assertEqual(red.viaje("A", "D"), TRANSBORDO_AD)
        self.assertEqual(red.ranking(5), RANKING_BASE)

    def test_ruta_de_una_parada_y_rutas_desconocidas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            escribir_red(
                carpeta, ["nombre", "A", "B"],
                ["ruta,orden,estacion", "T1,1,A", "T2,1,A", "T2,2,B"],
                ["ruta,estacion,hora"],
            )
            red = Red(carpeta)
            self.assertFalse(red.quitar_parada("T1", "A"))
            self.assertFalse(red.agregar_parada("T1", "B", "A"))   # sin sucesora
            self.assertEqual(red.recorrido("T1"), ["A"])
            self.assertEqual(red.recorrido("T1", al_reves=True), ["A"])
            self.assertEqual(red.recorrido("NOEXISTE"), [])
            self.assertFalse(red.quitar_parada("NOEXISTE", "A"))

    def test_anclas_ambiguas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            escribir_red(
                carpeta, ["nombre", "A", "B", "C", "D"],
                ["ruta,orden,estacion", "R1,1,A", "R1,2,B", "R1,3,A", "R1,4,C"],
                ["ruta,estacion,hora"],
            )
            red = Red(carpeta)
            self.assertFalse(red.agregar_parada("R1", "D", "A"))   # A aparece dos veces
            self.assertFalse(red.quitar_parada("R1", "A"))
            self.assertTrue(red.agregar_parada("R1", "D", "B"))
            self.assertEqual(red.recorrido("R1"), ["A", "B", "D", "A", "C"])
            self.assertTrue(red.quitar_parada("R1", "B"))
            self.assertEqual(red.recorrido("R1"), ["A", "D", "A", "C"])
            self.assertTrue(red.deshacer())
            self.assertTrue(red.deshacer())
            self.assertEqual(red.recorrido("R1"), ["A", "B", "A", "C"])

    def test_recorrido_devuelve_lista_nueva(self):
        red = self.red
        for al_reves, esperado in ((False, ["A", "B", "C"]), (True, ["C", "B", "A"])):
            lista = red.recorrido("T1", al_reves=al_reves)
            lista.append("ZZZ")
            lista.clear()
            self.assertEqual(red.recorrido("T1", al_reves=al_reves), esperado)


class HistorialTests(OperacionesBase):
    def test_mutacion_invalida_conserva_rehacer(self):
        red = self.red
        self.assertTrue(red.agregar_parada("T1", "E", "B"))
        self.assertTrue(red.deshacer())
        self.assertFalse(red.agregar_parada("T1", "E", "Q"))    # inválida
        self.assertFalse(red.cerrar("Z"))                       # inválida
        self.assertTrue(red.rehacer())
        self.assertEqual(red.recorrido("T1"), ["A", "B", "E", "C"])

    def test_mutacion_valida_vacia_rehacer(self):
        red = self.red
        self.assertTrue(red.agregar_parada("T1", "E", "B"))
        self.assertTrue(red.deshacer())
        self.assertTrue(red.quitar_parada("T2", "B"))           # mutación nueva
        self.assertFalse(red.rehacer())
        self.assertEqual(red.recorrido("T1"), ["A", "B", "C"])  # lo descartado no vuelve
        self.assertTrue(red.deshacer())
        self.assertFalse(red.deshacer())


class ModeloReferencia:
    """Modelo pequeño con listas, dict y set (permitido fuera de motor/)."""

    def __init__(self):
        self.rutas = {"T1": ["A", "B", "C"], "T2": ["B", "D"]}
        self.cerradas = set()
        self.pasado = []
        self.futuro = []

    def _foto(self):
        return ({k: list(v) for k, v in self.rutas.items()}, set(self.cerradas))

    def _restaurar(self, foto):
        self.rutas = {k: list(v) for k, v in foto[0].items()}
        self.cerradas = set(foto[1])

    def _guardar(self):
        self.pasado.append(self._foto())
        self.futuro.clear()

    def agregar(self, ruta, nueva, ancla):
        r = self.rutas.get(ruta)
        if r is None or nueva not in NOMBRES or nueva in r or r.count(ancla) != 1:
            return False
        i = r.index(ancla)
        if i == len(r) - 1:
            return False
        self._guardar()
        r.insert(i + 1, nueva)
        return True

    def quitar(self, ruta, estacion):
        r = self.rutas.get(ruta)
        if r is None or r.count(estacion) != 1 or len(r) == 1:
            return False
        self._guardar()
        r.remove(estacion)
        return True

    def cerrar(self, nombre):
        if nombre not in NOMBRES or nombre in self.cerradas:
            return False
        self._guardar()
        self.cerradas.add(nombre)
        return True

    def reabrir(self, nombre):
        if nombre not in self.cerradas:
            return False
        self._guardar()
        self.cerradas.discard(nombre)
        return True

    def deshacer(self):
        if not self.pasado:
            return False
        self.futuro.append(self._foto())
        self._restaurar(self.pasado.pop())
        return True

    def rehacer(self):
        if not self.futuro:
            return False
        self.pasado.append(self._foto())
        self._restaurar(self.futuro.pop())
        return True

    def abiertas(self):
        return [e for e in NOMBRES if e not in self.cerradas]

    def proximo(self, estacion, ruta):
        r = self.rutas.get(ruta)
        if estacion in self.cerradas or r is None or estacion not in r:
            return None
        minutos = MINUTOS.get((ruta, estacion))
        if not minutos:
            return None
        return f"{minutos[0] // 60:02d}:{minutos[0] % 60:02d}"

    def ranking(self, k):
        filas = []
        for e in self.abiertas():
            total = 0
            for ruta, paradas in self.rutas.items():
                if e in paradas:
                    total += len(MINUTOS.get((ruta, e), []))
            filas.append((-total, e))
        filas.sort()
        return [(e, -n) for n, e in filas][:k]


class ModeloTests(unittest.TestCase):
    def comparar(self, red, modelo, mensaje):
        for ruta in RUTAS_OBS:
            esperado = modelo.rutas.get(ruta, [])
            self.assertEqual(red.recorrido(ruta), esperado, mensaje)
            self.assertEqual(red.recorrido(ruta, al_reves=True), esperado[::-1], mensaje)
        for e in NOMBRES:
            esperado = "CERRADA" if e in modelo.cerradas else "ABIERTA"
            self.assertEqual(red.estado(e), esperado, mensaje)
            for ruta in RUTAS_OBS:
                self.assertEqual(red.proximo_bus(e, ruta, "00:00"), modelo.proximo(e, ruta), mensaje)
        self.assertEqual(red.autocompletar("", 10), modelo.abiertas(), mensaje)
        self.assertEqual(red.rango("A", "E"), modelo.abiertas(), mensaje)
        self.assertEqual(red.ranking(10), modelo.ranking(10), mensaje)

    def test_secuencias_contra_modelo(self):
        for semilla in range(6):
            with self.subTest(semilla=semilla), tempfile.TemporaryDirectory() as carpeta:
                escribir_red(carpeta)
                red = Red(carpeta)
                modelo = ModeloReferencia()
                base = observar(red)
                azar = random.Random(semilla)
                for paso in range(300):
                    op = azar.choice(["agregar", "agregar", "quitar", "quitar", "cerrar",
                                      "reabrir", "deshacer", "deshacer", "rehacer"])
                    ruta = azar.choice(RUTAS_OBS)
                    a = azar.choice(NOMBRES + ("Z",))
                    b = azar.choice(NOMBRES + ("Z",))
                    mensaje = f"semilla {semilla} paso {paso}: {op} {ruta} {a} {b}"
                    if op == "agregar":
                        esperado, obtenido = modelo.agregar(ruta, a, b), red.agregar_parada(ruta, a, b)
                    elif op == "quitar":
                        esperado, obtenido = modelo.quitar(ruta, a), red.quitar_parada(ruta, a)
                    elif op == "cerrar":
                        esperado, obtenido = modelo.cerrar(a), red.cerrar(a)
                    elif op == "reabrir":
                        esperado, obtenido = modelo.reabrir(a), red.reabrir(a)
                    elif op == "deshacer":
                        esperado, obtenido = modelo.deshacer(), red.deshacer()
                    else:
                        esperado, obtenido = modelo.rehacer(), red.rehacer()
                    self.assertEqual(obtenido, esperado, mensaje)
                    self.comparar(red, modelo, mensaje)

                # deshacer todo regresa exactamente a la red inicial
                while True:
                    esperado, obtenido = modelo.deshacer(), red.deshacer()
                    self.assertEqual(obtenido, esperado)
                    if not esperado:
                        break
                self.comparar(red, modelo, "tras deshacer todo")
                self.assertEqual(observar(red), base)
