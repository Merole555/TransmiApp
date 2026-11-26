import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.main import crear_app


class ApiAuxiliarTests(unittest.TestCase):
    def test_rutas_cerradas_e_historial(self):
        carpeta = self.enterContext(TemporaryDirectory())
        motor = Mock()
        motor.listar_rutas.return_value = ["T1", "T2"]
        motor.listar_cerradas.return_value = ["B"]
        motor.historial.return_value = (["Cerrar B"], ["Quitar B de T2"])
        app = crear_app(
            carpeta, crear_red=Mock(return_value=motor), simular_fila=Mock(),
            archivo_resultados=Path(carpeta) / "rendimiento.json",
        )
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/rutas").json(), {"rutas": ["T1", "T2"]})
            self.assertEqual(client.get("/api/cerradas").json(), {"estaciones": ["B"]})
            self.assertEqual(client.get("/api/historial").json(), {
                "deshacer": ["Cerrar B"], "rehacer": ["Quitar B de T2"],
            })
