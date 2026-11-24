"""Convierte el GTFS de TransMilenio a estaciones.csv, rutas.csv y horarios.csv.

Uso:
    python scripts/convertir_gtfs.py --gtfs GTFS.zip --salida datos --fecha-servicio 2021-07-21

Política (provisional, ver README):
- Se toman los servicios activos en la fecha según calendar.txt y las
  excepciones de calendar_dates.txt.
- Se usan los viajes activos ese día con horas 00-23 y los viajes del día
  anterior con horas 24-47, pasados al día civil (25:10 -> 01:10).
- Cada andén (stop) se resuelve a su estación con parent_station. Los nombres
  se pasan a mayúsculas sin tildes y con un solo espacio.
- Por defecto solo se dejan las rutas troncales: las que paran únicamente en
  andenes que pertenecen a una estación (tienen parent_station).
- Cada ruta, sentido y patrón de paradas distinto recibe un id propio,
  por ejemplo B74_0_01.
"""

import argparse
import csv
import io
import sys
import unicodedata
import zipfile
from datetime import date, timedelta
from pathlib import Path

DIAS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def normalizar(nombre):
    """Mayúsculas, sin tildes y con un solo espacio entre palabras."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre) if not unicodedata.combining(c)
    )
    return " ".join(sin_tildes.split()).upper()


def leer_tabla(archivo_zip, nombre, obligatorio=True):
    """Lee un .txt del ZIP como lista de diccionarios (fuera del motor sí se puede)."""
    if nombre not in archivo_zip.namelist():
        if obligatorio:
            raise SystemExit(f"ERROR: el GTFS no tiene {nombre}")
        return []
    with archivo_zip.open(nombre) as f:
        texto = io.TextIOWrapper(f, encoding="utf-8-sig")
        return list(csv.DictReader(texto))


def a_minutos(texto):
    """'25:10:59' -> 1510 (se trunca al minuto). None si está vacía."""
    texto = texto.strip()
    if texto == "":
        return None
    partes = texto.split(":")
    if len(partes) != 3 or not all(p.isdigit() for p in partes):
        raise ValueError(f"hora inválida {texto}")
    horas, minutos = int(partes[0]), int(partes[1])
    if minutos >= 60 or horas >= 48:
        raise ValueError(f"hora fuera de rango {texto}")
    return horas * 60 + minutos


def servicios_activos(calendario, excepciones, dia):
    """Ids de servicio que corren en la fecha dada."""
    activos = set()
    texto = dia.strftime("%Y%m%d")
    columna = DIAS[dia.weekday()]
    for fila in calendario:
        if fila["start_date"] <= texto <= fila["end_date"] and fila[columna] == "1":
            activos.add(fila["service_id"])
    for fila in excepciones:
        if fila["date"] == texto:
            if fila["exception_type"] == "1":
                activos.add(fila["service_id"])
            elif fila["exception_type"] == "2":
                activos.discard(fila["service_id"])
    return activos


def convertir(ruta_zip, carpeta_salida, fecha, solo_troncales=True):
    reporte = []
    with zipfile.ZipFile(ruta_zip) as archivo:
        paradas = leer_tabla(archivo, "stops.txt")
        rutas = leer_tabla(archivo, "routes.txt")
        viajes = leer_tabla(archivo, "trips.txt")
        tiempos = leer_tabla(archivo, "stop_times.txt")
        calendario = leer_tabla(archivo, "calendar.txt", obligatorio=False)
        excepciones = leer_tabla(archivo, "calendar_dates.txt", obligatorio=False)

    if not calendario and not excepciones:
        raise SystemExit("ERROR: el GTFS no tiene calendar.txt ni calendar_dates.txt; "
                         "no se puede saber qué servicios corren ese día")

    # 1. Andén -> estación
    por_id = {p["stop_id"]: p for p in paradas}
    estacion_de = {}       # stop_id -> nombre normalizado de la estación
    tiene_padre = {}       # stop_id -> True si el andén está dentro de una estación
    dueno = {}             # nombre normalizado -> stop_id de la estación que lo usa
    reportadas = set()
    for p in paradas:
        padre = p.get("parent_station", "").strip()
        estacion = por_id[padre] if padre in por_id else p
        nombre = normalizar(estacion["stop_name"])
        if nombre == "":
            continue
        estacion_de[p["stop_id"]] = nombre
        tiene_padre[p["stop_id"]] = padre in por_id
        if nombre not in dueno:
            dueno[nombre] = estacion["stop_id"]
        elif dueno[nombre] != estacion["stop_id"] and nombre not in reportadas:
            reportadas.add(nombre)
            reporte.append(f"colisión: {nombre} lo usan las estaciones {dueno[nombre]} y "
                           f"{estacion['stop_id']}; se unen en una sola")

    # 2. Viajes activos hoy (horas < 24) y ayer (horas >= 24)
    hoy = servicios_activos(calendario, excepciones, fecha)
    ayer = servicios_activos(calendario, excepciones, fecha - timedelta(days=1))
    if not hoy and not ayer:
        raise SystemExit(f"ERROR: ningún servicio corre el {fecha}; revisa la fecha")
    nombre_ruta = {r["route_id"]: (r.get("route_short_name") or r["route_id"]).strip() for r in rutas}
    viaje_info = {}
    for v in viajes:
        viaje_info[v["trip_id"]] = (v["route_id"], v.get("direction_id", "0") or "0", v["service_id"])

    # 3. Paradas de cada viaje ordenadas por stop_sequence
    paradas_viaje = {}
    descartes = 0
    for t in tiempos:
        if t["trip_id"] not in viaje_info or t["stop_id"] not in estacion_de:
            descartes += 1
            continue
        try:
            minuto = a_minutos(t.get("departure_time", ""))
            if minuto is None:
                minuto = a_minutos(t.get("arrival_time", ""))
        except ValueError as error:
            reporte.append(f"descartado viaje {t['trip_id']}: {error}")
            descartes += 1
            continue
        paradas_viaje.setdefault(t["trip_id"], []).append((int(t["stop_sequence"]), t["stop_id"], minuto))
    if descartes:
        reporte.append(f"filas de stop_times descartadas: {descartes}")

    # 4. Patrón de cada viaje y sus pasos del día civil
    patrones = {}   # (ruta, sentido, tupla de estaciones) -> lista de pasos (estacion, minuto)
    for trip_id, lista in paradas_viaje.items():
        ruta_id, sentido, servicio = viaje_info[trip_id]
        lista.sort()
        if solo_troncales and not all(tiene_padre[stop] for _, stop, _ in lista):
            continue
        secuencia = []
        pasos = []
        for _, stop, minuto in lista:
            nombre = estacion_de[stop]
            if secuencia and secuencia[-1] == nombre:
                continue   # varios andenes seguidos de la misma estación = un paso
            secuencia.append(nombre)
            pasos.append((nombre, minuto))
        if len(secuencia) < 2:
            continue
        clave = (nombre_ruta[ruta_id], sentido, tuple(secuencia))
        lista_pasos = patrones.setdefault(clave, [])
        for nombre, minuto in pasos:
            if minuto is None:
                continue
            if servicio in hoy and minuto < 1440:
                lista_pasos.append((nombre, minuto))
            elif servicio in ayer and minuto >= 1440:
                lista_pasos.append((nombre, minuto - 1440))   # 25:10 de ayer -> 01:10 de hoy

    # 5. Ids deterministas: ruta_sentido_número por orden de la secuencia
    contador = {}
    filas_rutas = []
    filas_horarios = []
    usadas = set()
    for clave in sorted(patrones):
        if not patrones[clave]:
            continue   # el patrón no tiene pasos ese día
        ruta, sentido, secuencia = clave
        contador[(ruta, sentido)] = contador.get((ruta, sentido), 0) + 1
        id_patron = f"{ruta}_{sentido}_{contador[(ruta, sentido)]:02d}"
        for orden, nombre in enumerate(secuencia, start=1):
            filas_rutas.append((id_patron, orden, nombre))
            usadas.add(nombre)
        for nombre, minuto in sorted(patrones[clave]):
            filas_horarios.append((id_patron, nombre, f"{minuto // 60:02d}:{minuto % 60:02d}"))

    # 6. Cada archivo se escribe en un .tmp y luego se reemplaza
    salida = Path(carpeta_salida)
    salida.mkdir(parents=True, exist_ok=True)
    escribir(salida / "estaciones.csv", ["nombre"], [(n,) for n in sorted(usadas)])
    escribir(salida / "rutas.csv", ["ruta", "orden", "estacion"], filas_rutas)
    escribir(salida / "horarios.csv", ["ruta", "estacion", "hora"], filas_horarios)

    resumen = {
        "estaciones": len(usadas),
        "rutas": len({f[0] for f in filas_rutas}),
        "paradas": len(filas_rutas),
        "pasos": len(filas_horarios),
    }
    return resumen, reporte


def escribir(ruta, cabecera, filas):
    temporal = ruta.with_suffix(".tmp")
    with open(temporal, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(cabecera)
        escritor.writerows(filas)
    temporal.replace(ruta)


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Convierte un GTFS a los tres CSV de TransmiApp")
    parser.add_argument("--gtfs", required=True, help="ruta al ZIP del GTFS")
    parser.add_argument("--salida", required=True, help="carpeta donde quedan los CSV")
    parser.add_argument("--fecha-servicio", required=True, help="día hábil AAAA-MM-DD")
    parser.add_argument("--todas-las-rutas", action="store_true",
                        help="no filtrar troncales (incluye zonales)")
    args = parser.parse_args(argumentos)

    try:
        fecha = date.fromisoformat(args.fecha_servicio)
    except ValueError:
        raise SystemExit("ERROR: la fecha debe ser AAAA-MM-DD")

    resumen, reporte = convertir(args.gtfs, args.salida, fecha, not args.todas_las_rutas)
    for linea in reporte:
        print("aviso:", linea, file=sys.stderr)
    print(f"Fecha {fecha}: {resumen['estaciones']} estaciones, {resumen['rutas']} rutas, "
          f"{resumen['paradas']} paradas y {resumen['pasos']} pasos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
