import { useEffect, useState } from 'react'
import { api, ErrorApi, type Rendimiento as DatosRendimiento, type SerieRendimiento } from '../api'
import { Tarjeta } from '../comunes'
import { usePeticion } from '../usePeticion'

const COMANDO = 'python -m scripts.benchmark --salida scripts/resultados/rendimiento.json'

function formatoNs(ns: number) {
  if (ns >= 1e6) return `${(ns / 1e6).toFixed(2)} ms`
  if (ns >= 1e3) return `${(ns / 1e3).toFixed(2)} µs`
  return `${ns.toFixed(0)} ns`
}

/** Gráfico SVG de mediana (ns/llamada) contra n. Sin librerías externas. */
function Grafico({ serie }: { serie: SerieRendimiento }) {
  const puntos = serie.puntos
  if (puntos.length === 0) return <p className="vacio">La serie no tiene puntos.</p>
  const ancho = 560, alto = 260, margen = { izq: 70, der: 20, sup: 16, inf: 40 }
  let maxN = 0, maxY = 0
  for (const p of puntos) { if (p.n > maxN) maxN = p.n; if (p.mediana_ns > maxY) maxY = p.mediana_ns }
  maxY = maxY * 1.1 || 1
  const x = (n: number) => margen.izq + (n / (maxN || 1)) * (ancho - margen.izq - margen.der)
  const y = (v: number) => alto - margen.inf - (v / maxY) * (alto - margen.sup - margen.inf)
  const marcasY = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxY)
  const camino = puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.n).toFixed(1)},${y(p.mediana_ns).toFixed(1)}`).join(' ')

  return (
    <svg viewBox={`0 0 ${ancho} ${alto}`} className="grafico" role="img"
      aria-label={`Mediana por llamada de ${serie.operacion} según n`}>
      {marcasY.map((v) => (
        <g key={v}>
          <line x1={margen.izq} x2={ancho - margen.der} y1={y(v)} y2={y(v)} className="guia" />
          <text x={margen.izq - 8} y={y(v) + 4} textAnchor="end">{formatoNs(v)}</text>
        </g>
      ))}
      {puntos.map((p) => (
        <text key={`n-${p.n}`} x={x(p.n)} y={alto - margen.inf + 18} textAnchor="middle">{p.n}</text>
      ))}
      <text x={(ancho + margen.izq) / 2} y={alto - 4} textAnchor="middle" className="eje">n</text>
      <path d={camino} className="linea" />
      {puntos.map((p) => (
        <circle key={`p-${p.n}`} cx={x(p.n)} cy={y(p.mediana_ns)} r={4} className="punto">
          <title>{`n=${p.n}: ${formatoNs(p.mediana_ns)}`}</title>
        </circle>
      ))}
    </svg>
  )
}

/** R11: panel de mediciones guardadas por scripts/benchmark.py. */
export function Rendimiento() {
  const [estado, cargar] = usePeticion<DatosRendimiento | null>()
  const [seleccion, setSeleccion] = useState(0)

  const recargar = () => cargar(async () => {
    try {
      return await api.rendimiento()
    } catch (error) {
      if (error instanceof ErrorApi && error.estado === 404) return null
      throw error
    }
  })

  useEffect(() => { recargar() // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="rejilla una">
      <Tarjeta titulo="Rendimiento medido" requisito="R11">
        <div className="botones">
          <button type="button" onClick={recargar} disabled={estado.tipo === 'cargando'}>Recargar resultados</button>
        </div>
        {estado.tipo === 'cargando' && <p className="aviso" role="status">Cargando resultados…</p>}
        {estado.tipo === 'error' && <p className="error" role="alert">{estado.mensaje}</p>}
        {estado.tipo === 'ok' && estado.datos === null && (
          <div className="aviso">
            <p>Todavía no hay una corrida de medición. Ejecútala desde la raíz del proyecto y luego pulsa «Recargar resultados»:</p>
            <pre>{COMANDO}</pre>
          </div>
        )}
        {estado.tipo === 'ok' && estado.datos !== null && (() => {
          const datos = estado.datos
          const serie = datos.series[Math.min(seleccion, datos.series.length - 1)]
          if (!serie) return <p className="vacio">El archivo no contiene series.</p>
          return (
            <>
              <label className="campo">
                <span>Operación</span>
                <select value={seleccion} onChange={(e) => setSeleccion(Number(e.target.value))}>
                  {datos.series.map((s, i) => <option key={s.operacion} value={i}>{s.operacion}</option>)}
                </select>
              </label>
              <dl className="ficha">
                <div><dt>Complejidad esperada</dt><dd>{serie.complejidad}</dd></div>
                <div><dt>Significado de n</dt><dd>{serie.variable}</dd></div>
              </dl>
              {serie.error ? <p className="error" role="alert">No se pudo medir: {serie.error}</p> : (
                <>
                  <Grafico serie={serie} />
                  <table>
                    <caption>Mediana por llamada y razón respecto al tamaño anterior</caption>
                    <thead>
                      <tr><th scope="col">n</th><th scope="col">Mediana</th><th scope="col">Razón</th><th scope="col">Dimensiones</th></tr>
                    </thead>
                    <tbody>
                      {serie.puntos.map((p) => (
                        <tr key={p.n}>
                          <td className="num">{p.n}</td>
                          <td className="num">{formatoNs(p.mediana_ns)}</td>
                          <td className="num">{p.razon_anterior === null ? '—' : `${p.razon_anterior.toFixed(2)}×`}</td>
                          <td>{Object.entries(p.dimensiones).map(([k, v]) => `${k}=${v}`).join(', ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
              <h3>Análisis</h3>
              <p>{serie.analisis || 'Sin análisis.'}</p>
              <p className="nota">
                {Object.entries(datos.configuracion).map(([k, v]) => `${k}: ${v}`).join(' · ')}
              </p>
            </>
          )
        })()}
      </Tarjeta>
    </div>
  )
}
