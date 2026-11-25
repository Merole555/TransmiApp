"""Pruebas reproducibles de estrés R1–R11 sobre una Red real y FastAPI.

No utilizan datos externos ni fijan umbrales de tiempo dependientes de CPU.
La intención es comprobar invariantes con volúmenes y repeticiones superiores
a las pruebas unitarias habituales. Para medir complejidad se usa R11.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import crear_app
from motor import Red, simular_fila
from scripts import benchmark


def preparar_csv(carpeta, n=400):
    """Una ruta larga y otra que transborda en la última parada de la primera."""
    carpeta = Path(carpeta)
    with (carpeta / "estaciones.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nombre"])
        for i in range(n):
            w.writerow([f"E{i:04d}"])
        w.writerow(["EXTRA"])

    mitad = n // 2
    with (carpeta / "rutas.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ruta", "orden", "estacion"])
        for i in range(mitad + 1):
            w.writerow(["T1", i + 1, f"E{i:04d}"])
        for i in range(mitad, n):
            w.writerow(["T2", i - mitad + 1, f"E{i:04d}"])

    with (carpeta / "horarios.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ruta", "estacion", "hora"])
        for ruta, start, end in (("T1", 0, mitad + 1), ("T2", mitad, n)):
            for i in range(start, end):
                for h in ("08:00", "08:00", "09:00"):
                    w.writerow([ruta, f"E{i:04d}", h])


class EstresMotor(unittest.TestCase):
    def setUp(self):
        self.carpeta = self.enterContext(tempfile.TemporaryDirectory())
        preparar_csv(self.carpeta)
        self.red = Red(self.carpeta)

    def test_r1_r2_r3_muchas_consultas(self):
        red = self.red
        for i in range(600):
            nombre = f"E{i % 400:04d}"
            self.assertEqual(red.estado(nombre), "ABIERTA")
            self.assertEqual(red.estado("NO_EXISTE"), "NO_EXISTE")
        for _ in range(60):
            sugerencias = red.autocompletar("E0", 20)
            self.assertEqual(len(sugerencias), 20)
            self.assertEqual(sugerencias, sorted(sugerencias))
            tramo = red.rango("E0100", "E0120")
            self.assertEqual(len(tramo), 21)
            self.assertEqual(tramo[0], "E0100")
            self.assertEqual(tramo[-1], "E0120")

    def test_r4_r5_r6_indices_grandes(self):
        red = self.red
        for i in range(120):
            nombre = f"E{i:04d}"
            self.assertEqual(red.proximo_bus(nombre, "T1", "08:00"), "08:00")
            self.assertEqual(red.proximo_bus(nombre, "T1", "08:01"), "09:00")
            self.assertIsNone(red.proximo_bus(nombre, "T1", "09:01"))
        for _ in range(8):
            directo = red.viaje("E0000", "E0200")
            self.assertEqual(directo[0], "DIRECTO")
            self.assertEqual(directo[1], 200)
            plan = red.viaje("E0000", "E0399")
            self.assertEqual(plan[0], "TRANSBORDO")
            self.assertEqual(plan[1], 399)
        ranking = red.ranking(401)
        self.assertEqual(len(ranking), 401)
        self.assertEqual(ranking[0], ("E0200", 6))
        self.assertEqual(ranking[-1], ("EXTRA", 0))
        self.assertEqual(len(red.ranking(12)), 12)

    def test_r7_r8_r9_mutaciones_y_reversion(self):
        red = self.red
        anterior = red.recorrido("T1")
        conteo = red.ranking(4)
        for _ in range(40):
            self.assertTrue(red.agregar_parada("T1", "EXTRA", "E0100"))
            self.assertEqual(len(red.recorrido("T1")), len(anterior) + 1)
            self.assertTrue(red.deshacer())
            self.assertEqual(red.recorrido("T1"), anterior)
            self.assertTrue(red.rehacer())
            self.assertTrue(red.quitar_parada("T1", "EXTRA"))
            self.assertEqual(red.recorrido("T1"), anterior)
            self.assertEqual(red.ranking(4), conteo)
        for _ in range(35):
            self.assertTrue(red.cerrar("E0200"))
            self.assertEqual(red.estado("E0200"), "CERRADA")
            self.assertIsNone(red.viaje("E0000", "E0399"))
            self.assertTrue(red.deshacer())
            self.assertEqual(red.estado("E0200"), "ABIERTA")
            self.assertTrue(red.rehacer())
            self.assertTrue(red.reabrir("E0200"))
            self.assertEqual(red.ranking(4), conteo)

    def test_r10_fila_muchos_pasajeros(self):
        llegadas = [i // 2 for i in range(20000)]
        esperas = simular_fila(llegadas, 5, 20)
        self.assertEqual(len(esperas), len(llegadas))
        self.assertTrue(all(e >= 0 for e in esperas))
        self.assertEqual(esperas[0], 0)
        self.assertEqual(simular_fila([], 5, 20), [])

    def test_r11_serie_completa_sin_errores(self):
        datos = benchmark.ejecutar((40, 80, 160), 1)
        self.assertEqual(len(datos["series"]), 15)
        for serie in datos["series"]:
            self.assertNotIn("error", serie, serie["operacion"])
            self.assertEqual(len(serie["puntos"]), 3)
            self.assertEqual([p["n"] for p in serie["puntos"]], [40, 80, 160])


class EstresHttp(unittest.TestCase):
    def test_rutas_minusculas_con_motor_real_y_carga(self):
        with tempfile.TemporaryDirectory() as carpeta:
            preparar_csv(carpeta, 120)
            archivo = Path(carpeta) / "rendimiento.json"
            archivo.write_text(json.dumps({"series": []}), encoding="utf-8")
            app = crear_app(carpeta, archivo_resultados=archivo)
            with TestClient(app) as client:
                for _ in range(30):
                    self.assertEqual(client.get("/api/estado", params={"nombre": "e0000"}).json(),
                                     {"existe": True, "abierta": True})
                    self.assertEqual(client.get("/api/proximo-bus", params={
                        "estacion": "e0000", "ruta": " t1 ", "hora": "08:00",
                    }).json()["hora"], "08:00")
                    self.assertEqual(len(client.get("/api/recorrido", params={
                        "ruta": "t1",
                    }).json()["estaciones"]), 61)
                self.assertTrue(client.post("/api/paradas/agregar", json={
                    "ruta": "t1", "nueva": "extra", "despues_de": "e0010",
                }).json()["cambio"])
                self.assertTrue(client.post("/api/deshacer").json()["cambio"])
                self.assertEqual(client.get("/api/rendimiento").status_code, 200)
                self.assertEqual(client.post("/api/simular-fila", json={
                    "llegadas": [0, 1, 5, 5], "frecuencia": 5, "capacidad": 2,
                }).json()["esperas"], [0, 4, 0, 5])


if __name__ == "__main__":
    unittest.main()
