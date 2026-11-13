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
