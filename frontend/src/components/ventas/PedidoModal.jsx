import { useEffect, useState } from 'react'
import {
  X, Link2, Trash2, Plus, Phone, Mail, Clock, Sparkles, History,
  StickyNote, ClipboardList, Handshake, FileSignature, CheckCircle2,
} from 'lucide-react'
import api from '../../utils/api'

const fmtFecha = s => s ? new Date(s).toLocaleString('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'
const TL_ICON = { nota: StickyNote, pedido: ClipboardList, oferta: Handshake, operacion: FileSignature }

const COLUMNAS = ['nuevo', 'contactado', 'en_seguimiento', 'esperando_respuesta', 'negociando', 'cerrado', 'perdido']
const COL_LABEL = {
  nuevo: 'Nuevo', contactado: 'Contactado', en_seguimiento: 'En seguimiento',
  esperando_respuesta: 'Esperando respuesta', negociando: 'Negociando',
  cerrado: 'Cerrado', perdido: 'Perdido',
}
const TIPOS = ['casa', 'departamento', 'lote', 'local', 'oficina', 'galpon', 'campo', 'otro']
const ESTADO_VINC = { sugerida: 'Sugerida', mostrada: 'Mostrada', descartada: 'Descartada' }

const empty = {
  cliente_id: '', estado: 'nuevo', prioridad: 'media', tipo: 'casa',
  zona: '', precio_min_usd: '', precio_max_usd: '', dormitorios_min: '',
  superficie_min_m2: '', detalle: '',
}
const num = v => v === '' || v == null ? null : Number(v)
const fmtUSD = n => n ? 'USD ' + n.toLocaleString('es-AR') : '—'

export default function PedidoModal({ initial, clientes, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...empty, ...initial } : { ...empty })
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(false)
  const [ficha, setFicha] = useState(null)
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  // Ficha 360° del cliente asociado (solo al editar un pedido existente)
  const loadFicha = () => {
    if (initial?.cliente_id) {
      api.get(`/api/ventas-crm/clientes/${initial.cliente_id}/ficha`)
        .then(r => setFicha(r.data)).catch(() => setFicha(null))
    }
  }
  useEffect(() => { loadFicha() }, [initial?.cliente_id])

  const submit = async e => {
    e.preventDefault(); setErr(''); setLoading(true)
    if (!form.cliente_id) { setErr('Elegí un cliente.'); setLoading(false); return }
    const payload = {
      cliente_id: Number(form.cliente_id), estado: form.estado, prioridad: form.prioridad,
      tipo: form.tipo, zona: form.zona || null,
      precio_min_usd: num(form.precio_min_usd), precio_max_usd: num(form.precio_max_usd),
      dormitorios_min: num(form.dormitorios_min), superficie_min_m2: num(form.superficie_min_m2),
      detalle: form.detalle || null,
    }
    try {
      if (initial) await api.patch(`/api/ventas-crm/pedidos/${initial.id}`, payload)
      else await api.post('/api/ventas-crm/pedidos', payload)
      onSaved()
    } catch (e) { setErr(e.response?.data?.detail || 'Error al guardar.') }
    finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-2xl shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-xl sm:text-2xl">{initial ? 'Editar pedido' : 'Nuevo pedido'}</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        {/* Ficha del cliente (resumen, última interacción, acciones recomendadas) */}
        {initial && ficha && <ClienteResumen ficha={ficha} />}

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Cliente *</label>
            <select className="input" value={form.cliente_id || ''} onChange={set('cliente_id')}>
              <option value="">— elegir —</option>
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div><label className="label">Tipo</label>
              <select className="input" value={form.tipo} onChange={set('tipo')}>
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select></div>
            <div><label className="label">Estado</label>
              <select className="input" value={form.estado} onChange={set('estado')}>
                {COLUMNAS.map(c => <option key={c} value={c}>{COL_LABEL[c]}</option>)}
              </select></div>
            <div><label className="label">Prioridad</label>
              <select className="input" value={form.prioridad} onChange={set('prioridad')}>
                {['baja', 'media', 'alta'].map(p => <option key={p} value={p}>{p}</option>)}
              </select></div>
          </div>
          <div><label className="label">Zona / barrio buscado</label>
            <input className="input" value={form.zona || ''} onChange={set('zona')} /></div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div><label className="label">USD mín</label><input className="input" type="number" value={form.precio_min_usd ?? ''} onChange={set('precio_min_usd')} /></div>
            <div><label className="label">USD máx</label><input className="input" type="number" value={form.precio_max_usd ?? ''} onChange={set('precio_max_usd')} /></div>
            <div><label className="label">Dorm. mín</label><input className="input" type="number" value={form.dormitorios_min ?? ''} onChange={set('dormitorios_min')} /></div>
            <div><label className="label">m² mín</label><input className="input" type="number" value={form.superficie_min_m2 ?? ''} onChange={set('superficie_min_m2')} /></div>
          </div>
          <div><label className="label">Detalle de lo que pidió</label>
            <textarea className="input resize-none" rows={3} value={form.detalle || ''} onChange={set('detalle')} /></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : 'Guardar'}</button>
          </div>
        </form>

        {/* Vincular propiedades (solo al editar un pedido existente) */}
        {initial && <PropiedadesVinculadas pedidoId={initial.id} />}

        {/* Historial de acciones con el cliente — abajo del todo */}
        {initial && ficha && (
          <ClienteHistorial historial={ficha.historial}
            clienteId={initial.cliente_id} onAdded={loadFicha} />
        )}
      </div>
    </div>
  )
}

function ClienteResumen({ ficha }) {
  const c = ficha.cliente
  const info = ficha.info || {}
  return (
    <div className="mb-6 rounded-2xl border-2 border-[#B8893A]/30 bg-[#B8893A]/[0.06] dark:bg-[#B8893A]/[0.08] overflow-hidden">
      {/* Encabezado con alto contraste */}
      <div className="bg-primary text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-full bg-white/20 grid place-items-center text-[15px] font-bold shrink-0">
            {(c.nombre?.[0] || '?').toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="font-bold text-[15px] truncate flex items-center gap-1.5">
              {c.nombre}
              {c.es_operado && <CheckCircle2 size={14} className="text-emerald-300" />}
            </p>
            <p className="text-[11px] text-white/70 flex items-center gap-1">
              <Clock size={10} /> Última interacción: {fmtFecha(ficha.ultima_interaccion)}
              {ficha.dias_sin_contacto != null && ` · hace ${ficha.dias_sin_contacto}d`}
            </p>
          </div>
        </div>
      </div>

      {/* Datos de contacto con contraste */}
      <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Campo label="Teléfono" value={c.telefono} icon={Phone} />
        <Campo label="Email" value={c.email} icon={Mail} />
        <Campo label="Origen" value={c.origen} />
        <Campo label="Presup. máx" value={info.presupuesto_max} />
      </div>

      {/* Info relevante */}
      <div className="px-4 pb-2 flex flex-wrap gap-2">
        <span className="chip-dark">{info.pedidos_activos} pedido(s) activo(s)</span>
        {info.operaciones > 0 && <span className="chip-success">{info.operaciones} operación(es)</span>}
        <span className="chip-muted">{info.notas} nota(s)</span>
      </div>

      {/* Acciones recomendadas */}
      <div className="px-4 pb-4 pt-2">
        <p className="text-[10px] uppercase tracking-widest font-bold text-[#8F6A2A] mb-1.5 flex items-center gap-1">
          <Sparkles size={11} /> Acciones recomendadas
        </p>
        <ul className="space-y-1">
          {ficha.recomendaciones.map((r, i) => (
            <li key={i} className="text-[13px] flex items-start gap-1.5">
              <span className="text-[#B8893A] mt-0.5">→</span> {r}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function Campo({ label, value, icon: Icon }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400 font-semibold">{label}</p>
      <p className="text-[13px] font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1 truncate">
        {Icon && value && <Icon size={11} className="text-[#B8893A] shrink-0" />}
        {value || '—'}
      </p>
    </div>
  )
}

function ClienteHistorial({ historial, clienteId, onAdded }) {
  const [texto, setTexto] = useState('')
  const [saving, setSaving] = useState(false)

  const agregar = async (e) => {
    e.preventDefault()
    if (!texto.trim()) return
    setSaving(true)
    try {
      await api.post(`/api/ventas-crm/clientes/${clienteId}/notas`, { texto, origen: 'web' })
      setTexto(''); onAdded && onAdded()
    } catch { /* noop */ } finally { setSaving(false) }
  }

  const borrar = async (nid) => {
    if (!confirm('¿Eliminar esta nota?')) return
    try {
      await api.delete(`/api/ventas-crm/clientes/${clienteId}/notas/${nid}`)
      onAdded && onAdded()
    } catch { /* noop */ }
  }

  return (
    <div className="mt-6 pt-5 border-t border-border">
      <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-3 flex items-center gap-1.5">
        <History size={13} /> Historial de acciones
      </p>

      {/* Agregar nota (queda fechada automáticamente) */}
      <form onSubmit={agregar} className="flex gap-2 mb-4">
        <input className="input flex-1" placeholder="Agregar una nota… (ej: 09/06 llamé, coordino visita)"
          value={texto} onChange={e => setTexto(e.target.value)} />
        <button type="submit" className="btn-primary px-4" disabled={saving || !texto.trim()}>
          {saving ? '…' : <><StickyNote size={14} /> Agregar</>}
        </button>
      </form>

      {(!historial || historial.length === 0) ? (
        <p className="text-[12px] text-muted">Sin acciones registradas todavía.</p>
      ) : (
        <div className="space-y-2 max-h-64 overflow-auto pr-1">
          {historial.map((h, i) => {
            const Icon = TL_ICON[h.tipo] || StickyNote
            return (
              <div key={i} className="flex gap-2.5">
                <div className="w-7 h-7 rounded-full bg-neutral-100 dark:bg-[#1E1E1E] grid place-items-center shrink-0">
                  <Icon size={13} className="text-[#B8893A]" />
                </div>
                <div className="flex-1 min-w-0 pb-2 border-b border-border/50">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[13px]">{h.texto}</p>
                    {h.tipo === 'nota' && h.id && (
                      <button type="button" onClick={() => borrar(h.id)}
                        className="p-1 -mt-0.5 text-muted hover:text-danger shrink-0" title="Eliminar nota">
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                  <p className="text-[10px] text-muted mt-0.5">
                    {fmtFecha(h.fecha)}{h.origen ? ` · ${h.origen}` : ''}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function PropiedadesVinculadas({ pedidoId }) {
  const [vinc, setVinc] = useState([])
  const [props, setProps] = useState([])
  const [sel, setSel] = useState('')
  const [estado, setEstado] = useState('sugerida')

  const load = () => {
    api.get(`/api/ventas-crm/pedidos/${pedidoId}/propiedades`).then(r => setVinc(r.data || []))
    api.get('/api/ventas-crm/propiedades').then(r => setProps(r.data || []))
  }
  useEffect(() => { load() }, [pedidoId])

  const propInfo = id => props.find(p => p.id === id)
  const agregar = async () => {
    if (!sel) return
    try {
      await api.post(`/api/ventas-crm/pedidos/${pedidoId}/propiedades`, { propiedad_id: Number(sel), estado })
      setSel(''); load()
    } catch (e) { alert(e.response?.data?.detail || 'Error') }
  }
  const cambiar = async (pp, nuevo) => { await api.patch(`/api/ventas-crm/pedido-propiedad/${pp.id}?estado=${nuevo}`); load() }
  const quitar = async (pp) => { await api.delete(`/api/ventas-crm/pedido-propiedad/${pp.id}`); load() }

  return (
    <div className="mt-6 pt-5 border-t border-border">
      <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-3 flex items-center gap-1.5">
        <Link2 size={13} /> Propiedades vinculadas
      </p>
      <div className="flex gap-2 mb-3">
        <select className="input flex-1" value={sel} onChange={e => setSel(e.target.value)}>
          <option value="">— elegir propiedad —</option>
          {props.map(p => <option key={p.id} value={p.id}>{p.titulo || p.direccion || `#${p.id}`} — {fmtUSD(p.precio_usd)}</option>)}
        </select>
        <select className="input w-32" value={estado} onChange={e => setEstado(e.target.value)}>
          {Object.entries(ESTADO_VINC).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <button type="button" onClick={agregar} className="btn-primary px-3"><Plus size={15} /></button>
      </div>
      <div className="space-y-1.5">
        {vinc.length === 0 && <p className="text-[12px] text-muted">Sin propiedades vinculadas.</p>}
        {vinc.map(pp => {
          const p = propInfo(pp.propiedad_id)
          return (
            <div key={pp.id} className="flex items-center gap-2 bg-neutral-50 dark:bg-[#141414] rounded-xl px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] truncate">{p?.titulo || p?.direccion || `Propiedad #${pp.propiedad_id}`}</p>
                <p className="text-[11px] text-muted">{fmtUSD(p?.precio_usd)}</p>
              </div>
              <select className="text-[11px] bg-transparent border border-border rounded-lg px-1.5 py-1"
                value={pp.estado} onChange={e => cambiar(pp, e.target.value)}>
                {Object.entries(ESTADO_VINC).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              <button type="button" onClick={() => quitar(pp)} className="p-1 text-muted hover:text-danger"><Trash2 size={13} /></button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
