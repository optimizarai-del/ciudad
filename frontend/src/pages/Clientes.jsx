import { useEffect, useState } from 'react'
import { Plus, Users, Pencil, Trash2, X, Phone, Mail } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const ROLES = ['propietario','inquilino','comprador','vendedor']
const ROL_CHIP = {
  propietario: 'chip-dark',
  inquilino:   'chip-gray',
  comprador:   'chip-success',
  vendedor:    'chip-warn',
}

const empty = { nombre:'', apellido:'', razon_social:'', documento:'', email:'', telefono:'', rol:'inquilino', notas:'' }

export default function Clientes() {
  const [list, setList] = useState([])
  const [filtro, setFiltro] = useState('todos')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = () => api.get('/api/clientes').then(r => setList(r.data))
  useEffect(() => { load() }, [])

  const filtered = filtro === 'todos' ? list : list.filter(c => c.rol === filtro)

  const del = async id => {
    if (!confirm('¿Eliminar cliente?')) return
    await api.delete(`/api/clientes/${id}`)
    load()
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Base de contactos</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Clientes.</h1>
              <p className="hero-sub">Propietarios, inquilinos, compradores y vendedores.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo cliente
            </button>
          </div>
        </header>

        {/* Filtros */}
        <div className="flex flex-wrap gap-2 mb-8">
          <FilterPill active={filtro === 'todos'} onClick={() => setFiltro('todos')} label={`Todos (${list.length})`} />
          {ROLES.map(r => (
            <FilterPill key={r} active={filtro === r} onClick={() => setFiltro(r)}
              label={`${r} (${list.filter(c => c.rol === r).length})`} />
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="card text-center py-24">
            <Users size={40} className="mx-auto text-muted/30 mb-4" />
            <p className="text-muted text-[15px] mb-4">No hay clientes en esta categoría.</p>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Agregar cliente
            </button>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead className="bg-neutral-50 border-b border-border">
                <tr>
                  <th className="th">Nombre</th>
                  <th className="th hidden md:table-cell">Contacto</th>
                  <th className="th hidden lg:table-cell">Documento</th>
                  <th className="th">Rol</th>
                  <th className="th w-20" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map(c => (
                  <tr key={c.id} className="hover:bg-neutral-50 transition">
                    <td className="td">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary text-white grid place-items-center text-[11px] font-semibold shrink-0">
                          {(c.nombre?.[0] || '?').toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-[13px]">{c.nombre} {c.apellido}</p>
                          {c.razon_social && <p className="text-[11px] text-muted">{c.razon_social}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="td hidden md:table-cell">
                      <div className="space-y-0.5">
                        {c.email && (
                          <div className="flex items-center gap-1.5">
                            <Mail size={11} className="text-muted" />
                            <span className="text-[12px] text-muted">{c.email}</span>
                          </div>
                        )}
                        {c.telefono && (
                          <div className="flex items-center gap-1.5">
                            <Phone size={11} className="text-muted" />
                            <span className="text-[12px] text-muted">{c.telefono}</span>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="td hidden lg:table-cell">
                      <span className="text-[12px] text-muted">{c.documento || '—'}</span>
                    </td>
                    <td className="td">
                      <span className={ROL_CHIP[c.rol] || 'chip-muted'}>{c.rol}</span>
                    </td>
                    <td className="td">
                      <div className="flex gap-1">
                        <button className="p-1.5 rounded-lg hover:bg-neutral-100 text-muted hover:text-primary transition"
                          onClick={() => { setEditing(c); setOpen(true) }}>
                          <Pencil size={13} />
                        </button>
                        <button className="p-1.5 rounded-lg hover:bg-danger/10 text-muted hover:text-danger transition"
                          onClick={() => del(c.id)}>
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {open && <Modal initial={editing} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
    </Layout>
  )
}

function FilterPill({ active, onClick, label }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[12px] font-medium tracking-tight transition capitalize
        ${active ? 'bg-primary text-white' : 'bg-white border border-border text-muted hover:bg-neutral-50'}`}>
      {label}
    </button>
  )
}

function Modal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...initial } : { ...empty })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      if (initial) await api.patch(`/api/clientes/${initial.id}`, form)
      else await api.post('/api/clientes', form)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-md shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">{initial ? 'Editar cliente' : 'Nuevo cliente'}.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" value={form.nombre} onChange={set('nombre')} required />
            </div>
            <div>
              <label className="label">Apellido</label>
              <input className="input" value={form.apellido || ''} onChange={set('apellido')} />
            </div>
          </div>
          <div>
            <label className="label">Razón social (empresa)</label>
            <input className="input" value={form.razon_social || ''} onChange={set('razon_social')} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">DNI / CUIT</label>
              <input className="input" value={form.documento || ''} onChange={set('documento')} />
            </div>
            <div>
              <label className="label">Rol</label>
              <select className="input" value={form.rol} onChange={set('rol')}>
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.email || ''} onChange={set('email')} />
          </div>
          <div>
            <label className="label">Teléfono / WhatsApp</label>
            <input className="input" placeholder="+54 9 11 ..." value={form.telefono || ''} onChange={set('telefono')} />
          </div>
          <div>
            <label className="label">Notas</label>
            <textarea className="input resize-none" rows={2} value={form.notas || ''} onChange={set('notas')} />
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : initial ? 'Guardar' : 'Crear cliente'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
