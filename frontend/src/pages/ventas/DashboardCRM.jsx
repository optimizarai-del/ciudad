import { useEffect, useState } from 'react'
import { TrendingUp, Users, ClipboardList, Building2, CheckCircle2, DollarSign } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ESTADO_LABEL = {
  nuevo: 'Nuevo', contactado: 'Contactado', en_seguimiento: 'En seguimiento',
  esperando_respuesta: 'Esperando resp.', negociando: 'Negociando',
  cerrado: 'Cerrado', perdido: 'Perdido',
}

const fmtUSD = (n) => 'USD ' + (n || 0).toLocaleString('es-AR')

export default function DashboardCRM() {
  const [d, setD] = useState(null)
  useEffect(() => { api.get('/api/ventas-crm/dashboard').then(r => setD(r.data)) }, [])

  if (!d) return <Layout><div className="max-w-6xl mx-auto py-20 text-center text-muted">Cargando…</div></Layout>

  const cards = [
    { icon: Users, label: 'Clientes', value: d.total_clientes, sub: `${d.clientes_operados} operados` },
    { icon: ClipboardList, label: 'Pedidos activos', value: d.total_pedidos },
    { icon: Building2, label: 'Propiedades disponibles', value: d.propiedades_disponibles },
    { icon: CheckCircle2, label: 'Operaciones cerradas', value: d.operaciones_cerradas },
    { icon: DollarSign, label: 'Monto cerrado', value: fmtUSD(d.monto_cerrado_usd) },
    { icon: TrendingUp, label: 'Comisiones', value: fmtUSD(d.comisiones_usd) },
  ]

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">CRM Comercial</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Dashboard Ventas</h1>
          <p className="hero-sub">{d.es_admin ? 'Vista de todo el equipo.' : 'Tu actividad comercial.'}</p>
        </header>

        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-8">
          {cards.map((c, i) => (
            <div key={i} className="card p-4 sm:p-5">
              <c.icon size={18} className="text-[#B8893A] mb-2" />
              <p className="stat-label">{c.label}</p>
              <p className="stat-value text-2xl sm:text-3xl mt-1">{c.value}</p>
              {c.sub && <p className="text-[11px] text-muted mt-0.5">{c.sub}</p>}
            </div>
          ))}
        </div>

        <div className="card p-5 sm:p-6">
          <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-4">
            Funnel de pedidos
          </p>
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-2">
            {Object.entries(d.pedidos_por_estado || {}).map(([est, n]) => (
              <div key={est} className="text-center p-3 rounded-xl bg-neutral-50 dark:bg-[#141414]">
                <p className="stat-value text-xl">{n}</p>
                <p className="text-[10px] text-muted mt-0.5">{ESTADO_LABEL[est] || est}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
