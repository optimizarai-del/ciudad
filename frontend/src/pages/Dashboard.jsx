import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, FileText, Users, TrendingUp, Plus, ArrowRight, AlertTriangle, BarChart2, Clock } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { useAuth } from '../context/AuthContext'

export default function Dashboard() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [stats, setStats]           = useState(null)
  const [propRecientes, setPropRec] = useState([])
  const [contratos, setContratos]   = useState([])
  const [alertas, setAlertas]       = useState([])
  const [indices, setIndices]       = useState(null)

  useEffect(() => {
    api.get('/api/dashboard/hud').then(r => setStats(r.data)).catch(() => {})
    api.get('/api/propiedades').then(r => setPropRec(r.data.slice(0, 5))).catch(() => {})
    api.get('/api/contratos').then(r => setContratos(r.data.slice(0, 5))).catch(() => {})
    api.get('/api/alertas/vencimientos?dias=60').then(r => setAlertas(r.data)).catch(() => {})
    api.get('/api/indices').then(r => setIndices(r.data)).catch(() => {})
  }, [])

  const hora = new Date().getHours()
  const saludo = hora < 12 ? 'Buenos días' : hora < 18 ? 'Buenas tardes' : 'Buenas noches'

  const alertasCriticas = alertas.filter(a => a.urgencia === 'critico')
  const alertasProximas = alertas.filter(a => a.urgencia !== 'critico')

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">

        {/* Hero */}
        <header className="mb-12">
          <div className="hero-eyebrow">Panel principal</div>
          <h1 className="hero-title text-5xl md:text-6xl mb-3">
            {saludo}, {user?.nombre?.split(' ')[0]}.
          </h1>
          <p className="hero-sub">Resumen del día en un solo lugar.</p>
        </header>

        {/* Alertas de vencimiento */}
        {alertas.length > 0 && (
          <section className="mb-8">
            {alertasCriticas.length > 0 && (
              <div className="mb-3 p-4 rounded-2xl border border-danger/20 bg-danger/5 dark:bg-danger/10 flex items-start gap-3">
                <AlertTriangle size={16} className="text-danger shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-[13px] font-semibold text-danger mb-2">
                    {alertasCriticas.length} contrato{alertasCriticas.length > 1 ? 's' : ''} vence{alertasCriticas.length > 1 ? 'n' : ''} en menos de 7 días
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {alertasCriticas.map(a => (
                      <button key={a.id} onClick={() => nav('/contratos')}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-danger/10 text-danger hover:bg-danger/15 transition">
                        <Clock size={10} />
                        {a.codigo} · {a.propiedad} · {a.dias_restantes}d
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {alertasProximas.length > 0 && (
              <div className="p-4 rounded-2xl border border-warn/20 bg-warn/5 dark:bg-warn/10 flex items-start gap-3">
                <Clock size={16} className="text-warn shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-[13px] font-semibold text-warn mb-2">
                    {alertasProximas.length} contrato{alertasProximas.length > 1 ? 's' : ''} vence{alertasProximas.length > 1 ? 'n' : ''} en los próximos 60 días
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {alertasProximas.slice(0, 4).map(a => (
                      <button key={a.id} onClick={() => nav('/contratos')}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-warn/10 text-warn hover:bg-warn/15 transition">
                        {a.codigo} · {a.dias_restantes}d
                      </button>
                    ))}
                    {alertasProximas.length > 4 && (
                      <span className="text-[11px] text-warn/70">+{alertasProximas.length - 4} más</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Big numbers */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <BigNum label="Propiedades" value={stats?.propiedades_total ?? '—'} sub="en cartera" onClick={() => nav('/propiedades')} />
          <BigNum label="Disponibles" value={stats?.propiedades_disponibles ?? '—'} sub="sin inquilino" color="success" onClick={() => nav('/propiedades')} />
          <BigNum label="Contratos" value={stats?.contratos_vigentes ?? '—'} sub="vigentes" onClick={() => nav('/contratos')} />
          <BigNum label="Clientes" value={stats?.clientes_total ?? '—'} sub="en base" onClick={() => nav('/clientes')} />
        </section>

        {/* Widget de índices */}
        {indices && (
          <section className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] uppercase tracking-[0.14em] text-[#737373] dark:text-[#7A7A7A] font-semibold">
                Índices económicos
              </h2>
              <button onClick={() => nav('/indices')} className="btn-link gap-1 text-[11px]">
                Ver detalle <ArrowRight size={11} />
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <MiniIndice label="IPC" dato={indices.ipc} fmt={v => v?.toFixed(1)} />
              <MiniIndice label="ICL" dato={indices.icl} fmt={v => v?.toFixed(3)} />
              <MiniIndice label="UVA" dato={indices.uva} fmt={v => `$${v?.toFixed(2)}`} />
              <MiniIndice label="USD Oficial" dato={indices.dolar_oficial} fmt={v => `$${v?.toLocaleString('es-AR')}`} valueKey="venta" />
            </div>
          </section>
        )}

        {/* Dos columnas */}
        <div className="grid md:grid-cols-2 gap-6">

          {/* Propiedades recientes */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-[15px] tracking-tight">Propiedades recientes</h2>
              <button onClick={() => nav('/propiedades')} className="btn-link gap-1">
                Ver todas <ArrowRight size={12} />
              </button>
            </div>
            {propRecientes.length === 0
              ? <Empty msg="No hay propiedades cargadas." cta="Agregar" onClick={() => nav('/propiedades')} />
              : <ul className="divide-y divide-[#E5E5E5] dark:divide-[#2A2A2A]">
                  {propRecientes.map(p => (
                    <li key={p.id} className="py-3 flex items-center justify-between gap-3 cursor-pointer hover:bg-[#F9F9F9] dark:hover:bg-[#1A1A1A] -mx-2 px-2 rounded-xl transition"
                      onClick={() => nav('/propiedades')}>
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-xl bg-[#F0F0F0] dark:bg-[#1E1E1E] grid place-items-center shrink-0">
                          <Building2 size={14} className="text-[#737373] dark:text-[#9A9A9A]" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium truncate">{p.direccion}</p>
                          <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A] capitalize">{p.tipo} · {p.ciudad}</p>
                        </div>
                      </div>
                      <EstadoBadge estado={p.estado} />
                    </li>
                  ))}
                </ul>
            }
          </div>

          {/* Contratos recientes */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-semibold text-[15px] tracking-tight">Contratos recientes</h2>
              <button onClick={() => nav('/contratos')} className="btn-link gap-1">
                Ver todos <ArrowRight size={12} />
              </button>
            </div>
            {contratos.length === 0
              ? <Empty msg="No hay contratos cargados." cta="Crear contrato" onClick={() => nav('/contratos')} />
              : <ul className="divide-y divide-[#E5E5E5] dark:divide-[#2A2A2A]">
                  {contratos.map(c => (
                    <li key={c.id} className="py-3 flex items-center justify-between gap-3 cursor-pointer hover:bg-[#F9F9F9] dark:hover:bg-[#1A1A1A] -mx-2 px-2 rounded-xl transition"
                      onClick={() => nav('/contratos')}>
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-xl bg-[#F0F0F0] dark:bg-[#1E1E1E] grid place-items-center shrink-0">
                          <FileText size={14} className="text-[#737373] dark:text-[#9A9A9A]" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium truncate">{c.codigo || `Contrato #${c.id}`}</p>
                          <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A] capitalize">{c.tipo?.replace(/_/g, ' ')}</p>
                        </div>
                      </div>
                      <ContratoEstadoBadge estado={c.estado} />
                    </li>
                  ))}
                </ul>
            }
          </div>
        </div>

        {/* Accesos rápidos */}
        <section className="mt-8">
          <h2 className="font-semibold text-[13px] text-[#737373] dark:text-[#7A7A7A] uppercase tracking-[0.12em] mb-4">Acciones rápidas</h2>
          <div className="flex flex-wrap gap-3">
            <QuickAction icon={Building2}  label="Nueva propiedad"  onClick={() => nav('/propiedades')} />
            <QuickAction icon={FileText}   label="Nuevo contrato"   onClick={() => nav('/contratos')} />
            <QuickAction icon={Users}      label="Nuevo cliente"    onClick={() => nav('/clientes')} />
            <QuickAction icon={TrendingUp} label="Calcular costos"  onClick={() => nav('/calculadora')} />
            <QuickAction icon={BarChart2}  label="Ver índices"      onClick={() => nav('/indices')} />
          </div>
        </section>

      </div>
    </Layout>
  )
}

function MiniIndice({ label, dato, fmt, valueKey = 'valor' }) {
  const ok = dato?.ok !== false && dato
  const val = ok ? dato[valueKey] ?? dato.valor : null
  const varPct = dato?.variacion_mensual
  return (
    <div className="card p-4 card-hover cursor-default">
      <p className="stat-label mb-1">{label}</p>
      <p className="text-lg font-semibold tracking-tight text-[#0A0A0A] dark:text-[#F5F5F5]">
        {ok && val != null ? fmt(val) : '—'}
      </p>
      {varPct != null && (
        <p className={`text-[10px] mt-0.5 ${varPct > 0 ? 'text-red-500' : 'text-success'}`}>
          {varPct > 0 ? '+' : ''}{varPct?.toFixed(2)}% mensual
        </p>
      )}
    </div>
  )
}

function BigNum({ label, value, sub, color, onClick }) {
  const numColor = color === 'success' ? 'text-success' : 'text-[#0A0A0A] dark:text-[#F5F5F5]'
  return (
    <div className="card p-6 card-hover cursor-pointer" onClick={onClick}>
      <div className="stat-label mb-2">{label}</div>
      <div className={`hero-title text-4xl ${numColor}`}>{value}</div>
      <div className="text-[12px] text-[#737373] dark:text-[#7A7A7A] mt-1">{sub}</div>
    </div>
  )
}

function Empty({ msg, cta, onClick }) {
  return (
    <div className="text-center py-10">
      <p className="text-[13px] text-[#737373] dark:text-[#9A9A9A] mb-3">{msg}</p>
      <button className="btn-secondary text-[12px] py-1.5" onClick={onClick}>
        <Plus size={12} /> {cta}
      </button>
    </div>
  )
}

function QuickAction({ icon: Icon, label, onClick }) {
  return (
    <button onClick={onClick}
      className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white dark:bg-[#141414] border border-[#E5E5E5] dark:border-[#2A2A2A]
                 text-[13px] font-medium hover:bg-[#F5F5F5] dark:hover:bg-[#1E1E1E] hover:shadow-soft transition">
      <Icon size={14} className="text-[#737373] dark:text-[#9A9A9A]" />
      {label}
    </button>
  )
}

function EstadoBadge({ estado }) {
  const map = {
    disponible: 'chip-success',
    ocupada:    'chip-dark',
    reservada:  'chip-warn',
    inactiva:   'chip-muted',
  }
  return <span className={map[estado] || 'chip-muted'}>{estado}</span>
}

function ContratoEstadoBadge({ estado }) {
  const map = {
    vigente:    'chip-dark',
    borrador:   'chip-gray',
    vencido:    'chip-warn',
    rescindido: 'chip-danger',
    cerrado:    'chip-muted',
  }
  return <span className={map[estado] || 'chip-muted'}>{estado}</span>
}
