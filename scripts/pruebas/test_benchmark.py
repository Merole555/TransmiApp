import json
import tempfile
import unittest
from pathlib import Path

from motor import Red
from scripts import benchmark


class BenchmarkTests(unittest.TestCase):
    def test_serie_simular_fila(self):
        datos = benchmark.ejecutar((50, 100, 200), 1, ["simular_fila"])
        serie = datos["series"][0]
        self.assertNotIn("error", serie)
        self.assertEqual([p["n"] for p in serie["puntos"]], [50, 100, 200])
        self.assertIsNone(serie["puntos"][0]["razon_anterior"])

    def test_guardar_crea_carpeta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "nueva" / "rendimiento.json"
            benchmark.guardar({"series": []}, ruta)
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8")), {"series": []})

    def test_cabeceras_csv(self):
        with tempfile.TemporaryDirectory() as carpeta:
            benchmark.red_muchas_estaciones(carpeta, 60)
            primera = [
                (Path(carpeta) / archivo).read_text(encoding="utf-8").splitlines()[0]
                for archivo in ("estaciones.csv", "rutas.csv", "horarios.csv")
            ]
            self.assertEqual(primera, ["nombre", "ruta,orden,estacion", "ruta,estacion,hora"])

    @unittest.skipIf(Red is None, "Red todavía no está integrada")
    def test_todas_las_series(self):
        datos = benchmark.ejecutar((40, 80, 160), 1)
        errores = [s["operacion"] for s in datos["series"] if "error" in s]
        self.assertEqual(errores, [])
