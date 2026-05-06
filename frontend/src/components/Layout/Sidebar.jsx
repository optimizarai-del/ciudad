import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Building2, FileText, Users, Calculator,
  BarChart2, Bot, TrendingUp, Settings, DollarSign,
  Home, CreditCard, Store, ChevronRight
} from 'lucide-react'
import { useRole } from '../../context/RoleContext'

const NavItem = ({ to, icon: Icon, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
        isActive
          ? 'bg-black dark:bg-white text-white dark:text-black'
          : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-black dark:hover:text-white'
      }`
    }
  >
    <Icon size={16} />
    {label}
  </NavLink>
)

const Section = ({ label, children }) => (
  <div className="mb-4">
    <p className="px-3 mb-1 text-[10px] font-bold tracking-widest uppercase text-gray-400 dark:text-gray-600">
      {label}
    </p>
    <div className="space-y-0.5">{children}</div>
  </div>
)

export default function Sidebar() {
  const { hasAlquileres, hasVentas, isAdmin, isGerencia, role } = useRole()

  return (
    <aside className="w-60 h-full bg-white dark:bg-[#0A0A0A] border-r border-gray-100 dark:border-gray-900 flex flex-col py-4 px-3">

      {/* Alquileres section */}
      {hasAlquileres && (
        <Section label="Alquileres">
          <NavItem to="/alquileres/dashboard"  icon={LayoutDashboard} label="Dashboard" />
          <NavItem to="/alquileres/propiedades" icon={Home}           label="Propiedades" />
          <NavItem to="/alquileres/contratos"   icon={FileText}       label="Contratos" />
          <NavItem to="/alquileres/cobranza"    icon={CreditCard}     label="Cobranza" />
          <NavItem to="/alquileres/clientes"    icon={Users}          label="Clientes" />
          <NavItem to="/calculadora"            icon={Calculator}     label="Calculadora" />
        </Section>
      )}

      {/* Ventas section */}
      {hasVentas && (
        <Section label="Ventas">
          <NavItem to="/ventas/dashboard"    icon={TrendingUp}  label="Dashboard" />
          <NavItem to="/ventas/propiedades"  icon={Building2}   label="Propiedades" />
          <NavItem to="/ventas/tokko"        icon={Store}       label="Portal Tokko" />
          <NavItem to="/ventas/clientes"     icon={Users}       label="Clientes Ventas" />
        </Section>
      )}

      {/* Herramientas */}
      <Section label="Herramientas">
        <NavItem to="/indices" icon={BarChart2} label="Índices" />
        <NavItem to="/agente"  icon={Bot}       label="Agente IA" />
      </Section>

      {/* Admin */}
      {isAdmin && (
        <Section label="Administración">
          <NavItem to="/dashboard"   icon={LayoutDashboard} label="Dashboard Maestro" />
          <NavItem to="/finanzas"    icon={DollarSign}      label="Finanzas" />
          <NavItem to="/equipo"      icon={Settings}        label="Equipo" />
        </Section>
      )}

      {/* Gerencia (not admin) */}
      {isGerencia && !isAdmin && (
        <Section label="Gerencia">
          <NavItem to="/dashboard"   icon={LayoutDashboard} label="Dashboard Maestro" />
        </Section>
      )}

    </aside>
  )
}
