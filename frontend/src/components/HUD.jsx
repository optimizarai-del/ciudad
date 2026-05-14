import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, Search, Bell, Sun, Moon, Menu, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import Logo from './Logo'
import NotificacionesPanel from './NotificacionesPanel'
import api from '../utils/api'

export default function HUD({ onToggleSidebar, drawerOpen }) {
  const { user, logout } = useAuth()
  const { isDark, toggle } = useTheme()
  const nav = useNavigate()
  const [stats, setStats]   = useState(null)
  const [resumen, setResumen] = useState({ total: 0, criticos: 0 })
  const [panelOpen, setPanelOpen] = useState(false)
  const bellRef = useRef(null)

  useEffect(() => {
    const fetchAll = () => {
      api.get('/api/dashboard/hud').then(r => setStats(r.data)).catch(() => {})
      // Resumen completo: vencimientos + pagos en mora + eventos críticos.
      // Devuelve {total, criticos, items}. Solo nos quedamos con los counts
      // para el badge; el panel pide los items al abrirse.
      api.get('/api/alertas/resumen')
        .then(r => setResumen({ total: r.data.total, criticos: r.data.criticos }))
        .catch(() => {})
    }
    fetchAll()
    const t = setInterval(fetchAll, 30000)
    return () => clearInterval(t)
  }, [])

  return (
    <header className="sticky top-0 z-40 glass border-b border-[#E5E5E5] dark:border-[#2A2A2A]">
      <div className="px-3 sm:px-4 lg:px-6 h-12 flex items-center gap-2 sm:gap-4 lg:gap-6">
        {/* Hamburger sólo mobile/tablet */}
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-2 -ml-1 rounded-lg text-[#737373] dark:text-[#9A9A9A] hover:bg-[#F0F0F0] dark:hover:bg-[#1E1E1E] transition"
            title="Menú"
          >
            {drawerOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        )}

        <button onClick={() => nav('/dashboard')} className="flex items-center hover:opacity-60 transition shrink-0">
          <Logo size="sm" />
        </button>

        {/* Stats sólo desde lg (1024px+) — en tablet ocupan demasiado */}
        {stats && (
          <div className="hidden lg:flex items-center gap-5 ml-2">
            <Stat label="Propiedades" value={stats.propiedades_total} />
            <Stat label="Disponibles" value={stats.propiedades_disponibles} />
            <Stat label="Contratos" value={stats.contratos_vigentes} />
            <Stat label="Clientes" value={stats.clientes_total} />
          </div>
        )}

        <div className="ml-auto flex items-center gap-0.5 sm:gap-1">
          {/* Buscar sólo en sm+ */}
          <div className="hidden sm:block">
            <IconBtn><Search size={15} /></IconBtn>
          </div>

          {/* Bell con badge + panel dropdown */}
          <div className="relative" ref={bellRef}>
            <IconBtn onClick={() => setPanelOpen(o => !o)} title="Notificaciones">
              <Bell size={15} />
            </IconBtn>
            {resumen.total > 0 && (
              <span className={`absolute top-1 right-1 min-w-4 h-4 px-1 rounded-full text-white text-[9px] font-bold grid place-items-center pointer-events-none
                ${resumen.criticos > 0 ? 'bg-danger' : 'bg-[#B8893A]'}`}>
                {resumen.total > 9 ? '9+' : resumen.total}
              </span>
            )}
            {panelOpen && (
              <NotificacionesPanel
                anchorRef={bellRef}
                onClose={() => setPanelOpen(false)}
              />
            )}
          </div>

          {/* Theme toggle */}
          <IconBtn onClick={toggle} title={isDark ? 'Modo claro' : 'Modo noche'}>
            {isDark
              ? <Sun size={15} className="text-[#C8C8C8]" />
              : <Moon size={15} />
            }
          </IconBtn>

          <div className="w-px h-4 bg-[#E5E5E5] dark:bg-[#2A2A2A] mx-1 sm:mx-2" />
          <button className="flex items-center gap-2 pl-1 pr-2 sm:pr-3 py-1 rounded-full hover:bg-[#F0F0F0] dark:hover:bg-[#1E1E1E] transition">
            <div className="w-7 h-7 rounded-full bg-[#0A0A0A] dark:bg-white text-white dark:text-[#0A0A0A] grid place-items-center text-[11px] font-semibold select-none">
              {user?.nombre?.[0]?.toUpperCase()}
            </div>
            <span className="text-[13px] font-medium hidden md:inline tracking-tight text-[#0A0A0A] dark:text-[#F5F5F5] max-w-[120px] truncate">
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
