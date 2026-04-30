import { NavLink } from 'react-router-dom'
import {
  LayoutGrid, Building2, FileText, Users,
  Calculator, Bot, TrendingUp, Settings
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import Logo from '../Logo'

const Item = ({ to, icon: Icon, label }) => (
  <NavLink to={to}
    className={({ isActive }) =>
      `nav-link ${isActive ? 'nav-link-active' : ''}`
    }>
    <Icon size={15} strokeWidth={1.8} />
    {label}
  </NavLink>
)

export default function Sidebar() {
  const { isAdmin, isFinanzas } = useAuth()

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-white min-h-[calc(100vh-3rem)] py-5 px-3 flex flex-col">

      <div className="section-label !mt-0">General</div>
      <Item to="/dashboard"   icon={LayoutGrid} label="Dashboard" />
      <Item to="/propiedades" icon={Building2}  label="Propiedades" />
      <Item to="/contratos"   icon={FileText}   label="Contratos" />
      <Item to="/clientes"    icon={Users}      label="Clientes" />

      <div className="section-label">Herramientas</div>
      <Item to="/calculadora" icon={Calculator} label="Calculadora" />
      <Item to="/agente"      icon={Bot}        label="Agente IA" />

      {isFinanzas && (
        <>
          <div className="section-label">Finanzas</div>
          <Item to="/finanzas" icon={TrendingUp} label="Finanzas" />
        </>
      )}

      {isAdmin && (
        <>
          <div className="section-label">Administración</div>
          <Item to="/equipo" icon={Settings} label="Equipo" />
        </>
      )}

      <div className="mt-auto pt-6 px-3">
        <Logo size="xs" tagline />
      </div>
    </aside>
  )
}
