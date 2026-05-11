import axios from 'axios'

// Resolución de la URL del backend:
//   1. VITE_API_URL si está definida en build-time (recomendado en deploy).
//   2. Autodetectar a partir del hostname:
//        ciudad.optimizar-ia.com → https://api.ciudad.optimizar-ia.com
//      (cubre el caso donde el build perdió la env var en Easypanel).
//   3. Fallback a localhost:8000 para dev.
function resolveApiBase() {
  const fromEnv = import.meta.env.VITE_API_URL
  if (fromEnv) return fromEnv
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'ciudad.optimizar-ia.com') {
      return 'https://api.ciudad.optimizar-ia.com'
    }
    // Subdominio de preview o staging: api.<resto>
    if (host.endsWith('.optimizar-ia.com')) {
      return `https://api.${host}`
    }
  }
  return 'http://localhost:8000'
}

const api = axios.create({
  baseURL: resolveApiBase(),
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('ciudad_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ciudad_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
