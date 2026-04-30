import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Search, Bell, Sun, Moon } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import Logo from './Logo'
import api from '../utils/api'

export default function HUD() {
  const { user, logout } = useAuth()
  const { isDark, toggle } = useTheme()
  const nav = useNavigate()
  const [stats, setStats]   = useState(null)
  const [alertas, setAlertas] = useState(0)

  useEffect(() => {
    const fetchAll = () => {
      api.get('/api/dashboard/hud').then(r => setStats(r.data)).catch(() => {})
      api.get('/api/alertas/vencimientos?dias=30').then(r => setAlertas(r.data.length)).catch(() => {})
    }
    fetchAll()
    const t = setInterval(fetchAll, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <header className="sticky top-0 z-40 glass border-b border-[#E5E5E5] dark:border-[#2A2A2A]">
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

          {/* Bell con badge de alertas */}
          <div className="relative">
            <IconBtn onClick={() => nav('/contratos')}>
              <Bell size={15} />
            </IconBtn>
            {alertas > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-danger text-white text-[9px] font-bold grid place-items-center pointer-events-none">
                {alertas > 9 ? '9+' : alertas}
              </span>
            )}
          </div>

          {/* Theme toggle */}
          <IconBtn onClick={toggle} title={isDark ? 'Modo claro' : 'Modo noche'}>
            {isDark
              ? <Sun size={15} className="text-[#C8C8C8]" />
              : <Moon size={15} />
            }
          </IconBtn>

          <div className="w-px h-4 bg-[#E5E5E5] dark:bg-[#2A2A2A] mx-2" />
          <button className="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full hover:bg-[#F0F0F0] dark:hover:bg-[#1E1E1E] transition">
            <div className="w-7 h-7 rounded-full bg-[#0A0A0A] dark:bg-white text-white dark:text-[#0A0A0A] grid place-items-center text-[11px] font-semibold select-none">
              {user?.nombre?.[0]?.toUpperCase()}
            </div>
            <span className="text-[13px] font-medium hidden md:inline tracking-tight text-[#0A0A0A] dark:text-[#F5F5F5]">
              {user?.nombre}
            </span>
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
      <span className="font-semibold text-[13px] tracking-tight text-[#0A0A0A] dark:text-[#F5F5F5]">
        {value ?? '—'}
      </span>
      <span className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">{label}</span>
    </div>
  )
}

function IconBtn({ children, onClick, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="p-2 rounded-full text-[#737373] dark:text-[#9A9A9A] hover:bg-[#F0F0F0] dark:hover:bg-[#1E1E1E] hover:text-[#0A0A0A] dark:hover:text-[#F5F5F5] transition"
    >
      {children}
    </button>
  )
}
