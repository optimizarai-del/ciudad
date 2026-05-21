import { useState, useEffect } from 'react'
import { LayoutGrid, List } from 'lucide-react'


/**
 * Toggle entre vista de tarjetas y vista de tabla.
 *
 * Uso:
 *   const [vista, setVista] = useVistaPersistida('propiedades', 'cards')
 *   <ViewToggle vista={vista} onChange={setVista} />
 *
 *   {vista === 'cards' ? <RenderCards /> : <RenderTabla />}
 */
export default function ViewToggle({ vista, onChange, className = '' }) {
  const base =
    'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-[11px] font-medium ' +
    'transition-colors border border-[#E5E5E5] dark:border-[#2A2A2A]'
  const activo = 'bg-[#0A0A0A] text-white dark:bg-white dark:text-[#0A0A0A]'
  const inactivo =
    'bg-white dark:bg-[#141414] text-muted hover:bg-neutral-50 dark:hover:bg-[#1E1E1E]'

  return (
    <div className={`inline-flex rounded-full overflow-hidden ${className}`}>
      <button
        type="button"
        onClick={() => onChange('cards')}
        title="Vista de tarjetas"
        className={`${base} rounded-l-full ${vista === 'cards' ? activo : inactivo}`}
      >
        <LayoutGrid size={12} />
        Tarjetas
      </button>
      <button
        type="button"
        onClick={() => onChange('tabla')}
        title="Vista de tabla"
        className={`${base} rounded-r-full border-l-0 ${vista === 'tabla' ? activo : inactivo}`}
      >
        <List size={12} />
        Tabla
      </button>
    </div>
  )
}


/**
 * Hook para que la preferencia de vista persista por página y por usuario.
 *   const [vista, setVista] = useVistaPersistida('propiedades', 'cards')
 */
export function useVistaPersistida(key, defaultValue = 'cards') {
  const storageKey = `ciudad_vista_${key}`
  const [vista, setVistaState] = useState(() => {
    if (typeof window === 'undefined') return defaultValue
    return localStorage.getItem(storageKey) || defaultValue
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(storageKey, vista)
    }
  }, [storageKey, vista])

  return [vista, setVistaState]
}
