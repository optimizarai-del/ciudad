import { useEffect, useMemo, useState } from 'react'
import { Plus, X, Check, Trash2, CalendarClock, AlertTriangle } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ESTADO_CHIP = { pendiente: 'chip-muted', hecha: 'chip-success', vencida: 'chip-warn' }
const TIPO_LABEL = {
  seguimiento_postventa: 'Post-venta', llamado: 'Llamado', visita: 'Visita', otro: 'Otro',
}
const fmtFecha = s => s ? new Date(s + 'T00:00:00').toLocaleDateString('es-AR') : '—'

export default function Tareas() {
  const [list, setList] = useState([])
  const [clientes, setClientes] = useState([])
  const [filtro, setFiltro] = useState('pendientes')
  const [open, setOpen] = useState(false)

  const load = () => {
    api.get('/api/ventas-crm/tareas').then(r => setList(r.data || []))
    api.get('/api/ventas-crm/clientes').then(r => setClientes(r.data || []))
  }
  useEffect(() => { load() }, [])
  const cli = id => clientes.find(c => c.id === id)?.nombre || (id ? `Cliente #${id}` : '—')

  const filtrados = useMemo(() => {
    if (filtro === 'pendientes') return list.filter(t => t.estado !== 'hecha')
    if (filtro === 'vencidas') return list.filter(t => t.estado === 'vencida')
    if (filtro === 'hechas') return list.filter(t => t.estado === 'hecha')
    return list
  }, [list, filtro])

  const hecha = async (t) => { await api.patch(`/api/ventas-crm/tareas/${t.id}/hecha`); load() }
  const del = async (t) => { if (!confirm('¿Eliminar tarea?')) return; await api.delete(`/api/ventas-crm/tareas/${t.id}`); load() }

  const hoy = new Date().toISOString().slice(0, 10)

  return (
    <Layout>
      <div className="max-w-4xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Seguimiento</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Tareas</h1>
              <p className="hero-sub">Recordatorios y seguimiento post-venta. Las post-venta se generan solas al cerrar una operación.</p>
            </div>
            <button className="btn-primary" onClick={() => setOpen(true)}><Plus size={14} /> Nueva tarea</button>
          </div>
        </header>

        <div className="flex gap-2 mb-4">
          {[['pendientes', 'Pendientes'], ['vencidas', 'Vencidas'], ['hechas', 'Hechas'], ['todas', 'Todas']].map(([k, l]) => (
            <button key={k} onClick={() => setFiltro(k)}
              className={`px-4 py-1.5 rounded-full text-[12px] font-medium transition ${
                filtro === k ? 'bg-primary text-white' : 'bg-white dark:bg-[#1A1A1A] border border-border text-muted'
              }`}>{l}</button>
          ))}
        </div>

        {filtrados.length === 0 ? (
          <div className="card text-center py-20">
            <CalendarClock size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">No hay tareas para este filtro.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtrados.map(t => {
              const vencida = t.estado === 'pendiente' && t.vencimiento && t.vencimiento <= hoy
              return (
                <div key={t.id} className="card p-4 flex items-center gap-3">
                  <button onClick={() => hecha(t)} disabled={t.estado === 'hecha'}
                    className={`w-6 h-6 rounded-full border-2 grid place-items-center shrink-0 ${
                      t.estado === 'hecha' ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-border hover:border-[#B8893A]'
                    }`}>
                    {t.estado === 'hecha' && <Check size={13} />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className={`text-[14px] font-medium ${t.estado === 'hecha' ? 'line-through text-muted' : ''}`}>{t.descripcion}</p>
                    <p className="text-[11px] text-muted flex items-center gap-2">
                      <span className="chip-muted">{TIPO_LABEL[t.tipo] || t.tipo}</span>
                      {cli(t.cliente_id)} · vence {fmtFecha(t.vencimiento)}
                      {(t.estado === 'vencida' || vencida) && <span className="text-amber-600 flex items-center gap-0.5"><AlertTriangle size={11} /> vencida</span>}
                    </p>
                  </div>
                  <span className={ESTADO_CHIP[t.estado] || 'chip-muted'}>{t.estado}</span>
                  <button onClick={() => del(t)} className="p-1.5 text-muted hover:text-danger"><Trash2 size={13} /></button>
                </div>
              )
            })}
          </div>
        )}
      </div>
      {open && <TareaModal clientes={clientes} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
    </Layout>
  )
}

function TareaModal({ clientes, onClose, onSaved }) {
  const [form, setForm] = useState({ cliente_id: '', tipo: 'llamado', descripcion: '', vencimiento: '' })
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(false)
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setErr(''); setLoading(true)
    if (!form.descripcion.trim()) { setErr('Poné una descripción.'); setLoading(false); return }
    try {
      await api.post('/api/ventas-crm/tareas', {
        cliente_id: form.cliente_id ? Number(form.cliente_id) : null,
        tipo: form.tipo, descripcion: form.descripcion, vencimiento: form.vencimiento || null,
      })
      onSaved()
    } catch (e) { setErr(e.response?.data?.detail || 'Error.') } finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-md shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6"><h2 className="hero-title text-xl">Nueva tarea</h2><button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button></div>
        <form onSubmit={submit} className="space-y-4">
          <div><label className="label">Descripción *</label><input className="input" value={form.descripcion} onChange={set('descripcion')} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Tipo</label>
              <select className="input" value={form.tipo} onChange={set('tipo')}>
                {Object.entries(TIPO_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select></div>
            <div><label className="label">Vence</label><input className="input" type="date" value={form.vencimiento} onChange={set('vencimiento')} /></div>
          </div>
          <div><label className="label">Cliente (opcional)</label>
            <select className="input" value={form.cliente_id} onChange={set('cliente_id')}>
              <option value="">— ninguno —</option>{clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1"><button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button><button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : 'Crear'}</button></div>
        </form>
      </div>
    </div>
  )
}
