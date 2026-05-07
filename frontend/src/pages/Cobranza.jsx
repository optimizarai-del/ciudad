import { useEffect, useMemo, useState } from 'react'
import Layout from '../components/Layout/Layout'
import SearchBar, { match } from '../components/SearchBar'
import api from '../utils/api'
import {
  CheckCircle, Clock, AlertCircle, ChevronLeft, ChevronRight,
  Phone, Mail, X, FileText, Download, Send, AlertTriangle,
} from 'lucide-react'

const ESTADO_CONFIG = {
  pagado:    { label: 'Cobrado',   bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', icon: CheckCircle },
  pendiente: { label: 'Pendiente', bg: 'bg-amber-50 dark:bg-amber-900/20',  text: 'text-amber-700 dark:text-amber-400', icon: Clock },
  vencido:   { label: 'Vencido',   bg: 'bg-red-50 dark:bg-red-900/20',      text: 'text-red-600 dark:text-red-400',     icon: AlertCircle },
  parcial:   { label: 'Parcial',   bg: 'bg-blue-50 dark:bg-blue-900/20',    text: 'text-blue-700 dark:text-blue-400',   icon: Clock },
}

const fmtMoney = n => '$' + Number(n || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 })
const prevMes = m => { const [y,mm]=m.split('-').map(Number); return mm===1?`${y-1}-12`:`${y}-${String(mm-1).padStart(2,'0')}` }
const nextMes = m => { const [y,mm]=m.split('-').map(Number); return mm===12?`${y+1}-01`:`${y}-${String(mm+1).padStart(2,'0')}` }
const mesLabel = m => { const [y,mm]=m.split('-').map(Number); return new Date(y,mm-1,1).toLocaleString('es-AR',{month:'long',year:'numeric'}) }

export default function Cobranza() {
  const hoy = new Date()
  const [mes, setMes]           = useState(`${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}`)
  const [items, setItems]       = useState([])
  const [resumen, setResumen]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const [filtro, setFiltro]     = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [registroOpen, setRegistroOpen] = useState(null)   // item activo
  const [resultado, setResultado] = useState(null)         // resultado del POST registrar-pago

  const cargar = async () => {
    setLoading(true)
    try {
      const [m, r] = await Promise.all([
        api.get(`/api/cobranza/mensual?mes=${mes}`),
        api.get(`/api/cobranza/resumen?mes=${mes}`),
      ])
      setItems(m.data)
      setResumen(r.data)
    } finally { setLoading(false) }
  }
  useEffect(() => { cargar() }, [mes])

  const filtrados = useMemo(() => {
    let r = filtro === 'todos' ? items : items.filter(p => p.estado === filtro)
    if (busqueda.trim()) {
      r = r.filter(p => match(
        busqueda,
        p.propiedad, p.propiedad_ciudad,
        p.inquilino, p.inquilino_email, p.inquilino_telefono,
        p.propietario, p.propietario_email,
        p.contrato_codigo,
      ))
    }
    return r
  }, [items, filtro, busqueda])

  const cuentas = useMemo(() => ({
    todos: items.length,
    pendiente: items.filter(p => p.estado === 'pendiente').length,
    pagado: items.filter(p => p.estado === 'pagado').length,
    vencido: items.filter(p => p.estado === 'vencido').length,
  }), [items])

  return (
    <Layout>
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 dark:text-gray-500 uppercase mb-1">Alquileres</p>
            <h1 className="text-3xl font-black">Cobranza</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setMes(prevMes(mes))} className="btn-ghost p-2"><ChevronLeft size={16} /></button>
            <span className="text-sm font-semibold capitalize min-w-[160px] text-center">{mesLabel(mes)}</span>
            <button onClick={() => setMes(nextMes(mes))} className="btn-ghost p-2"><ChevronRight size={16} /></button>
          </div>
        </div>

        {/* Resumen */}
        {resumen && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Total esperado" value={fmtMoney(resumen.total_esperado)} />
            <Stat label="Cobrado"        value={fmtMoney(resumen.cobrado)}    color="text-green-600 dark:text-green-400" />
            <Stat label="Pendiente"      value={fmtMoney(resumen.pendiente)}  color="text-amber-600" />
            <Stat label="Vencido"        value={fmtMoney(resumen.vencido)}    color={resumen.vencido > 0 ? 'text-red-500' : ''} />
          </div>
        )}

        {/* Búsqueda */}
        <div className="max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda}
            placeholder="Buscar por propiedad, inquilino, propietario..." />
        </div>

        {/* Filtros */}
        <div className="flex gap-2 flex-wrap">
          {['todos','pendiente','pagado','vencido'].map(f => (
            <button key={f} onClick={() => setFiltro(f)}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors
                ${filtro === f
                  ? 'bg-black dark:bg-white text-white dark:text-black'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}>
              {f === 'todos' ? 'Todos' : (ESTADO_CONFIG[f]?.label || f)}
              <span className="ml-1 opacity-60">{cuentas[f] ?? 0}</span>
            </button>
          ))}
        </div>

        {/* Tabla */}
        <div className="card overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-sm text-gray-400 dark:text-gray-500">Cargando...</div>
          ) : filtrados.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400 dark:text-gray-500">No hay contratos para este período.</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <th className="th text-left">Propiedad</th>
                  <th className="th text-left">Inquilino</th>
                  <th className="th text-left hidden lg:table-cell">Propietario</th>
                  <th className="th text-right">Monto</th>
                  <th className="th text-center">Estado</th>
                  <th className="th text-center">Acción</th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map((p, i) => {
                  const cfg = ESTADO_CONFIG[p.estado] || ESTADO_CONFIG.pendiente
                  const Icon = cfg.icon
                  return (
                    <tr key={p.contrato_id} className="border-b border-gray-50 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                      <td className="td">
                        <p className="font-medium text-sm">{p.propiedad}</p>
                        <p className="text-xs text-gray-400 dark:text-gray-500">{p.contrato_codigo} · {p.propiedad_ciudad}</p>
                      </td>
                      <td className="td">
                        <p className="text-sm">{p.inquilino}</p>
                        {p.inquilino_email && (
                          <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1 truncate max-w-[180px]">
                            <Mail size={10} />{p.inquilino_email}
                          </p>
                        )}
                      </td>
                      <td className="td hidden lg:table-cell">
                        <p className="text-sm">{p.propietario || '—'}</p>
                        {p.comision_porc > 0 && (
                          <p className="text-xs text-gray-400 dark:text-gray-500">Comisión {p.comision_porc}%</p>
                        )}
                      </td>
                      <td className="td text-right">
                        <p className="font-semibold text-sm">{fmtMoney(p.monto_total)}</p>
                      </td>
                      <td className="td text-center">
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>
                          <Icon size={11} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="td text-center">
                        {p.estado === 'pagado' ? (
                          <span className="text-xs text-green-600 dark:text-green-400">
                            ✓ {p.fecha_pago ? new Date(p.fecha_pago).toLocaleDateString('es-AR') : ''}
                          </span>
                        ) : (
                          <button onClick={() => setRegistroOpen(p)}
                            className="text-xs bg-black dark:bg-white text-white dark:text-black px-3 py-1.5 rounded-lg font-medium hover:opacity-80 transition">
                            Registrar pago
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {registroOpen && (
        <RegistrarPagoModal
          item={registroOpen}
          mes={mes}
          onClose={() => setRegistroOpen(null)}
          onSaved={(res) => { setRegistroOpen(null); setResultado(res); cargar() }}
        />
      )}
      {resultado && <ResultadoModal data={resultado} onClose={() => setResultado(null)} />}
    </Layout>
  )
}

function Stat({ label, value, color = '' }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-black ${color}`}>{value}</p>
    </div>
  )
}

function RegistrarPagoModal({ item, mes, onClose, onSaved }) {
  const [form, setForm] = useState({
    monto_alquiler: item.monto_total || 0,
    monto_expensas: 0,
    monto_tasas_municipales: 0,
    monto_otros: 0,
    fecha_pago: new Date().toISOString().slice(0, 10),
    notas: '',
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const total = ['monto_alquiler','monto_expensas','monto_tasas_municipales','monto_otros']
    .reduce((s, k) => s + (Number(form[k]) || 0), 0)
  // La comisión se calcula sólo sobre el alquiler. Los gastos pasantes
  // (expensas, tasas, otros) se cobran al inquilino y se derivan a quien
  // corresponda — no integran el neto al propietario.
  const alquiler = Number(form.monto_alquiler) || 0
  const comision = (item.comision_porc || 0) * alquiler / 100
  const neto = alquiler - comision

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true); setErr('')
    try {
      const payload = {
        periodo: mes,
        fecha_pago: form.fecha_pago || null,
        monto_alquiler: Number(form.monto_alquiler) || 0,
        monto_expensas: Number(form.monto_expensas) || 0,
        // El backend acepta los nombres legacy y los suma como tasas municipales
        monto_municipal: Number(form.monto_tasas_municipales) || 0,
        monto_impuestos: 0,
        monto_otros: Number(form.monto_otros) || 0,
        monto_total: total,
        notas: form.notas || null,
      }
      const r = await api.post(`/api/cobranza/${item.contrato_id}/registrar-pago`, payload)
      onSaved(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al registrar el pago.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-7 w-full max-w-lg shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="hero-title text-2xl mb-0.5">Registrar pago.</h2>
            <p className="text-[12px] text-[#737373]">{item.propiedad} · {item.contrato_codigo}</p>
            <p className="text-[12px] text-[#737373]">Inquilino: {item.inquilino}</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Período</label>
              <input className="input bg-neutral-50 dark:bg-[#1A1A1A]" value={mes} disabled />
            </div>
            <div>
              <label className="label">Fecha de pago</label>
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
            <div>
              <label className="label">Tasas municipales $</label>
              <input className="input" type="number"
                value={form.monto_tasas_municipales}
                onChange={set('monto_tasas_municipales')}
                placeholder="ABL + alumbrado + inmobiliario" />
            </div>
            <div>
              <label className="label">Otros conceptos $</label>
              <input className="input" type="number" value={form.monto_otros} onChange={set('monto_otros')} />
            </div>
          </div>

          <div>
            <label className="label">Notas</label>
            <textarea rows={2} className="input resize-none" value={form.notas} onChange={set('notas')} />
          </div>

          {/* Resumen */}
          <div className="rounded-2xl bg-[#F5F5F5] dark:bg-[#1A1A1A] p-4 space-y-1.5 text-[13px]">
            <div className="flex justify-between"><span className="text-muted">Total cobrado al inquilino</span><span className="font-semibold">{fmtMoney(total)}</span></div>
            <div className="flex justify-between"><span className="text-muted">Alquiler base</span><span>{fmtMoney(alquiler)}</span></div>
            <div className="flex justify-between"><span className="text-muted">Comisión ({item.comision_porc || 0}% s/ alquiler)</span><span>− {fmtMoney(comision)}</span></div>
            <div className="border-t border-border pt-1.5 flex justify-between font-semibold"><span>Neto al propietario</span><span className="text-[#B8893A]">{fmtMoney(neto)}</span></div>
          </div>

          <div className="text-[11px] text-muted bg-[#FAF8F3] dark:bg-[#141414] border border-[#E5E5E5] dark:border-[#2A2A2A] rounded-xl p-3 flex gap-2">
            <Send size={12} className="text-[#B8893A] shrink-0 mt-0.5" />
            <div>
              Al confirmar se generan dos comprobantes en PDF (recibo para el inquilino y
              liquidación para el propietario) y se intentan enviar por email a:
              <ul className="mt-1 space-y-0.5 list-disc list-inside opacity-80">
                <li><strong>Inquilino:</strong> {item.inquilino_email || 'sin email cargado'}</li>
                <li><strong>Propietario:</strong> {item.propietario_email || 'sin email cargado'}</li>
              </ul>
            </div>
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading || total <= 0}>
              {loading ? 'Procesando…' : 'Confirmar y emitir comprobantes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ResultadoModal({ data, onClose }) {
  const descargar = async (id) => {
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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[55] grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-7 w-full max-w-md shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="text-center mb-5">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 grid place-items-center mx-auto mb-3">
            <CheckCircle size={24} className="text-green-600 dark:text-green-400" />
          </div>
          <h3 className="hero-title text-2xl mb-0.5">Pago registrado.</h3>
          <p className="text-[12px] text-muted">
            Período {data.periodo} · {fmtMoney(data.monto_total)}
          </p>
        </div>

        <div className="rounded-2xl bg-[#F5F5F5] dark:bg-[#1A1A1A] p-4 mb-4 text-[13px] space-y-1">
          <div className="flex justify-between"><span className="text-muted">Total cobrado</span><span className="font-semibold">{fmtMoney(data.monto_total)}</span></div>
          <div className="flex justify-between"><span className="text-muted">Comisión</span><span>− {fmtMoney(data.comision)}</span></div>
          <div className="border-t border-border pt-1 flex justify-between font-semibold"><span>Neto al propietario</span><span className="text-[#B8893A]">{fmtMoney(data.neto_propietario)}</span></div>
        </div>

        <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-2">
          Comprobantes generados
        </p>
        <div className="space-y-2 mb-4">
          {data.comprobantes?.map(c => (
            <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl border border-[#E5E5E5] dark:border-[#2A2A2A]">
              <FileText size={16} className="text-[#737373] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium">
                  {c.tipo === 'inquilino' ? 'Recibo para el inquilino' : 'Liquidación para el propietario'}
                </p>
                <p className="text-[11px] text-muted truncate">
                  {c.destinatario}{c.email ? ` · ${c.email}` : ''}
                </p>
                <div className="flex items-center gap-1 mt-1">
                  {c.enviado_email ? (
                    <span className="inline-flex items-center gap-1 text-[10px] text-green-600 dark:text-green-400">
                      <Send size={9} /> Email enviado
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] text-amber-600">
                      <AlertTriangle size={9} /> {c.error || 'No enviado'}
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => descargar(c.id)}
                className="btn-secondary text-[11px] py-1.5 px-2.5 shrink-0">
                <Download size={11} /> PDF
              </button>
            </div>
          ))}
        </div>

        {!data.smtp_configurado && (
          <p className="text-[11px] text-muted bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900 rounded-xl p-3 mb-3">
            <strong>Email no configurado:</strong> los comprobantes quedaron guardados en la base
            y se pueden descargar en cualquier momento. Configurá SMTP_HOST/SMTP_USER/SMTP_PASS
            en <code>backend/.env</code> para activar el envío automático.
          </p>
        )}

        <button className="btn-primary w-full" onClick={onClose}>Cerrar</button>
      </div>
    </div>
  )
}
