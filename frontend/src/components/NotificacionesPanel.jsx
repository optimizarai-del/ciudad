import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell, AlertTriangle, Clock, FileText, DollarSign, Calendar, X,
} from 'lucide-react'
import api from '../utils/api'


const TIPO_ICONO = {
  contrato_vencido:    AlertTriangle,
  contrato_por_vencer: Calendar,
  pago_mora:           DollarSign,
  evento_critico:      AlertTriangle,
}

const URGENCIA_STYLES = {
  critico: {
    dot:    'bg-danger',
    ring:   'bg-danger/10 text-danger',
    chip:   'chip-danger',
    label:  'Crítico',
  },
  pronto: {
    dot:    'bg-[#B8893A]',
    ring:   'bg-[#B8893A]/10 text-[#B8893A]',
    chip:   'chip-warn',
    label:  'Pronto',
  },
  normal: {
    dot:    'bg-muted',
    ring:   'bg-neutral-100 dark:bg-[#1E1E1E] text-muted',
    chip:   'chip-muted',
    label:  'Info',
  },
}


/**
 * Panel de notificaciones que se abre desde la campana del HUD.
 *
 * Lista contratos por vencer, contratos vencidos, pagos en mora y eventos
 * críticos del loop de recordatorios. Cada item es navegable y lleva al
 * detalle correspondiente.
 *
 * Props:
 *   anchorRef: ref del botón que lo dispara, para posicionarse y para
 *              detectar clicks afuera y cerrar.
 *   onClose:   callback cuando hay que cerrarlo.
 */
export default function NotificacionesPanel({ anchorRef, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const panelRef = useRef(null)
  const nav = useNavigate()

  useEffect(() => {
    api.get('/api/alertas/resumen')
      .then(r => setData(r.data))
      .catch(() => setData({ total: 0, criticos: 0, items: [] }))
      .finally(() => setLoading(false))
  }, [])

  // Click fuera → cerrar
  useEffect(() => {
    const handleClick = (e) => {
      if (!panelRef.current) return
      if (panelRef.current.contains(e.target)) return
      if (anchorRef?.current?.contains(e.target)) return
      onClose?.()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [anchorRef, onClose])

  // Escape → cerrar
  useEffect(() => {
    const onEsc = e => { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', onEsc)
    return () => document.removeEventListener('keydown', onEsc)
  }, [onClose])

  const irA = (item) => {
    onClose?.()
    if (item.link) nav(item.link)
  }

  return (
    <div
      ref={panelRef}
      className="absolute top-12 right-0 w-[420px] max-w-[90vw] max-h-[80vh] overflow-hidden flex flex-col
                 bg-white dark:bg-[#121212] border border-[#E5E5E5] dark:border-[#2A2A2A]
                 rounded-2xl shadow-lift z-50 animate-fade-in"
      onClick={e => e.stopPropagation()}
    >
      <div className="px-5 py-4 border-b border-[#E5E5E5] dark:border-[#2A2A2A] flex items-center justify-between shrink-0">
        <div>
          <h3 className="font-semibold text-[14px] tracking-tight">Notificaciones</h3>
          {data && (
            <p className="text-[11px] text-muted dark:text-gray-500 mt-0.5">
              {data.total === 0
                ? 'Todo al día.'
                : `${data.total} total${data.total !== 1 ? 'es' : ''}${data.criticos ? ` · ${data.criticos} crítico${data.criticos !== 1 ? 's' : ''}` : ''}`}
            </p>
          )}
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-[#1E1E1E] text-muted">
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <p className="p-8 text-center text-[12px] text-muted">Cargando…</p>
        ) : !data || data.items.length === 0 ? (
          <div className="p-10 text-center">
            <Bell size={28} className="mx-auto text-muted/30 mb-3" />
            <p className="text-[13px] text-muted">No tenés notificaciones nuevas.</p>
            <p className="text-[11px] text-muted/60 mt-1">Vencimientos, pagos atrasados y avisos aparecen acá.</p>
          </div>
        ) : (
          <ul className="divide-y divide-[#E5E5E5] dark:divide-[#2A2A2A]">
            {data.items.map(item => {
              const sty = URGENCIA_STYLES[item.urgencia] || URGENCIA_STYLES.normal
              const Icon = TIPO_ICONO[item.tipo] || FileText
              return (
                <li
                  key={item.id}
                  onClick={() => irA(item)}
                  className="px-5 py-3.5 flex items-start gap-3 cursor-pointer hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition relative"
                >
                  <div className={`w-9 h-9 rounded-xl grid place-items-center shrink-0 ${sty.ring}`}>
                    <Icon size={15} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[13px] font-medium leading-snug truncate">{item.titulo}</p>
                      <span className={`${sty.chip} text-[9px] !py-0 shrink-0`}>{sty.label}</span>
                    </div>
                    {item.descripcion && (
                      <p className="text-[12px] text-muted dark:text-gray-500 mt-0.5 line-clamp-2">
                        {item.descripcion}
                      </p>
                    )}
                    <div className="flex items-center gap-1.5 mt-1 text-[10px] text-muted dark:text-gray-500">
                      <Clock size={9} />
                      {item.fecha
                        ? new Date(item.fecha).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
                        : 'sin fecha'}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="px-5 py-3 border-t border-[#E5E5E5] dark:border-[#2A2A2A] shrink-0">
        <button
          className="w-full text-[12px] text-muted dark:text-gray-500 hover:text-primary dark:hover:text-white transition"
          onClick={() => { onClose?.(); nav('/recordatorios') }}
        >
          Ver todos en Recordatorios →
        </button>
      </div>
    </div>
  )
}
