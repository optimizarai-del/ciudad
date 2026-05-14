import { useEffect, useMemo, useState } from 'react'
import {
  Landmark, RefreshCw, Save, Calendar, TrendingUp, ExternalLink, Search,
  AlertCircle, CheckCircle2,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'


/**
 * Página de actualización mensual de tasas municipales.
 *
 * Flujo: el admin entra una vez al mes (típicamente el día 2 cuando
 * suben los valores nuevos), repasa la lista, carga los nuevos importes
 * y guarda en bulk. El valor vigente queda en cada propiedad y se cobra
 * automáticamente cuando se genera el pago del inquilino.
 */
export default function ActualizarTasas() {
  const [resumen, setResumen]   = useState(null)
  const [props, setProps]       = useState([])
  const [draft, setDraft]       = useState({})  // {propiedad_id: nuevoMonto}
  const [busqueda, setBusqueda] = useState('')
  const [loading, setLoading]   = useState(true)
  const [saving, setSaving]     = useState(false)
  const [msg, setMsg]           = useState(null)
  const [pctBulk, setPctBulk]   = useState('')

  const cargar = () => {
    setLoading(true)
    Promise.all([
      api.get('/api/tasas-mensuales/resumen'),
      api.get('/api/tasas-mensuales/lista'),
    ]).then(([r1, r2]) => {
      setResumen(r1.data)
      setProps(r2.data || [])
      setDraft({})  // reset al recargar
    }).finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [])

  const filtradas = useMemo(() => {
    if (!busqueda.trim()) return props
    const q = busqueda.toLowerCase()
    return props.filter(p =>
      (p.direccion || '').toLowerCase().includes(q)
      || (p.ciudad || '').toLowerCase().includes(q)
      || (p.propietario_nombre || '').toLowerCase().includes(q)
      || (p.numero_referencia || '').toLowerCase().includes(q)
    )
  }, [props, busqueda])

  const setDraftValue = (id, val) => {
    setDraft(prev => ({ ...prev, [id]: val }))
  }

  // Aplicar % de aumento a todas las propiedades visibles
  const aplicarPctBulk = () => {
    const pct = parseFloat(pctBulk)
    if (isNaN(pct)) return
    setDraft(prev => {
      const next = { ...prev }
      filtradas.forEach(p => {
        const base = p.tasa_municipal || 0
        if (base > 0) {
          next[p.id] = Math.round(base * (1 + pct / 100))
        }
      })
      return next
    })
  }

  const guardar = async () => {
    const items = Object.entries(draft)
      .map(([id, monto]) => ({
        propiedad_id: Number(id),
        monto: Number(monto) || 0,
      }))
      .filter(it => it.monto >= 0)
    if (items.length === 0) {
      setMsg({ kind: 'warn', text: 'No cargaste ningún cambio. Editá las tasas y volvé a tocar Guardar.' })
      return
    }
    setSaving(true); setMsg(null)
    try {
      const r = await api.post('/api/tasas-mensuales/aplicar', { items })
      setMsg({
        kind: 'success',
        text: `${r.data.actualizados} propiedades actualizadas en el período ${r.data.periodo}.`,
      })
      cargar()
    } catch (e) {
      setMsg({
        kind: 'error',
        text: e.response?.data?.detail || 'Error al guardar los cambios.',
      })
    } finally { setSaving(false) }
  }

  const fmt = v => v == null ? '—' : `$ ${Number(v).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`
  const fmtFecha = s => {
    if (!s) return 'Nunca'
    return new Date(s).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
  }

  // Solo cuentan los drafts que realmente difieren del valor actual de
  // la propiedad. Esto evita marcar como "cambio" un input que quedó con
  // el mismo número (ej. después de un undo manual).
  const cambiosCount = Object.entries(draft).filter(([id, val]) => {
    const prop = props.find(p => p.id === Number(id))
    const actual = prop?.tasa_municipal || 0
    return Number(val) !== actual
  }).length

  return (
    <Layout>
      <div className="max-w-7xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Operaciones mensuales</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3 flex items-center gap-3">
                <Landmark className="text-[#B8893A]" /> Tasas municipales.
              </h1>
              <p className="hero-sub">
                Actualización mensual. Cuando el inquilino paga, se le cobra el valor vigente acá.
              </p>
            </div>
            <a
              href="https://consultadeuda.santarosa.gob.ar/"
              target="_blank" rel="noreferrer"
              className="btn-secondary text-[12px]"
            >
              <ExternalLink size={12} /> Abrir portal MSR
            </a>
          </div>
        </header>

        {/* Stats */}
        {resumen && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <div className="card p-4">
              <p className="stat-label flex items-center gap-1.5"><Calendar size={11} /> Mes actual</p>
              <p className="stat-value text-lg mt-1">{resumen.mes_actual}</p>
            </div>
            <div className="card p-4">
              <p className="stat-label">Total propiedades</p>
              <p className="stat-value text-lg mt-1">{resumen.total_propiedades}</p>
            </div>
            <div className="card p-4 border-l-4 !border-l-success">
              <p className="stat-label">Actualizadas este mes</p>
              <p className="stat-value text-lg mt-1 text-success">
                {resumen.actualizadas_este_mes}
              </p>
            </div>
            <div className={`card p-4 border-l-4 ${resumen.pendientes > 0 ? '!border-l-warn' : '!border-l-success'}`}>
              <p className="stat-label">Pendientes</p>
              <p className={`stat-value text-lg mt-1 ${resumen.pendientes > 0 ? 'text-warn' : 'text-success'}`}>
                {resumen.pendientes}
              </p>
            </div>
          </div>
        )}

        {/* Acciones bulk */}
        <div className="card p-4 mb-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="text"
              className="input pl-8 !py-2 text-[13px]"
              placeholder="Buscar por dirección, propietario, padrón…"
              value={busqueda}
              onChange={e => setBusqueda(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-muted">Aumentar todas:</span>
            <input
              type="number"
              step="0.1"
              className="input !py-1.5 !w-20 text-[12px] text-center"
              placeholder="%"
              value={pctBulk}
              onChange={e => setPctBulk(e.target.value)}
            />
            <button
              className="btn-secondary text-[11px] py-1.5 px-3"
              onClick={aplicarPctBulk}
              disabled={!pctBulk}
            >
              <TrendingUp size={11} /> Aplicar
            </button>
          </div>

          {cambiosCount > 0 && (
            <span className="chip-warn">{cambiosCount} sin guardar</span>
          )}

          <button
            className="btn-primary"
            onClick={guardar}
            disabled={saving || cambiosCount === 0}
          >
            <Save size={13} className={saving ? 'animate-pulse' : ''} />
            {saving ? 'Guardando…' : `Guardar ${cambiosCount || ''} cambio${cambiosCount === 1 ? '' : 's'}`}
          </button>

          <button className="btn-ghost text-[12px] py-1.5" onClick={cargar} disabled={loading}>
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {msg && (
          <div className={`card p-3 mb-4 flex items-start gap-2 border-l-4
            ${msg.kind === 'success' ? '!border-l-success bg-success/5'
              : msg.kind === 'warn'   ? '!border-l-warn bg-warn/5'
              : '!border-l-danger bg-danger/5'}`}>
            {msg.kind === 'success'
              ? <CheckCircle2 size={14} className="text-success shrink-0 mt-0.5" />
              : <AlertCircle size={14} className="text-warn shrink-0 mt-0.5" />}
            <p className={`text-[12px] ${msg.kind === 'success' ? 'text-success' : msg.kind === 'warn' ? 'text-warn' : 'text-danger'}`}>
              {msg.text}
            </p>
          </div>
        )}

        {/* Tabla */}
        <div className="card overflow-hidden">
          {loading ? (
            <p className="text-center text-muted py-16 text-[13px]">Cargando…</p>
          ) : filtradas.length === 0 ? (
            <p className="text-center text-muted py-16 text-[13px]">No hay propiedades.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border dark:border-[#2A2A2A]">
                  <tr>
                    <th className="th">Propiedad</th>
                    <th className="th hidden md:table-cell">Padrón</th>
                    <th className="th text-right">Tasa actual</th>
                    <th className="th text-right w-44">Tasa nueva</th>
                    <th className="th text-center hidden lg:table-cell w-32">Diferencia</th>
                    <th className="th hidden md:table-cell w-32">Última act.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border dark:divide-[#2A2A2A]">
                  {filtradas.map(p => {
                    const actual = p.tasa_municipal || 0
                    // Mostramos el valor vigente directamente en el input
                    // para que se pueda editar incluso después de aplicar un
                    // % bulk y guardar. Antes el input quedaba vacío y obligaba
                    // a re-tipear el monto completo para hacer correcciones.
                    const valorInput = draft[p.id] !== undefined ? draft[p.id] : (actual || '')
                    const nuevo = draft[p.id] !== undefined ? Number(draft[p.id]) : null
                    const diff = nuevo !== null && actual > 0 ? ((nuevo - actual) / actual) * 100 : null
                    // Solo marca "cambio" si el draft difiere del valor vigente.
                    const cambio = draft[p.id] !== undefined && Number(draft[p.id]) !== actual
                    return (
                      <tr key={p.id} className={`hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition ${cambio ? 'bg-[#B8893A]/5' : ''}`}>
                        <td className="td">
                          <p className="font-medium text-[13px]">{p.direccion}</p>
                          <p className="text-[11px] text-muted dark:text-gray-500 capitalize">
                            {p.tipo}{p.ciudad ? ` · ${p.ciudad}` : ''}
                            {p.propietario_nombre && <> · {p.propietario_nombre}</>}
                          </p>
                        </td>
                        <td className="td hidden md:table-cell">
                          {p.numero_referencia ? (
                            <a
                              href="https://consultadeuda.santarosa.gob.ar/"
                              target="_blank" rel="noreferrer"
                              className="font-mono text-[11px] text-primary dark:text-white hover:underline"
                              title="Abrir portal de la municipalidad"
                            >
                              {p.numero_referencia}
                            </a>
                          ) : (
                            <span className="text-[11px] text-muted dark:text-gray-600">—</span>
                          )}
                        </td>
                        <td className="td text-right tabular-nums">{fmt(actual)}</td>
                        <td className="td text-right">
                          <input
                            type="number"
                            className={`input !py-1.5 !w-32 text-right tabular-nums text-[13px] ${cambio ? '!border-[#B8893A] !bg-[#B8893A]/5' : ''}`}
                            placeholder={String(Math.round(actual))}
                            value={valorInput}
                            onChange={e => setDraftValue(p.id, e.target.value)}
                          />
                        </td>
                        <td className="td text-center hidden lg:table-cell">
                          {diff !== null ? (
                            <span className={`chip-${diff > 0 ? 'warn' : diff < 0 ? 'gray' : 'muted'}`}>
                              {diff > 0 ? '+' : ''}{diff.toFixed(1)} %
                            </span>
                          ) : (
                            <span className="text-[11px] text-muted">—</span>
                          )}
                        </td>
                        <td className="td hidden md:table-cell text-[11px] text-muted dark:text-gray-500">
                          {fmtFecha(p.tasa_consultada_at)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <p className="text-[11px] text-muted dark:text-gray-500 mt-4 text-center">
          💡 Los pagos generados después de guardar incluirán automáticamente la tasa actualizada.
        </p>
      </div>
    </Layout>
  )
}
