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

## Pruebas de estrés e integración (R1–R11)

Las pruebas reproducibles están en `scripts/pruebas/test_estres.py`.
Usan CSV sintéticos temporales (400 estaciones y dos rutas conectadas),
consultas repetidas, ediciones y reversión, una fila de 20.000 pasajeros,
la API real y las 15 series de R11 con tamaños reducidos. No dependen
de los CSV del profesor ni imponen umbrales de tiempo sensibles a la CPU.

```bash
# Desde la raíz del repositorio y con las dependencias de backend instaladas
python -m unittest discover -s scripts/pruebas -p "test_estres.py" -v
# Suite completa (incluye estas pruebas)
python -m unittest discover -s scripts/pruebas -p "test_*.py" -v
```

Para datos reales, conservar también la validación manual de arranque,
consultas y operaciones desde la web. Los identificadores de ruta que
llegan por HTTP se convierten a mayúsculas y se recortan los espacios
externos antes de consultar o modificar la red (`t1` y `T1` equivalen);
el motor y los CSV mantienen sus IDs originales.

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
intervalo. Para que las razones sean estables, las tres redes se preparan
primero y se mide en 5 rondas alternando n, 2n y 4n (una pausa del computador
afecta a los tres tamaños por igual), y el recolector de basura se apaga
mientras se cronometra, como hace `timeit`. Se usa Python 3.12: con 3.9 (el
que trae macOS) no se instalan las dependencias. Generar los CSV, cargar la red, HTTP y renderizar quedan fuera de
la medición. Antes de medir se comprueba el resultado de una llamada de cada
caso. Para cada serie se reporta la razón de medianas 2n/n y 4n/2n, junto
con la complejidad esperada y el análisis de la operación.

## Fichas R12

### R1 · `estado(nombre)` — miembro 1

- **Contrato.** Devuelve `"ABIERTA"`, `"CERRADA"` o `"NO_EXISTE"`. Una
  estación cerrada sigue registrada para poder responder y reabrirla.
- **Estructura.** `TablaHash` propia (`motor/estructuras.py`) con
  encadenamiento: cada cubo es una lista de pares `[clave, valor]`. El hash
  recorre los caracteres (`valor * 31 + ord(c)`) y la tabla duplica sus cubos
  cuando pasa de 0,75 elementos por cubo.
- **Alternativa descartada.** Buscar el nombre en una lista: O(n) por consulta.
- **Complejidad.** O(L) promedio, con L = largo del nombre (calcular el hash y
  comparar la clave). Peor caso O(n·L) si las n estaciones chocan en un cubo.
  Espacio O(n).
- **Relación con R11.** La serie `estado` duplica las estaciones con nombres de
  largo fijo; se espera razón ≈ 1.

### R2 · `autocompletar(prefijo, k)` y R3 · `rango(desde, hasta)` — miembro 1

- **Contrato.** R2 devuelve hasta k estaciones abiertas que empiezan por el
  prefijo, en orden; prefijo vacío devuelve las primeras k y `k <= 0` devuelve
  `[]`. R3 devuelve las abiertas entre `desde` y `hasta`, ambos incluidos; si
  `desde > hasta`, `[]`. Cada llamada devuelve una lista nueva.
- **Estructura.** `ArbolAVL` propio que solo guarda las estaciones abiertas.
  Se rebalancea con rotaciones simples y dobles, así su altura es O(log n).
- **Algoritmo.** `desde(clave)` baja hasta el primer nombre mayor o igual a la
  clave guardando en una pila los ancestros pendientes, y sigue el recorrido en
  orden con esa pila. R2 se detiene al juntar k nombres o cuando un nombre ya no
  empieza por el prefijo; R3, cuando el nombre pasa de `hasta`.
- **Cierres (R8).** `estaciones.retirar_abierta` y `reinsertar_abierta`
  cambian la tabla, sacan o meten el nombre del AVL y avisan al ranking, en
  O(log n). Así R2 y R3 nunca recorren estaciones cerradas.
- **Alternativas descartadas.** Una lista ordenada busca en O(log n), pero
  cerrar o reabrir desplaza elementos: O(n). Un árbol con todas las estaciones
  que filtra cerradas al consultar se degrada cuando hay muchos cierres.
- **Complejidad.** O(log n + s) visitas, con n estaciones abiertas y s
  resultados (s ≤ k en R2); materializar la salida cuesta O(s). Cada
  comparación de cadenas cuesta hasta O(L). Espacio O(n) para el árbol y O(s)
  para la salida (más la pila, O(log n)).
- **Relación con R11.** Las series `autocompletar` y `rango` duplican las
  estaciones con k = 10 y s = 10 fijos; se espera razón poco mayor que 1.

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

### R1–R9

(falta completar algunos R)

### R7 · `agregar_parada`, `quitar_parada`, `recorrido` — miembro 3

- **Contrato.** `agregar_parada(ruta, nueva, despues_de)` inserta `nueva`
  entre `despues_de` y su sucesora. Devuelve `False`, sin tocar nada, si la
  ruta no existe, `nueva` no es una estación, `nueva` ya figura en la ruta,
  el ancla no existe o aparece más de una vez, o el ancla es la última
  parada. `quitar_parada(ruta, estacion)` exige una ocurrencia única y deja
  al menos una parada. `recorrido(ruta, al_reves=False)` devuelve una lista
  nueva con el trazado físico (incluye cerradas) y `[]` si la ruta no existe.
- **Estructura.** Lista doblemente enlazada por ruta (`Nodo`, con cabeza y
  cola en `red.rutas`) y un índice `TablaHash` propio
  `(ruta, estación) -> [cantidad, nodo]` que se crea la primera vez que se
  muta. La cantidad detecta anclas ambiguas cuando el CSV repite una
  estación en una ruta. `red.paradas` (estación -> rutas) se actualiza con
  cada cambio.
- **Algoritmo.** Se valida todo antes de tocar estructuras. Insertar y
  quitar solo reparan los enlaces del nodo y de sus dos vecinos y, si el nodo
  es un extremo, la cabeza o la cola. Además se actualizan el índice, `red.paradas` y la
  membresía del ranking (`cambiar_membresia`): quitar resta los horarios de
  la pareja ruta-estación y agregar los reactiva si existen. Una parada sin
  horarios aporta cero.
- **Alternativa descartada.** Buscar el ancla recorriendo la ruta: O(p) por
  edición y no detecta ambigüedad. Una lista de Python con `insert` y `pop`
  desplazaría O(p) elementos y obligaría a recalcular posiciones.
- **Complejidad.** Con p paradas de la ruta, r rutas que pasan por la
  estación y n estaciones. Agregar: O(L) promedio para los hashes (L = largo
  del nombre) y O(1) para los enlaces, más la actualización del ranking.
  Quitar: lo mismo más O(r) para ubicar y sacar la entrada en `red.paradas`.
  `recorrido`: O(p) tiempo y espacio por la lista nueva. La primera mutación
  construye el índice en O(total de paradas). Espacio extra O(paradas).
  Ranking: el índice del miembro 2 busca en O(log n) pero inserta y elimina
  en un arreglo, así que el desplazamiento cuesta O(n).
- **Relación con R11.** `agregar_parada` y `quitar_parada` varían p
  (paradas de la ruta): no deberían depender de p, razón ≈ 1.
  `recorrido` y `recorrido_inverso` son O(p): razón ≈ 2.

### R8 · `cerrar(nombre)` y `reabrir(nombre)` — miembro 3

- **Contrato.** Devuelven `True` solo si cambia el estado. Cerrar una
  estación inexistente o ya cerrada devuelve `False`; igual con reabrir. Una
  cerrada sigue registrada y en el trazado, pero no se ofrece en R2, R3, R4,
  R6, ni se usa para subir, bajar o transbordar en R5.
- **Estructura.** No hay estructura nueva: delega en
  `estaciones.retirar_abierta` y `reinsertar_abierta`, que actualizan la
  `TablaHash` de R1, el `ArbolAVL` de abiertas y el índice del ranking. Los
  enlaces, horarios y conteos se conservan para poder reabrir.
- **Alternativa descartada.** Borrar la estación de la red: se perdería su
  registro, su lugar en las rutas y sus horarios, y reabrir sería
  reconstruirlos.
- **Complejidad.** O(L) para el hash + O(log n) para el AVL con n estaciones
  abiertas, más la actualización del ranking (búsqueda O(log n) y
  desplazamiento O(n) en el arreglo ordenado del miembro 2).
- **Relación con R11.** Series `cerrar` y `reabrir` con n estaciones. Se
  espera crecimiento suave; si la medición muestra más, es el
  desplazamiento del arreglo del ranking.

### R9 · `deshacer()` y `rehacer()` — miembro 3

- **Contrato.** Devuelven `True` solo si revierten o reaplican un cambio.
  Con la pila vacía devuelven `False`. Una mutación nueva y exitosa vacía
  rehacer; una inválida conserva ambas pilas.
- **Estructura.** Dos `Pila` propias (arreglos con `append` y `pop` al
  final) de `Registro`: acción, estación, ruta, nodo y vecinos exactos
  (más la posición en `red.paradas`). No se copia la red.
- **Algoritmo.** Una sola rutina interna aplica e invierte cada acción:
  agregar e invertir quitar son las mismas dos operaciones (`_enlazar` y
  `_desenlazar`) y cerrar/reabrir son inversas entre sí. `deshacer` saca de
  la pila de deshacer, invierte y apila en rehacer; `rehacer` hace lo
  contrario. Como se reutiliza el mismo nodo con sus vecinos guardados, el
  orden queda idéntico al original.
- **Alternativa descartada.** Guardar una copia de la red por cambio: O(red)
  por mutación en tiempo y espacio.
- **Complejidad.** Mover el registro entre pilas es O(1); el costo total es
  el de la acción revertida (R7 o R8). Vaciar rehacer es O(1) amortizado
  (cada entrada se apila una vez y se descarta una vez). Espacio O(cambios).
- **Relación con R11.** Series `deshacer` y `rehacer` con el estado previo
  restablecido fuera del intervalo medido.

## Datos

`datos/` contiene los tres CSV de la red real de TransMilenio **que entregó el
profesor** (Juan Carlos Rubio Coello) el 3 de noviembre de 2026 en el canal
General del equipo de Teams *9324 PERIODO 2026-2 ESTRUC DATOS Y ALGORITMOS*
(«Archivos para el proyecto final»). El profesor no compartió el ZIP GTFS y
dio los datos ya convertidos, así que se usan tal cual, sin modificarlos.

| Archivo | Filas (sin cabecera) | SHA-256 |
| --- | --- | --- |
| `estaciones.csv` | 147 estaciones | `d2d1a61e715469dbb4f272f3aff4954b360ca09a8df15dd84cbd6af8e6764376` |
| `rutas.csv` | 1.927 paradas en 181 rutas | `7fe7ef528ed1b55a218ee4e30125dd7c4f66142373616522668e6a6ae4dcec4c` |
| `horarios.csv` | 140.492 pasos | `6b50b2a150083a58766f11ae061879fe97b52ae03f3ea39a410331667320317c` |

`Red("datos")` los carga y valida en cerca de 1 s. `estaciones.csv` viene con
fin de línea CRLF (Windows); `csv.reader` lo lee igual.

`scripts/convertir_gtfs.py` queda como herramienta para regenerar CSV desde
cualquier GTFS (por ejemplo, para probar con otra red más grande).

### Conversión (miembro 1)

```bash
.venv/bin/python scripts/convertir_gtfs.py --gtfs "<RUTA_AL_ZIP>" --salida datos --fecha-servicio 2021-07-21
shasum -a 256 "<RUTA_AL_ZIP>"                      # macOS / Linux
Get-FileHash "<RUTA_AL_ZIP>" -Algorithm SHA256      # Windows PowerShell
```

Política provisional del conversor:

1. **Servicios del día.** Los de `calendar.txt` que corren ese día de la semana
   dentro de su rango de fechas, más las excepciones de `calendar_dates.txt`
   (tipo 1 agrega, tipo 2 quita). Sin calendario, la conversión se detiene.
2. **Estaciones.** Cada andén se resuelve a su estación con `parent_station`.
   Nombres en mayúsculas, sin tildes y con un solo espacio; si dos estaciones
   distintas quedan con el mismo nombre, se reporta la colisión.
3. **Rutas troncales.** Se dejan las rutas cuyos viajes paran solo en andenes
   que pertenecen a una estación. `--todas-las-rutas` incluye las zonales.
4. **Patrones.** Cada ruta, sentido y secuencia de estaciones distinta recibe
   un id determinista (`B74_0_01`). Las paradas se ordenan por `stop_sequence`
   numérico y varios andenes seguidos de la misma estación cuentan como uno.
5. **Horas.** Se usa la salida (o la llegada si falta), truncada al minuto. Se
   toman las horas 00–23 de los viajes activos ese día y las horas 24–47 de los
   del día anterior pasadas al día civil (25:10 → 01:10). Se conservan pasos
   simultáneos de buses distintos.

### Carga en el motor

`Red(carpeta)` lee los CSV con `csv.reader` en orden estaciones → rutas →
horarios y valida cabeceras exactas, estaciones únicas, `orden` entero y único
por ruta, referencias existentes y horas `HH:MM`. Cada error indica archivo y
fila (por ejemplo `rutas.csv, fila 3: orden 1 repetido en T1`). Acepta filas
desordenadas: cada ruta se ordena con mergesort propio y se arma como lista
doblemente enlazada.

```bash
.venv/bin/python -m unittest discover -s scripts/pruebas -p "test_estaciones.py" -v
.venv/bin/python -m unittest discover -s scripts/pruebas -p "test_conversion.py" -v
```
