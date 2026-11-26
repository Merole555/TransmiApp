import { useEffect, useRef, useState } from 'react'
import { api, type FilaRanking, type Viaje } from '../api'
import { Campo, Formulario, Resultado, Tarjeta } from '../comunes'
import { usePeticion } from '../usePeticion'

function horaActual() {
  const ahora = new Date()
  return `${String(ahora.getHours()).padStart(2, '0')}:${String(ahora.getMinutes()).padStart(2, '0')}`
}

/** R4–R6: próximo bus, plan de viaje y ranking de estaciones. */
export function Viajes({ version }: { version: number }) {
  const [estacion, setEstacion] = useState('')
  const [ruta, setRuta] = useState('')
  const [hora, setHora] = useState('08:00')
  const [bus, consultarBus] = usePeticion<string | null>()
  const ultimoBus = useRef<[string, string, string] | null>(null)

  const [origen, setOrigen] = useState('')
  const [destino, setDestino] = useState('')
  const [plan, consultarPlan] = usePeticion<Viaje | null>()
  const ultimoPlan = useRef<[string, string] | null>(null)

  const [k, setK] = useState('10')
  const [ranking, consultarRanking] = usePeticion<FilaRanking[]>()
  const ultimoK = useRef<number | null>(null)

  const buscarBus = (e: string, r: string, h: string) => {
    ultimoBus.current = [e, r, h]
    consultarBus(() => api.proximoBus(e, r, h))
  }
  const buscarPlan = (o: string, d: string) => {
    ultimoPlan.current = [o, d]
    consultarPlan(() => api.viaje(o, d))
  }
  const buscarRanking = (cantidad: number) => {
    ultimoK.current = cantidad
    consultarRanking(() => api.ranking(cantidad))
  }

  useEffect(() => {
    if (version === 0) return
    if (ultimoBus.current) buscarBus(...ultimoBus.current)
    if (ultimoPlan.current) buscarPlan(...ultimoPlan.current)
    if (ultimoK.current !== null) buscarRanking(ultimoK.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version])

  return (
    <div className="rejilla">
      <Tarjeta titulo="Próximo bus" requisito="R4">
        <Formulario boton="Buscar" onEnviar={() => buscarBus(estacion, ruta, hora)} ocupado={bus.tipo === 'cargando'}>
          <Campo etiqueta="Estación" valor={estacion} onCambio={setEstacion} lista="lista-estaciones" />
          <Campo etiqueta="Ruta" valor={ruta} onCambio={setRuta} lista="lista-rutas" marcador="Identificador exacto" />
          <Campo etiqueta="Hora (HH:MM)" valor={hora} onCambio={setHora} marcador="08:00" />
          <button type="button" className="secundario" onClick={() => setHora(horaActual())}>Ahora</button>
        </Formulario>
        <Resultado estado={bus}>
          {(h) => h === null
            ? <p className="vacio">No hay más buses de esa ruta en esa estación hoy.</p>
            : <p className="grande">{h}</p>}
        </Resultado>
      </Tarjeta>

      <Tarjeta titulo="Planear viaje" requisito="R5">
        <Formulario boton="Planear" onEnviar={() => buscarPlan(origen, destino)} ocupado={plan.tipo === 'cargando'}>
          <Campo etiqueta="Origen" valor={origen} onCambio={setOrigen} lista="lista-estaciones" />
          <button type="button" className="secundario intercambiar" aria-label="Intercambiar origen y destino"
            title="Intercambiar origen y destino"
            onClick={() => { setOrigen(destino); setDestino(origen) }}>⇄</button>
          <Campo etiqueta="Destino" valor={destino} onCambio={setDestino} lista="lista-estaciones" />
        </Formulario>
        <Resultado estado={plan}>
          {(v) => v === null
            ? <p className="vacio">No hay viaje directo ni con un transbordo.</p>
            : (
              <>
                <p>
                  <strong>{v.tipo === 'DIRECTO' ? 'Directo' : 'Con transbordo'}</strong> · {v.saltos}{' '}
                  {v.saltos === 1 ? 'parada' : 'paradas'}
                </p>
                {v.tramos.length === 0 ? <p className="vacio">Ya estás en el destino.</p> : (
                  <ol className="tramos">
                    {v.tramos.map((t, i) => (
                      <li key={i}><span className="ruta">{t.ruta}</span> {t.sube} → {t.baja}</li>
                    ))}
                  </ol>
                )}
              </>
            )}
        </Resultado>
      </Tarjeta>

      <Tarjeta titulo="Ranking de estaciones" requisito="R6">
        <Formulario boton="Ver ranking" onEnviar={() => buscarRanking(Number(k))} ocupado={ranking.tipo === 'cargando'}>
          <Campo etiqueta="Cantidad (k)" valor={k} onCambio={setK} tipo="number" min={0} />
        </Formulario>
        <Resultado estado={ranking}>
          {(filas) => filas.length === 0 ? <p className="vacio">Sin resultados.</p> : (
            <table>
              <thead><tr><th scope="col">#</th><th scope="col">Estación</th><th scope="col">Buses</th></tr></thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr key={f.estacion}><td>{i + 1}</td><td>{f.estacion}</td><td className="num">{f.buses}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Resultado>
      </Tarjeta>
    </div>
  )
}
