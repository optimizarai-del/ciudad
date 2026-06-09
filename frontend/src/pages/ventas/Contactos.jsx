import { useEffect, useState } from 'react'
import { Plus, X, Pencil, Trash2, Phone, Mail, Network, Building } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const TIPOS = ['colega', 'inmobiliaria', 'escribano', 'proveedor', 'otro']
const empty = { nombre: '', tipo: 'colega', telefono: '', email: '', empresa: '', notas: '' }

export default function Contactos() {
  const [list, setList] = useState([])
  const [vendedores, setVendedores] = useState([])
  const [me, setMe] = useState(null)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = () => {
    api.get('/api/ventas-crm/contactos').then(r => setList(r.data || []))
    api.get('/api/ventas-crm/me').then(r => setMe(r.data))
    api.get('/api/ventas-crm/vendedores').then(r => setVendedores(r.data || []))
  }
  useEffect(() => { load() }, [])

  const vendNombre = id => vendedores.find(v => v.id === id)?.nombre || `Vendedor #${id}`
  const del = async c => { if (!confirm('¿Eliminar contacto?')) return; await api.delete(`/api/ventas-crm/contactos/${c.id}`); load() }

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Red de contactos</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Contactos</h1>
              <p className="hero-sub">{me?.es_admin ? 'Red completa del equipo (todos los vendedores).' : 'Tu agenda de colegas y proveedores.'}</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}><Plus size={14} /> Nuevo contacto</button>
          </div>
        </header>

        {list.length === 0 ? (
          <div className="card text-center py-20"><Network size={36} className="mx-auto text-muted/30 mb-3" /><p className="text-muted text-[14px]">Aún no hay contactos en la red.</p></div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {list.map(c => (
              <div key={c.id} className="card p-4">
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <p className="font-medium text-[14px] truncate">{c.nombre}</p>
                    <span className="chip-muted capitalize mt-1">{c.tipo}</span>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => { setEditing(c); setOpen(true) }} className="p-1.5 text-muted hover:text-primary"><Pencil size={13} /></button>
                    <button onClick={() => del(c)} className="p-1.5 text-muted hover:text-danger"><Trash2 size={13} /></button>
                  </div>
                </div>
                <div className="mt-2 space-y-0.5">
                  {c.empresa && <div className="flex items-center gap-1.5 text-[12px] text-muted"><Building size={11} />{c.empresa}</div>}
                  {c.telefono && <div className="flex items-center gap-1.5 text-[12px] text-muted"><Phone size={11} />{c.telefono}</div>}
                  {c.email && <div className="flex items-center gap-1.5 text-[12px] text-muted"><Mail size={11} />{c.email}</div>}
                </div>
                {c.notas && <p className="text-[12px] mt-2">{c.notas}</p>}
                {me?.es_admin && <p className="text-[10px] text-muted mt-2 pt-2 border-t border-border">de {vendNombre(c.vendedor_id)}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
      {open && <ContactoModal initial={editing} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
    </Layout>
  )
}

function ContactoModal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...empty, ...initial } : { ...empty })
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(false)
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setErr(''); setLoading(true)
    if (!form.nombre?.trim()) { setErr('El nombre es obligatorio.'); setLoading(false); return }
    const payload = { nombre: form.nombre, tipo: form.tipo, telefono: form.telefono || null, email: form.email || null, empresa: form.empresa || null, notas: form.notas || null }
    try {
      if (initial) await api.patch(`/api/ventas-crm/contactos/${initial.id}`, payload)
      else await api.post('/api/ventas-crm/contactos', payload)
      onSaved()
    } catch (e) { setErr(e.response?.data?.detail || 'Error.') } finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6"><h2 className="hero-title text-xl sm:text-2xl">{initial ? 'Editar contacto' : 'Nuevo contacto'}</h2><button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button></div>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Nombre *</label><input className="input" value={form.nombre || ''} onChange={set('nombre')} /></div>
            <div><label className="label">Tipo</label><select className="input" value={form.tipo} onChange={set('tipo')}>{TIPOS.map(t => <option key={t}>{t}</option>)}</select></div>
          </div>
          <div><label className="label">Empresa</label><input className="input" value={form.empresa || ''} onChange={set('empresa')} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Teléfono</label><input className="input" value={form.telefono || ''} onChange={set('telefono')} /></div>
            <div><label className="label">Email</label><input className="input" type="email" value={form.email || ''} onChange={set('email')} /></div>
          </div>
          <div><label className="label">Notas</label><textarea className="input resize-none" rows={2} value={form.notas || ''} onChange={set('notas')} /></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1"><button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button><button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : 'Guardar'}</button></div>
        </form>
      </div>
    </div>
  )
}
