import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Building2, FileText, Users, Calculator,
  BarChart2, Bot, TrendingUp, Settings, DollarSign,
  Home, CreditCard, Store, ChevronRight, KeyRound, Bell, Receipt, Landmark, Wrench, HardDrive
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

export default function Sidebar({ onNavigate }) {
  const { hasAlquileres, hasVentas, isAdmin, isGerencia, isAdminDemo, role } = useRole()

  // Cuando es drawer mobile, queremos que al tocar un item se cierre el drawer.
  // El padre (Layout) nos pasa onNavigate para eso. NavLink + click handler
  // simple porque el NavLink ya dispara la navegación.
  const handleClick = onNavigate ? () => onNavigate() : undefined

  return (
    <aside
      className="w-64 lg:w-60 h-[calc(100vh-3rem)] lg:h-full bg-white dark:bg-[#0A0A0A] border-r border-gray-100 dark:border-gray-900 flex flex-col py-4 px-3 overflow-y-auto"
      onClick={handleClick}
    >

      {/* Banner cuando estás logueado como admin_demo: workspace aislado */}
      {isAdminDemo && (
        <div className="mb-3 px-3 py-2 rounded-xl bg-[#B8893A]/10 border border-[#B8893A]/30">
          <p className="text-[10px] uppercase tracking-widest font-bold text-[#B8893A]">
            Modo Demo
          </p>
          <p className="text-[10px] text-muted mt-0.5">
            Solo ves datos de prueba. Tus cambios no afectan la data real.
          </p>
        </div>
      )}

      {/* Alquileres section */}
      {hasAlquileres && (
        <Section label="Alquileres">
          <NavItem to="/alquileres/dashboard"  icon={LayoutDashboard} label="Dashboard" />
          <NavItem to="/alquileres/propiedades" icon={Home}           label="Propiedades" />
          <NavItem to="/alquileres/contratos"   icon={FileText}       label="Contratos" />
          <NavItem to="/alquileres/cobranza"       icon={CreditCard}     label="Cobranza" />
          <NavItem to="/alquileres/liquidaciones"  icon={Receipt}        label="Liquidaciones" />
          <NavItem to="/alquileres/tasas"          icon={Landmark}       label="Tasas municipales" />
          <NavItem to="/alquileres/refacciones"    icon={Wrench}         label="Refacciones" />
          <NavItem to="/alquileres/clientes"       icon={Users}          label="Clientes" />
          <NavItem to="/alquileres/propietarios"   icon={KeyRound}       label="Propietarios" />
          <NavItem to="/calculadora"               icon={Calculator}     label="Calculadora" />
        </Section>
      )}

      {/* Ventas section */}
      {hasVentas && (
        <Section label="Ventas">
          <NavItem to="/ventas/dashboard"    icon={TrendingUp}  label="Dashboard" />
          <NavItem to="/ventas/propiedades"  icon={Building2}   label="Propiedades" />
          <NavItem to="/ventas/clientes"     icon={Users}       label="Clientes Ventas" />
        </Section>
      )}

      {/* Herramientas */}
      <Section label="Herramientas">
        <NavItem to="/indices"                         icon={BarChart2}  label="Índices" />
        <NavItem to="/agente"                          icon={Bot}        label="Agente IA" />
        <NavItem to="/recordatorios"                   icon={Bell}       label="Recordatorios" />
        <NavItem to="/herramientas/versiones-local"    icon={HardDrive}  label="Versiones local" />
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
