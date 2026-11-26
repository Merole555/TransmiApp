// Cliente tipado del contrato HTTP del miembro 2 (backend/main.py).
// Usa rutas relativas: en desarrollo Vite reenvía /api a FastAPI.

export class ErrorApi extends Error {
  readonly estado: number

  constructor(estado: number, mensaje: string) {
    super(mensaje)
    this.estado = estado
  }
}

export interface Estado { existe: boolean; abierta: boolean }
export interface Tramo { ruta: string; sube: string; baja: string }
export interface Viaje { tipo: 'DIRECTO' | 'TRANSBORDO'; saltos: number; tramos: Tramo[] }
export interface FilaRanking { estacion: string; buses: number }
export interface ResultadoFila {
  esperas: number[]
  espera_total: number
  espera_promedio: number
  espera_maxima: number
}
/** Acciones que se pueden deshacer / rehacer, la más reciente primero. */
export interface Historial { deshacer: string[]; rehacer: string[] }

export interface PuntoRendimiento {
  n: number
  mediana_ns: number
  razon_anterior: number | null
  dimensiones: Record<string, number>
}
export interface SerieRendimiento {
  operacion: string
  variable: string
  complejidad: string
  analisis: string
  puntos: PuntoRendimiento[]
  error?: string
}
export interface Rendimiento {
  configuracion: Record<string, string | number>
  series: SerieRendimiento[]
}

function mensajeDeError(cuerpo: unknown, estado: number): string {
  if (cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo) {
    const detalle = (cuerpo as { detail: unknown }).detail
    if (typeof detalle === 'string') return detalle
    if (Array.isArray(detalle)) {
      // Errores de validación de FastAPI/Pydantic.
      return detalle
        .map((d) => {
          const item = d as { loc?: unknown[]; msg?: string }
          const campo = item.loc ? item.loc[item.loc.length - 1] : ''
          return `${String(campo)}: ${item.msg ?? 'valor inválido'}`
        })
        .join('; ')
    }
  }
  if (estado >= 500) return 'El servidor tuvo un error interno. Revisa la terminal donde corre el backend.'
  return `Error HTTP ${estado}`
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(ruta, opciones)
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ErrorApi(0, 'No se pudo conectar con el servidor. ¿Está corriendo el backend?')
  }
  let cuerpo: unknown = null
  try {
    cuerpo = await respuesta.json()
  } catch {
    cuerpo = null
  }
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status))
  return cuerpo as T
}

function obtener<T>(ruta: string, parametros: Record<string, string | number | boolean>, senal?: AbortSignal) {
  const consulta = new URLSearchParams()
  for (const [clave, valor] of Object.entries(parametros)) consulta.set(clave, String(valor))
  return pedir<T>(`${ruta}?${consulta.toString()}`, { signal: senal })
}

function enviar<T>(ruta: string, cuerpo?: unknown) {
  return pedir<T>(ruta, {
    method: 'POST',
    headers: cuerpo === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  })
}

export const api = {
  salud: () => pedir<{ ok: boolean }>('/api/salud'),

  // R1–R3
  estado: (nombre: string) => obtener<Estado>('/api/estado', { nombre }),
  autocompletar: (prefijo: string, k: number, senal?: AbortSignal) =>
    obtener<{ estaciones: string[] }>('/api/autocompletar', { prefijo, k }, senal).then((r) => r.estaciones),
  rango: (desde: string, hasta: string) =>
    obtener<{ estaciones: string[] }>('/api/rango', { desde, hasta }).then((r) => r.estaciones),

  // R4–R6
  proximoBus: (estacion: string, ruta: string, hora: string) =>
    obtener<{ hora: string | null }>('/api/proximo-bus', { estacion, ruta, hora }).then((r) => r.hora),
  viaje: (origen: string, destino: string) =>
    obtener<{ viaje: Viaje | null }>('/api/viaje', { origen, destino }).then((r) => r.viaje),
  ranking: (k: number) =>
    obtener<{ ranking: FilaRanking[] }>('/api/ranking', { k }).then((r) => r.ranking),

  // R7–R9
  recorrido: (ruta: string, alReves: boolean) =>
    obtener<{ estaciones: string[] }>('/api/recorrido', { ruta, al_reves: alReves }).then((r) => r.estaciones),
  agregarParada: (ruta: string, nueva: string, despuesDe: string) =>
    enviar<{ cambio: boolean }>('/api/paradas/agregar', { ruta, nueva, despues_de: despuesDe }).then((r) => r.cambio),
  quitarParada: (ruta: string, estacion: string) =>
    enviar<{ cambio: boolean }>('/api/paradas/quitar', { ruta, estacion }).then((r) => r.cambio),
  cerrar: (nombre: string) => enviar<{ cambio: boolean }>('/api/cerrar', { nombre }).then((r) => r.cambio),
  reabrir: (nombre: string) => enviar<{ cambio: boolean }>('/api/reabrir', { nombre }).then((r) => r.cambio),
  deshacer: () => enviar<{ cambio: boolean }>('/api/deshacer').then((r) => r.cambio),
  rehacer: () => enviar<{ cambio: boolean }>('/api/rehacer').then((r) => r.cambio),

  // Listas auxiliares para la interfaz
  rutas: () => pedir<{ rutas: string[] }>('/api/rutas').then((r) => r.rutas),
  cerradas: () => pedir<{ estaciones: string[] }>('/api/cerradas').then((r) => r.estaciones),
  historial: () => pedir<Historial>('/api/historial'),

  // R10–R11
  simularFila: (llegadas: number[], frecuencia: number, capacidad: number) =>
    enviar<ResultadoFila>('/api/simular-fila', { llegadas, frecuencia, capacidad }),
  rendimiento: () => pedir<Rendimiento>('/api/rendimiento'),
}
