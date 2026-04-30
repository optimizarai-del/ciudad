import { useEffect, useState } from 'react'
import { Calculator, Search, ArrowRight, RefreshCw, Info } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

export default function Calculadora() {
  const [propiedades, setProp] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [propId, setPropId] = useState('')
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10))
  const [resultado, setResultado] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/api/propiedades').then(r => setProp(r.data.filter(p => p.modalidad !== 'venta')))
  }, [])

  const sugerencias = propiedades.filter(p =>
    busqueda.length > 1 &&
    p.direccion.toLowerCase().includes(busqueda.toLowerCase())
  ).slice(0, 5)

  const calcular = async () => {
    if (!busqueda && !propId) { setErr('Ingresá una dirección o seleccioná una propiedad.'); return }
    setLoading(true); setErr(''); setResultado(null)
    try {
      const r = await api.post('/api/calculadora', {
        direccion: busqueda || null,
        propiedad_id: propId ? Number(propId) : null,
        fecha,
      })
      setResultado(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'No se encontró la propiedad.')
    } finally { setLoading(false) }
  }

  const pct = val => val !== undefined ? `${(val * 100 - 100).toFixed(2)}%` : '—'

  return (
    <Layout>
      <div className="max-w-3xl mx-auto animate-fade-in">

        <header className="mb-10">
          <div className="hero-eyebrow">Herramientas</div>
          <h1 className="hero-title text-5xl md:text-6xl mb-3">Calculadora.</h1>
          <p className="hero-sub">
            Escribí la dirección y obtenés el costo total actualizado al instante.
          </p>
        </header>

        {/* Formulario */}
        <div className="card p-8 mb-6">
          <div className="space-y-5">

            {/* Búsqueda por dirección */}
            <div className="relative">
              <label className="label">Dirección del inmueble</label>
              <div className="relative">
                <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
                <input
                  className="input pl-10"
                  placeholder="Av. Corrientes 1234…"
                  value={busqueda}
                  onChange={e => { setBusqueda(e.target.value); setPropId('') }}
                />
              </div>
              {sugerencias.length > 0 && (
                <div className="absolute z-20 w-full mt-1 card shadow-card overflow-hidden">
                  {sugerencias.map(p => (
                    <button key={p.id}
                      onClick={() => { setBusqueda(p.direccion); setPropId(p.id); }}
                      className="w-full text-left px-4 py-3 text-[13px] hover:bg-neutral-50 border-b border-border last:border-0 transition">
                      <span className="font-medium">{p.direccion}</span>
                      <span className="text-muted ml-2">{p.ciudad} · {p.tipo}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 text-[12px] text-muted">
              <div className="h-px flex-1 bg-border" />
              <span>o seleccioná directamente</span>
              <div className="h-px flex-1 bg-border" />
            </div>

            <div>
              <label className="label">Propiedad de la lista</label>
              <select className="input" value={propId} onChange={e => { setPropId(e.target.value); setBusqueda('') }}>
                <option value="">Seleccionar…</option>
                {propiedades.map(p => (
                  <option key={p.id} value={p.id}>{p.direccion} — {p.ciudad}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Fecha de cálculo</label>
              <input className="input" type="date" value={fecha} onChange={e => setFecha(e.target.value)} />
            </div>

            {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2.5 rounded-xl">{err}</p>}

            <button className="btn-primary btn-lg w-full" onClick={calcular} disabled={loading}>
              {loading
                ? <><RefreshCw size={15} className="animate-spin" /> Calculando…</>
                : <><Calculator size={15} /> Calcular costos</>
              }
            </button>
          </div>
        </div>

        {/* Resultado */}
        {resultado && (
          <div className="animate-scale-in space-y-4">

            {/* Cabecera propiedad */}
            <div className="card p-6">
              <p className="hero-eyebrow !mb-2">Resultado para</p>
              <h2 className="font-bold text-xl tracking-tight">{resultado.propiedad.direccion}</h2>
              <p className="text-[12px] text-muted capitalize">{resultado.propiedad.tipo} · código {resultado.propiedad.codigo || resultado.propiedad.id}</p>
            </div>

            {/* Big total */}
            <div className="card p-8 flex items-center justify-between">
              <div>
                <p className="stat-label mb-2">Total mensual estimado</p>
                <p className="hero-title text-5xl text-primary">
                  ${resultado.total_mensual?.toLocaleString('es-AR')}
                </p>
              </div>
              {resultado.factor_ajuste > 1 && (
                <div className="text-right">
                  <span className="chip-success text-base px-4 py-2">
                    +{pct(resultado.factor_ajuste)} acum.
                  </span>
                </div>
              )}
            </div>

            {/* Desglose */}
            <div className="card p-6">
              <p className="text-[11px] uppercase tracking-[0.14em] text-muted font-semibold mb-4">Desglose</p>
              <div className="space-y-3">
                <DesgloseFila
                  label="Alquiler base"
                  value={resultado.base_alquiler}
                  sub={`× ${resultado.factor_ajuste} ajuste (${resultado.detalle.indice?.toUpperCase()})`}
                />
                <DesgloseFila
                  label="Alquiler actualizado"
                  value={resultado.alquiler_actualizado}
                  highlight
                />
                {resultado.expensas > 0 && <DesgloseFila label="Expensas" value={resultado.expensas} />}
                {resultado.impuesto_inmobiliario > 0 && <DesgloseFila label="Impuesto inmobiliario" value={resultado.impuesto_inmobiliario} />}
                {resultado.tasa_municipal > 0 && <DesgloseFila label="Tasa municipal" value={resultado.tasa_municipal} />}
                <div className="border-t border-border pt-3 flex justify-between items-baseline">
                  <span className="font-semibold text-[14px]">Total</span>
                  <span className="font-bold text-xl tracking-tight">${resultado.total_mensual?.toLocaleString('es-AR')}</span>
                </div>
              </div>
            </div>

            {/* Contrato info */}
            {resultado.contrato && (
              <div className="card p-5 flex items-start gap-3">
                <Info size={15} className="text-muted shrink-0 mt-0.5" />
                <div className="text-[13px] text-muted">
                  <span className="font-medium text-primary">Contrato {resultado.contrato.codigo || `#${resultado.contrato.id}`}</span>
                  {' '}— ajuste {resultado.contrato.indice?.toUpperCase()} cada {resultado.contrato.periodicidad_meses} meses
                  {resultado.detalle.periodos_aplicados > 0 && ` · ${resultado.detalle.periodos_aplicados} períodos aplicados`}.
                  <p className="mt-1 text-[11px] opacity-70">{resultado.detalle.nota}</p>
                </div>
              </div>
            )}

          </div>
        )}

        {/* Info extra vacío */}
        {!resultado && !loading && (
          <div className="card p-8 text-center">
            <Calculator size={36} className="mx-auto text-muted/20 mb-4" />
            <p className="text-[15px] text-muted font-light">
              El resultado aparece acá al instante.<br />
              Todos los inmuebles con contrato activo incluyen el ajuste automático.
            </p>
          </div>
        )}

      </div>
    </Layout>
  )
}

function DesgloseFila({ label, value, sub, highlight }) {
  return (
    <div className={`flex items-start justify-between gap-2 ${highlight ? 'text-primary font-medium' : 'text-muted'}`}>
      <div>
        <span className="text-[13px]">{label}</span>
        {sub && <p className="text-[11px] text-muted/70 mt-0.5">{sub}</p>}
      </div>
      <span className="text-[13px] shrink-0">${value?.toLocaleString('es-AR')}</span>
    </div>
  )
}
