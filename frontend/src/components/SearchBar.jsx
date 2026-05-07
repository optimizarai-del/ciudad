import { Search, X } from 'lucide-react'

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
