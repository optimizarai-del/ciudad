import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { RoleProvider } from './context/RoleContext'
import ProtectedRoute from './components/Layout/ProtectedRoute'

import Login              from './pages/Login'
import Register           from './pages/Register'
import Dashboard          from './pages/Dashboard'
import Propiedades        from './pages/Propiedades'
import Clientes           from './pages/Clientes'
import Contratos          from './pages/Contratos'
import Calculadora        from './pages/Calculadora'
import Agente             from './pages/Agente'
import Finanzas           from './pages/Finanzas'
import Equipo             from './pages/Equipo'
import Indices            from './pages/Indices'
import DashboardAlquileres from './pages/DashboardAlquileres'
import Cobranza           from './pages/Cobranza'
import DashboardVentas    from './pages/DashboardVentas'
import PropiedadesVenta   from './pages/PropiedadesVenta'
import Propietarios       from './pages/Propietarios'
import Liquidaciones      from './pages/Liquidaciones'
import Recordatorios      from './pages/Recordatorios'
import ActualizarTasas    from './pages/ActualizarTasas'
import Refacciones        from './pages/Refacciones'
import ClientesVentas     from './pages/ClientesVentas'
import VentasDashboardCRM from './pages/ventas/DashboardCRM'
import VentasCRM          from './pages/ventas/CRMVentas'
import VentasPedidos      from './pages/ventas/Pedidos'
import VentasConfig       from './pages/ventas/Configuracion'
import VentasMatches      from './pages/ventas/Matches'
import VentasTareas       from './pages/ventas/Tareas'
import VentasNotificaciones from './pages/ventas/Notificaciones'
import VentasClientes     from './pages/ventas/Clientes'
import VentasPropiedades  from './pages/ventas/Propiedades'
import VentasOperaciones  from './pages/ventas/Operaciones'
import VentasContactos    from './pages/ventas/Contactos'
import VersionesLocal     from './pages/VersionesLocal'
import HistorialAcciones  from './pages/HistorialAcciones'

export default function App() {
  return (
    <ThemeProvider>
    <AuthProvider>
    <BrowserRouter>
    <RoleProvider>
      <Routes>
        {/* Públicas */}
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Dashboard maestro */}
        <Route path="/dashboard" element={
          <ProtectedRoute><Dashboard /></ProtectedRoute>
        } />

        {/* Alquileres */}
        <Route path="/alquileres/dashboard" element={
          <ProtectedRoute requireAlquileres><DashboardAlquileres /></ProtectedRoute>
        } />
        <Route path="/alquileres/propiedades" element={
          <ProtectedRoute requireAlquileres><Propiedades /></ProtectedRoute>
        } />
        <Route path="/alquileres/contratos" element={
          <ProtectedRoute requireAlquileres><Contratos /></ProtectedRoute>
        } />
        <Route path="/alquileres/cobranza" element={
          <ProtectedRoute requireAlquileres><Cobranza /></ProtectedRoute>
        } />
        <Route path="/alquileres/clientes" element={
          <ProtectedRoute requireAlquileres><Clientes /></ProtectedRoute>
        } />
        <Route path="/alquileres/propietarios" element={
          <ProtectedRoute requireAlquileres><Propietarios /></ProtectedRoute>
        } />
        <Route path="/alquileres/liquidaciones" element={
          <ProtectedRoute requireAlquileres><Liquidaciones /></ProtectedRoute>
        } />
        <Route path="/alquileres/tasas" element={
          <ProtectedRoute requireAlquileres><ActualizarTasas /></ProtectedRoute>
        } />
        <Route path="/alquileres/refacciones" element={
          <ProtectedRoute requireAlquileres><Refacciones /></ProtectedRoute>
        } />
        <Route path="/alquileres/historial" element={
          <ProtectedRoute requireAlquileres><HistorialAcciones /></ProtectedRoute>
        } />
        <Route path="/recordatorios" element={
          <ProtectedRoute><Recordatorios /></ProtectedRoute>
        } />

        {/* Ventas */}
        <Route path="/ventas/dashboard" element={
          <ProtectedRoute requireVentas><DashboardVentas /></ProtectedRoute>
        } />
        <Route path="/ventas/propiedades" element={
          <ProtectedRoute requireVentas><PropiedadesVenta /></ProtectedRoute>
        } />
        {/* /ventas/tokko removida — Tokko se sincroniza desde el botón
           "Sync Tokko" dentro de /ventas/propiedades. Mantengo la ruta
           apuntando al mismo componente por compatibilidad de links viejos. */}
        <Route path="/ventas/tokko" element={
          <ProtectedRoute requireVentas><PropiedadesVenta /></ProtectedRoute>
        } />
        <Route path="/ventas/clientes" element={
          <ProtectedRoute requireVentas><ClientesVentas /></ProtectedRoute>
        } />

        {/* Ventas CRM — módulo aislado Fase 1 (tablas ventas_*) */}
        <Route path="/ventas-crm/dashboard" element={
          <ProtectedRoute requireVentas><VentasDashboardCRM /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/crm" element={
          <ProtectedRoute requireVentas><VentasCRM /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/pedidos" element={
          <ProtectedRoute requireVentas><VentasPedidos /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/configuracion" element={
          <ProtectedRoute requireVentas><VentasConfig /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/matches" element={
          <ProtectedRoute requireVentas><VentasMatches /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/tareas" element={
          <ProtectedRoute requireVentas><VentasTareas /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/notificaciones" element={
          <ProtectedRoute requireVentas><VentasNotificaciones /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/clientes" element={
          <ProtectedRoute requireVentas><VentasClientes /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/propiedades" element={
          <ProtectedRoute requireVentas><VentasPropiedades /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/operaciones" element={
          <ProtectedRoute requireVentas><VentasOperaciones /></ProtectedRoute>
        } />
        <Route path="/ventas-crm/contactos" element={
          <ProtectedRoute requireVentas><VentasContactos /></ProtectedRoute>
        } />

        {/* Legacy / shared routes */}
        <Route path="/propiedades" element={
          <ProtectedRoute><Propiedades /></ProtectedRoute>
        } />
        <Route path="/clientes" element={
          <ProtectedRoute><Clientes /></ProtectedRoute>
        } />
        <Route path="/contratos" element={
          <ProtectedRoute><Contratos /></ProtectedRoute>
        } />
        <Route path="/calculadora" element={
          <ProtectedRoute><Calculadora /></ProtectedRoute>
        } />
        <Route path="/agente" element={
          <ProtectedRoute><Agente /></ProtectedRoute>
        } />
        <Route path="/indices" element={
          <ProtectedRoute><Indices /></ProtectedRoute>
        } />

        {/* Finanzas */}
        <Route path="/finanzas" element={
          <ProtectedRoute requireFinanzas><Finanzas /></ProtectedRoute>
        } />

        {/* Admin */}
        <Route path="/equipo" element={
          <ProtectedRoute requireAdmin><Equipo /></ProtectedRoute>
        } />

        {/* Herramientas */}
        <Route path="/herramientas/versiones-local" element={
          <ProtectedRoute><VersionesLocal /></ProtectedRoute>
        } />

        {/* Redirects */}
        <Route path="/"  element={<Navigate to="/dashboard" replace />} />
        <Route path="*"  element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </RoleProvider>
    </BrowserRouter>
    </AuthProvider>
    </ThemeProvider>
  )
}
