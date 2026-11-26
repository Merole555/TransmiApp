import { useEffect, useRef, useState } from 'react'
import { api, type Historial } from '../api'
import { Campo, Formulario, ListaEstaciones, Resultado, Tarjeta } from '../comunes'
import { normalizar } from '../texto'
import { usePeticion } from '../usePeticion'

const SIN_HISTORIAL: Historial = { deshacer: [], rehacer: [] }
const MOSTRAR_HISTORIAL = 8

/** R7–R9: recorrido, edición de paradas, cierres e historial. */
export function Operacion({ version, alCambiar }: { version: number; alCambiar: () => void }) {
  const [ruta, setRuta] = useState('')
  const [alReves, setAlReves] = useState(false)
  const [recorrido, consultarRecorrido] = usePeticion<string[]>()
  const ultimo = useRef<[string, boolean] | null>(null)

  const [rutaEdicion, setRutaEdicion] = useState('')
  const [nueva, setNueva] = useState('')
  const [despuesDe, setDespuesDe] = useState('')
  const [quitar, setQuitar] = useState('')
  const [trazado, consultarTrazado] = usePeticion<{ ruta: string; estaciones: string[] }>()
  const ultimoTrazado = useRef<string | null>(null)
  const [resaltar, setResaltar] = useState('')

  const [estacion, setEstacion] = useState('')
  const [aReabrir, setAReabrir] = useState('')
  const [cerradas, setCerradas] = useState<string[]>([])
  const [historial, setHistorial] = useState<Historial>(SIN_HISTORIAL)

  const [mensaje, setMensaje] = useState<{ texto: string; bien: boolean } | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const verRecorrido = (r: string, inverso: boolean) => {
    ultimo.current = [r, inverso]
    consultarRecorrido(() => api.recorrido(r, inverso))
  }
  const verTrazado = (r: string) => {
    ultimoTrazado.current = r
    consultarTrazado(async () => ({ ruta: r, estaciones: await api.recorrido(r, false) }))
  }

  // Tras cualquier cambio se repiten las vistas abiertas de esta pestaña.
  useEffect(() => {
    if (version > 0 && ultimo.current) verRecorrido(...ultimo.current)
    if (version > 0 && ultimoTrazado.current) verTrazado(ultimoTrazado.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version])

  // Historial y estaciones cerradas vienen del motor (al abrir y tras cada cambio).
  useEffect(() => {
    let vigente = true
    Promise.all([api.historial(), api.cerradas()])
      .then(([h, c]) => {
        if (!vigente) return
        setHistorial(h)
        setCerradas(c)
        setAReabrir((actual) => (c.includes(actual) ? actual : ''))
      })
      .catch(() => undefined)
    return () => { vigente = false }
  }, [version])

  // Ejecuta una mutación. Solo si hubo cambio efectivo se refrescan las vistas.
  const mutar = async (
    descripcion: string,
    tarea: () => Promise<boolean>,
    extra: { marca?: string; pista?: string } = {},
  ) => {
    setOcupado(true)
    try {
      const cambio = await tarea()
      setMensaje(cambio
        ? { texto: `✓ ${descripcion}: hecho.`, bien: true }
        : { texto: `${descripcion}: no se aplicó. ${extra.pista ?? 'La operación no era válida en el estado actual.'}`, bien: false })
      if (cambio) {
        setResaltar(extra.marca ?? '')
        alCambiar()
      }
    } catch (error) {
      setMensaje({ texto: `${descripcion}: ${(error as Error).message}`, bien: false })
    } finally {
      setOcupado(false)
    }
  }

  const puedeDeshacer = historial.deshacer.length > 0
  const puedeRehacer = historial.rehacer.length > 0

  return (
    <>
    <p className={`barra-estado ${mensaje ? (mensaje.bien ? 'bien' : 'advertencia') : ''}`} role="status">
      {mensaje ? mensaje.texto : 'Las mutaciones efectivas actualizan automáticamente las consultas abiertas en las demás pestañas.'}
    </p>
    <div className="rejilla">
      <Tarjeta titulo="Recorrido de una ruta" requisito="R7">
        <Formulario boton="Ver recorrido" onEnviar={() => verRecorrido(ruta, alReves)} ocupado={recorrido.tipo === 'cargando'}>
          <Campo etiqueta="Ruta" valor={ruta} onCambio={setRuta} lista="lista-rutas" />
          <label className="casilla">
            <input type="checkbox" checked={alReves} onChange={(e) => setAlReves(e.target.checked)} />
            Sentido inverso
          </label>
        </Formulario>
        <Resultado estado={recorrido}>{(lista) => <ListaEstaciones estaciones={lista} />}</Resultado>
      </Tarjeta>

      <Tarjeta titulo="Editar paradas" requisito="R7">
        <Campo etiqueta="Ruta" valor={rutaEdicion} onCambio={setRutaEdicion} lista="lista-rutas" />
        <div className="botones">
          <button type="button" className="secundario" disabled={!rutaEdicion.trim()}
            onClick={() => verTrazado(rutaEdicion.trim())}>Ver trazado actual</button>
        </div>
        <Formulario boton="Agregar parada" ocupado={ocupado}
          onEnviar={() => {
            ultimoTrazado.current = rutaEdicion.trim()
            return mutar(`Agregar ${nueva} después de ${despuesDe}`,
              () => api.agregarParada(rutaEdicion, nueva, despuesDe),
              {
                marca: normalizar(nueva),
                pista: 'Revisa que la ruta exista, que la estación nueva exista y no esté ya en la ruta, y que «Después de» aparezca una sola vez y no sea la última parada.',
              })
          }}>
          <Campo etiqueta="Nueva estación" valor={nueva} onCambio={setNueva} lista="lista-estaciones" />
          <Campo etiqueta="Después de" valor={despuesDe} onCambio={setDespuesDe} lista="lista-estaciones" />
        </Formulario>
        <Formulario boton="Quitar parada" ocupado={ocupado}
          onEnviar={() => {
            ultimoTrazado.current = rutaEdicion.trim()
            return mutar(`Quitar ${quitar}`, () => api.quitarParada(rutaEdicion, quitar),
              { pista: 'Revisa que la estación esté una sola vez en la ruta y que la ruta tenga más de una parada.' })
          }}>
          <Campo etiqueta="Estación a quitar" valor={quitar} onCambio={setQuitar} lista="lista-estaciones" />
        </Formulario>
        <Resultado estado={trazado}>
          {({ ruta: r, estaciones }) => (
            <>
              <p className="nota">Trazado actual de {r} ({estaciones.length} paradas)</p>
              <ListaEstaciones estaciones={estaciones} resaltar={resaltar} />
            </>
          )}
        </Resultado>
      </Tarjeta>

      <Tarjeta titulo="Cerrar y reabrir" requisito="R8">
        <Formulario boton="Cerrar" ocupado={ocupado}
          onEnviar={() => mutar(`Cerrar ${estacion}`, () => api.cerrar(estacion),
            { pista: 'La estación no existe o ya estaba cerrada.' })}>
          <Campo etiqueta="Estación a cerrar" valor={estacion} onCambio={setEstacion} lista="lista-estaciones" />
        </Formulario>
        <Formulario boton="Reabrir" ocupado={ocupado || cerradas.length === 0}
          onEnviar={() => mutar(`Reabrir ${aReabrir}`, () => api.reabrir(aReabrir))}>
          <label className="campo">
            <span>Estación cerrada</span>
            <select value={aReabrir} required onChange={(e) => setAReabrir(e.target.value)}>
              <option value="">{cerradas.length === 0 ? 'No hay estaciones cerradas' : 'Elige una estación'}</option>
              {cerradas.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        </Formulario>
      </Tarjeta>

      <Tarjeta titulo="Historial" requisito="R9">
        <div className="botones">
          <button type="button" disabled={ocupado || !puedeDeshacer}
            onClick={() => mutar(`Deshacer «${historial.deshacer[0] ?? ''}»`, api.deshacer)}>↶ Deshacer</button>
          <button type="button" disabled={ocupado || !puedeRehacer}
            onClick={() => mutar(`Rehacer «${historial.rehacer[0] ?? ''}»`, api.rehacer)}>↷ Rehacer</button>
        </div>
        <h3>Hechas (la más reciente primero)</h3>
        {puedeDeshacer
          ? <ol className="lista-historial">{historial.deshacer.slice(0, MOSTRAR_HISTORIAL).map((t, i) => <li key={`${t}-${i}`}>{t}</li>)}</ol>
          : <p className="vacio">Todavía no hay cambios.</p>}
        {puedeRehacer && (
          <>
            <h3>Para rehacer</h3>
            <ol className="lista-historial">{historial.rehacer.slice(0, MOSTRAR_HISTORIAL).map((t, i) => <li key={`${t}-${i}`}>{t}</li>)}</ol>
          </>
        )}
      </Tarjeta>
    </div>
    </>
  )
}
