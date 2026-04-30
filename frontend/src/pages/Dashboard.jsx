import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, FileText, Users, TrendingUp, Plus, ArrowRight } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { useAuth } from '../context/AuthContext'

export default function Dashboard() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [stats, setStats] = useState(null)
  const [propRecientes, setPropRecientes] = useState([])
  const [contratos, setContratos] = useState([])

  useEffect(() => {
    api.get('/api/dashboard/hud').then(r => setStats(r.data)).catch(() => {})
    api.get('/api/propiedades').then(r => setPropRecientes(r.data.slice(0, 5))).catch(() => {})
    api.get('/api/contratos').then(r => setContratos(r.data.slice(0, 5))).catch(() => {})
  }, [])

  const hora = new Date().getHours()
  const saludo = hora < 12 ? 'Buenos días' : hora < 18 ? 'Buenas tardes' : 'Buenas noches'

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

        {/* Big numbers */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <BigNum label="Propiedades" value={stats?.propiedades_total ?? '—'} sub="en cartera" onClick={() => nav('/propiedades')} />
          <BigNum label="Disponibles" value={stats?.propiedades_disponibles ?? '—'} sub="sin inquilino" color="success" onClick={() => nav('/propiedades')} />
          <BigNum label="Contratos" value={stats?.contratos_vigentes ?? '—'} sub="vigentes" onClick={() => nav('/contratos')} />
          <BigNum label="Clientes" value={stats?.clientes_total ?? '—'} sub="en base" onClick={() => nav('/clientes')} />
        </section>

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
              : <ul className="divide-y divide-border">
                  {propRecientes.map(p => (
                    <li key={p.id} className="py-3 flex items-center justify-between gap-3 cursor-pointer hover:bg-neutral-50 -mx-2 px-2 rounded-xl transition"
                      onClick={() => nav('/propiedades')}>
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-xl bg-neutral-100 grid place-items-center shrink-0">
                          <Building2 size={14} className="text-muted" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium truncate">{p.direccion}</p>
                          <p className="text-[11px] text-muted capitalize">{p.tipo} · {p.ciudad}</p>
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
              : <ul className="divide-y divide-border">
                  {contratos.map(c => (
                    <li key={c.id} className="py-3 flex items-center justify-between gap-3 cursor-pointer hover:bg-neutral-50 -mx-2 px-2 rounded-xl transition"
                      onClick={() => nav('/contratos')}>
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-xl bg-neutral-100 grid place-items-center shrink-0">
                          <FileText size={14} className="text-muted" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[13px] font-medium truncate">{c.codigo || `Contrato #${c.id}`}</p>
                          <p className="text-[11px] text-muted capitalize">{c.tipo?.replace(/_/g, ' ')}</p>
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
          <h2 className="font-semibold text-[13px] text-muted uppercase tracking-[0.12em] mb-4">Acciones rápidas</h2>
          <div className="flex flex-wrap gap-3">
            <QuickAction icon={Building2} label="Nueva propiedad" onClick={() => nav('/propiedades')} />
            <QuickAction icon={FileText}  label="Nuevo contrato"  onClick={() => nav('/contratos')} />
            <QuickAction icon={Users}     label="Nuevo cliente"   onClick={() => nav('/clientes')} />
            <QuickAction icon={TrendingUp} label="Calcular costos" onClick={() => nav('/calculadora')} />
          </div>
        </section>

      </div>
    </Layout>
  )
}

function BigNum({ label, value, sub, color, onClick }) {
  const numColor = color === 'success' ? 'text-success' : 'text-primary'
  return (
    <div className="card p-6 card-hover cursor-pointer" onClick={onClick}>
      <div className="stat-label mb-2">{label}</div>
      <div className={`hero-title text-4xl ${numColor}`}>{value}</div>
      <div className="text-[12px] text-muted mt-1">{sub}</div>
    </div>
  )
}

function Empty({ msg, cta, onClick }) {
  return (
    <div className="text-center py-10">
      <p className="text-[13px] text-muted mb-3">{msg}</p>
      <button className="btn-secondary text-[12px] py-1.5" onClick={onClick}>
        <Plus size={12} /> {cta}
      </button>
    </div>
  )
}

function QuickAction({ icon: Icon, label, onClick }) {
  return (
    <button onClick={onClick}
      className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-white border border-border
                 text-[13px] font-medium hover:bg-neutral-50 hover:shadow-soft transition">
      <Icon size={14} className="text-muted" />
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
