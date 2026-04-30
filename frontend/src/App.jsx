import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/Layout/ProtectedRoute'

import Login       from './pages/Login'
import Register    from './pages/Register'
import Dashboard   from './pages/Dashboard'
import Propiedades from './pages/Propiedades'
import Clientes    from './pages/Clientes'
import Contratos   from './pages/Contratos'
import Calculadora from './pages/Calculadora'
import Agente      from './pages/Agente'
import Finanzas    from './pages/Finanzas'
import Equipo      from './pages/Equipo'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Públicas */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Autenticadas */}
          <Route path="/dashboard" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />
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
      </BrowserRouter>
    </AuthProvider>
  )
}
