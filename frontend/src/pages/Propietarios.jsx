import { useEffect, useMemo, useState } from 'react'
import { Plus, KeyRound, Mail, Phone, Building2, Search, X, Pencil } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const empty = {
  nombre:'', apellido:'', razon_social:'', documento:'',
  email:'', telefono:'', rol:'propietario', notas:'',
}

export default function Propietarios() {
  const [clientes, setClientes]   = useState([])
  const [propiedades, setProps]   = useState([])
  const [busqueda, setBusqueda]   = useState('')
  const [open, setOpen]           = useState(false)
  const [editing, setEditing]     = useState(null)

  const load = () => {
    api.get('/api/clientes').then(r => setClientes(r.data))
    api.get('/api/propiedades').then(r => setProps(r.data))
  }
  useEffect(() => { load() }, [])

  // Solo propietarios
  const propietarios = useMemo(
    () => clientes.filter(c => c.rol === 'propietario'),
    [clientes]
  )

  const propsPorPropietario = useMemo(() => {
    const map = {}
    for (const p of propiedades) {
      if (!p.propietario_id) continue
      ;(map[p.propietario_id] ||= []).push(p)
    }
    return map
  }, [propiedades])

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return propietarios
    return propietarios.filter(p => {
      const txt = [p.nombre, p.apellido, p.razon_social, p.documento, p.email, p.telefono]
        .filter(Boolean).join(' ').toLowerCase()
      return txt.includes(q)
    })
  }, [propietarios, busqueda])

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Cartera</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Propietarios.</h1>
              <p className="hero-sub">Listado de dueños y sus propiedades en cartera.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo propietario
            </button>
          </div>
        </header>

        {/* Búsqueda */}
        <div className="relative mb-6 max-w-md">
          <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            placeholder="Buscar por nombre, DNI, email..."
            className="input pl-10 pr-10"
          />
          {busqueda && (
            <button onClick={() => setBusqueda('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-primary">
              <X size={14} />
            </button>
          )}
        </div>

        {filtrados.length === 0 ? (
          <div className="card text-center py-20">
            <KeyRound size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">
              {busqueda ? 'No hay propietarios que coincidan con la búsqueda.' : 'Aún no hay propietarios cargados.'}
            </p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtrados.map(p => {
              const props = propsPorPropietario[p.id] || []
              const nombre = p.razon_social || `${p.nombre} ${p.apellido || ''}`.trim()
              return (
                <div key={p.id} className="card p-6 card-hover flex flex-col gap-3">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-[#B8893A]/10 grid place-items-center shrink-0">
                      <KeyRound size={16} className="text-[#8F6A2A]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-[15px] tracking-tight truncate">{nombre}</p>
                      {p.documento && <p className="text-[11px] text-muted">{p.documento}</p>}
                    </div>
                    <button className="btn-ghost p-1.5"
                      onClick={() => { setEditing(p); setOpen(true) }}>
                      <Pencil size={12} />
                    </button>
                  </div>

                  <div className="space-y-1 text-[12px] text-muted border-t border-border pt-3">
                    {p.email && (
                      <div className="flex items-center gap-2 truncate">
                        <Mail size={11} /> <span className="truncate">{p.email}</span>
                      </div>
                    )}
                    {p.telefono && (
                      <div className="flex items-center gap-2"><Phone size={11} /> {p.telefono}</div>
                    )}
                  </div>

                  <div className="border-t border-border pt-3">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-muted font-semibold mb-2">
                      {props.length} {props.length === 1 ? 'propiedad' : 'propiedades'}
                    </p>
                    {props.length === 0 ? (
                      <p className="text-[11px] text-muted/70">Sin propiedades asignadas</p>
                    ) : (
                      <ul className="space-y-1">
                        {props.slice(0,4).map(pr => (
                          <li key={pr.id} className="flex items-center gap-2 text-[12px]">
                            <Building2 size={11} className="text-muted shrink-0" />
                            <span className="truncate">{pr.direccion}</span>
                          </li>
                        ))}
                        {props.length > 4 && (
                          <li className="text-[11px] text-muted/70 italic">y {props.length - 4} más…</li>
                        )}
                      </ul>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {open && <Modal initial={editing} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
    </Layout>
  )
}

function Modal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...initial } : { ...empty })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form, rol: 'propietario' }
    try {
      if (initial) await api.patch(`/api/clientes/${initial.id}`, payload)
      else await api.post('/api/clientes', payload)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-8 w-full max-w-xl shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">{initial ? 'Editar propietario' : 'Nuevo propietario'}.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" required value={form.nombre || ''} onChange={set('nombre')} />
            </div>
            <div>
              <label className="label">Apellido</label>
              <input className="input" value={form.apellido || ''} onChange={set('apellido')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Razón social (si aplica)</label>
              <input className="input" value={form.razon_social || ''} onChange={set('razon_social')} />
            </div>
            <div>
              <label className="label">DNI / CUIT</label>
              <input className="input" value={form.documento || ''} onChange={set('documento')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" value={form.email || ''} onChange={set('email')} />
            </div>
            <div>
              <label className="label">Teléfono</label>
              <input className="input" value={form.telefono || ''} onChange={set('telefono')} />
            </div>
          </div>
          <div>
            <label className="label">Notas</label>
            <textarea rows={2} className="input resize-none" value={form.notas || ''} onChange={set('notas')} />
          </div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : (initial ? 'Guardar' : 'Crear')}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
