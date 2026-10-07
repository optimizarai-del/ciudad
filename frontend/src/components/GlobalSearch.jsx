import { useState, useEffect, useRef, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { Search, CornerDownLeft } from 'lucide-react'
import { match } from './SearchBar'

/**
 * Buscador global (paleta de comandos) para saltar a cualquier sección de la
 * plataforma. Se abre desde la lupa del header o con Ctrl/Cmd+K.
 *
 * `keywords` agrega términos alternativos para que, por ejemplo, "ganancia"
 * encuentre "Caja" y "dueños" encuentre "Propietarios".
 */
const SECCIONES = [
  { label: 'Dashboard', ruta: '/alquileres/dashboard', grupo: 'Alquileres', keywords: 'inicio resumen panel' },
  { label: 'Propiedades', ruta: '/alquileres/propiedades', grupo: 'Alquileres', keywords: 'inmuebles casas departamentos' },
  { label: 'Contratos', ruta: '/alquileres/contratos', grupo: 'Alquileres', keywords: 'alquiler locacion' },
  { label: 'Cobros', ruta: '/alquileres/cobranza', grupo: 'Alquileres', keywords: 'cobranza pagos cobrar recibo' },
  { label: 'Liquidaciones', ruta: '/alquileres/liquidaciones', grupo: 'Alquileres', keywords: 'propietarios entregar rendir' },
  { label: 'Caja', ruta: '/alquileres/caja', grupo: 'Alquileres', keywords: 'ingresos egresos ganancia dinero flujo' },
  { label: 'Tasas municipales', ruta: '/alquileres/tasas', grupo: 'Alquileres', keywords: 'impuestos abl municipio' },
  { label: 'Refacciones', ruta: '/alquileres/refacciones', grupo: 'Alquileres', keywords: 'arreglos reparaciones descuentos' },
  { label: 'Clientes', ruta: '/alquileres/clientes', grupo: 'Alquileres', keywords: 'inquilinos personas' },
  { label: 'Propietarios', ruta: '/alquileres/propietarios', grupo: 'Alquileres', keywords: 'duenos dueños' },
  { label: 'Historial', ruta: '/alquileres/historial', grupo: 'Alquileres', keywords: 'acciones auditoria' },
  { label: 'Calculadora', ruta: '/calculadora', grupo: 'Herramientas', keywords: 'ajuste indice calcular' },
  { label: 'Índices', ruta: '/indices', grupo: 'Herramientas', keywords: 'ipc icl inflacion' },
  { label: 'Agente IA', ruta: '/agente', grupo: 'Herramientas', keywords: 'asistente chat bot' },
  { label: 'Recordatorios', ruta: '/recordatorios', grupo: 'Herramientas', keywords: 'alertas avisos' },
  { label: 'Versiones local', ruta: '/herramientas/versiones-local', grupo: 'Herramientas', keywords: 'backup export import' },
  { label: 'Finanzas', ruta: '/finanzas', grupo: 'Administración', keywords: 'reportes dinero' },
  { label: 'Equipo', ruta: '/equipo', grupo: 'Administración', keywords: 'usuarios permisos colaboradores' },
  { label: 'Dashboard Maestro', ruta: '/dashboard', grupo: 'Administración', keywords: 'general gerencia' },
]

export default function GlobalSearch({ open, onClose }) {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)
  const inputRef = useRef(null)

  const resultados = useMemo(
    () => SECCIONES.filter(s => match(q, s.label, s.grupo, s.keywords)),
    [q]
  )

  useEffect(() => { if (open) { setQ(''); setSel(0); setTimeout(() => inputRef.current?.focus(), 30) } }, [open])
  useEffect(() => { setSel(0) }, [q])

  const ir = (s) => { if (s) { onClose(); nav(s.ruta) } }

  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel(i => Math.min(i + 1, resultados.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); ir(resultados[sel]) }
    else if (e.key === 'Escape') { e.preventDefault(); onClose() }
  }

  if (!open) return null

  return createPortal((
    <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
      onClick={onClose}>
      <div className="w-full max-w-lg card overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 border-b border-border">
          <Search size={16} className="text-muted shrink-0" />
          <input
            ref={inputRef} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey}
            placeholder="Buscar sección… (Cobros, Caja, Propietarios…)"
            className="flex-1 bg-transparent py-3.5 text-[14px] outline-none placeholder:text-muted"
          />
          <kbd className="text-[10px] text-muted border border-border rounded px-1.5 py-0.5">Esc</kbd>
        </div>

        <div className="max-h-[50vh] overflow-y-auto py-1">
          {resultados.length === 0 ? (
            <p className="text-[13px] text-muted text-center py-8">Sin resultados para "{q}"</p>
          ) : resultados.map((s, i) => (
            <button key={s.ruta} onClick={() => ir(s)} onMouseEnter={() => setSel(i)}
              className={`w-full flex items-center justify-between px-4 py-2.5 text-left transition ${
                i === sel ? 'bg-[#B8893A]/10' : 'hover:bg-neutral-50 dark:hover:bg-[#1A1A1A]'
              }`}>
              <span className="text-[14px]">{s.label}</span>
              <span className="flex items-center gap-2">
                <span className="text-[11px] text-muted">{s.grupo}</span>
                {i === sel && <CornerDownLeft size={13} className="text-muted" />}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  ), document.body)
}
