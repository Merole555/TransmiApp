"""R11 · Medición reproducible de rendimiento (miembro 4).

Uso desde la raíz del proyecto:

    python -m scripts.benchmark --salida scripts/resultados/rendimiento.json
    python -m scripts.benchmark --rapido          # tamaños pequeños, para probar

Protocolo
- Para cada operación se generan redes deterministas (semilla fija) en una
  carpeta temporal con los tres CSV del contrato, de tamaño n, 2n y 4n en la
  variable relevante. La generación de CSV, la carga, HTTP y el renderizado
  quedan fuera del intervalo medido.
- Se usa ``time.perf_counter_ns``, una ronda de calentamiento y varias
  muestras; se reporta la mediana. Las consultas rápidas se cronometran en
  lotes y se divide por la cantidad de llamadas. Las mutaciones se miden una a
  una y el estado previo se restablece fuera del intervalo (con ``deshacer``).
- Antes de medir se comprueba el resultado de una llamada de cada caso.
- Para cada serie se calcula la razón de medianas 2n/n y 4n/2n.

El script usa solo el import público ``from motor import Red, simular_fila``.
La función ``ejecutar`` es importable para reutilizarla desde otros scripts.
"""

import argparse
import csv
import json
import os
import platform
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motor import Red, simular_fila  # noqa: E402

SALIDA_POR_DEFECTO = RAIZ / "scripts" / "resultados" / "rendimiento.json"
SEMILLA = 42
K_FIJO = 10


# --------------------------------------------------------------------------
# Generación de redes
# --------------------------------------------------------------------------

def nombre_estacion(i):
    return f"E{i:06d}"


def nombre_extra(i):
    return f"X{i:06d}"


def hora(minuto):
    minuto %= 24 * 60
    return f"{minuto // 60:02d}:{minuto % 60:02d}"


def escribir_red(carpeta, estaciones, rutas, horarios_por_par, extras=0, semilla=SEMILLA):
    """Escribe los tres CSV.

    ``rutas`` es una lista de ``(id, [indices de estación])``. Las filas se
    barajan con la semilla para que el cargador no dependa del orden.
    Devuelve un objeto con las dimensiones efectivas.
    """
    azar = random.Random(semilla)
    carpeta = Path(carpeta)
    nombres = [nombre_estacion(i) for i in range(estaciones)]
    nombres += [nombre_extra(i) for i in range(extras)]
    filas_rutas = []
    filas_horarios = []
    for ruta, indices in rutas:
        for orden, indice in enumerate(indices, start=1):
            filas_rutas.append((ruta, str(orden), nombre_estacion(indice)))
            base = azar.randrange(0, 5)
            for paso in range(horarios_por_par):
                # Pasos repartidos en el día; con H > 1440 hay minutos repetidos
                # (buses distintos que pasan el mismo minuto).
                minuto = base + (paso * 1430) // horarios_por_par
                filas_horarios.append((ruta, nombre_estacion(indice), hora(minuto)))
    azar.shuffle(filas_rutas)
    azar.shuffle(filas_horarios)
    with open(carpeta / "estaciones.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["nombre"])
        for nombre in nombres:
            escritor.writerow([nombre])
    with open(carpeta / "rutas.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["ruta", "orden", "estacion"])
        escritor.writerows(filas_rutas)
    with open(carpeta / "horarios.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["ruta", "estacion", "hora"])
        escritor.writerows(filas_horarios)
    longitudes = [len(indices) for _, indices in rutas]
    return {
        "estaciones": len(nombres),
        "rutas": len(rutas),
        "longitud_ruta": max(longitudes) if longitudes else 0,
        "horarios_por_par": horarios_por_par,
        "filas_horarios": len(filas_horarios),
    }


def rutas_solapadas(estaciones, longitud=20, paso=10):
    """Rutas de ``longitud`` paradas que avanzan ``paso`` estaciones, de modo
    que cada estación pertenece a unas dos rutas y hay transbordos."""
    rutas = []
    inicio = 0
    numero = 0
    while inicio + longitud <= estaciones:
        rutas.append((f"R{numero:05d}", list(range(inicio, inicio + longitud))))
        inicio += paso
        numero += 1
    return rutas


def red_estaciones(carpeta, n):
    """n estaciones repartidas en rutas cortas solapadas, 2 horarios por par."""
    return escribir_red(carpeta, n, rutas_solapadas(n), 2)


def red_horarios(carpeta, n):
    """Una ruta corta; n horarios para cada par ruta-estación."""
    return escribir_red(carpeta, 50, [("R00000", list(range(10)))], n)


def red_ruta_larga(carpeta, n):
    """Una sola ruta de n paradas y estaciones extra para insertar."""
    return escribir_red(carpeta, n, [("R00000", list(range(n)))], 1, extras=8)


# --------------------------------------------------------------------------
# Medición
# --------------------------------------------------------------------------

def mediana_lote(funcion, llamadas, repeticiones):
    """Mediana de ns por llamada, cronometrando lotes de ``llamadas``."""
    for _ in range(llamadas):          # calentamiento
        funcion()
    muestras = []
    for _ in range(repeticiones):
        inicio = time.perf_counter_ns()
        for _ in range(llamadas):
            funcion()
        muestras.append((time.perf_counter_ns() - inicio) / llamadas)
    return statistics.median(muestras)


def mediana_mutacion(preparar, medir, restablecer, repeticiones):
    """Mide una mutación por muestra; preparar y restablecer quedan fuera."""
    muestras = []
    for indice in range(repeticiones + 1):
        preparar()
        inicio = time.perf_counter_ns()
        medir()
        fin = time.perf_counter_ns()
        restablecer()
        if indice > 0:                 # la primera muestra es calentamiento
            muestras.append(fin - inicio)
    return statistics.median(muestras)


def comprobar(condicion, mensaje):
    if not condicion:
        raise AssertionError(mensaje)


def abierta(estado):
    # Acepta el contrato del repositorio ("ABIERTA") y el de la guía (True, True).
    return estado == "ABIERTA" or estado == (True, True)


# Cada caso recibe (red, n, config) y devuelve la mediana en ns.

def caso_estado(red, n, c):
    nombre = nombre_estacion(n // 2)
    comprobar(abierta(red.estado(nombre)), "estado debe encontrar una estación abierta")
    return mediana_lote(lambda: red.estado(nombre), c["lote"], c["repeticiones"])


def caso_autocompletar(red, n, c):
    prefijo = nombre_estacion(n // 2)[:-1]
    comprobar(len(red.autocompletar(prefijo, K_FIJO)) == K_FIJO, "autocompletar debe llenar k")
    return mediana_lote(lambda: red.autocompletar(prefijo, K_FIJO), c["lote"], c["repeticiones"])


def caso_rango(red, n, c):
    desde, hasta = nombre_estacion(n // 2), nombre_estacion(n // 2 + K_FIJO - 1)
    comprobar(len(red.rango(desde, hasta)) == K_FIJO, "rango debe devolver s fijo")
    return mediana_lote(lambda: red.rango(desde, hasta), c["lote"], c["repeticiones"])


def caso_proximo_bus(red, n, c):
    estacion = nombre_estacion(5)
    comprobar(red.proximo_bus(estacion, "R00000", "12:00") is not None, "debe existir próximo bus")
    return mediana_lote(lambda: red.proximo_bus(estacion, "R00000", "12:00"), c["lote"], c["repeticiones"])


def caso_viaje(red, n, c):
    origen, destino = nombre_estacion(0), nombre_estacion(25)
    comprobar(red.viaje(origen, destino) is not None, "viaje con transbordo debe existir")
    return mediana_lote(lambda: red.viaje(origen, destino), max(1, c["lote"] // 10), c["repeticiones"])


def caso_ranking(red, n, c):
    comprobar(len(red.ranking(K_FIJO)) == K_FIJO, "ranking debe devolver k filas")
    return mediana_lote(lambda: red.ranking(K_FIJO), c["lote"], c["repeticiones"])


def caso_recorrido(red, n, c):
    comprobar(len(red.recorrido("R00000")) == n, "recorrido debe tener n paradas")
    return mediana_lote(lambda: red.recorrido("R00000"), max(1, c["lote"] // 10), c["repeticiones"])


def caso_recorrido_inverso(red, n, c):
    lista = red.recorrido("R00000", al_reves=True)
    comprobar(len(lista) == n and lista[0] == nombre_estacion(n - 1), "recorrido inverso incorrecto")
    return mediana_lote(lambda: red.recorrido("R00000", al_reves=True), max(1, c["lote"] // 10), c["repeticiones"])


def caso_agregar(red, n, c):
    ancla = nombre_estacion(n // 2)
    comprobar(red.agregar_parada("R00000", nombre_extra(0), ancla) is True, "agregar debe aplicar")
    red.deshacer()
    return mediana_mutacion(
        lambda: None,
        lambda: red.agregar_parada("R00000", nombre_extra(0), ancla),
        red.deshacer,
        c["repeticiones_mutacion"],
    )


def caso_quitar(red, n, c):
    estacion = nombre_estacion(n // 2)
    comprobar(red.quitar_parada("R00000", estacion) is True, "quitar debe aplicar")
    red.deshacer()
    return mediana_mutacion(
        lambda: None,
        lambda: red.quitar_parada("R00000", estacion),
        red.deshacer,
        c["repeticiones_mutacion"],
    )


def caso_cerrar(red, n, c):
    nombre = nombre_estacion(n // 2)
    comprobar(red.cerrar(nombre) is True, "cerrar debe aplicar")
    red.deshacer()
    return mediana_mutacion(lambda: None, lambda: red.cerrar(nombre), red.deshacer, c["repeticiones_mutacion"])


def caso_reabrir(red, n, c):
    nombre = nombre_estacion(n // 2)
    red.cerrar(nombre)
    comprobar(red.reabrir(nombre) is True, "reabrir debe aplicar")
    red.deshacer()
    red.deshacer()

    def preparar():
        red.cerrar(nombre)

    def restablecer():
        red.deshacer()   # deshace reabrir
        red.deshacer()   # deshace cerrar

    return mediana_mutacion(preparar, lambda: red.reabrir(nombre), restablecer, c["repeticiones_mutacion"])


def caso_deshacer(red, n, c):
    nombre = nombre_estacion(n // 2)
    red.cerrar(nombre)
    comprobar(red.deshacer() is True, "deshacer debe aplicar")
    return mediana_mutacion(lambda: red.cerrar(nombre), red.deshacer, lambda: None, c["repeticiones_mutacion"])


def caso_rehacer(red, n, c):
    nombre = nombre_estacion(n // 2)
    red.cerrar(nombre)
    red.deshacer()
    comprobar(red.rehacer() is True, "rehacer debe aplicar")
    red.deshacer()

    def preparar():
        red.cerrar(nombre)
        red.deshacer()

    return mediana_mutacion(preparar, red.rehacer, red.deshacer, c["repeticiones_mutacion"])


def caso_simular_fila(n, c):
    azar = random.Random(SEMILLA)
    llegadas = []
    actual = 0
    for _ in range(n):
        actual += azar.randint(0, 3)
        llegadas.append(actual)
    comprobar(len(simular_fila(llegadas, 5, 40)) == n, "simular_fila debe devolver n esperas")
    return mediana_lote(lambda: simular_fila(llegadas, 5, 40), max(1, c["lote"] // 100), c["repeticiones"])


# Definición de cada serie, con su análisis metodológico junto al caso.
SERIES = [
    {
        "operacion": "estado", "red": red_estaciones, "caso": caso_estado,
        "variable": "n: estaciones de la red",
        "complejidad": "O(L) promedio con tabla hash (L = longitud del nombre)",
        "analisis": "Consulta de un nombre presente. Con hash propio y factor de carga acotado se espera tiempo casi constante al duplicar n (razón ≈ 1); el nombre tiene longitud fija.",
    },
    {
        "operacion": "autocompletar", "red": red_estaciones, "caso": caso_autocompletar,
        "variable": "n: estaciones abiertas (k = 10 fijo)",
        "complejidad": "O(log n + k)",
        "analisis": "Prefijo presente con k fijo, de modo que la salida no crece. Con árbol balanceado se espera un crecimiento logarítmico: razón levemente mayor que 1.",
    },
    {
        "operacion": "rango", "red": red_estaciones, "caso": caso_rango,
        "variable": "n: estaciones abiertas (s = 10 resultados fijos)",
        "complejidad": "O(log n + s)",
        "analisis": "Intervalo con tamaño de salida constante. Se espera razón cercana a 1, dominada por el descenso logarítmico en el árbol.",
    },
    {
        "operacion": "proximo_bus", "red": red_horarios, "caso": caso_proximo_bus,
        "variable": "H: horarios del par ruta-estación",
        "complejidad": "O(log H) más búsqueda hash promedio",
        "analisis": "Se crece la cantidad de pasos del mismo par ruta-estación. La búsqueda binaria debería dar razones apenas mayores que 1.",
    },
    {
        "operacion": "viaje", "red": red_estaciones, "caso": caso_viaje,
        "variable": "n: estaciones (rutas de 20 paradas solapadas cada 10)",
        "complejidad": "O(Σ longitudes de rutas que pasan por el origen y los transbordos)",
        "analisis": "R5 se mide aunque el criterio de escalamiento lo exceptúa. Con rutas de longitud fija y grado acotado por estación, el trabajo depende de las rutas que tocan el origen, no de n: razón esperada ≈ 1.",
    },
    {
        "operacion": "ranking", "red": red_estaciones, "caso": caso_ranking,
        "variable": "n: estaciones abiertas (k = 10 fijo)",
        "complejidad": "O(k) con índice ordenado mantenido",
        "analisis": "El índice ordenado se mantiene en cada mutación, así que la consulta lee los primeros k: razón esperada ≈ 1.",
    },
    {
        "operacion": "agregar_parada", "red": red_ruta_larga, "caso": caso_agregar,
        "variable": "p: paradas de la ruta editada",
        "complejidad": "O(1) promedio para enlazar, más actualización del ranking",
        "analisis": "Inserción tras un ancla localizada con hash. El enlace no depende de p; si el ranking usa un arreglo ordenado, su actualización puede crecer con n.",
    },
    {
        "operacion": "quitar_parada", "red": red_ruta_larga, "caso": caso_quitar,
        "variable": "p: paradas de la ruta editada",
        "complejidad": "O(1) promedio para desenlazar, más actualización del ranking",
        "analisis": "Simétrico a agregar_parada; el estado se restablece con deshacer fuera del intervalo.",
    },
    {
        "operacion": "recorrido", "red": red_ruta_larga, "caso": caso_recorrido,
        "variable": "p: paradas de la ruta",
        "complejidad": "O(p) incluyendo materializar la lista",
        "analisis": "Recorre la lista enlazada y construye una lista nueva: se espera razón ≈ 2 al duplicar p.",
    },
    {
        "operacion": "recorrido_inverso", "red": red_ruta_larga, "caso": caso_recorrido_inverso,
        "variable": "p: paradas de la ruta",
        "complejidad": "O(p) incluyendo materializar la lista",
        "analisis": "Llama recorrido(ruta, al_reves=True) desde la cola. Debe comportarse igual que el directo: razón ≈ 2.",
    },
    {
        "operacion": "cerrar", "red": red_estaciones, "caso": caso_cerrar,
        "variable": "n: estaciones abiertas",
        "complejidad": "O(log n) en los árboles de abiertas, más ranking",
        "analisis": "Cierre efectivo de una estación presente; se restablece con deshacer fuera del intervalo.",
    },
    {
        "operacion": "reabrir", "red": red_estaciones, "caso": caso_reabrir,
        "variable": "n: estaciones abiertas",
        "complejidad": "O(log n) en los árboles de abiertas, más ranking",
        "analisis": "La estación se cierra antes del intervalo; se mide solo la reapertura.",
    },
    {
        "operacion": "deshacer", "red": red_estaciones, "caso": caso_deshacer,
        "variable": "n: estaciones abiertas",
        "complejidad": "O(1) amortizado en la pila más el costo de invertir la acción",
        "analisis": "Se prepara un cierre fuera del intervalo y se mide deshacerlo: el costo es el de reabrir más mover la entrada entre pilas.",
    },
    {
        "operacion": "rehacer", "red": red_estaciones, "caso": caso_rehacer,
        "variable": "n: estaciones abiertas",
        "complejidad": "O(1) amortizado en la pila más el costo de reaplicar la acción",
        "analisis": "Se prepara un cierre deshecho fuera del intervalo y se mide rehacerlo.",
    },
    {
        "operacion": "simular_fila", "red": None, "caso": caso_simular_fila,
        "variable": "n: pasajeros (frecuencia 5 y capacidad 40 fijas)",
        "complejidad": "O(n) tiempo, O(n) salida, O(1) auxiliar",
        "analisis": "Un cursor recorre las llegadas una vez y salta directo al siguiente bus útil: se espera razón ≈ 2 al duplicar n.",
    },
]


def _razones(puntos):
    anterior = None
    for punto in puntos:
        if anterior is None or anterior == 0:
            punto["razon_anterior"] = None
        else:
            punto["razon_anterior"] = round(punto["mediana_ns"] / anterior, 3)
        anterior = punto["mediana_ns"]


def _observacion(puntos):
    razones = [p["razon_anterior"] for p in puntos if p["razon_anterior"] is not None]
    if not razones:
        return ""
    texto = ", ".join(f"{r:.2f}" for r in razones)
    return f" Razones observadas al duplicar: {texto}."


def ejecutar(tamanos=(1000, 2000, 4000), repeticiones=7, lote=200, repeticiones_mutacion=51, operaciones=None):
    """Ejecuta todas las series y devuelve el objeto JSON de resultados."""
    config = {"repeticiones": repeticiones, "lote": lote, "repeticiones_mutacion": repeticiones_mutacion}
    series = []
    for definicion in SERIES:
        if operaciones and definicion["operacion"] not in operaciones:
            continue
        serie = {
            "operacion": definicion["operacion"],
            "variable": definicion["variable"],
            "complejidad": definicion["complejidad"],
            "analisis": definicion["analisis"],
            "puntos": [],
        }
        try:
            for n in tamanos:
                if definicion["red"] is None:
                    mediana = definicion["caso"](n, config)
                    dimensiones = {"pasajeros": n}
                else:
                    if Red is None:
                        raise RuntimeError("motor.Red todavía no está integrado")
                    with tempfile.TemporaryDirectory(prefix="transmiapp-bench-") as carpeta:
                        dimensiones = definicion["red"](carpeta, n)
                        red = Red(carpeta)
                    mediana = definicion["caso"](red, n, config)
                serie["puntos"].append({
                    "n": n,
                    "mediana_ns": round(mediana, 1),
                    "razon_anterior": None,
                    "dimensiones": dimensiones,
                })
            _razones(serie["puntos"])
            serie["analisis"] += _observacion(serie["puntos"])
        except Exception as error:  # se registra y se continúa con las demás series
            serie["error"] = f"{type(error).__name__}: {error}"
            print(f"  ! {definicion['operacion']}: {serie['error']}", file=sys.stderr)
        series.append(serie)
        print(f"  · {definicion['operacion']}: {len(serie['puntos'])} puntos", file=sys.stderr)
    return {
        "configuracion": {
            "semilla": SEMILLA,
            "repeticiones": repeticiones,
            "lote": lote,
            "repeticiones_mutacion": repeticiones_mutacion,
            "tamanos": ", ".join(str(t) for t in tamanos),
            "unidad": "ns/llamada",
            "python": platform.python_version(),
            "entorno": f"{platform.system()} {platform.release()} · {platform.machine()}",
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
        },
        "series": series,
    }


def guardar(resultados, ruta):
    """Escribe el JSON en UTF-8 por reemplazo atómico."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=".rendimiento-", suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(resultados, archivo, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.unlink(temporal)
        raise


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Mide R1–R10 y guarda el JSON del panel R11.")
    parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="ruta del JSON de resultados")
    parser.add_argument("--n", type=int, default=1000, help="tamaño base n (se mide n, 2n y 4n)")
    parser.add_argument("--repeticiones", type=int, default=7)
    parser.add_argument("--rapido", action="store_true", help="tamaños y repeticiones pequeños")
    parser.add_argument("--solo", nargs="*", help="medir solo estas operaciones")
    args = parser.parse_args(argumentos)
    if args.rapido:
        tamanos, repeticiones, lote, mutaciones = (100, 200, 400), 3, 20, 11
    else:
        tamanos = (args.n, args.n * 2, args.n * 4)
        repeticiones, lote, mutaciones = args.repeticiones, 200, 51
    print(f"Midiendo con tamaños {tamanos}…", file=sys.stderr)
    resultados = ejecutar(tamanos, repeticiones, lote, mutaciones, args.solo)
    guardar(resultados, args.salida)
    print(f"Resultados guardados en {args.salida}", file=sys.stderr)
    fallidas = [s["operacion"] for s in resultados["series"] if "error" in s]
    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
