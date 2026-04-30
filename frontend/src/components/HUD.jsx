import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Search, Bell } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Logo from './Logo'
import api from '../utils/api'

export default function HUD() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api.get('/api/dashboard/hud').then(r => setStats(r.data)).catch(() => {})
    const t = setInterval(() => {
      api.get('/api/dashboard/hud').then(r => setStats(r.data)).catch(() => {})
    }, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <header className="sticky top-0 z-40 glass border-b border-border">
      <div className="px-6 h-12 flex items-center gap-6">
        <button onClick={() => nav('/dashboard')} className="flex items-center hover:opacity-60 transition">
          <Logo size="sm" />
        </button>

        {stats && (
          <div className="hidden md:flex items-center gap-5 ml-2">
            <Stat label="Propiedades" value={stats.propiedades_total} />
            <Stat label="Disponibles" value={stats.propiedades_disponibles} />
            <Stat label="Contratos" value={stats.contratos_vigentes} />
            <Stat label="Clientes" value={stats.clientes_total} />
          </div>
        )}

        <div className="ml-auto flex items-center gap-1">
          <IconBtn><Search size={15} /></IconBtn>
          <IconBtn><Bell size={15} /></IconBtn>
          <div className="w-px h-4 bg-border mx-2" />
          <button className="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full hover:bg-neutral-100 transition">
            <div className="w-7 h-7 rounded-full bg-primary text-white grid place-items-center text-[11px] font-semibold select-none">
              {user?.nombre?.[0]?.toUpperCase()}
            </div>
            <span className="text-[13px] font-medium hidden md:inline tracking-tight">{user?.nombre}</span>
          </button>
          <IconBtn onClick={logout}><LogOut size={15} /></IconBtn>
        </div>
      </div>
    </header>
  )
}

function Stat({ label, value }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-semibold text-[13px] tracking-tight text-primary">{value ?? '—'}</span>
      <span className="text-[11px] text-muted">{label}</span>
    </div>
  )
}

function IconBtn({ children, onClick }) {
  return (
    <button onClick={onClick}
      className="p-2 rounded-full text-muted hover:bg-neutral-100 hover:text-primary transition">
      {children}
    </button>
  )
}
