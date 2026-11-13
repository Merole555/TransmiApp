import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.main import crear_app
from motor import viajes
from test_planes import RedPrueba
from test_viajes import TablaPrueba


class ApiTests(unittest.TestCase):
    def setUp(self):
        carpeta = self.enterContext(TemporaryDirectory())
        self.archivo = Path(carpeta) / "rendimiento.json"
        red = RedPrueba([("t1", ["A", "B", "C"]), ("T2", ["B", "D"])])
        red.horarios = viajes.indexar_horarios(TablaPrueba(), [("t1", "B", "08:05")])
        red.tiene_parada = lambda ruta, nombre: any(
            actual == ruta for actual, _ in red.salidas(nombre)
        )
        self.motor = Mock()
        self.motor.estado = red.estado
        self.motor.viaje = lambda *args: viajes.viaje(red, *args)
        self.motor.proximo_bus = lambda *args: viajes.proximo_bus(red, *args)
        self.motor.ranking.return_value = [("B", 3)]
        self.motor.autocompletar.return_value = ["B"]
        self.motor.rango.return_value = ["A", "B"]
        self.motor.recorrido.return_value = ["C", "B", "A"]
        self.motor.cerrar.side_effect = lambda nombre: red.abiertas.remove(nombre) is None
        self.motor.reabrir.side_effect = lambda nombre: red.abiertas.add(nombre) is None
        self.motor.deshacer.side_effect = lambda: self.motor.reabrir("B")
        self.motor.rehacer.side_effect = lambda: self.motor.cerrar("B")
        self.motor.agregar_parada.return_value = True
        self.motor.quitar_parada.return_value = False
        self.crear_red = Mock(return_value=self.motor)
        self.simular = Mock(return_value=([(0, 0, 0)], 0, 0.0, 0))
        self.medir = Mock(side_effect=self._medir)
        app = crear_app(
            carpeta, crear_red=self.crear_red, simular_fila=self.simular,
            medir=self.medir, archivo_resultados=self.archivo,
        )
        self.client = self.enterContext(TestClient(app))
        self.crear_red.assert_called_once_with(carpeta)

    @staticmethod
    def _medir(salida):
        datos = {"operaciones": []}
        salida.write_text(json.dumps(datos), encoding="utf-8")
        return datos

    def test_consultas_de_estaciones(self):
        self.assertEqual(self.client.get("/api/salud").json(), {"ok": True})
        self.assertEqual(
            self.client.get("/api/estado", params={"nombre": "  bé  "}).json(),
            {"existe": False, "abierta": False},
        )
        self.assertEqual(
            self.client.get("/api/autocompletar", params={"prefijo": "  b ", "k": 1}).json(),
            {"estaciones": ["B"]},
        )
        self.motor.autocompletar.assert_called_once_with("B", 1)
        self.assertEqual(
            self.client.get("/api/rango", params={"desde": "á", "hasta": "b"}).json(),
            {"estaciones": ["A", "B"]},
        )
        self.motor.rango.assert_called_once_with("A", "B")

    def test_proximo_bus_hora_y_ruta(self):
        ruta = "/api/proximo-bus"
        parametros = {"estacion": " b ", "ruta": "t1", "hora": "08:05"}
        self.assertEqual(self.client.get(ruta, params=parametros).json(), {"hora": "08:05"})
        parametros["ruta"] = "T1"
        respuesta = self.client.get(ruta, params=parametros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"hora": None})
        parametros["hora"] = "24:00"
        self.assertEqual(self.client.get(ruta, params=parametros).status_code, 422)

    def test_viaje_cierre_e_historial(self):
        def plan(origen, destino):
            respuesta = self.client.get("/api/viaje", params={"origen": origen, "destino": destino})
            self.assertEqual(respuesta.status_code, 200)
            return respuesta.json()["viaje"]

        self.assertEqual(plan("á", "c"), {
            "saltos": 2, "tramos": [{"ruta": "t1", "sube": "A", "baja": "C"}],
        })
        esperado = {"saltos": 2, "tramos": [
            {"ruta": "t1", "sube": "A", "baja": "B"},
            {"ruta": "T2", "sube": "B", "baja": "D"},
        ]}
        self.assertEqual(plan("a", "d"), esperado)
        self.assertIsNone(plan("d", "a"))
        self.assertEqual(self.client.post("/api/cerrar", json={"nombre": "b"}).json(), {"cambio": True})
        self.assertIsNone(plan("a", "d"))
        self.assertEqual(self.client.post("/api/deshacer").json(), {"cambio": True})
        self.assertEqual(plan("a", "d"), esperado)
        self.assertEqual(self.client.post("/api/rehacer").json(), {"cambio": True})
        self.assertIsNone(plan("a", "d"))
        self.assertEqual(self.client.post("/api/reabrir", json={"nombre": "b"}).json(), {"cambio": True})
        self.assertEqual(plan("a", "d"), esperado)

    def test_ranking_recorrido_y_ediciones(self):
        self.assertEqual(self.client.get("/api/ranking?k=1").json(), {
            "ranking": [{"estacion": "B", "buses": 3}],
        })
        self.assertEqual(self.client.get("/api/ranking?k=uno").status_code, 422)
        self.assertEqual(self.client.get("/api/recorrido?ruta=t1&al_reves=true").json(), {
            "estaciones": ["C", "B", "A"],
        })
        self.motor.recorrido.assert_called_once_with("t1", True)
        self.assertEqual(self.client.post("/api/paradas/agregar", json={
            "ruta": "t1", "nueva": "é", "despues_de": " b ",
        }).json(), {"cambio": True})
        self.motor.agregar_parada.assert_called_once_with("t1", "E", "B")
        respuesta = self.client.post("/api/paradas/quitar", json={"ruta": "t1", "estacion": "e"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"cambio": False})
        self.motor.quitar_parada.assert_called_once_with("t1", "E")

    def test_fila_valida_y_tipo_invalido(self):
        url = "/api/simular-fila"
        entrada = {"llegadas": [0], "frecuencia": 4, "capacidad": 2}
        self.assertEqual(self.client.post(url, json=entrada).json(), {
            "abordajes": [{"indice_original": 0, "llegada": 0, "salida": 0}],
            "espera_total": 0, "espera_promedio": 0.0, "espera_maxima": 0,
        })
        entrada["capacidad"] = True
        self.assertEqual(self.client.post(url, json=entrada).status_code, 422)
        self.simular.assert_called_once_with([0], 4, 2)

    def test_rendimiento_ausente_guardado_y_en_curso(self):
        url = "/api/rendimiento"
        self.assertEqual(self.client.get(url).status_code, 404)
        iniciada = Event()
        continuar = Event()

        def medicion(salida):
            iniciada.set()
            if not continuar.wait(5):
                raise TimeoutError("La prueba no liberó la medición")
            return self._medir(salida)

        self.medir.side_effect = medicion
        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            trabajo = ejecutor.submit(self.client.post, url)
            try:
                self.assertTrue(iniciada.wait(5))
                self.assertEqual(self.client.post(url).status_code, 409)
                self.assertEqual(self.client.get("/api/ranking?k=1").status_code, 200)
            finally:
                continuar.set()
            self.assertEqual(trabajo.result().json(), {"operaciones": []})
        self.assertEqual(self.client.get(url).json(), {"operaciones": []})
