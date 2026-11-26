import { useState } from 'react'
import { api, type ResultadoFila } from '../api'
import { Campo, Formulario, Resultado, Tarjeta } from '../comunes'
import { usePeticion } from '../usePeticion'

const POR_PAGINA = 20
const MAX_BARRAS = 120

function leerLlegadas(texto: string): number[] {
  const partes = texto.split(/[\s,;]+/).filter((p) => p !== '')
  return partes.map((p) => {
    if (!/^-?\d+$/.test(p)) throw new Error(`"${p}" no es un minuto entero`)
    return Number(p)
  })
}

/** Barras SVG con la espera de cada persona, en orden de llegada. */
function GraficoEsperas({ esperas }: { esperas: number[] }) {
  const datos = esperas.slice(0, MAX_BARRAS)
  if (datos.length === 0) return null
  let maximo = 0
  for (const e of datos) if (e > maximo) maximo = e
  const escala = maximo === 0 ? 1 : maximo
  const ancho = 560, alto = 200
  const margen = { izq: 40, der: 10, sup: 10, inf: 28 }
  const paso = (ancho - margen.izq - margen.der) / datos.length
  const grosor = Math.max(1, paso - 2)
  const alturaUtil = alto - margen.sup - margen.inf
  const y = (v: number) => alto - margen.inf - (v / escala) * alturaUtil

  return (
    <div>
      <svg viewBox={`0 0 ${ancho} ${alto}`} className="grafico" role="img"
        aria-label="Espera de cada persona en orden de llegada">
        <line x1={margen.izq} x2={ancho - margen.der} y1={y(0)} y2={y(0)} className="guia" />
        <line x1={margen.izq} x2={ancho - margen.der} y1={y(maximo)} y2={y(maximo)} className="guia" />
        <text x={margen.izq - 6} y={y(0) + 4} textAnchor="end">0</text>
        <text x={margen.izq - 6} y={y(maximo) + 4} textAnchor="end">{maximo}</text>
        {datos.map((espera, i) => (
          <rect key={i} x={margen.izq + i * paso + 1} y={y(espera)} width={grosor}
            height={Math.max(0, y(0) - y(espera))} className="barra">
            <title>{`Persona ${i}: espera ${espera} min`}</title>
          </rect>
        ))}
        <text x={(ancho + margen.izq) / 2} y={alto - 6} textAnchor="middle" className="eje">
          Persona (orden de llegada) · espera en minutos
        </text>
      </svg>
      {esperas.length > MAX_BARRAS && (
        <p className="nota">Se muestran las primeras {MAX_BARRAS} de {esperas.length} personas.</p>
      )}
    </div>
  )
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
                <GraficoEsperas esperas={datos.esperas} />
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
