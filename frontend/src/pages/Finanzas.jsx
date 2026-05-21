import { useEffect, useMemo, useState } from 'react'
import { TrendingUp, AlertTriangle, Clock, DollarSign, BarChart3 } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const fmtK = n => `$${Math.round((Number(n) || 0) / 1000).toLocaleString('es-AR')}K`
const fmt$ = n => `$${(Number(n) || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`

export default function Finanzas() {
  const [historico, setHistorico] = useState([])
  const [mora, setMora]           = useState(null)
  const [proyeccion, setProy]     = useState([])
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get('/api/finanzas/historico?meses=12'),
      api.get('/api/finanzas/mora'),
      api.get('/api/finanzas/proyeccion?meses=3'),
    ])
      .then(([h, m, p]) => {
        setHistorico(h.data?.data || [])
        setMora(m.data)
        setProy(p.data?.data || [])
      })
      .finally(() => setLoading(false))
  }, [])

  const acumulados = useMemo(() => {
    const c = historico.reduce((s, x) => s + (x.cobrado || 0), 0)
    const p = historico.reduce((s, x) => s + (x.pendiente || 0), 0)
    const v = historico.reduce((s, x) => s + (x.vencido || 0), 0)
    return { cobrado: c, pendiente: p, vencido: v, total: c + p + v }
  }, [historico])

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Análisis financiero</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Finanzas</h1>
          <p className="hero-sub">Histórico, mora y proyección de la cartera.</p>
        </header>

        {/* KPIs acumulados últimos 12 meses */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <KPI label="Cobrado 12m" value={fmtK(acumulados.cobrado)} color="text-green-600 dark:text-green-400" icon={DollarSign} />
          <KPI label="Pendiente 12m" value={fmtK(acumulados.pendiente)} color="text-amber-600" icon={Clock} />
          <KPI label="Vencido 12m" value={fmtK(acumulados.vencido)} color={acumulados.vencido > 0 ? 'text-red-500' : ''} icon={AlertTriangle} />
          <KPI label="Mora actual" value={mora ? fmtK(mora.monto_total) : '—'} sub={mora ? `${mora.total_items} pagos` : ''} color={mora?.monto_total > 0 ? 'text-red-500' : ''} icon={AlertTriangle} />
        </section>

        {/* Gráfico histórico cobrado vs pendiente */}
        <div className="card p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold">Cobros históricos · últimos 12 meses</p>
              <p className="text-[11px] text-muted dark:text-gray-500 mt-0.5">Cobrado en verde · pendiente en ámbar · vencido en rojo</p>
            </div>
            <BarChart3 size={18} className="text-muted" />
          </div>
          {loading || historico.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm text-gray-400 dark:text-gray-500">
              {loading ? 'Cargando…' : 'Sin datos suficientes'}
            </div>
          ) : (
            <BarChartHistorico data={historico} />
          )}
        </div>

        {/* Proyección + Mora detalle */}
        <div className="grid md:grid-cols-2 gap-6 mb-6">
          <div className="card p-6">
            <p className="text-sm font-semibold mb-1">Proyección de cobro</p>
            <p className="text-[11px] text-muted dark:text-gray-500 mb-4">Próximos 3 meses · contratos vigentes</p>
            {proyeccion.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500">Sin proyección.</p>
            ) : (
              <table className="w-full text-[13px]">
                <thead className="text-[11px] uppercase tracking-wider text-muted dark:text-gray-500">
                  <tr><th className="text-left py-1.5">Mes</th><th className="text-right">Esperado</th><th className="text-right">Contratos</th></tr>
                </thead>
                <tbody>
                  {proyeccion.map(p => (
                    <tr key={p.mes} className="border-t border-border dark:border-[#2A2A2A]">
                      <td className="py-2 font-medium">{p.mes}</td>
                      <td className="py-2 text-right font-semibold">{fmt$(p.esperado)}</td>
                      <td className="py-2 text-right text-muted dark:text-gray-500">{p.contratos}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card p-6">
            <p className="text-sm font-semibold mb-1">Mora actual</p>
            <p className="text-[11px] text-muted dark:text-gray-500 mb-4">
              {mora ? `${mora.total_items} pagos atrasados · ${fmt$(mora.monto_total)}` : '—'}
            </p>
            {!mora || mora.items.length === 0 ? (
              <p className="text-sm text-green-600 dark:text-green-400">✓ Sin mora.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {mora.items.slice(0, 8).map(it => (
                  <div key={it.pago_id} className="flex items-center justify-between border-b border-border dark:border-[#2A2A2A] pb-2 last:border-0">
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium truncate">{it.propiedad}</p>
                      <p className="text-[11px] text-muted dark:text-gray-500">{it.contrato_codigo} · {it.periodo} · {it.dias_atraso}d</p>
                    </div>
                    <span className="text-[13px] font-semibold text-red-500 shrink-0">{fmt$(it.monto)}</span>
                  </div>
                ))}
                {mora.items.length > 8 && (
                  <p className="text-[11px] text-muted dark:text-gray-500 italic pt-1">y {mora.items.length - 8} más…</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}

function KPI({ label, value, sub, color = '', icon: Icon }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-2">
        <p className="text-[10px] uppercase tracking-widest text-gray-400 dark:text-gray-500 font-semibold">{label}</p>
        {Icon && <Icon size={14} className="text-gray-300 dark:text-gray-600" />}
      </div>
      <p className={`text-2xl font-black ${color}`}>{value}</p>
      {sub && <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
    </div>
  )
}

/**
 * Bar chart inline (sin libs). Cada mes una columna apilada cobrado/pend/venc.
 */
function BarChartHistorico({ data }) {
  const w = 720
  const h = 200
  const padL = 38
  const padR = 8
  const padT = 8
  const padB = 28
  const innerW = w - padL - padR
  const innerH = h - padT - padB
  const max = Math.max(1, ...data.map(d => (d.cobrado || 0) + (d.pendiente || 0) + (d.vencido || 0)))
  const bw = innerW / data.length

  // Eje Y: 0, 50%, 100%
  const yLines = [0, 0.5, 1.0]

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" preserveAspectRatio="none">
        {/* Grid */}
        {yLines.map((p, i) => (
          <g key={i}>
            <line x1={padL} x2={w - padR} y1={padT + (1 - p) * innerH} y2={padT + (1 - p) * innerH}
              stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
            <text x={padL - 6} y={padT + (1 - p) * innerH + 4} textAnchor="end"
              className="fill-gray-400 dark:fill-gray-500" fontSize="10">
              {fmtK(max * p)}
            </text>
          </g>
        ))}

        {/* Barras */}
        {data.map((d, i) => {
          const cob = d.cobrado || 0
          const pen = d.pendiente || 0
          const ven = d.vencido || 0
          const x = padL + i * bw + bw * 0.18
          const bar = bw * 0.64
          const hCob = (cob / max) * innerH
          const hPen = (pen / max) * innerH
          const hVen = (ven / max) * innerH
          let y = padT + innerH

          const segs = []
          if (hCob) {
            y -= hCob
            segs.push(<rect key="c" x={x} y={y} width={bar} height={hCob} fill="#16A34A" rx="2" />)
          }
          if (hPen) {
            y -= hPen
            segs.push(<rect key="p" x={x} y={y} width={bar} height={hPen} fill="#D97706" rx="2" />)
          }
          if (hVen) {
            y -= hVen
            segs.push(<rect key="v" x={x} y={y} width={bar} height={hVen} fill="#DC2626" rx="2" />)
          }

          return (
            <g key={d.mes}>
              {segs}
              <text x={x + bar / 2} y={h - padB + 14} textAnchor="middle"
                className="fill-gray-400 dark:fill-gray-500" fontSize="9">
                {d.mes.slice(5)}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
