import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Campo, Formulario, ListaEstaciones, Resultado, Tarjeta } from '../comunes'
import { usePeticion } from '../usePeticion'

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
  const [estacion, setEstacion] = useState('')
  const [mensaje, setMensaje] = useState<{ texto: string; bien: boolean } | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const verRecorrido = (r: string, inverso: boolean) => {
    ultimo.current = [r, inverso]
    consultarRecorrido(() => api.recorrido(r, inverso))
  }

  useEffect(() => {
    if (version > 0 && ultimo.current) verRecorrido(...ultimo.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version])

  // Ejecuta una mutación. Solo si hubo cambio efectivo se refrescan las vistas.
  const mutar = async (descripcion: string, tarea: () => Promise<boolean>) => {
    setOcupado(true)
    try {
      const cambio = await tarea()
      setMensaje(cambio
        ? { texto: `${descripcion}: hecho.`, bien: true }
        : { texto: `${descripcion}: no se aplicó (la operación no era válida en el estado actual).`, bien: false })
      if (cambio) alCambiar()
    } catch (error) {
      setMensaje({ texto: `${descripcion}: ${(error as Error).message}`, bien: false })
    } finally {
      setOcupado(false)
    }
  }

  return (
    <>
    <p className={`barra-estado ${mensaje ? (mensaje.bien ? 'bien' : 'advertencia') : ''}`} role="status">
      {mensaje ? mensaje.texto : 'Las mutaciones efectivas actualizan automáticamente las consultas abiertas en las demás pestañas.'}
    </p>
    <div className="rejilla">
      <Tarjeta titulo="Recorrido de una ruta" requisito="R7">
        <Formulario boton="Ver recorrido" onEnviar={() => verRecorrido(ruta, alReves)} ocupado={recorrido.tipo === 'cargando'}>
          <Campo etiqueta="Ruta" valor={ruta} onCambio={setRuta} />
          <label className="casilla">
            <input type="checkbox" checked={alReves} onChange={(e) => setAlReves(e.target.checked)} />
            Sentido inverso
          </label>
        </Formulario>
        <Resultado estado={recorrido}>{(lista) => <ListaEstaciones estaciones={lista} />}</Resultado>
      </Tarjeta>

      <Tarjeta titulo="Editar paradas" requisito="R7">
        <Campo etiqueta="Ruta" valor={rutaEdicion} onCambio={setRutaEdicion} />
        <Formulario boton="Agregar parada" ocupado={ocupado}
          onEnviar={() => mutar(`Agregar ${nueva} después de ${despuesDe}`, () => api.agregarParada(rutaEdicion, nueva, despuesDe))}>
          <Campo etiqueta="Nueva estación" valor={nueva} onCambio={setNueva} />
          <Campo etiqueta="Después de" valor={despuesDe} onCambio={setDespuesDe} />
        </Formulario>
        <Formulario boton="Quitar parada" ocupado={ocupado}
          onEnviar={() => mutar(`Quitar ${quitar}`, () => api.quitarParada(rutaEdicion, quitar))}>
          <Campo etiqueta="Estación a quitar" valor={quitar} onCambio={setQuitar} />
        </Formulario>
      </Tarjeta>

      <Tarjeta titulo="Cerrar y reabrir" requisito="R8">
        <div className="formulario">
          <Campo etiqueta="Estación" valor={estacion} onCambio={setEstacion} />
          <div className="botones">
            <button type="button" disabled={ocupado || !estacion.trim()}
              onClick={() => mutar(`Cerrar ${estacion}`, () => api.cerrar(estacion))}>Cerrar</button>
            <button type="button" disabled={ocupado || !estacion.trim()}
              onClick={() => mutar(`Reabrir ${estacion}`, () => api.reabrir(estacion))}>Reabrir</button>
          </div>
        </div>
      </Tarjeta>

      <Tarjeta titulo="Historial" requisito="R9">
        <div className="botones">
          <button type="button" disabled={ocupado} onClick={() => mutar('Deshacer', api.deshacer)}>↶ Deshacer</button>
          <button type="button" disabled={ocupado} onClick={() => mutar('Rehacer', api.rehacer)}>↷ Rehacer</button>
        </div>
      </Tarjeta>
    </div>
    </>
  )
}
