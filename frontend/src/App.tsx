import { useEffect, useState } from 'react'
import { api } from './api'
import { useListas } from './useListas'
import { Estaciones } from './vistas/Estaciones'
import { Fila } from './vistas/Fila'
import { Operacion } from './vistas/Operacion'
import { Rendimiento } from './vistas/Rendimiento'
import { Viajes } from './vistas/Viajes'

const PESTANAS = [
  { id: 'estaciones', titulo: 'Estaciones' },
  { id: 'viajes', titulo: 'Viajes' },
  { id: 'operacion', titulo: 'Operación' },
  { id: 'fila', titulo: 'Fila' },
  { id: 'rendimiento', titulo: 'Rendimiento' },
] as const

type Pestana = (typeof PESTANAS)[number]['id']
type Tema = 'claro' | 'oscuro'

function temaInicial(): Tema {
  try {
    const guardado = localStorage.getItem('tema')
    if (guardado === 'claro' || guardado === 'oscuro') return guardado
  } catch {
    /* sin almacenamiento disponible */
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'
}

export default function App() {
  const [activa, setActiva] = useState<Pestana>('estaciones')
  // Sube con cada mutación efectiva para que las vistas repitan sus consultas.
  const [version, setVersion] = useState(0)
  const [conectado, setConectado] = useState<boolean | null>(null)
  const [tema, setTema] = useState<Tema>(temaInicial)
  const { estaciones, rutas } = useListas(version)

  useEffect(() => {
    api.salud().then(() => setConectado(true)).catch(() => setConectado(false))
  }, [])

  useEffect(() => {
    document.documentElement.dataset.tema = tema
    try {
      localStorage.setItem('tema', tema)
    } catch {
      /* sin almacenamiento disponible */
    }
  }, [tema])

  return (
    <div className="app">
      <header className="cabecera">
        <h1>TransmiApp</h1>
        <div className="cabecera-derecha">
          <span className={`conexion ${conectado === false ? 'mal' : ''}`} role="status">
            {conectado === null ? 'Conectando…' : conectado ? 'API conectada' : 'Sin conexión con la API'}
          </span>
          <button type="button" className="secundario"
            onClick={() => setTema(tema === 'oscuro' ? 'claro' : 'oscuro')}
            aria-label={tema === 'oscuro' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}>
            {tema === 'oscuro' ? '☀ Claro' : '☾ Oscuro'}
          </button>
        </div>
      </header>
      <nav className="pestanas" role="tablist" aria-label="Secciones">
        {PESTANAS.map((p) => (
          <button key={p.id} role="tab" type="button" aria-selected={activa === p.id}
            className={activa === p.id ? 'activa' : ''} onClick={() => setActiva(p.id)}>
            {p.titulo}
          </button>
        ))}
      </nav>

      {/* Listas compartidas para el autocompletado de estaciones y rutas en todas las vistas. */}
      <datalist id="lista-estaciones">
        {estaciones.map((e) => <option key={e} value={e} />)}
      </datalist>
      <datalist id="lista-rutas">
        {rutas.map((r) => <option key={r} value={r} />)}
      </datalist>

      <main>
        {/* Las vistas se conservan montadas para no perder formularios al cambiar de pestaña. */}
        <div hidden={activa !== 'estaciones'}><Estaciones version={version} /></div>
        <div hidden={activa !== 'viajes'}><Viajes version={version} /></div>
        <div hidden={activa !== 'operacion'}>
          <Operacion version={version} alCambiar={() => setVersion((v) => v + 1)} />
        </div>
        <div hidden={activa !== 'fila'}><Fila /></div>
        {activa === 'rendimiento' && <Rendimiento />}
      </main>
    </div>
  )
}
