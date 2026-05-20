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

// ─── Cache de respuestas GET ──────────────────────────────────────────────────
// Almacena en memoria las respuestas de endpoints estables durante 30 segundos.
// Evita que navegar entre páginas dispare la misma request múltiples veces.
// Se invalida completamente ante cualquier escritura (POST/PATCH/PUT/DELETE).
const _cache = new Map()          // url → { data, ts }
const CACHE_TTL = 30_000          // 30 segundos

// Prefijos de endpoints que se pueden cachear (solo GETs sin side-effects)
const CACHE_PREFIXES = [
  '/api/propiedades',
  '/api/clientes',
  '/api/contratos',
  '/api/indices',
  '/api/dashboard/hud',
  '/api/alertas',
  '/api/cobranza/resumen',
]

function isCacheable(url = '') {
  return CACHE_PREFIXES.some(p => url === p || url.startsWith(p + '?') || url.startsWith(p + '/'))
}

// ─────────────────────────────────────────────────────────────────────────────

const api = axios.create({
  baseURL: resolveApiBase(),
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('ciudad_token')
  if (token) config.headers.Authorization = `Bearer ${token}`

  // Servir desde cache para GET en endpoints estables
  const method = (config.method || 'get').toLowerCase()
  if (method === 'get' && isCacheable(config.url)) {
    const hit = _cache.get(config.url)
    if (hit && Date.now() - hit.ts < CACHE_TTL) {
      // Inyectar respuesta cacheada via adapter personalizado
      config.adapter = () =>
        Promise.resolve({
          data:       hit.data,
          status:     200,
          statusText: 'OK',
          headers:    {},
          config,
          request:    {},
        })
    }
  }

  return config
})

api.interceptors.response.use(
  r => {
    const method = (r.config.method || 'get').toLowerCase()

    if (method === 'get' && isCacheable(r.config.url)) {
      // Guardar en cache solo si vino de la red (no del adapter)
      if (!r.config.adapter) {
        _cache.set(r.config.url, { data: r.data, ts: Date.now() })
      }
    } else if (['post', 'put', 'patch', 'delete'].includes(method)) {
      // Cualquier escritura invalida todo el cache para que la próxima
      // lectura traiga datos frescos de la DB.
      _cache.clear()
    }

    return r
  },
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('ciudad_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

/** Invalida el cache manualmente (útil tras operaciones locales). */
export function invalidarCache() {
  _cache.clear()
}

export default api
