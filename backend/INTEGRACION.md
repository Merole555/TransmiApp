# Integración de viajes

Contrato provisional para revisión con los miembros 1, 3 y 4. Las firmas
públicas de `Red` conservan los parámetros de la diapositiva 10.

- Carga (miembro 1): `viajes.indexar_horarios(tabla, filas)` recibe una tabla
  hash propia vacía con `obtener(clave)` (devuelve `None` si falta) y
  `asignar(clave, valor)`. La clave es la tupla `(ruta, estacion)`. Las filas
  de horarios ya pasaron la validación de referencias del cargador. El resultado
  se guarda como `red.horarios`; conserva todos los pasos fuente.
- Operaciones (miembro 3): `red.tiene_parada(ruta, estacion)` consulta el índice
  vigente de ocurrencias con búsqueda hash promedio. Una pareja con varias
  ocurrencias está activa mientras conserve alguna. Editar y deshacer cambian
  este índice; cerrar y reabrir cambian `red.estado(estacion)`.
- `Red.proximo_bus(estacion, ruta, hora)` delega a
  `viajes.proximo_bus(self, estacion, ruta, hora)`.
- R4 usa mergesort al cargar y búsqueda binaria de límite inferior al consultar.
  Con H horarios para el par, ordenar cuesta O(H log H), almacenar cuesta O(H)
  y consultar cuesta O(log H) más las búsquedas hash promedio. Un recorrido de
  la lista de horarios por consulta crecería linealmente con H.

## R5 y R6

- `red.salidas(nombre)` itera pares `(ruta, nodo)` de todas las ocurrencias
  vigentes de una estación mediante el índice estación → rutas y ocurrencias.
  Cada nodo expone `estacion` (nombre) y `siguiente` (nodo o `None`).
  La iteración incluye ocurrencias de estaciones cerradas. La consulta verifica
  la apertura en los puntos de abordaje, descenso y transbordo.
- `Red.viaje(origen, destino)` delega a `viajes.viaje`. Recorre nodos hacia
  adelante y compara cada candidato con el mejor según saltos, tramos y orden
  lexicográfico. Con I ocurrencias del origen, P paradas por ruta como máximo y
  C ocurrencias candidatas por punto de cambio como máximo, la cota es
  O(I·P·(1 + C·P)), considerando acceso promedio al índice y comparaciones
  de nombres de costo constante. No requiere construir un grafo por consulta.
- `red.indice_ranking` es `RankingEstaciones(tabla, arbol, red.horarios)`.
  La tabla es propia y está vacía. El árbol balanceado compartido acepta claves
  ordenables y expone `insertar(clave)`, `eliminar(clave)` y `ascendente()`
  como iterador perezoso desde la menor clave.
- Al cargar, registrar cada estación una vez con `registrar(nombre)` y luego
  activar cada pareja ruta-estación una vez con `cambiar_membresia`. El cargador
  conserva las filas de horarios aun cuando una edición retire su parada.
- R7–R9 llaman `cambiar_membresia(ruta, estacion, activa)` al pasar entre
  cero y una o más ocurrencias. Llaman `cambiar_apertura(nombre, abierta)`
  al cambiar la disponibilidad. Deshacer y rehacer siguen las mismas rutas
  de actualización. El adaptador mantiene el bloqueo durante cada operación.
- `Red.ranking(k)` delega a `viajes.ranking`. Las consultas cuestan
  O(log n + k') para n abiertas y k' resultados. Cada cambio cuesta O(log n)
  más búsquedas hash promedio. Mantener el orden en el árbol evita ordenar
  las estaciones en cada consulta.
