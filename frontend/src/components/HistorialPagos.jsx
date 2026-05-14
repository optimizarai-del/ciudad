import { useEffect, useState } from 'react'
import { X, CheckCircle, Clock, AlertCircle, Circle, DollarSign, FileText, Download, Info } from 'lucide-react'
import api from '../utils/api'

const ESTADO_CONFIG = {
  pagado:   { label: 'Pagado',   cls: 'chip-success', icon: CheckCircle, dot: 'bg-success' },
  pendiente:{ label: 'Pendiente',cls: 'chip-warn',    icon: Clock,       dot: 'bg-warn' },
  vencido:  { label: 'Vencido',  cls: 'chip-danger',  icon: AlertCircle, dot: 'bg-danger' },
  parcial:  { label: 'Parcial',  cls: 'chip-gray',    icon: Circle,      dot: 'bg-[#888]' },
}

/**
 * Modal de SÓLO LECTURA con el historial de pagos del contrato.
 * El alta de pagos se hace exclusivamente desde Cobranza > "Registrar pago".
 */
export default function HistorialPagos({ contrato, onClose }) {
  const [pagos, setPagos]               = useState([])
  const [comprobantesPorPago, setCxP]   = useState({})
  const [loading, setLoading]           = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([
      api.get(`/api/contratos/${contrato.id}/pagos`),
      api.get(`/api/comprobantes/?contrato_id=${contrato.id}`),
    ])
      .then(([pp, cc]) => {
        setPagos(pp.data || [])
        const map = {}
        for (const c of (cc.data || [])) {
          ;(map[c.pago_id] ||= []).push(c)
        }
        setCxP(map)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [contrato.id])

  const totales = pagos.reduce(
    (acc, p) => ({
      total: acc.total + (p.monto_total || 0),
      pagado: acc.pagado + (p.estado === 'pagado' ? p.monto_total || 0 : 0),
      pendiente: acc.pendiente + (p.estado !== 'pagado' ? p.monto_total || 0 : 0),
    }),
    { total: 0, pagado: 0, pendiente: 0 }
  )

  const descargarComp = async (id) => {
    try {
      const r = await api.get(`/api/comprobantes/${id}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url; a.download = `comprobante-${id}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      alert('No se pudo descargar el comprobante.')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}>
      <div className="card w-full max-w-2xl shadow-lift animate-scale-in flex flex-col max-h-[90vh]"
        onClick={e => e.stopPropagation()}>

        <div className="px-6 py-5 border-b border-[#E5E5E5] dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-2xl mb-0.5">Historial de pagos.</h2>
            <p className="text-[12px] text-[#737373] dark:text-[#7A7A7A]">
              {contrato.codigo || `Contrato #${contrato.id}`} · sólo lectura
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2 mt-0.5"><X size={16} /></button>
        </div>

        <div className="px-6 pt-4 shrink-0">
          <div className="flex items-start gap-2 px-3 py-2 rounded-xl bg-blue-50 dark:bg-blue-900/15 border border-blue-200 dark:border-blue-900/40">
            <Info size={14} className="text-blue-600 dark:text-blue-300 shrink-0 mt-0.5" />
            <p className="text-[12px] text-blue-700 dark:text-blue-200 leading-snug">
              Esta vista es <strong>solo lectura</strong>. Los pagos se registran desde
              el módulo <strong>Cobranza</strong> con el botón <em>Registrar pago</em>.
            </p>
          </div>
        </div>

        <div className="px-6 py-4 grid grid-cols-3 gap-3 shrink-0 border-b border-[#E5E5E5] dark:border-[#2A2A2A]">
          <SumCard label="Total facturado" value={totales.total} />
          <SumCard label="Cobrado"         value={totales.pagado}    color="success" />
          <SumCard label="Pendiente"       value={totales.pendiente} color="warn" />
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-16 rounded-2xl bg-[#F0F0F0] dark:bg-[#1E1E1E] animate-pulse" />
              ))}
            </div>
          ) : pagos.length === 0 ? (
            <div className="text-center py-14">
              <DollarSign size={36} className="mx-auto text-[#C8C8C8] dark:text-[#3A3A3A] mb-3" />
              <p className="text-[#737373] dark:text-[#7A7A7A] text-[14px]">
                Aún no hay pagos registrados para este contrato.
              </p>
              <p className="text-[#737373] dark:text-[#7A7A7A] text-[12px] mt-1">
                Los pagos se registran desde el módulo <strong>Cobranza</strong>.
              </p>
            </div>
          ) : (
            <div className="relative">
              <div className="absolute left-[17px] top-4 bottom-4 w-px bg-[#E5E5E5] dark:bg-[#2A2A2A]" />
              <div className="space-y-3">
                {pagos.map(p => {
                  const cfg = ESTADO_CONFIG[p.estado] || ESTADO_CONFIG.pendiente
                  const Icon = cfg.icon
                  const comps = comprobantesPorPago[p.id] || []
                  return (
                    <div key={p.id}
                      className="relative flex gap-4 p-4 rounded-2xl border border-[#E5E5E5] dark:border-[#2A2A2A] bg-white dark:bg-[#141414]">
                      <div className={`w-8 h-8 rounded-full ${cfg.dot} grid place-items-center shrink-0 z-10`}>
                        <Icon size={13} className="text-white" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="font-semibold text-[13px] tracking-tight">
                            {p.periodo || `Pago #${p.id}`}
                          </span>
                          <span className={cfg.cls}>{cfg.label}</span>
                        </div>

                        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-[#737373] dark:text-[#7A7A7A]">
                          {p.fecha_vencimiento && <span>Vence: {p.fecha_vencimiento}</span>}
                          {p.fecha_pago        && <span>Pagado: {p.fecha_pago}</span>}
                          {p.monto_alquiler > 0 && <span>Alquiler: ${Number(p.monto_alquiler).toLocaleString('es-AR')}</span>}
                          {p.monto_expensas > 0 && <span>Expensas: ${Number(p.monto_expensas).toLocaleString('es-AR')}</span>}
                        </div>

                        {comps.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {comps.map(c => (
                              <button key={c.id} onClick={() => descargarComp(c.id)}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#F0F0F0] dark:bg-[#1E1E1E] text-[10px] hover:bg-[#E0E0E0] dark:hover:bg-[#2A2A2A] transition">
                                <FileText size={10} />
                                {c.tipo === 'inquilino' ? 'Recibo inquilino' : 'Liquidación propietario'}
                                <Download size={9} className="opacity-60" />
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-semibold text-[14px] tracking-tight">
                          ${Number(p.monto_total || 0).toLocaleString('es-AR')}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-[#E5E5E5] dark:border-[#2A2A2A] shrink-0">
          <button className="btn-secondary w-full" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  )
}

function SumCard({ label, value, color }) {
  const cls = color === 'success' ? 'text-success' : color === 'warn' ? 'text-warn' : 'text-[#0A0A0A] dark:text-[#F5F5F5]'
  return (
    <div className="rounded-2xl bg-[#F7F7F7] dark:bg-[#1A1A1A] p-3">
      <p className="stat-label mb-1">{label}</p>
      <p className={`text-lg font-semibold tracking-tight ${cls}`}>
        ${Number(value || 0).toLocaleString('es-AR')}
      </p>
    </div>
  )
}
