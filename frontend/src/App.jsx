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

        {/* Ventas */}
        <Route path="/ventas/dashboard" element={
          <ProtectedRoute requireVentas><DashboardVentas /></ProtectedRoute>
        } />
        <Route path="/ventas/propiedades" element={
          <ProtectedRoute requireVentas><PropiedadesVenta /></ProtectedRoute>
        } />
        <Route path="/ventas/tokko" element={
          <ProtectedRoute requireVentas><Propiedades /></ProtectedRoute>
        } />
        <Route path="/ventas/clientes" element={
          <ProtectedRoute requireVentas><Clientes /></ProtectedRoute>
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
