import csv
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from motor import Red
from scripts.convertir_gtfs import a_minutos, convertir, normalizar

GTFS = {
    "stops.txt": [
        "stop_id,stop_name,location_type,parent_station",
        "S1,Portal  Norte,1,",
        "P1a,Portal Norte - Vagón 1,0,S1",
        "P1b,Portal Norte - Vagón 2,0,S1",
        "S2,Calle 100,1,",
        "P2,Calle 100 andén,0,S2",
        "S3,Héroes,1,",
        "P3,Héroes andén,0,S3",
        "Z1,Cra 7 con 72,0,",
    ],
    "routes.txt": [
        "route_id,route_short_name,route_type",
        "R1,B74,3",
        "R2,ZON,3",
    ],
    "calendar.txt": [
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date",
        "SEMANA,1,1,1,1,1,0,0,20210701,20210731",
        "SABADO,0,0,0,0,0,1,0,20210701,20210731",
    ],
    "calendar_dates.txt": [
        "service_id,date,exception_type",
        "SEMANA,20210722,2",
    ],
    "trips.txt": [
        "route_id,service_id,trip_id,direction_id",
        "R1,SEMANA,t1,0",
        "R1,SEMANA,t2,0",
        "R1,SEMANA,t3,1",
        "R2,SEMANA,t4,0",
        "R1,SABADO,t5,0",
    ],
    "stop_times.txt": [
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence",
        # t1: dos vagones seguidos de Portal Norte cuentan como un solo paso
        "t1,08:00:00,08:00:30,P1a,1",
        "t1,08:01:00,08:01:00,P1b,2",
        "t1,08:10:00,,P2,3",
        "t1,08:20:59,08:20:59,P3,10",
        # t2: viaje que pasa la medianoche
        "t2,24:50:00,24:50:00,P1a,1",
        "t2,25:10:00,25:10:00,P2,2",
        "t2,25:30:00,25:30:00,P3,3",
        # t3: otro sentido
        "t3,09:00:00,09:00:00,P3,1",
        "t3,09:30:00,09:30:00,P1a,2",
        # t4: zonal (Z1 no está dentro de una estación)
        "t4,10:00:00,10:00:00,Z1,1",
        "t4,10:10:00,10:10:00,P2,2",
        # t5: solo sábados
        "t5,11:00:00,11:00:00,P1a,1",
        "t5,11:10:00,11:10:00,P2,2",
    ],
}


def crear_zip(carpeta, tablas=GTFS):
    ruta = Path(carpeta) / "gtfs.zip"
    with zipfile.ZipFile(ruta, "w") as archivo:
        for nombre, lineas in tablas.items():
            archivo.writestr(nombre, "\n".join(lineas) + "\n")
    return ruta


def leer(carpeta, nombre):
    with open(Path(carpeta) / nombre, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.carpeta = self.enterContext(tempfile.TemporaryDirectory())
        self.zip = crear_zip(self.carpeta)
        self.salida = Path(self.carpeta) / "datos"

    def test_dia_habil(self):
        resumen, _ = convertir(self.zip, self.salida, date(2021, 7, 21))
        self.assertEqual(leer(self.salida, "estaciones.csv"),
                         [["nombre"], ["CALLE 100"], ["HEROES"], ["PORTAL NORTE"]])
        self.assertEqual(leer(self.salida, "rutas.csv"), [
            ["ruta", "orden", "estacion"],
            ["B74_0_01", "1", "PORTAL NORTE"], ["B74_0_01", "2", "CALLE 100"], ["B74_0_01", "3", "HEROES"],
            ["B74_1_01", "1", "HEROES"], ["B74_1_01", "2", "PORTAL NORTE"],
        ])
        self.assertEqual(leer(self.salida, "horarios.csv"), [
            ["ruta", "estacion", "hora"],
            ["B74_0_01", "CALLE 100", "01:10"], ["B74_0_01", "CALLE 100", "08:10"],
            ["B74_0_01", "HEROES", "01:30"], ["B74_0_01", "HEROES", "08:20"],
            ["B74_0_01", "PORTAL NORTE", "00:50"], ["B74_0_01", "PORTAL NORTE", "08:00"],
            ["B74_1_01", "HEROES", "09:00"], ["B74_1_01", "PORTAL NORTE", "09:30"],
        ])
        self.assertEqual(resumen["estaciones"], 3)
        # los CSV generados se pueden cargar en el motor
        red = Red(self.salida)
        self.assertEqual(red.proximo_bus("CALLE 100", "B74_0_01", "08:00"), "08:10")
        self.assertEqual(red.viaje("PORTAL NORTE", "HEROES"), ("DIRECTO", 2, [("B74_0_01", "PORTAL NORTE", "HEROES")]))

    def test_excepcion_quita_el_servicio(self):
        # el 22 de julio SEMANA no corre; solo quedan los pasos de después de
        # medianoche del viaje t2 del 21 de julio
        convertir(self.zip, self.salida, date(2021, 7, 22))
        horas = [fila[2] for fila in leer(self.salida, "horarios.csv")[1:]]
        self.assertEqual(sorted(horas), ["00:50", "01:10", "01:30"])

    def test_todas_las_rutas_incluye_zonales(self):
        convertir(self.zip, self.salida, date(2021, 7, 21), solo_troncales=False)
        nombres = [fila[0] for fila in leer(self.salida, "estaciones.csv")[1:]]
        self.assertIn("CRA 7 CON 72", nombres)

    def test_sin_calendario_se_detiene(self):
        tablas = dict(GTFS)
        del tablas["calendar.txt"]
        del tablas["calendar_dates.txt"]
        with self.assertRaises(SystemExit):
            convertir(crear_zip(self.carpeta, tablas), self.salida, date(2021, 7, 21))

    def test_fecha_sin_servicio_se_detiene(self):
        with self.assertRaises(SystemExit):
            convertir(self.zip, self.salida, date(2030, 1, 1))

    def test_utilidades(self):
        self.assertEqual(normalizar("  Héroes   del  Sur "), "HEROES DEL SUR")
        self.assertEqual(a_minutos("25:10:59"), 1510)
        self.assertIsNone(a_minutos(""))
        for mala in ("8:00", "08:60:00", "48:00:00", "aa:bb:cc"):
            with self.assertRaises(ValueError):
                a_minutos(mala)
