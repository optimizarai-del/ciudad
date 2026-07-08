import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Building2, FileText, Users, Calculator,
  BarChart2, TrendingUp, Settings, DollarSign,
  Home, CreditCard, KeyRound, Bell, Receipt, Landmark, Wrench, HardDrive, History,
  ClipboardList, Handshake, Network, LayoutGrid, Sparkles, CalendarClock, Map, Globe, Plug,
  Menu, ChevronDown,
} from 'lucide-react'
import { useRole } from '../../context/RoleContext'

const LS_COLLAPSED = 'ciudad_sidebar_collapsed'
const LS_GRUPOS = 'ciudad_sidebar_groups'

function leer(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function Item({ to, icon: Icon, label, collapsed, onNavigate }) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-xl text-sm font-medium transition-colors ${
          collapsed ? 'justify-center px-0 py-2.5' : 'px-3 py-2'
        } ${
          isActive
            ? 'bg-black dark:bg-white text-white dark:text-black'
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-black dark:hover:text-white'
        }`
      }
    >
      <Icon size={16} className="shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  )
}

export default function Sidebar({ onNavigate }) {
  const { hasAlquileres, hasVentas, isAdmin, isGerencia, isAdminDemo } = useRole()

  const drawer = !!onNavigate               // en drawer mobile siempre va expandido
  const [collapsed, setCollapsed] = useState(() => leer(LS_COLLAPSED, false))
  const [abiertos, setAbiertos] = useState(() => leer(LS_GRUPOS, {})) // {[label]: false} = cerrado
  const col = drawer ? false : collapsed

  const toggleCollapse = () => setCollapsed(c => {
    const next = !c
    try { localStorage.setItem(LS_COLLAPSED, JSON.stringify(next)) } catch {}
    return next
  })

  const toggleGrupo = (label) => setAbiertos(prev => {
    const next = { ...prev, [label]: prev[label] === false ? true : false }
    try { localStorage.setItem(LS_GRUPOS, JSON.stringify(next)) } catch {}
    return next
  })

  // ── Grupos lógicos (gateados por rol) ────────────────────────────────────
  const grupos = []

  if (hasAlquileres) {
    grupos.push({
      label: 'Alquileres',
      items: [
        { to: '/alquileres/dashboard',    icon: LayoutDashboard, label: 'Dashboard' },
        { to: '/alquileres/propiedades',  icon: Home,            label: 'Propiedades' },
        { to: '/alquileres/contratos',    icon: FileText,        label: 'Contratos' },
        { to: '/alquileres/cobranza',     icon: CreditCard,      label: 'Cobros' },
        { to: '/alquileres/liquidaciones', icon: Receipt,        label: 'Liquidaciones' },
        { to: '/alquileres/tasas',        icon: Landmark,        label: 'Tasas municipales' },
        { to: '/alquileres/refacciones',  icon: Wrench,          label: 'Refacciones' },
        { to: '/alquileres/clientes',     icon: Users,           label: 'Clientes' },
        { to: '/alquileres/propietarios', icon: KeyRound,        label: 'Propietarios' },
        { to: '/alquileres/historial',    icon: History,         label: 'Historial' },
        { to: '/calculadora',             icon: Calculator,      label: 'Calculadora' },
      ],
    })
  }

  if (hasVentas) {
    grupos.push({
      label: 'Ventas',
      items: [
        { to: '/ventas-crm/dashboard',   icon: TrendingUp,    label: 'Dashboard' },
        ...(isGerencia ? [{ to: '/ventas-crm/ejecutivo', icon: BarChart2, label: 'Ejecutivo' }] : []),
        { to: '/ventas-crm/crm',          icon: LayoutGrid,    label: 'CRM de Ventas' },
        { to: '/ventas-crm/pedidos',      icon: ClipboardList, label: 'Pedidos' },
        { to: '/ventas-crm/clientes',     icon: Users,         label: 'Clientes' },
        { to: '/ventas-crm/propiedades',  icon: Building2,     label: 'Propiedades' },
        { to: '/ventas-crm/red-tokko',    icon: Globe,         label: 'Red Tokko' },
        { to: '/ventas-crm/webs',         icon: Network,       label: 'Webs' },
        { to: '/ventas-crm/mapas',        icon: Map,           label: 'Mapas' },
        { to: '/ventas-crm/operaciones',  icon: Handshake,     label: 'Operaciones' },
        { to: '/ventas-crm/matches',      icon: Sparkles,      label: 'Matches' },
        { to: '/ventas-crm/tareas',       icon: CalendarClock, label: 'Tareas' },
        { to: '/ventas-crm/contactos',    icon: Network,       label: 'Contactos' },
        { to: '/ventas-crm/notificaciones', icon: Bell,        label: 'Notificaciones' },
        { to: '/ventas-crm/configuracion', icon: Settings,     label: 'Configuración' },
        ...(isGerencia && !isAdminDemo ? [{ to: '/ventas-crm/conexiones', icon: Plug, label: 'Conexiones' }] : []),
      ],
    })
  }

  grupos.push({
    label: 'Herramientas',
    items: [
      { to: '/asistente',                    icon: Sparkles,  label: 'Asistente IA' },
      { to: '/indices',                      icon: BarChart2, label: 'Índices' },
      { to: '/recordatorios',                icon: Bell,      label: 'Recordatorios' },
      { to: '/herramientas/versiones-local', icon: HardDrive, label: 'Versiones local' },
    ],
  })

  if (isAdmin) {
    grupos.push({
      label: 'Administración',
      items: [
        { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard Maestro' },
        { to: '/finanzas',  icon: DollarSign,      label: 'Finanzas' },
        { to: '/equipo',    icon: Settings,        label: 'Equipo' },
      ],
    })
  } else if (isGerencia) {
    grupos.push({
      label: 'Gerencia',
      items: [
        { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard Maestro' },
      ],
    })
  }

  return (
    <aside
      className={`shrink-0 h-[calc(100vh-3rem)] lg:h-full bg-white dark:bg-[#0A0A0A] border-r border-gray-100 dark:border-gray-900 flex flex-col py-3 px-2 overflow-y-auto transition-[width] duration-200 ${
        drawer ? 'w-64' : col ? 'w-[68px]' : 'w-60'
      }`}
    >
      {/* Header: hamburguesa para contraer/expandir (solo desktop) */}
      {!drawer && (
        <div className={`flex items-center mb-3 h-8 ${col ? 'justify-center' : 'justify-between px-1'}`}>
          {!col && (
            <span className="px-1 text-[10px] font-bold tracking-widest uppercase text-gray-400 dark:text-gray-600">
              Menú
            </span>
          )}
          <button
            onClick={toggleCollapse}
            title={col ? 'Expandir menú' : 'Contraer menú'}
            className="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-black dark:hover:text-white transition"
          >
            <Menu size={18} />
          </button>
        </div>
      )}

      {/* Banner modo demo (oculto en riel) */}
      {isAdminDemo && !col && (
        <div className="mb-3 px-3 py-2 rounded-xl bg-[#B8893A]/10 border border-[#B8893A]/30">
          <p className="text-[10px] uppercase tracking-widest font-bold text-[#B8893A]">Modo Demo</p>
          <p className="text-[10px] text-muted mt-0.5">
            Solo ves datos de prueba. Tus cambios no afectan la data real.
          </p>
        </div>
      )}
      {isAdminDemo && col && (
        <div className="mb-2 flex justify-center" title="Modo Demo — solo datos de prueba">
          <span className="w-2 h-2 rounded-full bg-[#B8893A]" />
        </div>
      )}

      {/* Navegación */}
      <nav className="flex-1 flex flex-col gap-1">
        {grupos.map((g) => {
          // Riel: solo íconos, sin encabezado, separados por divisor.
          if (col) {
            return (
              <div
                key={g.label}
                className="flex flex-col gap-0.5 pb-2 mb-1 border-b border-gray-100 dark:border-gray-900 last:border-0"
              >
                {g.items.map((it) => <Item key={it.to} {...it} collapsed onNavigate={onNavigate} />)}
              </div>
            )
          }
          // Expandido: encabezado desplegable.
          const open = abiertos[g.label] !== false // por defecto abierto
          return (
            <div key={g.label} className="mb-2">
              <button
                onClick={() => toggleGrupo(g.label)}
                className="w-full flex items-center justify-between px-3 py-1.5 group"
              >
                <span className="text-[10px] font-bold tracking-widest uppercase text-gray-400 dark:text-gray-600 group-hover:text-gray-500 dark:group-hover:text-gray-400 transition-colors">
                  {g.label}
                </span>
                <ChevronDown
                  size={13}
                  className={`text-gray-400 dark:text-gray-600 transition-transform duration-200 ${open ? '' : '-rotate-90'}`}
                />
              </button>
              {open && (
                <div className="space-y-0.5 mt-0.5">
                  {g.items.map((it) => <Item key={it.to} {...it} collapsed={false} onNavigate={onNavigate} />)}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
