import { useEffect, useState } from 'react'
import { api } from './api'

/** Estaciones (abiertas y cerradas) y rutas para los autocompletados de todas las vistas. */
export function useListas(version: number) {
  const [estaciones, setEstaciones] = useState<string[]>([])
  const [rutas, setRutas] = useState<string[]>([])

  useEffect(() => {
    let vigente = true
    const vacia = () => [] as string[]
    Promise.all([
      api.autocompletar('', 5000).catch(vacia),
      api.cerradas().catch(vacia),
      api.rutas().catch(vacia),
    ]).then(([abiertas, cerradas, todasLasRutas]) => {
      if (!vigente) return
      setEstaciones([...abiertas, ...cerradas])
      setRutas(todasLasRutas)
    })
    return () => { vigente = false }
  }, [version])

  return { estaciones, rutas }
}
