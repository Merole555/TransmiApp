# TransmiApp

Aplicación web local para consultar estaciones de TransMilenio, encontrar el
próximo bus, planear viajes, editar la red, simular la fila de abordaje y ver
mediciones de rendimiento. Motor en Python, API en FastAPI y frontend en
React + TypeScript + Vite.

## Instalación

Requisitos: Python 3.12, Node 22.12+ y Git.

```bash
# macOS / Linux
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
```

## Arranque (comando único)

Con las dependencias instaladas y los tres CSV en `datos/`:

```bash
.venv/bin/python scripts/iniciar.py                 # macOS / Linux
.\.venv\Scripts\python.exe scripts/iniciar.py       # Windows
```

Abre `http://127.0.0.1:5173`. El backend queda en `http://127.0.0.1:8000`
(documentación interactiva en `/docs`) y Vite reenvía `/api` allí. Ctrl+C
detiene ambos procesos. El lanzador comprueba antes los CSV, FastAPI/Uvicorn,
Node, `frontend/node_modules` y que los puertos 8000 y 5173 estén libres.

## Pruebas

```bash
.venv/bin/python -m unittest discover -s scripts/pruebas -p "test_*.py" -v
npm --prefix frontend run build
npm --prefix frontend run lint
```

## Medición de rendimiento (R11)

```bash
.venv/bin/python -m scripts.benchmark --salida scripts/resultados/rendimiento.json
.venv/bin/python -m scripts.benchmark --rapido     # corrida corta de prueba
```

El JSON alimenta la pestaña **Rendimiento** (GET `/api/rendimiento`). Tras
una corrida nueva basta con pulsar «Recargar resultados».

**Protocolo.** Para cada operación se generan, con semilla 42, redes
temporales de tamaño n, 2n y 4n en la variable que importa para esa
operación (estaciones, horarios por par o paradas de la ruta). Se usa
`time.perf_counter_ns`, calentamiento, 7 muestras y mediana. Las consultas se
cronometran en lotes y se divide por la cantidad de llamadas; las mutaciones
se miden una a una y el estado previo se restablece con `deshacer` fuera del
intervalo. Generar los CSV, cargar la red, HTTP y renderizar quedan fuera de
la medición. Antes de medir se comprueba el resultado de una llamada de cada
caso. Para cada serie se reporta la razón de medianas 2n/n y 4n/2n, junto
con la complejidad esperada y el análisis de la operación.

## Fichas R12

### R10 · `simular_fila(llegadas, frecuencia, capacidad)` — miembro 4

- **Contrato.** Devuelve una lista nueva con la espera de cada persona, en
  orden FIFO. Sale un bus en el minuto 0 y en cada múltiplo de la
  frecuencia; cada bus lleva hasta `capacidad` personas; quien llega justo a
  la salida alcanza a subir. Llegadas no negativas y no decrecientes,
  frecuencia y capacidad enteros positivos; si no, `ValueError`. La API
  calcula espera total, promedio y máxima a partir de la lista.
- **Estructura.** Fila implícita sobre el arreglo de llegadas: un cursor
  `frente` marca a la primera persona que no ha subido. No se elimina el
  primer elemento del arreglo (eso costaría O(n) por cada `pop(0)`).
- **Algoritmo.** Para la persona al frente se calcula el siguiente bus útil
  con `((llegada + f − 1) // f) · f`; si ese bus ya salió, se toma el
  siguiente al último procesado. El bus sube personas mientras haya cupo y
  `llegada ≤ salida`. Así se salta directo entre buses útiles y nunca se
  simulan buses vacíos en intervalos largos.
- **Alternativa descartada.** Avanzar minuto a minuto o bus por bus: su costo
  depende del rango de tiempo (por ejemplo llegadas en 0 y 10⁹ con
  frecuencia 10 simularían 10⁸ buses). Se conserva solo como modelo de
  referencia en las pruebas.
- **Complejidad.** Tiempo O(n) con n pasajeros: cada persona sube una vez y
  cada iteración del ciclo externo sube al menos a una persona. Espacio O(n)
  por la lista de salida y O(1) auxiliar.
- **Relación con R11.** La serie `simular_fila` usa frecuencia 5 y capacidad
  40 fijas y n creciente; se espera razón ≈ 2 al duplicar n.

### R1–R3 — miembro 1

Pendientes: las documentará el responsable cuando integre la red compartida.

### R4 · `proximo_bus(estacion, ruta, hora)` — miembro 2

- **Contrato.** Devuelve la primera hora programada mayor o igual a la consultada,
  o `None` si no existe servicio disponible. Comprueba que la estación esté
  `ABIERTA` y pertenezca a la ruta vigente. Acepta `HH:MM` con horas
  extendidas de 00 a 99 y minutos de 00 a 59; un formato inválido produce
  `ValueError`. Las horas repetidas se conservan.
- **Estructura.** Tabla hash propia indexada por `(ruta, estación)`, cuyo
  valor es una lista de minutos enteros ordenados de menor a mayor.
- **Algoritmo.** `indexar_horarios` convierte las horas a minutos y aplica
  mergesort propio a cada lista. `proximo_bus` realiza una búsqueda binaria
  manual del primer minuto que cumple `minuto >= consulta` y reconstruye
  `HH:MM`.
- **Alternativa descartada.** Recorrer linealmente todos los horarios en cada
  consulta obligaría a examinar hasta H entradas.
- **Complejidad.** Para H horarios de una pareja: construcción
  O(H log H) y espacio O(H) para ordenar esa lista; consulta O(log H)
  más búsquedas hash de costo promedio. El almacenamiento total depende
  de todos los registros cargados.
- **Relación con R11.** La serie `proximo_bus` varía la cantidad de horarios
  por pareja y contrasta las consultas con el crecimiento logarítmico esperado.

### R5 · `viaje(origen, destino)` — miembro 2

- **Contrato.** Devuelve `None` si no hay viaje, o
  `("DIRECTO" | "TRANSBORDO", saltos, tramos)`; cada tramo es
  `(ruta, estación_de_subida, estación_de_bajada)`. Solo se avanza en el
  sentido de las rutas y se permite **como máximo un transbordo**.
  Las estaciones cerradas pueden atravesarse y cuentan como saltos,
  pero no sirven para subir, bajar ni cambiar de ruta.
- **Estructura.** Consulta el índice de ocurrencias
  estación → `(ruta, nodo)` aportado por `red.salidas`. Cada nodo de
  recorrido enlazado expone `estacion` y `siguiente`; las ocurrencias
  repetidas no se colapsan.
- **Algoritmo.** Recorre hacia adelante cada salida del origen; examina
  destinos directos y, en estaciones intermedias abiertas, recorre
  salidas de otra ruta para buscar un destino con un único cambio.
  Conserva el mejor candidato por menor número de saltos; ante empate,
  prefiere un tramo directo y después el orden lexicográfico de tramos.
- **Alternativa descartada.** Construir un grafo completo por cada consulta
  duplicaría trabajo ya disponible en los índices de recorridos.
- **Complejidad.** Si I es el número de ocurrencias de salida del origen,
  P la longitud máxima de un recorrido y C las salidas candidatas por
  estación de transbordo, la cota conservadora del recorrido es
  O(I · P · (1 + C · P)), sin contar el trabajo de construir el índice
  compartido. Guarda únicamente el candidato mejor y sus tramos.
- **Relación con R11.** La serie `viaje` mide el tiempo de planificación
  aunque no esté sujeta al mismo umbral de escalamiento.

### R6 · `ranking(k)` — miembro 2

- **Contrato.** Devuelve hasta k tuplas nuevas `(estación, buses_diarios)`
  para estaciones abiertas, ordenadas por conteo descendente y nombre
  ascendente en caso de empate. Con k no positivo devuelve una lista vacía.
  La cuenta incluye registros de paso repetidos y puede ser cero.
- **Estructura.** Una tabla propia guarda `(conteo, abierta)` por estación
  y una **lista preordenada** contiene claves `(-conteo, nombre)` de las
  estaciones abiertas. Esta es la estructura implementada; no depende
  de un árbol AVL externo.
- **Algoritmo.** `registrar` incorpora cada estación. Al activar o
  desactivar una pareja `(ruta, estación)` se suma o resta la cantidad
  de horarios correspondiente. Al cerrar una estación se elimina su
  clave del orden, pero se conserva el conteo para reabrirla. Las
  actualizaciones buscan la posición por búsqueda binaria manual e
  insertan o quitan la clave; `consultar` devuelve los primeros k.
- **Alternativa descartada.** Reordenar todas las estaciones en cada
  consulta repetiría trabajo innecesario. Un árbol balanceado facilitaría
  las actualizaciones O(log n), pero exige otra implementación compartida.
- **Complejidad.** La consulta cuesta O(min(k, n)) sobre n estaciones
  abiertas; cada actualización del orden cuesta O(n) por los desplazamientos
  de la lista, aunque la posición se encuentre en O(log n). El índice
  ocupa O(n) espacio, además de la tabla de conteos.
- **Relación con R11.** La serie `ranking` mide consultas de los primeros
  k resultados con k fijo. Deben medirse también cierres y reaperturas
  después de integrar las operaciones reales.

### R7–R9 — miembro 3

Pendientes: las documentará el responsable cuando integre las operaciones
y la historia de cambios de la red.

## Datos

`datos/` contiene `estaciones.csv`, `rutas.csv` y `horarios.csv`, generados
desde el GTFS con `scripts/convertir_gtfs.py` (procedencia, fecha de servicio
y SHA-256 del ZIP: pendiente, miembro 1).
