import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

// admin_demo es un sandbox aislado por workspace pero con todos los permisos.
// Si lo dejamos afuera de estas listas, las rutas redirigen a /dashboard sin
// avisar nada y el usuario demo no llega a Cobranza, Equipo, etc.
export default function ProtectedRoute({
  children,
  requireAdmin = false,
  requireFinanzas = false,
  requireAlquileres = false,
  requireVentas = false,
}) {
  const { user, loading, isAdmin, isFinanzas } = useAuth()

  if (loading) return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
    </div>
  )
  if (!user) return <Navigate to="/login" replace />
  if (requireAdmin && !isAdmin) return <Navigate to="/dashboard" replace />
  if (requireFinanzas && !isFinanzas) return <Navigate to="/dashboard" replace />

  if (requireAlquileres) {
    const role = user?.role || ''
    const allowed = ['admin', 'gerencia', 'alquileres', 'admin_demo'].includes(role)
    if (!allowed) return <Navigate to="/dashboard" replace />
  }

  if (requireVentas) {
    const role = user?.role || ''
    const allowed = ['admin', 'gerencia', 'ventas', 'admin_demo'].includes(role)
    if (!allowed) return <Navigate to="/dashboard" replace />
  }

  return children
}
