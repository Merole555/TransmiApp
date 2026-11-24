import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from motor import Red
from scripts import benchmark


class BenchmarkTests(unittest.TestCase):
    def test_serie_simular_fila_y_razones(self):
        datos = benchmark.ejecutar((50, 100, 200), repeticiones=1, lote=100, repeticiones_mutacion=3,
                                   operaciones=["simular_fila"])
        serie = datos["series"][0]
        self.assertEqual(serie["operacion"], "simular_fila")
        self.assertNotIn("error", serie)
        self.assertEqual([p["n"] for p in serie["puntos"]], [50, 100, 200])
        self.assertIsNone(serie["puntos"][0]["razon_anterior"])
        self.assertIsNotNone(serie["puntos"][1]["razon_anterior"])
        self.assertEqual(datos["configuracion"]["unidad"], "ns/llamada")

    def test_guardar_es_atomico_y_crea_carpeta(self):
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "nueva" / "rendimiento.json"
            benchmark.guardar({"configuracion": {}, "series": []}, ruta)
            self.assertEqual(json.loads(ruta.read_text(encoding="utf-8")), {"configuracion": {}, "series": []})
            self.assertEqual([p.name for p in ruta.parent.iterdir()], ["rendimiento.json"])

    def test_redes_generadas_respetan_cabeceras(self):
        with TemporaryDirectory() as carpeta:
            dimensiones = benchmark.red_estaciones(carpeta, 60)
            self.assertEqual(dimensiones["estaciones"], 60)
            cabeceras = [
                (Path(carpeta) / nombre).read_text(encoding="utf-8").splitlines()[0]
                for nombre in ("estaciones.csv", "rutas.csv", "horarios.csv")
            ]
            self.assertEqual(cabeceras, ["nombre", "ruta,orden,estacion", "ruta,estacion,hora"])

    @unittest.skipIf(Red is None, "motor.Red todavía no está integrado")
    def test_todas_las_series_con_la_red_real(self):
        datos = benchmark.ejecutar((40, 80, 160), repeticiones=1, lote=2, repeticiones_mutacion=3)
        errores = [(s["operacion"], s["error"]) for s in datos["series"] if "error" in s]
        self.assertEqual(errores, [])


if __name__ == "__main__":
    unittest.main()
