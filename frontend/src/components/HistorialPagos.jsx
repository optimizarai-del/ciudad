import { useEffect, useState } from 'react'
import { X, Plus, CheckCircle, Clock, AlertCircle, Circle, Pencil, Trash2, DollarSign } from 'lucide-react'
import api from '../utils/api'

const ESTADO_CONFIG = {
  pagado:   { label: 'Pagado',   cls: 'chip-success', icon: CheckCircle,   dot: 'bg-success' },
  pendiente:{ label: 'Pendiente',cls: 'chip-warn',    icon: Clock,         dot: 'bg-warn' },
  vencido:  { label: 'Vencido',  cls: 'chip-danger',  icon: AlertCircle,   dot: 'bg-danger' },
  parcial:  { label: 'Parcial',  cls: 'chip-gray',    icon: Circle,        dot: 'bg-[#888]' },
}

const emptyPago = {
  periodo: '', fecha_vencimiento: '', fecha_pago: '',
  monto_alquiler: '', monto_expensas: '', monto_impuestos: '',
  monto_municipal: '', monto_otros: '',
  estado: 'pendiente', notas: '',
}

export default function HistorialPagos({ contrato, onClose }) {
  const [pagos, setPagos]     = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editando, setEditando] = useState(null)

  const load = () => {
    setLoading(true)
    api.get(`/api/contratos/${contrato.id}/pagos`)
      .then(r => setPagos(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [contrato.id])

  const del = async id => {
    if (!confirm('¿Eliminar este pago?')) return
    await api.delete(`/api/pagos/${id}`)
    load()
  }

  const totales = pagos.reduce(
    (acc, p) => ({
      total: acc.total + (p.monto_total || 0),
      pagado: acc.pagado + (p.estado === 'pagado' ? p.monto_total || 0 : 0),
      pendiente: acc.pendiente + (p.estado !== 'pagado' ? p.monto_total || 0 : 0),
    }),
    { total: 0, pagado: 0, pendiente: 0 }
  )

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}>
      <div className="card w-full max-w-2xl shadow-lift animate-scale-in flex flex-col max-h-[90vh]"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="px-6 py-5 border-b border-[#E5E5E5] dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-2xl mb-0.5">Historial de pagos.</h2>
            <p className="text-[12px] text-[#737373] dark:text-[#7A7A7A]">
              {contrato.codigo || `Contrato #${contrato.id}`}
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2 mt-0.5"><X size={16} /></button>
        </div>

        {/* Resumen */}
        <div className="px-6 py-4 grid grid-cols-3 gap-3 shrink-0 border-b border-[#E5E5E5] dark:border-[#2A2A2A]">
          <SumCard label="Total facturado" value={totales.total} />
          <SumCard label="Cobrado" value={totales.pagado} color="success" />
          <SumCard label="Pendiente" value={totales.pendiente} color="warn" />
        </div>

        {/* Timeline */}
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
              <p className="text-[#737373] dark:text-[#7A7A7A] text-[14px] mb-4">
                No hay pagos registrados para este contrato.
              </p>
              <button className="btn-primary" onClick={() => { setEditando(null); setShowForm(true) }}>
                <Plus size={13} /> Registrar primer pago
              </button>
            </div>
          ) : (
            <div className="relative">
              {/* Línea de tiempo */}
              <div className="absolute left-[17px] top-4 bottom-4 w-px bg-[#E5E5E5] dark:bg-[#2A2A2A]" />

              <div className="space-y-3">
                {pagos.map((p, idx) => {
                  const cfg = ESTADO_CONFIG[p.estado] || ESTADO_CONFIG.pendiente
                  const Icon = cfg.icon
                  return (
                    <div key={p.id}
                      className="relative flex gap-4 p-4 rounded-2xl border border-[#E5E5E5] dark:border-[#2A2A2A] bg-white dark:bg-[#141414] hover:border-[#C8C8C8] dark:hover:border-[#3A3A3A] transition group">

                      {/* Dot */}
                      <div className={`w-8 h-8 rounded-full ${cfg.dot} grid place-items-center shrink-0 z-10`}>
                        <Icon size={13} className="text-white" />
                      </div>

                      {/* Info */}
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
                      </div>

                      {/* Total + acciones */}
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-semibold text-[14px] tracking-tight">
                          ${Number(p.monto_total || 0).toLocaleString('es-AR')}
                        </span>
                        <div className="opacity-0 group-hover:opacity-100 transition flex gap-1">
                          <button onClick={() => { setEditando(p); setShowForm(true) }}
                            className="p-1.5 rounded-lg hover:bg-[#F0F0F0] dark:hover:bg-[#2A2A2A] text-[#737373] dark:text-[#9A9A9A] transition">
                            <Pencil size={12} />
                          </button>
                          <button onClick={() => del(p.id)}
                            className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/30 text-[#737373] dark:text-[#9A9A9A] hover:text-danger transition">
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[#E5E5E5] dark:border-[#2A2A2A] shrink-0">
          <button className="btn-primary w-full"
            onClick={() => { setEditando(null); setShowForm(true) }}>
            <Plus size={13} /> Registrar pago
          </button>
        </div>
      </div>

      {/* Formulario de pago */}
      {showForm && (
        <FormPago
          contrato={contrato}
          initial={editando}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); load() }}
        />
      )}
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

function FormPago({ contrato, initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? {
    periodo: initial.periodo || '',
    fecha_vencimiento: initial.fecha_vencimiento || '',
    fecha_pago: initial.fecha_pago || '',
    monto_alquiler: initial.monto_alquiler || '',
    monto_expensas: initial.monto_expensas || '',
    monto_impuestos: initial.monto_impuestos || '',
    monto_municipal: initial.monto_municipal || '',
    monto_otros: initial.monto_otros || '',
    estado: initial.estado || 'pendiente',
    notas: initial.notas || '',
  } : { ...emptyPago })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const total = ['monto_alquiler','monto_expensas','monto_impuestos','monto_municipal','monto_otros']
    .reduce((s, k) => s + (Number(form[k]) || 0), 0)

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    ;['monto_alquiler','monto_expensas','monto_impuestos','monto_municipal','monto_otros'].forEach(k => {
      payload[k] = Number(payload[k]) || 0
    })
    payload.monto_total = total
    if (!payload.fecha_vencimiento) payload.fecha_vencimiento = null
    if (!payload.fecha_pago) payload.fecha_pago = null

    try {
      if (initial) await api.patch(`/api/pagos/${initial.id}`, payload)
      else await api.post(`/api/contratos/${contrato.id}/pagos`, payload)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-7 w-full max-w-md shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="hero-title text-xl">{initial ? 'Editar pago' : 'Registrar pago'}.</h3>
          <button onClick={onClose} className="btn-ghost p-2"><X size={15} /></button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Período</label>
              <input className="input" placeholder="2026-04" value={form.periodo} onChange={set('periodo')} />
            </div>
            <div>
              <label className="label">Estado</label>
              <select className="input" value={form.estado} onChange={set('estado')}>
                <option value="pendiente">Pendiente</option>
                <option value="pagado">Pagado</option>
                <option value="vencido">Vencido</option>
                <option value="parcial">Parcial</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Fecha venc.</label>
              <input className="input" type="date" value={form.fecha_vencimiento} onChange={set('fecha_vencimiento')} />
            </div>
            <div>
              <label className="label">Fecha pago</label>
              <input className="input" type="date" value={form.fecha_pago} onChange={set('fecha_pago')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Alquiler $</label>
              <input className="input" type="number" value={form.monto_alquiler} onChange={set('monto_alquiler')} />
            </div>
            <div>
              <label className="label">Expensas $</label>
              <input className="input" type="number" value={form.monto_expensas} onChange={set('monto_expensas')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Impuestos $</label>
              <input className="input" type="number" value={form.monto_impuestos} onChange={set('monto_impuestos')} />
            </div>
            <div>
              <label className="label">Tasa munic. $</label>
              <input className="input" type="number" value={form.monto_municipal} onChange={set('monto_municipal')} />
            </div>
          </div>

          {/* Total automático */}
          <div className="px-4 py-3 rounded-2xl bg-[#F5F5F5] dark:bg-[#1A1A1A] flex items-center justify-between">
            <span className="text-[12px] text-[#737373] dark:text-[#9A9A9A] font-medium">Total calculado</span>
            <span className="font-semibold text-[15px] tracking-tight">
              ${total.toLocaleString('es-AR')}
            </span>
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
