import { useEffect, useRef, useState } from 'react'
import { api, type Estado } from '../api'
import { Campo, Formulario, ListaEstaciones, Resultado, Tarjeta } from '../comunes'
import { usePeticion } from '../usePeticion'

/** R1–R3: consulta exacta, autocompletar por prefijo y rango alfabético. */
export function Estaciones({ version }: { version: number }) {
  const [nombre, setNombre] = useState('')
  const [estado, consultarEstado] = usePeticion<{ nombre: string; estado: Estado }>()
  const ultimoNombre = useRef<string | null>(null)

  const [prefijo, setPrefijo] = useState('')
  const [k, setK] = useState('10')
  const [sugerencias, setSugerencias] = useState<string[]>([])
  const [errorPrefijo, setErrorPrefijo] = useState<string | null>(null)

  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [rango, consultarRango] = usePeticion<string[]>()
  const ultimoRango = useRef<[string, string] | null>(null)

  const buscarEstado = (valor: string) => {
    ultimoNombre.current = valor
    consultarEstado(async () => ({ nombre: valor, estado: await api.estado(valor) }))
  }
  const buscarRango = (a: string, b: string) => {
    ultimoRango.current = [a, b]
    consultarRango(() => api.rango(a, b))
  }

  // Autocompletado mientras se escribe: cancela la petición anterior para
  // que una respuesta vieja no reemplace a una nueva.
  useEffect(() => {
    const cantidad = Number(k)
    if (!Number.isInteger(cantidad)) return
    const control = new AbortController()
    const espera = setTimeout(() => {
      api.autocompletar(prefijo, cantidad, control.signal)
        .then((lista) => { setSugerencias(lista); setErrorPrefijo(null) })
        .catch((error: Error) => { if (error.name !== 'AbortError') setErrorPrefijo(error.message) })
    }, 150)
    return () => { clearTimeout(espera); control.abort() }
  }, [prefijo, k, version])

  // Tras una mutación efectiva se repiten las últimas consultas.
  useEffect(() => {
    if (version === 0) return
    if (ultimoNombre.current !== null) buscarEstado(ultimoNombre.current)
    if (ultimoRango.current !== null) buscarRango(...ultimoRango.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version])

  return (
    <div className="rejilla">
      <Tarjeta titulo="Consulta exacta" requisito="R1">
        <Formulario boton="Consultar" onEnviar={() => buscarEstado(nombre)} ocupado={estado.tipo === 'cargando'}>
          <Campo etiqueta="Estación" valor={nombre} onCambio={setNombre} lista="sugerencias-estaciones" />
        </Formulario>
        <Resultado estado={estado}>
          {({ nombre: consultado, estado: e }) => (
            <p>
              <strong>{consultado.trim().toUpperCase()}</strong>:{' '}
              {!e.existe ? <span className="mal">no existe</span>
                : e.abierta ? <span className="bien">abierta</span>
                  : <span className="advertencia">cerrada</span>}
            </p>
          )}
        </Resultado>
      </Tarjeta>

      <Tarjeta titulo="Autocompletar" requisito="R2">
        <div className="formulario">
          <Campo etiqueta="Prefijo" valor={prefijo} onCambio={setPrefijo} requerido={false} marcador="Ej. POR" />
          <Campo etiqueta="Máximo (k)" valor={k} onCambio={setK} tipo="number" min={0} />
        </div>
        {errorPrefijo ? <p className="error" role="alert">{errorPrefijo}</p> : <ListaEstaciones estaciones={sugerencias} />}
        <datalist id="sugerencias-estaciones">
          {sugerencias.map((s) => <option key={s} value={s} />)}
        </datalist>
      </Tarjeta>

      <Tarjeta titulo="Rango alfabético" requisito="R3">
        <Formulario boton="Buscar rango" onEnviar={() => buscarRango(desde, hasta)} ocupado={rango.tipo === 'cargando'}>
          <Campo etiqueta="Desde" valor={desde} onCambio={setDesde} lista="lista-estaciones" />
          <Campo etiqueta="Hasta" valor={hasta} onCambio={setHasta} lista="lista-estaciones" />
        </Formulario>
        <Resultado estado={rango}>{(lista) => <ListaEstaciones estaciones={lista} />}</Resultado>
      </Tarjeta>
    </div>
  )
}
