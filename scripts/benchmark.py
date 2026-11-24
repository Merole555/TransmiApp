"""R11: mide el tiempo de las operaciones con redes de tamaño n, 2n y 4n.

Uso desde la raíz:
    python -m scripts.benchmark --salida scripts/resultados/rendimiento.json
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
sys.path.insert(0, str(RAIZ))

from motor import Red, simular_fila  # noqa: E402

SEMILLA = 42
K = 10


def nombre(i):
    return f"E{i:06d}"


def hora(minuto):
    minuto = minuto % 1440
    return f"{minuto // 60:02d}:{minuto % 60:02d}"


def crear_csv(carpeta, n_estaciones, rutas, horarios_por_par, extras=0):
    """Escribe estaciones.csv, rutas.csv y horarios.csv en la carpeta.

    rutas es una lista de (id_ruta, [indices de estaciones]).
    """
    azar = random.Random(SEMILLA)
    filas_rutas = []
    filas_horarios = []
    for ruta, indices in rutas:
        orden = 1
        for i in indices:
            filas_rutas.append([ruta, orden, nombre(i)])
            for paso in range(horarios_por_par):
                minuto = paso * 1430 // horarios_por_par + orden
                filas_horarios.append([ruta, nombre(i), hora(minuto)])
            orden += 1
    # se desordenan para que la carga no dependa del orden
    azar.shuffle(filas_rutas)
    azar.shuffle(filas_horarios)

    with open(Path(carpeta) / "estaciones.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["nombre"])
        for i in range(n_estaciones):
            escritor.writerow([nombre(i)])
        for i in range(extras):
            escritor.writerow([f"X{i:06d}"])
    with open(Path(carpeta) / "rutas.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["ruta", "orden", "estacion"])
        escritor.writerows(filas_rutas)
    with open(Path(carpeta) / "horarios.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["ruta", "estacion", "hora"])
        escritor.writerows(filas_horarios)
    return {"estaciones": n_estaciones + extras, "rutas": len(rutas), "horarios_por_par": horarios_por_par}


# Tres tipos de red según lo que se quiere hacer crecer

def red_muchas_estaciones(carpeta, n):
    # rutas de 20 paradas que se cruzan cada 10 estaciones (así hay transbordos)
    rutas = []
    inicio = 0
    while inicio + 20 <= n:
        rutas.append((f"R{len(rutas):05d}", list(range(inicio, inicio + 20))))
        inicio += 10
    return crear_csv(carpeta, n, rutas, 2)


def red_muchos_horarios(carpeta, n):
    return crear_csv(carpeta, 50, [("R00000", list(range(10)))], n)


def red_ruta_larga(carpeta, n):
    return crear_csv(carpeta, n, [("R00000", list(range(n)))], 1, extras=2)


def medir_consulta(funcion, veces, repeticiones):
    """Mediana de ns por llamada, midiendo lotes de varias llamadas."""
    for _ in range(veces):
        funcion()  # calentamiento
    muestras = []
    for _ in range(repeticiones):
        inicio = time.perf_counter_ns()
        for _ in range(veces):
            funcion()
        muestras.append((time.perf_counter_ns() - inicio) / veces)
    return statistics.median(muestras)


def medir_mutacion(antes, funcion, despues, repeticiones):
    """Mide una sola llamada por muestra. antes y despues no se cuentan."""
    muestras = []
    for _ in range(repeticiones):
        antes()
        inicio = time.perf_counter_ns()
        funcion()
        muestras.append(time.perf_counter_ns() - inicio)
        despues()
    return statistics.median(muestras)


def nada():
    pass


# Cada caso recibe la red ya cargada y n, y devuelve la mediana en ns.
# Primero se revisa que la operación responda bien.

def caso_estado(red, n, rep):
    e = nombre(n // 2)
    assert red.estado(e) in ("ABIERTA", (True, True))
    return medir_consulta(lambda: red.estado(e), 200, rep)


def caso_autocompletar(red, n, rep):
    prefijo = nombre(n // 2)[:-1]
    assert len(red.autocompletar(prefijo, K)) == K
    return medir_consulta(lambda: red.autocompletar(prefijo, K), 200, rep)


def caso_rango(red, n, rep):
    desde, hasta = nombre(n // 2), nombre(n // 2 + K - 1)
    assert len(red.rango(desde, hasta)) == K
    return medir_consulta(lambda: red.rango(desde, hasta), 200, rep)


def caso_proximo_bus(red, n, rep):
    assert red.proximo_bus(nombre(5), "R00000", "12:00") is not None
    return medir_consulta(lambda: red.proximo_bus(nombre(5), "R00000", "12:00"), 200, rep)


def caso_viaje(red, n, rep):
    assert red.viaje(nombre(0), nombre(25)) is not None
    return medir_consulta(lambda: red.viaje(nombre(0), nombre(25)), 20, rep)


def caso_ranking(red, n, rep):
    assert len(red.ranking(K)) == K
    return medir_consulta(lambda: red.ranking(K), 200, rep)


def caso_recorrido(red, n, rep):
    assert len(red.recorrido("R00000")) == n
    return medir_consulta(lambda: red.recorrido("R00000"), 20, rep)


def caso_recorrido_inverso(red, n, rep):
    assert red.recorrido("R00000", al_reves=True)[0] == nombre(n - 1)
    return medir_consulta(lambda: red.recorrido("R00000", al_reves=True), 20, rep)


def caso_agregar(red, n, rep):
    return medir_mutacion(nada, lambda: red.agregar_parada("R00000", "X000000", nombre(n // 2)),
                          red.deshacer, rep * 5)


def caso_quitar(red, n, rep):
    return medir_mutacion(nada, lambda: red.quitar_parada("R00000", nombre(n // 2)), red.deshacer, rep * 5)


def caso_cerrar(red, n, rep):
    return medir_mutacion(nada, lambda: red.cerrar(nombre(n // 2)), red.deshacer, rep * 5)


def caso_reabrir(red, n, rep):
    e = nombre(n // 2)

    def despues():
        red.deshacer()  # deshace reabrir
        red.deshacer()  # deshace cerrar

    return medir_mutacion(lambda: red.cerrar(e), lambda: red.reabrir(e), despues, rep * 5)


def caso_deshacer(red, n, rep):
    return medir_mutacion(lambda: red.cerrar(nombre(n // 2)), red.deshacer, nada, rep * 5)


def caso_rehacer(red, n, rep):
    def antes():
        red.cerrar(nombre(n // 2))
        red.deshacer()

    return medir_mutacion(antes, red.rehacer, red.deshacer, rep * 5)


def caso_simular_fila(n, rep):
    azar = random.Random(SEMILLA)
    llegadas = []
    actual = 0
    for _ in range(n):
        actual += azar.randint(0, 3)
        llegadas.append(actual)
    assert len(simular_fila(llegadas, 5, 40)) == n
    return medir_consulta(lambda: simular_fila(llegadas, 5, 40), 2, rep)


# (operación, red, caso, significado de n, complejidad esperada, análisis)
SERIES = [
    ("estado", red_muchas_estaciones, caso_estado, "n: estaciones", "O(L) promedio con tabla hash",
     "Búsqueda por nombre en la tabla hash. Debería quedar casi igual al duplicar n."),
    ("autocompletar", red_muchas_estaciones, caso_autocompletar, "n: estaciones abiertas (k = 10)",
     "O(log n + k)", "Con k fijo la salida no crece, así que debería crecer poco (logarítmico)."),
    ("rango", red_muchas_estaciones, caso_rango, "n: estaciones abiertas (10 resultados)",
     "O(log n + s)", "Rango con 10 resultados fijos; se espera crecimiento logarítmico."),
    ("proximo_bus", red_muchos_horarios, caso_proximo_bus, "H: horarios del par ruta-estación",
     "O(log H) más búsqueda hash", "Búsqueda binaria en los horarios: la razón debería ser poco más de 1."),
    ("viaje", red_muchas_estaciones, caso_viaje, "n: estaciones (rutas de 20 paradas)",
     "O(suma de las rutas que pasan por el origen y los transbordos)",
     "Las rutas tienen tamaño fijo, entonces el trabajo no depende mucho de n."),
    ("ranking", red_muchas_estaciones, caso_ranking, "n: estaciones abiertas (k = 10)", "O(k)",
     "El ranking ya está ordenado, solo se leen los primeros k."),
    ("agregar_parada", red_ruta_larga, caso_agregar, "p: paradas de la ruta",
     "O(1) promedio más actualizar el ranking", "Solo se cambian enlaces de la lista; no depende de p."),
    ("quitar_parada", red_ruta_larga, caso_quitar, "p: paradas de la ruta",
     "O(1) promedio más actualizar el ranking", "Igual que agregar, pero quitando el nodo."),
    ("recorrido", red_ruta_larga, caso_recorrido, "p: paradas de la ruta", "O(p)",
     "Recorre toda la lista y crea una nueva: al duplicar p debería duplicarse."),
    ("recorrido_inverso", red_ruta_larga, caso_recorrido_inverso, "p: paradas de la ruta", "O(p)",
     "Igual que recorrido pero desde la cola (al_reves=True)."),
    ("cerrar", red_muchas_estaciones, caso_cerrar, "n: estaciones abiertas", "O(log n)",
     "Quita la estación de los índices de abiertas."),
    ("reabrir", red_muchas_estaciones, caso_reabrir, "n: estaciones abiertas", "O(log n)",
     "Vuelve a meter la estación en los índices de abiertas."),
    ("deshacer", red_muchas_estaciones, caso_deshacer, "n: estaciones abiertas",
     "O(1) en la pila más el costo de la acción", "Saca de una pila, invierte la acción y la pasa a la otra pila."),
    ("rehacer", red_muchas_estaciones, caso_rehacer, "n: estaciones abiertas",
     "O(1) en la pila más el costo de la acción", "Igual que deshacer pero al revés."),
    ("simular_fila", None, caso_simular_fila, "n: pasajeros (frecuencia 5, capacidad 40)", "O(n)",
     "Recorre las llegadas una sola vez: al duplicar n el tiempo debería duplicarse."),
]


def ejecutar(tamanos=(1000, 2000, 4000), repeticiones=7, solo=None):
    series = []
    for operacion, crear_red, caso, variable, complejidad, analisis in SERIES:
        if solo and operacion not in solo:
            continue
        serie = {"operacion": operacion, "variable": variable, "complejidad": complejidad,
                 "analisis": analisis, "puntos": []}
        try:
            anterior = None
            for n in tamanos:
                if crear_red is None:
                    mediana = caso(n, repeticiones)
                    dimensiones = {"pasajeros": n}
                else:
                    if Red is None:
                        raise RuntimeError("Red todavía no está en el motor")
                    with tempfile.TemporaryDirectory() as carpeta:
                        dimensiones = crear_red(carpeta, n)
                        red = Red(carpeta)
                    mediana = caso(red, n, repeticiones)
                razon = None if anterior is None else round(mediana / anterior, 2)
                serie["puntos"].append({"n": n, "mediana_ns": round(mediana, 1),
                                        "razon_anterior": razon, "dimensiones": dimensiones})
                anterior = mediana
            razones = [str(p["razon_anterior"]) for p in serie["puntos"][1:]]
            serie["analisis"] += " Razones observadas: " + ", ".join(razones) + "."
        except Exception as error:
            serie["error"] = f"{type(error).__name__}: {error}"
        print(operacion, "->", serie.get("error", "ok"))
        series.append(serie)

    return {
        "configuracion": {
            "semilla": SEMILLA,
            "repeticiones": repeticiones,
            "tamanos": ", ".join(str(t) for t in tamanos),
            "unidad": "ns/llamada",
            "python": platform.python_version(),
            "entorno": f"{platform.system()} {platform.machine()}",
        },
        "series": series,
    }


def guardar(resultados, ruta):
    """Guarda primero en un archivo temporal y luego lo reemplaza."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", default="scripts/resultados/rendimiento.json")
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--rapido", action="store_true", help="tamaños pequeños para probar")
    parser.add_argument("--solo", nargs="*")
    args = parser.parse_args()

    if args.rapido:
        resultados = ejecutar((100, 200, 400), 3, args.solo)
    else:
        resultados = ejecutar((args.n, 2 * args.n, 4 * args.n), 7, args.solo)
    guardar(resultados, args.salida)
    print("Guardado en", args.salida)
