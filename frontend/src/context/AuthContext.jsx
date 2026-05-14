import { createContext, useContext, useEffect, useState } from 'react'
import api from '../utils/api'

const AuthContext = createContext()
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('ciudad_token')
    if (token) {
      api.get('/auth/me')
        .then(r => setUser(r.data))
        .catch(() => localStorage.removeItem('ciudad_token'))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email, password) => {
    const r = await api.post('/auth/login', { email, password })
    localStorage.setItem('ciudad_token', r.data.access_token)
    setUser(r.data.user)
  }

  const logout = () => {
    localStorage.removeItem('ciudad_token')
    setUser(null)
    window.location.href = '/login'
  }

  // admin_demo cuenta como admin/finanzas pero en su propio workspace aislado
  // (lo aísla el backend con is_demo). Si no lo incluyéramos, el usuario demo
  // no podría entrar a Equipo, Finanzas, etc. y vería redirecciones silenciosas.
  const isAdmin    = user?.role === 'admin' || user?.role === 'admin_demo'
  const isFinanzas = ['finanzas', 'admin', 'admin_demo'].includes(user?.role)

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, isAdmin, isFinanzas }}>
      {children}
    </AuthContext.Provider>
  )
}
