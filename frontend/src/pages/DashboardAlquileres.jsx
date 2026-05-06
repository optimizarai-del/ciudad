import { useState, useEffect } from 'react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { Home, FileText, AlertTriangle, CreditCard, TrendingUp, Clock, CheckCircle, XCircle } from 'lucide-react'

function MetricCard({ label, value, sub, icon: Icon, color = 'black' }) {
  const colors = {
    black:  'text-black dark:text-white',
    green:  'text-green-600 dark:text-green-400',
    red:    'text-red-500',
    amber:  'text-amber-500',
    blue:   'text-blue-600 dark:text-blue-400',
  }
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400">{label}</p>
        <Icon size={16} className="text-gray-300 dark:text-gray-700" />
      </div>
      <p className={`text-3xl font-black ${colors[color]}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

export default function DashboardAlquileres() {
  const [stats, setStats] = useState(null)
  const [cobranza, setCobranza] = useState(null)
  const [alertas, setAlertas] = useState([])

  useEffect(() => {
    const hoy = new Date()
    const mes = `${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}`
    Promise.all([
      api.get('/api/dashboard/stats'),
      api.get(`/api/cobranza/resumen?mes=${mes}`),
      api.get('/api/alertas/vencimientos?dias=60'),
    ]).then(([s, c, a]) => {
      setStats(s.data)
      setCobranza(c.data)
      setAlertas(a.data)
    }).catch(console.error)
  }, [])

  const criticas = alertas.filter(a => a.urgencia === 'critico')
  const proximas = alertas.filter(a => a.urgencia === 'pronto')

  const hoy = new Date()
  const mesLabel = hoy.toLocaleString('es-AR', { month: 'long', year: 'numeric' })

  return (
    <Layout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-1">Alquileres</p>
          <h1 className="text-3xl font-black capitalize">{mesLabel}</h1>
        </div>

        {/* Alertas críticas */}
        {criticas.length > 0 && (
          <div className="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900 flex items-start gap-3">
            <AlertTriangle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                {criticas.length} contrato{criticas.length > 1 ? 's' : ''} vence{criticas.length === 1 ? '' : 'n'} en menos de 7 días
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                {criticas.map(a => (
                  <span key={a.contrato_id} className="text-xs bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 px-2 py-0.5 rounded-full">
                    {a.codigo} · {a.dias_restantes}d
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Métricas principales */}
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="Contratos activos" value={stats?.contratos_vigentes ?? '—'} icon={FileText} />
          <MetricCard label="Propiedades ocupadas" value={stats?.propiedades_ocupadas ?? '—'} icon={Home} />
          <MetricCard
            label="Cobrado este mes"
            value={cobranza ? `$${(cobranza.cobrado/1000).toFixed(0)}K` : '—'}
            sub={cobranza ? `${cobranza.porcentaje_cobrado}% del total` : ''}
            icon={CheckCircle}
            color="green"
          />
          <MetricCard
            label="Pendiente de cobro"
            value={cobranza ? `$${(cobranza.pendiente/1000).toFixed(0)}K` : '—'}
            sub={cobranza?.vencido > 0 ? `+ $${(cobranza.vencido/1000).toFixed(0)}K vencido` : ''}
            icon={Clock}
            color={cobranza?.pendiente > 0 ? 'amber' : 'green'}
          />
        </div>

        {/* Barra de cobranza */}
        {cobranza && cobranza.total_esperado > 0 && (
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold">Cobranza del mes</p>
              <p className="text-sm text-gray-400">${(cobranza.total_esperado/1000).toFixed(0)}K total</p>
            </div>
            <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-black dark:bg-white rounded-full transition-all duration-500"
                style={{ width: `${cobranza.porcentaje_cobrado}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-xs text-gray-400">
              <span className="text-green-600 dark:text-green-400 font-medium">${(cobranza.cobrado/1000).toFixed(0)}K cobrado</span>
              <span>${(cobranza.pendiente/1000).toFixed(0)}K pendiente</span>
            </div>
          </div>
        )}

        {/* Próximos vencimientos */}
        {proximas.length > 0 && (
          <div className="card p-5">
            <p className="text-sm font-semibold mb-3">Contratos por vencer (próximos 60 días)</p>
            <div className="space-y-2">
              {proximas.slice(0, 5).map(a => (
                <div key={a.contrato_id} className="flex items-center justify-between py-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{a.codigo}</p>
                    <p className="text-xs text-gray-400">{a.propiedad_direccion}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    a.dias_restantes <= 30
                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                  }`}>
                    {a.dias_restantes}d
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
