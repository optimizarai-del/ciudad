import { useEffect, useMemo, useState } from 'react'
import {
  Plus, UserCircle, Pencil, Trash2, X, Phone, Mail, Sparkles,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import SearchBar, { match } from '../components/SearchBar'
import api from '../utils/api'


// Pipeline comercial de ventas: el cliente arranca como prospecto, puede
// moverse a seguimiento, dejar una seña, cerrar (comprador) o descartarse.
const ETAPAS = ['prospecto', 'seguimiento', 'sena', 'comprador', 'no_interesado']

const ETAPA_LABEL = {
  prospecto:     'Prospecto',
  seguimiento:   'Seguimiento',
  sena:          'Dejó seña',
  comprador:     'Comprador',
  no_interesado: 'No le interesa',
}

const ETAPA_CHIP = {
  prospecto:     'chip-gray',
  seguimiento:   'chip-warn',
  sena:          'chip-success',
  comprador:     'chip-dark',
  no_interesado: 'chip-muted',
}

// Solo aplican estos dos roles en el área de ventas
const ROLES = ['comprador', 'vendedor']
const ROL_LABEL = { comprador: 'Comprador', vendedor: 'Vendedor' }

const empty = {
  nombre: '', apellido: '', razon_social: '', documento: '',
  email: '', telefono: '', rol: 'comprador',
  etapa_venta: 'prospecto', notas: '',
}

/**
 * Clientes del área de Ventas: compradores y vendedores con su etapa
 * en el pipeline (prospecto / seguimiento / dejó seña / comprador / no
 * interesado). Distinto de /alquileres/clientes que maneja inquilinos.
 */
export default function ClientesVentas() {
  const [list, setList]         = useState([])
  const [filtroEtapa, setFE]    = useState('todos')
  const [filtroRol, setFR]      = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [open, setOpen]         = useState(false)
  const [editing, setEditing]   = useState(null)

  const load = () => api.get('/api/clientes').then(r => setList(r.data || []))
  useEffect(() => { load() }, [])

  // Solo clientes con rol=comprador o vendedor
  const clientes = useMemo(
    () => list.filter(c => c.rol === 'comprador' || c.rol === 'vendedor'),
    [list]
  )

  const filtrados = useMemo(() => {
    let r = clientes
    if (filtroRol !== 'todos') r = r.filter(c => c.rol === filtroRol)
    if (filtroEtapa !== 'todos') r = r.filter(c => (c.etapa_venta || 'prospecto') === filtroEtapa)
    if (busqueda.trim()) {
      r = r.filter(c => match(busqueda,
        c.nombre, c.apellido, c.razon_social, c.documento, c.email, c.telefono, c.notas,
      ))
    }
    return r
  }, [clientes, filtroEtapa, filtroRol, busqueda])

  const cuentasEtapa = useMemo(() => {
    const acc = { prospecto: 0, seguimiento: 0, sena: 0, comprador: 0, no_interesado: 0 }
    for (const c of clientes) {
      const e = c.etapa_venta || 'prospecto'
      if (e in acc) acc[e]++
    }
    return acc
  }, [clientes])

  const del = async (c) => {
    if (!confirm(`¿Eliminar a ${c.nombre} ${c.apellido || ''}?`)) return
    try {
      await api.delete(`/api/clientes/${c.id}`)
      load()
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo eliminar.')
    }
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Pipeline comercial</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Clientes Ventas</h1>
              <p className="hero-sub">Compradores y vendedores, con etapa en el pipeline.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo cliente
            </button>
          </div>
        </header>

        {/* Pipeline visual: contadores por etapa */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3 mb-6">
          {ETAPAS.map(et => (
            <button
              key={et}
              onClick={() => setFE(filtroEtapa === et ? 'todos' : et)}
              className={`card p-3 sm:p-4 text-left transition hover:shadow-lift ${
                filtroEtapa === et ? 'ring-2 ring-[#B8893A]' : ''
              }`}
            >
              <p className="stat-label flex items-center gap-1.5">
                {et === 'sena' && <Sparkles size={10} className="text-[#B8893A]" />}
                {ETAPA_LABEL[et]}
              </p>
              <p className="stat-value text-xl sm:text-2xl mt-1">{cuentasEtapa[et]}</p>
            </button>
          ))}
        </div>

        {/* Búsqueda */}
        <div className="mb-4 max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda}
            placeholder="Buscar por nombre, DNI, email…" />
        </div>

        {/* Filtros por rol */}
        <div className="flex flex-wrap gap-2 mb-4">
          <FilterPill active={filtroRol === 'todos'} onClick={() => setFR('todos')}
            label={`Todos (${clientes.length})`} />
          {ROLES.map(r => (
            <FilterPill key={r} active={filtroRol === r} onClick={() => setFR(r)}
              label={`${ROL_LABEL[r]} (${clientes.filter(c => c.rol === r).length})`} />
          ))}
          {filtroEtapa !== 'todos' && (
            <button className="ml-1 text-[11px] text-muted underline" onClick={() => setFE('todos')}>
              Limpiar etapa: {ETAPA_LABEL[filtroEtapa]} ×
            </button>
          )}
        </div>

        {/* Lista */}
        {filtrados.length === 0 ? (
          <div className="card text-center py-20">
            <UserCircle size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px] mb-4">
              {busqueda || filtroEtapa !== 'todos' || filtroRol !== 'todos'
                ? 'No hay clientes que coincidan con los filtros.'
                : 'Aún no hay clientes de ventas. Empezá agregando un prospecto.'}
            </p>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Agregar cliente
            </button>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border dark:border-[#2A2A2A]">
                  <tr>
                    <th className="th">Nombre</th>
                    <th className="th hidden md:table-cell">Contacto</th>
                    <th className="th text-center">Etapa</th>
                    <th className="th text-center hidden lg:table-cell">Rol</th>
                    <th className="th w-28" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filtrados.map(c => {
                    const etapa = c.etapa_venta || 'prospecto'
                    return (
                      <tr key={c.id} className="hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition">
                        <td className="td">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-primary text-white grid place-items-center text-[11px] font-semibold shrink-0">
                              {(c.nombre?.[0] || '?').toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <p className="font-medium text-[13px] truncate">{c.nombre} {c.apellido}</p>
                              {c.razon_social && (
                                <p className="text-[11px] text-muted truncate">{c.razon_social}</p>
                              )}
                              {c.documento && (
                                <p className="text-[10px] text-muted/70">{c.documento}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="td hidden md:table-cell">
                          <div className="space-y-0.5">
                            {c.email && (
                              <div className="flex items-center gap-1.5 text-[12px] text-muted">
                                <Mail size={11} /> <span className="truncate">{c.email}</span>
                              </div>
                            )}
                            {c.telefono && (
                              <div className="flex items-center gap-1.5 text-[12px] text-muted">
                                <Phone size={11} /> {c.telefono}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="td text-center">
                          <span className={ETAPA_CHIP[etapa] || 'chip-muted'}>
                            {ETAPA_LABEL[etapa] || etapa}
                          </span>
                        </td>
                        <td className="td text-center hidden lg:table-cell">
                          <span className="chip-muted">{ROL_LABEL[c.rol] || c.rol}</span>
                        </td>
                        <td className="td">
                          <div className="flex gap-1 justify-end">
                            <button className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-[#1E1E1E] text-muted hover:text-primary"
                              onClick={() => { setEditing(c); setOpen(true) }}>
                              <Pencil size={13} />
                            </button>
                            <button className="p-1.5 rounded-lg hover:bg-danger/10 text-muted hover:text-danger"
                              onClick={() => del(c)}>
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {open && (
        <Modal
          initial={editing}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); load() }}
        />
      )}
    </Layout>
  )
}


function FilterPill({ active, onClick, label }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[12px] font-medium capitalize transition
        ${active
          ? 'bg-[#0A0A0A] dark:bg-white text-white dark:text-[#0A0A0A]'
          : 'bg-white dark:bg-[#1A1A1A] border border-border dark:border-[#2A2A2A] text-muted hover:bg-neutral-50 dark:hover:bg-[#252525]'
        }`}>
      {label}
    </button>
  )
}


function Modal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial
    ? { ...initial, etapa_venta: initial.etapa_venta || 'prospecto' }
    : { ...empty }
  )
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    // Validación mínima
    if (!payload.nombre?.trim()) {
      setErr('El nombre es obligatorio.'); setLoading(false); return
    }
    if (!['comprador', 'vendedor'].includes(payload.rol)) {
      payload.rol = 'comprador'
    }
    try {
      if (initial) await api.patch(`/api/clientes/${initial.id}`, payload)
      else await api.post('/api/clientes', payload)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-xl shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-xl sm:text-2xl">
            {initial ? 'Editar cliente' : 'Nuevo cliente de ventas'}
          </h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" required value={form.nombre || ''} onChange={set('nombre')} />
            </div>
            <div>
              <label className="label">Apellido</label>
              <input className="input" value={form.apellido || ''} onChange={set('apellido')} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Razón social (opcional)</label>
              <input className="input" value={form.razon_social || ''} onChange={set('razon_social')} />
            </div>
            <div>
              <label className="label">DNI / CUIT</label>
              <input className="input" value={form.documento || ''} onChange={set('documento')} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" value={form.email || ''} onChange={set('email')} />
            </div>
            <div>
              <label className="label">Teléfono</label>
              <input className="input" value={form.telefono || ''} onChange={set('telefono')} />
            </div>
          </div>

          <div className="divider !my-1" />
          <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">
            Pipeline comercial
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Rol *</label>
              <select className="input" value={form.rol || 'comprador'} onChange={set('rol')}>
                {ROLES.map(r => <option key={r} value={r}>{ROL_LABEL[r]}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Etapa *</label>
              <select className="input" value={form.etapa_venta || 'prospecto'} onChange={set('etapa_venta')}>
                {ETAPAS.map(et => (
                  <option key={et} value={et}>{ETAPA_LABEL[et]}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Notas / historial de la conversación</label>
            <textarea className="input resize-none" rows={4} value={form.notas || ''} onChange={set('notas')}
              placeholder="Ej: 14/05 — me llamó por la oficina de Viamonte, le mando ficha. 20/05 — confirma visita el sábado." />
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
