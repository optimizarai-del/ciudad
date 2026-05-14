import { createContext, useContext } from 'react'
import { useAuth } from './AuthContext'

const RoleContext = createContext({})

// admin_demo es un rol "sandbox" que tiene los mismos permisos que admin
// (puede ver todos los módulos) pero ve solo datos con is_demo=True. El
// aislamiento real lo aplica el backend; el frontend solo le da acceso a las
// pantallas. Por eso aparece en todas las áreas.
const AREA_ROLES = {
  alquileres: ['admin', 'gerencia', 'alquileres', 'admin_demo'],
  ventas:     ['admin', 'gerencia', 'ventas', 'admin_demo'],
  admin:      ['admin', 'admin_demo'],
  gerencia:   ['admin', 'gerencia', 'admin_demo'],
  agente:     ['admin', 'gerencia', 'alquileres', 'ventas', 'agente_ia', 'admin_demo'],
}

export function RoleProvider({ children }) {
  const { user } = useAuth()
  const role = user?.role || ''

  const can = (area) => AREA_ROLES[area]?.includes(role) ?? false
  const isAdmin = role === 'admin' || role === 'admin_demo'
  const isAdminDemo = role === 'admin_demo'
  const isGerencia = ['admin', 'gerencia', 'admin_demo'].includes(role)
  const hasAlquileres = AREA_ROLES.alquileres.includes(role)
  const hasVentas = AREA_ROLES.ventas.includes(role)

  return (
    <RoleContext.Provider value={{
      role, can, isAdmin, isAdminDemo, isGerencia, hasAlquileres, hasVentas,
    }}>
      {children}
    </RoleContext.Provider>
  )
}

export const useRole = () => useContext(RoleContext)
