import { useEffect, useState } from 'react'
import {
  Users, TrendingUp, DollarSign, Building2, Handshake, Radio,
  Gauge, Trophy, Layers,
} from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ORO = '#B8893A'
const fmtUSD = (n) => 'USD ' + Math.round(n || 0).toLocaleString('es-AR')
const fmtN = (n) => (n || 0).toLocaleString('es-AR')

const CANAL_LABEL = {
  instagram: 'Instagram', whatsapp: 'WhatsApp', web: 'Web', referido: 'Referido',
  telegram: 'Telegram', tokko: 'Red Tokko', scraping: 'Portales', sin_origen: 'Sin origen',
}
const canalLabel = (c) => CANAL_LABEL[c] || (c ? c[0].toUpperCase() + c.slice(1) : '—')

const EST_OP_LABEL = { abierta: 'Abiertas', sena: 'Con seña', cerrada: 'Cerradas', caida: 'Caídas' }
const EST_OP_BAR = { abierta: 'bg-blue-400', sena: 'bg-amber-500', cerrada: 'bg-emerald-500', caida: 'bg-neutral-400' }

export default function DashboardEjecutivo() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/api/ventas-crm/dashboard-ejecutivo')
      .then((r) => setD(r.data))
      .catch((e) => setErr(e?.response?.status === 403
        ? 'El dashboard ejecutivo es solo para la gerencia.'
        : 'No se pudo cargar el dashboard.'))
  }, [])

  if (err) return <Layout><div className="max-w-6xl mx-auto py-20 text-center text-muted">{err}</div></Layout>
  if (!d) return <Layout><div className="max-w-6xl mx-auto py-20 text-center text-muted">Cargando…</div></Layout>

  const r = d.resumen
  const capMax = Math.max(1, ...d.captacion.map((c) => c.total))
  const opMax = Math.max(1, ...d.operaciones.por_estado.map((o) => o.n))
  const invDisp = d.inventario.por_estado.find((x) => x.estado === 'disponible')?.n || 0
  const equipo = (d.equipo?.vendedores || []).slice().sort((a, b) => (b.valor_ponderado_usd || 0) - (a.valor_ponderado_usd || 0))

  const hero = [
    { icon: TrendingUp, label: 'Leads últimos 30 días', value: fmtN(r.leads_ult_30d), sub: `${fmtN(r.clientes_total)} clientes en total` },
    { icon: Gauge, label: 'Pipeline ponderado', value: fmtUSD(r.pipeline_ponderado_usd), sub: `${fmtUSD(r.pipeline_valor_usd)} en juego` },
    { icon: DollarSign, label: 'Comisiones cerradas', value: fmtUSD(r.comision_cerrada_usd), sub: `${fmtN(r.operaciones_cerradas)} operaciones cerradas` },
  ]

  const kpis = [
    { icon: Handshake, label: 'Operaciones abiertas', value: fmtN(r.operaciones_abiertas) },
    { icon: DollarSign, label: 'Monto cerrado', value: fmtUSD(d.operaciones.monto_cerrado_usd) },
    { icon: Building2, label: 'Inventario disponible', value: fmtN(invDisp) },
    { icon: Layers, label: 'Valor inventario', value: fmtUSD(d.inventario.valor_disponible_usd) },
  ]

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Gerencia</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Dashboard ejecutivo</h1>
          <p className="hero-sub">La foto del negocio en una pantalla: captación, pipeline, operaciones e inventario.</p>
        </header>

        {/* Hero — los 3 números que importan */}
        <div className="grid sm:grid-cols-3 gap-3 sm:gap-4 mb-4">
          {hero.map((h, i) => (
            <div key={i} className="card p-5 sm:p-6 relative overflow-hidden">
              <div className="absolute right-0 top-0 h-full w-1" style={{ background: ORO }} />
              <div className="flex items-center gap-2 mb-1">
                <h.icon size={16} style={{ color: ORO }} />
                <p className="stat-label">{h.label}</p>
              </div>
              <p className="stat-value text-2xl sm:text-3xl lg:text-4xl">{h.value}</p>
              <p className="text-[11px] text-muted mt-1">{h.sub}</p>
            </div>
          ))}
        </div>

        {/* KPIs secundarios */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-4">
          {kpis.map((c, i) => (
            <div key={i} className="card p-4 sm:p-5">
              <c.icon size={18} className="mb-2" style={{ color: ORO }} />
              <p className="stat-label">{c.label}</p>
              <p className="stat-value text-xl sm:text-2xl mt-1">{c.value}</p>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-2 gap-3 sm:gap-4 mb-4">
          {/* Captación por canal */}
          <div className="card p-5 sm:p-6">
            <div className="flex items-center gap-2 mb-4">
              <Radio size={15} style={{ color: ORO }} />
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">Captación por canal</p>
            </div>
            {d.captacion.length === 0 && <p className="text-sm text-muted">Todavía no hay leads cargados.</p>}
            <div className="space-y-2.5">
              {d.captacion.map((c) => (
                <div key={c.canal} className="flex items-center gap-3">
                  <span className="w-24 text-[12px] text-muted shrink-0 truncate">{canalLabel(c.canal)}</span>
                  <div className="flex-1 h-6 rounded-lg bg-neutral-100 dark:bg-[#1A1A1A] overflow-hidden">
                    <div className="h-full rounded-lg transition-all"
                      style={{ width: `${Math.max(c.total ? 6 : 0, (100 * c.total) / capMax)}%`, background: ORO }} />
                  </div>
                  <span className="w-10 text-right stat-value text-sm">{c.total}</span>
                  <span className="w-16 text-right text-[11px] text-emerald-600 dark:text-emerald-400">+{c.ult_30d}/30d</span>
                </div>
              ))}
            </div>
          </div>

          {/* Operaciones por estado */}
          <div className="card p-5 sm:p-6">
            <div className="flex items-center gap-2 mb-4">
              <Handshake size={15} style={{ color: ORO }} />
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">Operaciones</p>
            </div>
            <div className="space-y-2.5">
              {d.operaciones.por_estado.map((o) => (
                <div key={o.estado} className="flex items-center gap-3">
                  <span className="w-24 text-[12px] text-muted shrink-0 truncate">{EST_OP_LABEL[o.estado] || o.estado}</span>
                  <div className="flex-1 h-6 rounded-lg bg-neutral-100 dark:bg-[#1A1A1A] overflow-hidden">
                    <div className={`h-full rounded-lg transition-all ${EST_OP_BAR[o.estado] || 'bg-neutral-400'}`}
                      style={{ width: `${Math.max(o.n ? 6 : 0, (100 * o.n) / opMax)}%` }} />
                  </div>
                  <span className="w-10 text-right stat-value text-sm">{o.n}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-800 flex justify-between text-[12px]">
              <span className="text-muted">Monto cerrado</span>
              <span className="stat-value text-sm">{fmtUSD(d.operaciones.monto_cerrado_usd)}</span>
            </div>
          </div>
        </div>

        {/* Inventario + Ranking del equipo */}
        <div className="grid lg:grid-cols-2 gap-3 sm:gap-4">
          <div className="card p-5 sm:p-6">
            <div className="flex items-center gap-2 mb-4">
              <Building2 size={15} style={{ color: ORO }} />
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">Inventario ({fmtN(d.inventario.total)})</p>
            </div>
            <div className="grid grid-cols-2 gap-2 mb-3">
              {d.inventario.por_estado.map((x) => (
                <div key={x.estado} className="rounded-lg bg-neutral-50 dark:bg-[#161616] p-3">
                  <p className="stat-value text-xl">{x.n}</p>
                  <p className="text-[11px] text-muted capitalize">{x.estado}</p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {d.inventario.por_fuente.filter((f) => f.n > 0).map((f) => (
                <span key={f.fuente} className="chip-muted text-[11px] capitalize">{f.fuente}: {f.n}</span>
              ))}
            </div>
          </div>

          <div className="card p-5 sm:p-6">
            <div className="flex items-center gap-2 mb-4">
              <Trophy size={15} style={{ color: ORO }} />
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">Ranking del equipo</p>
            </div>
            {equipo.length === 0 && <p className="text-sm text-muted">Sin vendedores con actividad.</p>}
            <div className="space-y-2">
              {equipo.slice(0, 8).map((v, i) => (
                <div key={v.vendedor_id ?? i} className="flex items-center gap-3">
                  <span className="w-5 text-center stat-value text-sm" style={{ color: i === 0 ? ORO : undefined }}>{i + 1}</span>
                  <Users size={14} className="text-muted shrink-0" />
                  <span className="flex-1 text-sm truncate">{v.nombre || `Vendedor ${v.vendedor_id}`}</span>
                  <span className="text-[11px] text-muted">{fmtN(v.activos)} activos</span>
                  <span className="w-28 text-right stat-value text-sm">{fmtUSD(v.valor_ponderado_usd)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <p className="text-[11px] text-muted mt-6 text-center">
          Generado {new Date(d.generado_at).toLocaleString('es-AR')}
        </p>
      </div>
    </Layout>
  )
}
