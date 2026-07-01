import { useEffect, useState } from 'react'
import {
  Users, ClipboardList, Building2, CheckCircle2, DollarSign, Gauge,
  Flame, Thermometer, Snowflake, AlertTriangle, CalendarX, ShieldAlert,
  Download, FileText
} from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ORO = '#B8893A'
const fmtUSD = (n) => 'USD ' + (n || 0).toLocaleString('es-AR')

const TEMP_META = {
  caliente: { label: 'Caliente', icon: Flame, tint: 'text-red-600 dark:text-red-400', bar: 'bg-red-500' },
  tibio: { label: 'Tibio', icon: Thermometer, tint: 'text-amber-600 dark:text-amber-400', bar: 'bg-amber-500' },
  frio: { label: 'Frío', icon: Snowflake, tint: 'text-blue-500 dark:text-blue-400', bar: 'bg-blue-400' },
}

export default function DashboardCRM() {
  const [d, setD] = useState(null)
  const [m, setM] = useState(null)
  const [bajando, setBajando] = useState('')

  useEffect(() => {
    api.get('/api/ventas-crm/dashboard').then((r) => setD(r.data))
    api.get('/api/ventas-crm/pipeline/metricas').then((r) => setM(r.data)).catch(() => {})
  }, [])

  const descargar = async (fmt) => {
    setBajando(fmt)
    try {
      const r = await api.get(`/api/ventas-crm/pipeline/export.${fmt}`, { responseType: 'blob' })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `pipeline_${new Date().toISOString().slice(0, 10)}.${fmt}`
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error(e)
    } finally {
      setBajando('')
    }
  }

  if (!d) return <Layout><div className="max-w-6xl mx-auto py-20 text-center text-muted">Cargando…</div></Layout>

  const cards = [
    { icon: Users, label: 'Clientes', value: d.total_clientes, sub: `${d.clientes_operados} operados` },
    { icon: ClipboardList, label: 'Pedidos activos', value: d.total_pedidos },
    { icon: Building2, label: 'Propiedades disponibles', value: d.propiedades_disponibles },
    { icon: CheckCircle2, label: 'Operaciones cerradas', value: d.operaciones_cerradas },
    { icon: DollarSign, label: 'Monto cerrado', value: fmtUSD(d.monto_cerrado_usd) },
    { icon: DollarSign, label: 'Comisiones', value: fmtUSD(d.comisiones_usd) },
  ]

  const embudoMax = m ? Math.max(1, ...m.embudo.map((e) => e.alcanzaron)) : 1
  const tempTotal = m ? (m.temperatura.caliente + m.temperatura.tibio + m.temperatura.frio) || 1 : 1
  const riesgos = m ? [
    { icon: CalendarX, label: 'Sin próxima acción', value: m.riesgo.sin_proxima_accion, tint: 'text-amber-600 dark:text-amber-400' },
    { icon: AlertTriangle, label: 'Acción vencida', value: m.riesgo.proxima_accion_vencida, tint: 'text-orange-600 dark:text-orange-400' },
    { icon: ShieldAlert, label: 'SLA vencido', value: m.riesgo.sla_vencido, tint: 'text-red-600 dark:text-red-400' },
  ] : []

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="hero-eyebrow">CRM Comercial</div>
            <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Dashboard Ventas</h1>
            <p className="hero-sub">{d.es_admin ? 'Vista de todo el equipo.' : 'Tu actividad comercial.'}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => descargar('csv')} disabled={bajando}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-neutral-200 dark:border-neutral-800 text-sm font-medium hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition disabled:opacity-50">
              <Download size={15} /> {bajando === 'csv' ? 'Generando…' : 'CSV'}
            </button>
            <button onClick={() => descargar('pdf')} disabled={bajando}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-neutral-200 dark:border-neutral-800 text-sm font-medium hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition disabled:opacity-50">
              <FileText size={15} /> {bajando === 'pdf' ? 'Generando…' : 'PDF'}
            </button>
          </div>
        </header>

        {/* Valor del pipeline — signature del dashboard */}
        {m && (
          <div className="grid sm:grid-cols-2 gap-3 sm:gap-4 mb-4">
            <div className="card p-5 sm:p-6 relative overflow-hidden">
              <div className="absolute right-0 top-0 h-full w-1" style={{ background: ORO }} />
              <div className="flex items-center gap-2 mb-1">
                <Gauge size={16} style={{ color: ORO }} />
                <p className="stat-label">Valor del pipeline</p>
              </div>
              <p className="stat-value text-3xl sm:text-4xl">{fmtUSD(m.valor_pipeline_usd)}</p>
              <p className="text-[11px] text-muted mt-1">{m.activos} clientes activos en juego</p>
            </div>
            <div className="card p-5 sm:p-6">
              <p className="stat-label mb-1">Valor ponderado</p>
              <p className="stat-value text-3xl sm:text-4xl" style={{ color: ORO }}>{fmtUSD(m.valor_ponderado_usd)}</p>
              <p className="text-[11px] text-muted mt-1">Esperado según probabilidad de cierre por etapa</p>
            </div>
          </div>
        )}

        {/* KPIs operativos */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-4">
          {cards.map((c, i) => (
            <div key={i} className="card p-4 sm:p-5">
              <c.icon size={18} className="mb-2" style={{ color: ORO }} />
              <p className="stat-label">{c.label}</p>
              <p className="stat-value text-2xl sm:text-3xl mt-1">{c.value}</p>
              {c.sub && <p className="text-[11px] text-muted mt-0.5">{c.sub}</p>}
            </div>
          ))}
        </div>

        {m && (
          <div className="grid lg:grid-cols-5 gap-3 sm:gap-4 mb-4">
            {/* Embudo por etapa */}
            <div className="card p-5 sm:p-6 lg:col-span-3">
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-4">
                Embudo del pipeline
              </p>
              <div className="space-y-2">
                {m.embudo.map((e) => (
                  <div key={e.etapa} className="flex items-center gap-3">
                    <span className="w-40 text-[12px] text-muted shrink-0 truncate">{e.label}</span>
                    <div className="flex-1 h-6 rounded-lg bg-neutral-100 dark:bg-[#1A1A1A] overflow-hidden">
                      <div className="h-full rounded-lg transition-all"
                        style={{ width: `${Math.max(e.alcanzaron ? 6 : 0, (100 * e.alcanzaron) / embudoMax)}%`, background: ORO }} />
                    </div>
                    <span className="w-8 text-right stat-value text-sm">{e.alcanzaron}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Termómetro */}
            <div className="card p-5 sm:p-6 lg:col-span-2">
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-4">
                Temperatura de la cartera
              </p>
              <div className="flex h-3 rounded-full overflow-hidden mb-5">
                {['caliente', 'tibio', 'frio'].map((k) => (
                  <div key={k} className={TEMP_META[k].bar}
                    style={{ width: `${(100 * m.temperatura[k]) / tempTotal}%` }} />
                ))}
              </div>
              <div className="space-y-3">
                {['caliente', 'tibio', 'frio'].map((k) => {
                  const T = TEMP_META[k]
                  return (
                    <div key={k} className="flex items-center gap-2">
                      <T.icon size={16} className={T.tint} />
                      <span className="text-sm flex-1">{T.label}</span>
                      <span className="stat-value text-lg">{m.temperatura[k]}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {/* Riesgo — dónde se está enfriando la cartera */}
        {m && (
          <div className="grid grid-cols-3 gap-3 sm:gap-4">
            {riesgos.map((r, i) => (
              <div key={i} className="card p-4 sm:p-5">
                <r.icon size={18} className={`mb-2 ${r.tint}`} />
                <p className="stat-value text-2xl sm:text-3xl">{r.value}</p>
                <p className="text-[11px] text-muted mt-0.5">{r.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
