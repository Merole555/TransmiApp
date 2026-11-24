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

### R1–R9

Pendientes: las escribe el autor de cada requisito.

## Datos

`datos/` contiene `estaciones.csv`, `rutas.csv` y `horarios.csv`, generados
desde el GTFS con `scripts/convertir_gtfs.py` (procedencia, fecha de servicio
y SHA-256 del ZIP: pendiente, miembro 1).
