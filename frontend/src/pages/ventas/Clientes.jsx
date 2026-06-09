import { useEffect, useMemo, useState } from 'react'
import { Plus, X, Pencil, Trash2, Phone, Mail, MessageSquarePlus, UserCircle, CheckCircle2 } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import SearchBar from '../../components/SearchBar'
import api from '../../utils/api'

const empty = { nombre: '', telefono: '', email: '', origen: '', observaciones: '' }

export default function Clientes() {
  const [list, setList] = useState([])
  const [filtro, setFiltro] = useState('todos') // todos | activos | operados
  const [busqueda, setBusqueda] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [notasDe, setNotasDe] = useState(null)

  const load = () => api.get('/api/ventas-crm/clientes').then(r => setList(r.data || []))
  useEffect(() => { load() }, [])

  const filtrados = useMemo(() => {
    let r = list
    if (filtro === 'operados') r = r.filter(c => c.es_operado)
    else if (filtro === 'activos') r = r.filter(c => !c.es_operado)
    if (busqueda.trim()) {
      const b = busqueda.toLowerCase()
      r = r.filter(c => [c.nombre, c.email, c.telefono, c.origen].some(v => (v || '').toLowerCase().includes(b)))
    }
    return r
  }, [list, filtro, busqueda])

  const del = async (c) => {
    if (!confirm(`¿Eliminar a ${c.nombre}?`)) return
    await api.delete(`/api/ventas-crm/clientes/${c.id}`); load()
  }

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">CRM Comercial</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Clientes</h1>
              <p className="hero-sub">Prospectos y clientes ya operados, con su hilo de notas.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo cliente
            </button>
          </div>
        </header>

        <div className="flex gap-2 mb-4">
          {[['todos', 'Todos'], ['activos', 'Activos'], ['operados', 'Operados']].map(([k, l]) => (
            <button key={k} onClick={() => setFiltro(k)}
              className={`px-4 py-1.5 rounded-full text-[12px] font-medium transition ${
                filtro === k ? 'bg-primary text-white' : 'bg-white dark:bg-[#1A1A1A] border border-border text-muted'
              }`}>{l}</button>
          ))}
        </div>
        <div className="mb-4 max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda} placeholder="Buscar por nombre, email, teléfono…" />
        </div>

        {filtrados.length === 0 ? (
          <div className="card text-center py-20">
            <UserCircle size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">Aún no hay clientes.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {filtrados.map(c => (
              <div key={c.id} className="card p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-full bg-primary text-white grid place-items-center text-[12px] font-semibold shrink-0">
                      {(c.nombre?.[0] || '?').toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-[14px] truncate flex items-center gap-1.5">
                        {c.nombre}
                        {c.es_operado && <CheckCircle2 size={13} className="text-green-600" />}
                      </p>
                      {c.origen && <p className="text-[11px] text-muted">vía {c.origen}</p>}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => { setEditing(c); setOpen(true) }} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-[#1E1E1E] text-muted"><Pencil size={13} /></button>
                    <button onClick={() => del(c)} className="p-1.5 rounded-lg hover:bg-danger/10 text-muted hover:text-danger"><Trash2 size={13} /></button>
                  </div>
                </div>
                <div className="mt-2 space-y-0.5">
                  {c.email && <div className="flex items-center gap-1.5 text-[12px] text-muted"><Mail size={11} />{c.email}</div>}
                  {c.telefono && <div className="flex items-center gap-1.5 text-[12px] text-muted"><Phone size={11} />{c.telefono}</div>}
                </div>
                <button onClick={() => setNotasDe(c)}
                  className="mt-3 w-full flex items-center justify-center gap-1.5 text-[12px] text-[#B8893A] border border-[#B8893A]/30 rounded-xl py-1.5 hover:bg-[#B8893A]/10">
                  <MessageSquarePlus size={13} /> Notas ({c.notas?.length || 0})
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {open && <ClienteModal initial={editing} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
      {notasDe && <NotasModal cliente={notasDe} onClose={() => { setNotasDe(null); load() }} />}
    </Layout>
  )
}

function ClienteModal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...empty, ...initial } : { ...empty })
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(false)
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setErr(''); setLoading(true)
    if (!form.nombre?.trim()) { setErr('El nombre es obligatorio.'); setLoading(false); return }
    const payload = { nombre: form.nombre, telefono: form.telefono || null, email: form.email || null, origen: form.origen || null, observaciones: form.observaciones || null }
    try {
      if (initial) await api.patch(`/api/ventas-crm/clientes/${initial.id}`, payload)
      else await api.post('/api/ventas-crm/clientes', payload)
      onSaved()
    } catch (e) { setErr(e.response?.data?.detail || 'Error al guardar.') }
    finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-xl sm:text-2xl">{initial ? 'Editar cliente' : 'Nuevo cliente'}</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div><label className="label">Nombre *</label><input className="input" value={form.nombre || ''} onChange={set('nombre')} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Teléfono</label><input className="input" value={form.telefono || ''} onChange={set('telefono')} /></div>
            <div><label className="label">Email</label><input className="input" type="email" value={form.email || ''} onChange={set('email')} /></div>
          </div>
          <div><label className="label">Origen</label><input className="input" placeholder="referido, web, instagram…" value={form.origen || ''} onChange={set('origen')} /></div>
          <div><label className="label">Observaciones</label><textarea className="input resize-none" rows={3} value={form.observaciones || ''} onChange={set('observaciones')} /></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : 'Guardar'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function NotasModal({ cliente, onClose }) {
  const [notas, setNotas] = useState([])
  const [texto, setTexto] = useState('')
  const load = () => api.get(`/api/ventas-crm/clientes/${cliente.id}/notas`).then(r => setNotas(r.data || []))
  useEffect(() => { load() }, [])
  const enviar = async e => {
    e.preventDefault()
    if (!texto.trim()) return
    await api.post(`/api/ventas-crm/clientes/${cliente.id}/notas`, { texto, origen: 'web' })
    setTexto(''); load()
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6 flex flex-col max-h-[85vh]" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="hero-title text-xl">Notas — {cliente.nombre}</h2>
            <p className="hero-sub text-[12px]">Historial de interacciones</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <div className="flex-1 overflow-auto space-y-2 mb-4">
          {notas.length === 0 && <p className="text-muted text-[13px] text-center py-8">Sin notas todavía.</p>}
          {notas.map(n => (
            <div key={n.id} className="bg-neutral-50 dark:bg-[#141414] rounded-xl p-3">
              <p className="text-[13px]">{n.texto}</p>
              <p className="text-[10px] text-muted mt-1">
                {new Date(n.created_at).toLocaleString('es-AR')} · {n.origen}
              </p>
            </div>
          ))}
        </div>
        <form onSubmit={enviar} className="flex gap-2">
          <input className="input flex-1" placeholder="Ej: se interesó en la casa del Centro…"
            value={texto} onChange={e => setTexto(e.target.value)} />
          <button className="btn-primary px-4"><MessageSquarePlus size={15} /></button>
        </form>
      </div>
    </div>
  )
}
