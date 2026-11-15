# Integración de miembro 2 (contratos aprobados)

Esta rama contiene R4, R5, R6 y adaptador FastAPI. No incluye aún la
implementación real de `Red`, el cargador CSV ni `simular_fila`; pertenecen
a la integración con los demás miembros. Las pruebas HTTP usan dobles.

## R1 y R4

`red.estado(nombre)` devuelve `"ABIERTA"`, `"CERRADA"` o `"NO_EXISTE"`.
`red.tiene_parada(ruta, estacion)` devuelve Booleano para una pareja vigente.
`red.horarios` es una tabla hash propia con `obtener` y `asignar`.
`viajes.indexar_horarios(tabla, filas)` recibe tuplas `(ruta, estacion, HH:MM)`,
con horas GTFS extendidas de 00 a 99. Ordena los minutos con mergesort propio;
`viajes.proximo_bus(red, estacion, ruta, hora)` usa búsqueda binaria y devuelve
`HH:MM` o `None`.

## R5

`red.salidas(nombre)` entrega pares `(ruta, nodo)` por cada ocurrencia
vigente. Cada nodo expone `estacion` y `siguiente`. La búsqueda solo avanza
en el sentido de la ruta, permite máximo un transbordo, no usa estaciones
cerradas para subir, bajar ni transbordar, y sí puede atravesarlas a bordo.
`viajes.viaje` devuelve `None` o
`(tipo, saltos, tramos)`, donde `tipo` es `"DIRECTO"` o
`"TRANSBORDO"` y `tramos` es una lista de
`(ruta, origen_del_tramo, destino_del_tramo)`.

## R6

`red.indice_ranking = viajes.RankingEstaciones(tabla, None, red.horarios)`.
La tabla es propia y está vacía. El segundo argumento se conserva únicamente
por compatibilidad con el adaptador previo; **no se necesita AVL**.
Registrar estaciones con `registrar(nombre)`; activar una pareja ruta-estación
una vez mediante `cambiar_membresia(ruta, estacion, True)`. Las operaciones,
deshacer y rehacer notifican transiciones efectivas de membresía y apertura.
Se mantiene un arreglo ordenado de claves `(-buses, estacion)`, con inserción
y eliminación por búsqueda binaria manual. Consultar los primeros k cuesta
O(k); cada actualización cuesta O(n) por desplazamiento del arreglo.

## API y R10

`crear_app` construye la aplicación y acepta inyección de `crear_red` y
`simular_fila` para pruebas. En ejecución real, importa ambos desde
`motor`. La API convierte `estado` a `{existe, abierta}`; el viaje a
`{viaje: {tipo, saltos, tramos}}`; la simulación recibe una lista de
esperas por persona y expone `esperas`, total, promedio y máximo.
Los errores de validación son HTTP 422.

## R11 y pendientes antes de integración final

`GET /api/rendimiento` lee el JSON previamente generado por el arnés
reproducible del miembro 4. No ejecuta benchmarks durante solicitudes HTTP.
El panel de un solo gráfico y el script de benchmarks quedan pendientes
hasta que el miembro 4 publique su implementación.

**Bloqueantes para declarar el producto funcional:**
1. Exportar `Red` y `simular_fila` en `motor/__init__.py`.
2. Conectar el cargador de los tres CSV a horarios, salidas y ranking.
3. Conectar R7-R9 y sus notificaciones de cambios/undo/redo.
4. Incorporar el benchmark JSON reproducible y el frontend.
5. Probar con la red real, además de los dobles, y revisar la guía original
   del miembro 2 contra esta implementación.
