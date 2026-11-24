import { useState } from 'react'
import { api, type ResultadoFila } from '../api'
import { Campo, Formulario, Resultado, Tarjeta } from '../comunes'
import { usePeticion } from '../usePeticion'

const POR_PAGINA = 20

function leerLlegadas(texto: string): number[] {
  const partes = texto.split(/[\s,;]+/).filter((p) => p !== '')
  return partes.map((p) => {
    if (!/^-?\d+$/.test(p)) throw new Error(`"${p}" no es un minuto entero`)
    return Number(p)
  })
}

/** R10: simulación de la fila de abordaje. El cálculo lo hace el motor. */
export function Fila() {
  const [llegadas, setLlegadas] = useState('0, 1, 5, 5')
  const [frecuencia, setFrecuencia] = useState('5')
  const [capacidad, setCapacidad] = useState('2')
  const [resultado, simular] = usePeticion<{ llegadas: number[]; datos: ResultadoFila }>()
  const [pagina, setPagina] = useState(0)

  const enviar = () => {
    setPagina(0)
    simular(async () => {
      const lista = leerLlegadas(llegadas)
      return { llegadas: lista, datos: await api.simularFila(lista, Number(frecuencia), Number(capacidad)) }
    })
  }

  return (
    <div className="rejilla">
      <Tarjeta titulo="Simular fila de abordaje" requisito="R10">
        <Formulario boton="Simular" onEnviar={enviar} ocupado={resultado.tipo === 'cargando'}>
          <label className="campo ancho">
            <span>Llegadas (minutos, en orden, separadas por coma o espacio)</span>
            <textarea value={llegadas} onChange={(e) => setLlegadas(e.target.value)} rows={3} />
          </label>
          <Campo etiqueta="Frecuencia (min)" valor={frecuencia} onCambio={setFrecuencia} tipo="number" min={1} />
          <Campo etiqueta="Capacidad por bus" valor={capacidad} onCambio={setCapacidad} tipo="number" min={1} />
        </Formulario>
        <p className="nota">Sale un bus en el minuto 0 y en cada múltiplo de la frecuencia. Quien llega justo a la salida alcanza a subir.</p>
      </Tarjeta>

      <Tarjeta titulo="Resultado" requisito="R10">
        <Resultado estado={resultado}>
          {({ llegadas: lista, datos }) => {
            const paginas = Math.max(1, Math.ceil(datos.esperas.length / POR_PAGINA))
            const inicio = pagina * POR_PAGINA
            return (
              <>
                <dl className="metricas">
                  <div><dt>Personas</dt><dd>{datos.esperas.length}</dd></div>
                  <div><dt>Espera total</dt><dd>{datos.espera_total} min</dd></div>
                  <div><dt>Promedio</dt><dd>{datos.espera_promedio.toFixed(2)} min</dd></div>
                  <div><dt>Máxima</dt><dd>{datos.espera_maxima} min</dd></div>
                </dl>
                {datos.esperas.length > 0 && (
                  <>
                    <table>
                      <thead>
                        <tr><th scope="col">#</th><th scope="col">Llegada</th><th scope="col">Sube</th><th scope="col">Espera</th></tr>
                      </thead>
                      <tbody>
                        {datos.esperas.slice(inicio, inicio + POR_PAGINA).map((espera, i) => {
                          const indice = inicio + i
                          return (
                            <tr key={indice}>
                              <td>{indice}</td>
                              <td className="num">{lista[indice]}</td>
                              <td className="num">{lista[indice] + espera}</td>
                              <td className="num">{espera}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    {paginas > 1 && (
                      <div className="paginacion">
                        <button type="button" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>Anterior</button>
                        <span>Página {pagina + 1} de {paginas}</span>
                        <button type="button" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
                      </div>
                    )}
                  </>
                )}
              </>
            )
          }}
        </Resultado>
      </Tarjeta>
    </div>
  )
}
