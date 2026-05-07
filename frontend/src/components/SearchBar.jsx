import { Search, X } from 'lucide-react'

/**
 * Normaliza un texto para búsqueda tolerante:
 *   - lowercase
 *   - sin acentos
 *   - puntos y comas convertidos a espacios
 *   - múltiples espacios colapsados
 * Así "av gaona" matchea "Av. Gaona 3100" y "Bolívar" matchea "bolivar".
 */
export function normalizar(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')   // saca acentos
    .replace(/[.,;]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * `match(query, ...campos)` → true si todos los tokens de la query aparecen
 * (en cualquier orden) dentro del texto unificado de los campos.
 */
export function match(query, ...campos) {
  const q = normalizar(query)
  if (!q) return true
  const txt = normalizar(campos.filter(Boolean).join(' '))
  return q.split(' ').every(tok => txt.includes(tok))
}

/**
 * Input de búsqueda reutilizable.
 * <SearchBar value={q} onChange={setQ} placeholder="..." />
 */
export default function SearchBar({ value, onChange, placeholder = 'Buscar…', className = '' }) {
  return (
    <div className={`relative ${className}`}>
      <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="input pl-10 pr-10"
      />
      {value && (
        <button onClick={() => onChange('')} type="button"
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-primary">
          <X size={14} />
        </button>
      )}
    </div>
  )
}
