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


def _ruta(texto):
    """Los IDs de ruta se conservan salvo mayúsculas y espacios externos."""
    return texto.strip().upper()


def _crear_red(carpeta):
    from motor import Red

    return Red(carpeta)


def _simular(llegadas, frecuencia, capacidad):
    from motor import simular_fila

    return simular_fila(llegadas, frecuencia, capacidad)


def crear_app(
    carpeta_datos=RAIZ / "datos",
    *,
    crear_red=_crear_red,
    simular_fila=_simular,
    archivo_resultados=RAIZ / "scripts" / "resultados" / "rendimiento.json",
):
    bloqueo_red = Lock()
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
        situacion = consultar("estado", _nombre(nombre))
        return {"existe": situacion != "NO_EXISTE", "abierta": situacion == "ABIERTA"}

    @aplicacion.get("/api/autocompletar")
    def autocompletar(prefijo: str, k: int):
        return {"estaciones": consultar("autocompletar", _nombre(prefijo), k)}

    @aplicacion.get("/api/rango")
    def rango(desde: str, hasta: str):
        return {"estaciones": consultar("rango", _nombre(desde), _nombre(hasta))}

    @aplicacion.get("/api/proximo-bus")
    def proximo_bus(estacion: str, ruta: str, hora: str):
        return {"hora": consultar("proximo_bus", _nombre(estacion), _ruta(ruta), hora)}

    @aplicacion.get("/api/viaje")
    def viaje(origen: str, destino: str):
        plan = consultar("viaje", _nombre(origen), _nombre(destino))
        if plan is None:
            return {"viaje": None}
        tipo, saltos, tramos = plan
        return {"viaje": {
            "tipo": tipo,
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
        return {"estaciones": consultar("recorrido", _ruta(ruta), al_reves)}

    @aplicacion.post("/api/paradas/agregar")
    def agregar_parada(entrada: AgregarParada):
        return {"cambio": consultar(
            "agregar_parada", _ruta(entrada.ruta), _nombre(entrada.nueva), _nombre(entrada.despues_de),
        )}

    @aplicacion.post("/api/paradas/quitar")
    def quitar_parada(entrada: QuitarParada):
        return {"cambio": consultar("quitar_parada", _ruta(entrada.ruta), _nombre(entrada.estacion))}

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
        esperas = simular_fila(
            entrada.llegadas, entrada.frecuencia, entrada.capacidad,
        )
        total = sum(esperas)
        return {
            "esperas": esperas,
            "espera_total": total,
            "espera_promedio": total / len(esperas) if esperas else 0.0,
            "espera_maxima": max(esperas) if esperas else 0,
        }

    @aplicacion.get("/api/rendimiento")
    def leer_rendimiento():
        try:
            with resultados.open(encoding="utf-8") as archivo:
                return json.load(archivo)
        except FileNotFoundError as error:
            raise HTTPException(404, "No hay resultados de rendimiento") from error

    return aplicacion


app = crear_app()
