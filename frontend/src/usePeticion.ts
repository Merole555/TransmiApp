import { useCallback, useState } from 'react'

export type EstadoPeticion<T> =
  | { tipo: 'inicial' }
  | { tipo: 'cargando' }
  | { tipo: 'ok'; datos: T }
  | { tipo: 'error'; mensaje: string }

/** Ejecuta una petición y conserva su estado de carga, resultado o error. */
export function usePeticion<T>() {
  const [estado, setEstado] = useState<EstadoPeticion<T>>({ tipo: 'inicial' })
  const ejecutar = useCallback(async (tarea: () => Promise<T>) => {
    setEstado({ tipo: 'cargando' })
    try {
      const datos = await tarea()
      setEstado({ tipo: 'ok', datos })
      return datos
    } catch (error) {
      setEstado({ tipo: 'error', mensaje: (error as Error).message })
      return undefined
    }
  }, [])
  return [estado, ejecutar] as const
}
