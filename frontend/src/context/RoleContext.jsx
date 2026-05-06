import { createContext, useContext } from 'react'
import { useAuth } from './AuthContext'

const RoleContext = createContext({})

const AREA_ROLES = {
  alquileres: ['admin', 'gerencia', 'alquileres'],
  ventas:     ['admin', 'gerencia', 'ventas'],
  admin:      ['admin'],
  gerencia:   ['admin', 'gerencia'],
  agente:     ['admin', 'gerencia', 'alquileres', 'ventas', 'agente_ia'],
}

export function RoleProvider({ children }) {
  const { user } = useAuth()
  const role = user?.role || ''

  const can = (area) => AREA_ROLES[area]?.includes(role) ?? false
  const isAdmin = role === 'admin'
  const isGerencia = ['admin', 'gerencia'].includes(role)
  const hasAlquileres = AREA_ROLES.alquileres.includes(role)
  const hasVentas = AREA_ROLES.ventas.includes(role)

  return (
    <RoleContext.Provider value={{ role, can, isAdmin, isGerencia, hasAlquileres, hasVentas }}>
      {children}
    </RoleContext.Provider>
  )
}

export const useRole = () => useContext(RoleContext)
