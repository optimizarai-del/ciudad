import { useEffect, useState } from 'react'
import { Bell, Check, Sparkles, CalendarClock, UserPlus, Info } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ICON = { match: Sparkles, tarea: CalendarClock, asignacion: UserPlus, sistema: Info }
const fmt = s => s ? new Date(s).toLocaleString('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''

export default function Notificaciones() {
  const [list, setList] = useState([])
  const load = () => api.get('/api/ventas-crm/notificaciones').then(r => setList(r.data || []))
  useEffect(() => { load() }, [])

  const leer = async (n) => { if (n.leida) return; await api.post(`/api/ventas-crm/notificaciones/${n.id}/leida`); load() }
  const leerTodas = async () => { await api.post('/api/ventas-crm/notificaciones/marcar-todas'); load() }

  const noLeidas = list.filter(n => !n.leida).length

  return (
    <Layout>
      <div className="max-w-3xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Avisos</div>
          <div className="flex items-end justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Notificaciones</h1>
              <p className="hero-sub">{noLeidas > 0 ? `${noLeidas} sin leer` : 'Todo al día.'}</p>
            </div>
            {noLeidas > 0 && <button className="btn-secondary" onClick={leerTodas}><Check size={14} /> Marcar todas</button>}
          </div>
        </header>

        {list.length === 0 ? (
          <div className="card text-center py-20">
            <Bell size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">No hay notificaciones.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {list.map(n => {
              const Icon = ICON[n.tipo] || Info
              return (
                <button key={n.id} onClick={() => leer(n)}
                  className={`w-full text-left card p-4 flex gap-3 transition ${n.leida ? 'opacity-60' : 'border-l-4 border-l-[#B8893A]'}`}>
                  <div className="w-9 h-9 rounded-full bg-[#B8893A]/10 grid place-items-center shrink-0">
                    <Icon size={16} className="text-[#B8893A]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-[14px]">{n.titulo}</p>
                    <p className="text-[13px] text-muted">{n.cuerpo}</p>
                    <p className="text-[10px] text-muted mt-1">{fmt(n.created_at)}{n.enviada_telegram ? ' · enviada por Telegram' : ''}</p>
                  </div>
                  {!n.leida && <span className="w-2 h-2 rounded-full bg-[#B8893A] mt-1 shrink-0" />}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </Layout>
  )
}
