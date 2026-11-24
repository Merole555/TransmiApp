import type { FormEvent, ReactNode } from 'react'
import type { EstadoPeticion } from './usePeticion'

export function Tarjeta({ titulo, requisito, children }: { titulo: string; requisito: string; children: ReactNode }) {
  return (
    <section className="tarjeta" aria-label={titulo}>
      <header>
        <h2>{titulo}</h2>
        <span className="etiqueta">{requisito}</span>
      </header>
      {children}
    </section>
  )
}

export function Campo(props: {
  etiqueta: string
  valor: string
  onCambio: (valor: string) => void
  tipo?: string
  min?: number
  marcador?: string
  lista?: string
  requerido?: boolean
}) {
  return (
    <label className="campo">
      <span>{props.etiqueta}</span>
      <input
        type={props.tipo ?? 'text'}
        value={props.valor}
        min={props.min}
        placeholder={props.marcador}
        list={props.lista}
        required={props.requerido ?? true}
        onChange={(e) => props.onCambio(e.target.value)}
      />
    </label>
  )
}

export function Formulario({ onEnviar, boton, children, ocupado }: {
  onEnviar: () => void
  boton: string
  children: ReactNode
  ocupado?: boolean
}) {
  return (
    <form
      className="formulario"
      onSubmit={(e: FormEvent) => {
        e.preventDefault()
        onEnviar()
      }}
    >
      {children}
      <button type="submit" disabled={ocupado}>{boton}</button>
    </form>
  )
}

/** Muestra carga, error o el contenido de un resultado. */
export function Resultado<T>({ estado, children }: { estado: EstadoPeticion<T>; children: (datos: T) => ReactNode }) {
  if (estado.tipo === 'inicial') return null
  if (estado.tipo === 'cargando') return <p className="aviso" role="status">Consultando…</p>
  if (estado.tipo === 'error') return <p className="error" role="alert">{estado.mensaje}</p>
  return <div className="resultado" aria-live="polite">{children(estado.datos)}</div>
}

export function ListaEstaciones({ estaciones }: { estaciones: string[] }) {
  if (estaciones.length === 0) return <p className="vacio">Sin resultados.</p>
  return (
    <ol className="lista-estaciones">
      {estaciones.map((nombre, i) => <li key={`${nombre}-${i}`}>{nombre}</li>)}
    </ol>
  )
}
