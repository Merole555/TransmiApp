import json
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictInt

RAIZ = Path(__file__).resolve().parents[1]


class Nombre(BaseModel):
    nombre: str


class AgregarParada(BaseModel):
    ruta: str
    nueva: str
    despues_de: str


class QuitarParada(BaseModel):
    ruta: str
    estacion: str


class Fila(BaseModel):
    llegadas: list[StrictInt]
    frecuencia: StrictInt
    capacidad: StrictInt


def _nombre(texto):
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.split()).upper()


def _crear_red(carpeta):
    from motor import Red

    return Red(carpeta)


def _simular(llegadas, frecuencia, capacidad):
    from motor import simular_fila

    return simular_fila(llegadas, frecuencia, capacidad)


def _medir(salida):
    try:
        from scripts.benchmark import ejecutar_web
    except ModuleNotFoundError as error:
        if error.name not in ("scripts", "scripts.benchmark"):
            raise
        raise HTTPException(503, "El arnés de rendimiento aún no está disponible") from error

    return ejecutar_web(salida)


def crear_app(
    carpeta_datos=RAIZ / "datos",
    *,
    crear_red=_crear_red,
    simular_fila=_simular,
    medir=_medir,
    archivo_resultados=RAIZ / "scripts" / "resultados" / "rendimiento.json",
):
    bloqueo_red = Lock()
    bloqueo_medicion = Lock()
    resultados = Path(archivo_resultados)

    @asynccontextmanager
    async def vida(aplicacion):
        aplicacion.state.red = crear_red(str(carpeta_datos))
        try:
            yield
        finally:
            del aplicacion.state.red

    aplicacion = FastAPI(title="TransmiApp API", lifespan=vida)

    @aplicacion.exception_handler(ValueError)
    async def entrada_invalida(_solicitud: Request, error: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(error)})

    def consultar(metodo, *argumentos):
        with bloqueo_red:
            return getattr(aplicacion.state.red, metodo)(*argumentos)

    @aplicacion.get("/api/salud")
    def salud():
        return {"ok": True}

    @aplicacion.get("/api/estado")
    def estado(nombre: str):
        existe, abierta = consultar("estado", _nombre(nombre))
        return {"existe": existe, "abierta": abierta}

    @aplicacion.get("/api/autocompletar")
    def autocompletar(prefijo: str, k: int):
        return {"estaciones": consultar("autocompletar", _nombre(prefijo), k)}

    @aplicacion.get("/api/rango")
    def rango(desde: str, hasta: str):
        return {"estaciones": consultar("rango", _nombre(desde), _nombre(hasta))}

    @aplicacion.get("/api/proximo-bus")
    def proximo_bus(estacion: str, ruta: str, hora: str):
        return {"hora": consultar("proximo_bus", _nombre(estacion), ruta, hora)}

    @aplicacion.get("/api/viaje")
    def viaje(origen: str, destino: str):
        plan = consultar("viaje", _nombre(origen), _nombre(destino))
        if plan is None:
            return {"viaje": None}
        saltos, tramos = plan
        return {"viaje": {
            "saltos": saltos,
            "tramos": [
                {"ruta": ruta, "sube": sube, "baja": baja}
                for ruta, sube, baja in tramos
            ],
        }}

    @aplicacion.get("/api/ranking")
    def ranking(k: int):
        return {"ranking": [
            {"estacion": estacion, "buses": buses}
            for estacion, buses in consultar("ranking", k)
        ]}

    @aplicacion.get("/api/recorrido")
    def recorrido(ruta: str, al_reves: bool = False):
        return {"estaciones": consultar("recorrido", ruta, al_reves)}

    @aplicacion.post("/api/paradas/agregar")
    def agregar_parada(entrada: AgregarParada):
        return {"cambio": consultar(
            "agregar_parada", entrada.ruta, _nombre(entrada.nueva), _nombre(entrada.despues_de),
        )}

    @aplicacion.post("/api/paradas/quitar")
    def quitar_parada(entrada: QuitarParada):
        return {"cambio": consultar("quitar_parada", entrada.ruta, _nombre(entrada.estacion))}

    @aplicacion.post("/api/cerrar")
    def cerrar(entrada: Nombre):
        return {"cambio": consultar("cerrar", _nombre(entrada.nombre))}

    @aplicacion.post("/api/reabrir")
    def reabrir(entrada: Nombre):
        return {"cambio": consultar("reabrir", _nombre(entrada.nombre))}

    @aplicacion.post("/api/deshacer")
    def deshacer():
        return {"cambio": consultar("deshacer")}

    @aplicacion.post("/api/rehacer")
    def rehacer():
        return {"cambio": consultar("rehacer")}

    @aplicacion.post("/api/simular-fila")
    def fila(entrada: Fila):
        abordajes, total, promedio, maxima = simular_fila(
            entrada.llegadas, entrada.frecuencia, entrada.capacidad,
        )
        return {
            "abordajes": [
                {"indice_original": indice, "llegada": llegada, "salida": salida}
                for indice, llegada, salida in abordajes
            ],
            "espera_total": total,
            "espera_promedio": promedio,
            "espera_maxima": maxima,
        }

    @aplicacion.get("/api/rendimiento")
    def leer_rendimiento():
        try:
            with resultados.open(encoding="utf-8") as archivo:
                return json.load(archivo)
        except FileNotFoundError as error:
            raise HTTPException(404, "No hay resultados de rendimiento") from error

    @aplicacion.post("/api/rendimiento")
    def medir_rendimiento():
        if not bloqueo_medicion.acquire(blocking=False):
            raise HTTPException(409, "Ya hay una medición en curso")
        try:
            return medir(resultados)
        finally:
            bloqueo_medicion.release()

    return aplicacion


app = crear_app()
