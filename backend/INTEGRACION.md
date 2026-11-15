# Integracion de Member 2: R4, R5, R6 y FastAPI

> Contratos provisionales acordados por el grupo. No modificar las firmas
> publicas que evalua el profesor. Los algoritmos R1-R10 viven en `motor/`.

## Pendiente compartido: Red

En esta rama aun no existe la clase publica `Red` ni la carga de los tres CSV.
`motor/__init__.py` esta vacio. Los tests de Member 2 usan dobles independientes,
por lo que NO demuestran que la aplicacion completa se pueda iniciar con datos
reales. Member 1 debe integrar el cargador y exponer `Red(carpeta)` desde
`motor/__init__.py`; Member 3 debe integrar mutaciones e historial.

Se espera que el objeto `Red` ofrezca estas propiedades/operaciones internas:

- `red.horarios`: tabla hash propia con `obtener((ruta, estacion))` y
  `asignar((ruta, estacion), lista_de_minutos)`. Se construye una vez con
  `viajes.indexar_horarios(tabla, filas)`. Conservar los horarios duplicados.
- `red.estado(nombre)`: devuelve `"ABIERTA"`, `"CERRADA"` o `"NO_EXISTE"`.
- `red.tiene_parada(ruta, estacion)`: bool segun el recorrido vigente.
  Tiene en cuenta las rutas editadas y las paradas repetidas.
- `red.salidas(nombre)`: iterable de `(ruta, nodo)` para cada ocurrencia
  vigente. Cada nodo expone `estacion` y `siguiente`; nunca recorrer
  hacia atras para planificar el viaje.
- `red.indice_ranking`: instancia de
  `viajes.RankingEstaciones(tabla_de_estaciones, None, red.horarios)`.
  `tabla_de_estaciones` debe ser tabla hash propia con
  `obtener(nombre)` y `asignar(nombre, valor)`.

Las funciones publicas delegan sin cambiar nombres ni parametros:

```python
def proximo_bus(self, estacion, ruta, hora):
    return viajes.proximo_bus(self, estacion, ruta, hora)

def viaje(self, origen, destino):
    return viajes.viaje(self, origen, destino)

def ranking(self, k):
    return viajes.ranking(self, k)
```

## R4: proximo bus

- `indexar_horarios(tabla, filas)` guarda minutos por pareja
  `(ruta, estacion)`, ordenados mediante mergesort propio.
- `proximo_bus` exige estacion abierta y pareja presente en ruta.
- Convierte `HH:MM` a minutos, aceptando horas extendidas de dos digitos
  (ejemplo: 25:10). Los minutos deben ser de 00 a 59.
- Retorna primer paso `>=` hora consultada como texto `HH:MM`, o `None`.
- Consulta `O(log H)` tras cargar el indice; preprocesamiento de
  cada lista `O(H log H)`.

## R5: viaje

- `None` si no existe un plan valido con cero o un transbordo.
- Caso trivial con la misma estacion abierta:
  `("DIRECTO", 0, [])`.
- Viaje directo: `("DIRECTO", saltos, [(ruta, subir, bajar)])`.
- Con transbordo:
  `("TRANSBORDO", saltos, [(r1, origen, cambio), (r2, cambio, destino)])`.
- Se minimizan saltos entre paradas consecutivas. Con empate, gana
  el menor numero de transbordos y luego el orden alfabetico de las
  tuplas de tramos. No se puede subir/bajar/transbordar en estacion cerrada.
  Se puede pasar por una parada cerrada sin bajar.
- Orden de la ruta siempre hacia adelante, inclusive en repetidas
  ocurrencias de una estacion.
- El profesor no evalua escalamiento de R5, pero si su correccion.

## R6: ranking

- `ranking(k)` retorna `[(estacion, buses), ...]` para estaciones
  abiertas, ordenado por cantidad descendente y nombre ascendente.
- El conteo equivale al numero de filas de horarios de parejas
  ruta-estacion **activas**. Si una ruta deja de contener la parada,
  se retira su contribucion. No inventar horarios para paradas nuevas.
- `RankingEstaciones.registrar(nombre)` registra conteo cero.
- `cambiar_membresia(ruta, estacion, activa)` recibe solamente transiciones
  entre una y cero ocurrencias de esa pareja y ajusta las contribuciones.
- `cambiar_apertura(estacion, abierta)` oculta o muestra estaciones sin
  perder el conteo acumulado. Undo/redo debe llamar los mismos cambios.
- Estructura aprobada: arreglo ordenado de claves `(-buses, nombre)`
  con busqueda binaria propia. Consulta `O(k)`; insertar/quitar
  una clave cuesta `O(n)` por desplazamiento del arreglo, aunque
  encontrar su posicion cueste `O(log n)`. Este costo real se
  debe documentar y medir en R11; NO afirmar actualizaciones `O(log n)`.

## API HTTP

El adaptador `backend/main.py` contiene la serializacion JSON y
validacion (estas librerias si estan permitidas fuera de `motor/`).
`crear_app` admite inyectar un objeto Red para pruebas.

| Metodo | Ruta | Respuesta |
|---|---|---|
| GET | /api/salud | `{"ok":true}` |
| GET | /api/estado | `{"existe":true,"abierta":true}` |
| GET | /api/autocompletar | `{"estaciones":["A"]}` |
| GET | /api/rango | `{"estaciones":["A","B"]}` |
| GET | /api/proximo-bus | `{"hora":"25:10"}` o `{"hora":null}` |
| GET | /api/viaje | `{"viaje":{"tipo":"DIRECTO","saltos":2,"tramos":[...]}}` o null |
| GET | /api/ranking | `{"ranking":[{"estacion":"A","buses":3}]}` |
| GET | /api/recorrido | `{"estaciones":["A","B"]}` |
| POST | /api/paradas/agregar | `{"cambio":true}` |
| POST | /api/paradas/quitar | `{"cambio":true}` |
| POST | /api/cerrar | `{"cambio":true}` |
| POST | /api/reabrir | `{"cambio":true}` |
| POST | /api/deshacer | `{"cambio":true}` |
| POST | /api/rehacer | `{"cambio":true}` |
| POST | /api/simular-fila | `{"esperas":[0,2],"espera_total":2,"espera_promedio":1.0,"espera_maxima":2}` |
| GET | /api/rendimiento | JSON medido guardado, o HTTP 404 |

R11 utiliza mediciones reproducibles hechas fuera del servidor, no POST
para lanzar benchmarks desde la web. La interfaz React lee el JSON
guardado desde `GET /api/rendimiento`.

## Verificacion

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s scripts/pruebas -p "test_*.py" -v
.\.venv\Scripts\python.exe -m compileall -q motor backend scripts/pruebas
```

Las pruebas actuales verifican R4-R6 y HTTP contra dobles. Faltan pruebas
de integracion con `Red` y CSV reales una vez que Member 1 y 3
incorporen el cargador, las estructuras y las mutaciones.
