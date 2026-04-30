import { useEffect, useState } from 'react'
import { Plus, Building2, Trash2, Pencil, X, MapPin, Home, RefreshCw } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import TokkoSync from '../components/TokkoSync'
import api from '../utils/api'

const TIPOS = ['departamento','casa','local','campo']
const MODALIDADES = ['alquiler','venta','ambas']
const ESTADOS = ['disponible','ocupada','reservada','inactiva']

const ESTADO_CHIP = {
  disponible: 'chip-success',
  ocupada:    'chip-dark',
  reservada:  'chip-warn',
  inactiva:   'chip-muted',
}

const MODALIDAD_CHIP = {
  alquiler: 'chip-gray',
  venta:    'chip-dark',
  ambas:    'chip-muted',
}

const empty = {
  codigo:'', direccion:'', ciudad:'', provincia:'', tipo:'departamento',
  modalidad:'alquiler', estado:'disponible', superficie_m2:'', ambientes:'',
  descripcion:'', precio_alquiler:'', precio_venta:'', expensas:'',
  impuesto_inmobiliario:'', tasa_municipal:'', tokko_id:'', propietario_id:'',
}

export default function Propiedades() {
  const [list, setList] = useState([])
  const [filtered, setFiltered] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [filtroTipo, setFiltroTipo] = useState('todos')
  const [filtroModalidad, setFiltroModalidad] = useState('todos')
  const [clientes, setClientes] = useState([])
  const [tokkoOpen, setTokkoOpen] = useState(false)

  const load = () => {
    api.get('/api/propiedades').then(r => setList(r.data))
    api.get('/api/clientes').then(r => setClientes(r.data))
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    let r = [...list]
    if (filtroTipo !== 'todos') r = r.filter(p => p.tipo === filtroTipo)
    if (filtroModalidad !== 'todos') r = r.filter(p => p.modalidad === filtroModalidad)
    setFiltered(r)
  }, [list, filtroTipo, filtroModalidad])

  const del = async id => {
    if (!confirm('¿Eliminar propiedad?')) return
    await api.delete(`/api/propiedades/${id}`)
    load()
  }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Cartera inmobiliaria</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Propiedades.</h1>
              <p className="hero-sub">Todas las unidades en un solo lugar.</p>
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setTokkoOpen(true)}>
                <RefreshCw size={14} /> Sync Tokko
              </button>
              <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
                <Plus size={14} /> Nueva propiedad
              </button>
            </div>
          </div>
        </header>

        {/* Filtros */}
        <div className="flex flex-wrap gap-2 mb-8">
          <FilterPill active={filtroTipo === 'todos'} onClick={() => setFiltroTipo('todos')}
            label={`Todos (${list.length})`} />
          {TIPOS.map(t => (
            <FilterPill key={t} active={filtroTipo === t} onClick={() => setFiltroTipo(t)}
              label={`${t} (${list.filter(p => p.tipo === t).length})`} />
          ))}
          <div className="w-px bg-border mx-1" />
          {MODALIDADES.map(m => (
            <FilterPill key={m} active={filtroModalidad === m} onClick={() => setFiltroModalidad(m === filtroModalidad ? 'todos' : m)}
              label={m} />
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="card text-center py-24">
            <Building2 size={40} className="mx-auto text-muted/30 mb-4" />
            <p className="text-muted text-[15px] mb-4">Aún no hay propiedades cargadas.</p>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Agregar primera propiedad
            </button>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(p => (
              <div key={p.id} className="card p-6 card-hover flex flex-col gap-4">
                {/* Header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="w-10 h-10 rounded-2xl bg-neutral-100 grid place-items-center shrink-0">
                    <Home size={16} className="text-muted" />
                  </div>
                  <div className="flex gap-1.5 ml-auto">
                    <span className={ESTADO_CHIP[p.estado] || 'chip-muted'}>{p.estado}</span>
                    <span className={MODALIDAD_CHIP[p.modalidad] || 'chip-gray'}>{p.modalidad}</span>
                  </div>
                </div>

                {/* Info */}
                <div>
                  <p className="font-semibold text-[15px] tracking-tight leading-snug">{p.direccion}</p>
                  <div className="flex items-center gap-1 mt-1">
                    <MapPin size={11} className="text-muted shrink-0" />
                    <p className="text-[12px] text-muted capitalize">{p.ciudad}{p.provincia ? `, ${p.provincia}` : ''}</p>
                  </div>
                  <p className="text-[11px] text-muted mt-1 capitalize">{p.tipo} {p.superficie_m2 ? `· ${p.superficie_m2} m²` : ''} {p.ambientes ? `· ${p.ambientes} amb.` : ''}</p>
                </div>

                {/* Precios */}
                <div className="border-t border-border pt-3 flex gap-4 flex-wrap">
                  {p.precio_alquiler > 0 && (
                    <div>
                      <p className="stat-label">Alquiler</p>
                      <p className="stat-value text-lg">${p.precio_alquiler?.toLocaleString('es-AR')}</p>
                    </div>
                  )}
                  {p.precio_venta > 0 && (
                    <div>
                      <p className="stat-label">Venta</p>
                      <p className="stat-value text-lg">${p.precio_venta?.toLocaleString('es-AR')}</p>
                    </div>
                  )}
                  {p.expensas > 0 && (
                    <div>
                      <p className="stat-label">Expensas</p>
                      <p className="stat-value text-base">${p.expensas?.toLocaleString('es-AR')}</p>
                    </div>
                  )}
                </div>

                {p.tokko_id && (
                  <div className="flex items-center gap-1.5">
                    <span className="chip-muted text-[10px]">Tokko {p.tokko_id}</span>
                  </div>
                )}

                {/* Acciones */}
                <div className="flex gap-2 mt-auto">
                  <button className="btn-secondary flex-1 text-[12px] py-2"
                    onClick={() => { setEditing(p); setOpen(true) }}>
                    <Pencil size={12} /> Editar
                  </button>
                  <button className="btn-danger py-2 px-3" onClick={() => del(p.id)}>
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {open && (
        <Modal
          initial={editing}
          clientes={clientes}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); load() }}
        />
      )}

      {tokkoOpen && (
        <TokkoSync
          onClose={() => setTokkoOpen(false)}
          onSynced={() => load()}
        />
      )}
    </Layout>
  )
}

function FilterPill({ active, onClick, label }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[12px] font-medium tracking-tight transition
        ${active ? 'bg-primary text-white' : 'bg-white border border-border text-muted hover:bg-neutral-50'}`}>
      {label}
    </button>
  )
}

function Modal({ initial, clientes, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...initial } : { ...empty })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    // Convertir numéricos
    ;['superficie_m2','ambientes','precio_alquiler','precio_venta','expensas',
      'impuesto_inmobiliario','tasa_municipal','propietario_id'].forEach(k => {
      if (payload[k] === '' || payload[k] === null) payload[k] = null
      else payload[k] = Number(payload[k]) || null
    })
    try {
      if (initial) await api.patch(`/api/propiedades/${initial.id}`, payload)
      else await api.post('/api/propiedades', payload)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-2xl shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">{initial ? 'Editar propiedad' : 'Nueva propiedad'}.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Código</label>
              <input className="input" placeholder="DEP-001" value={form.codigo || ''} onChange={set('codigo')} />
            </div>
            <div>
              <label className="label">Tipo *</label>
              <select className="input" value={form.tipo} onChange={set('tipo')} required>
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Dirección *</label>
            <input className="input" placeholder="Av. Corrientes 1234, 5°A" value={form.direccion || ''} onChange={set('direccion')} required />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Ciudad</label>
              <input className="input" placeholder="CABA" value={form.ciudad || ''} onChange={set('ciudad')} />
            </div>
            <div>
              <label className="label">Provincia</label>
              <input className="input" placeholder="Buenos Aires" value={form.provincia || ''} onChange={set('provincia')} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Modalidad</label>
              <select className="input" value={form.modalidad} onChange={set('modalidad')}>
                {MODALIDADES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Estado</label>
              <select className="input" value={form.estado} onChange={set('estado')}>
                {ESTADOS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Ambientes</label>
              <input className="input" type="number" min="0" value={form.ambientes || ''} onChange={set('ambientes')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Superficie m²</label>
              <input className="input" type="number" value={form.superficie_m2 || ''} onChange={set('superficie_m2')} />
            </div>
            <div>
              <label className="label">Propietario</label>
              <select className="input" value={form.propietario_id || ''} onChange={set('propietario_id')}>
                <option value="">Sin asignar</option>
                {clientes.filter(c => c.rol === 'propietario').map(c => (
                  <option key={c.id} value={c.id}>{c.nombre} {c.apellido}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="divider !my-1" />
          <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">Costos mensuales</p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Alquiler base $</label>
              <input className="input" type="number" value={form.precio_alquiler || ''} onChange={set('precio_alquiler')} />
            </div>
            <div>
              <label className="label">Precio venta $</label>
              <input className="input" type="number" value={form.precio_venta || ''} onChange={set('precio_venta')} />
            </div>
            <div>
              <label className="label">Expensas $</label>
              <input className="input" type="number" value={form.expensas || ''} onChange={set('expensas')} />
            </div>
            <div>
              <label className="label">Impuesto inmobiliario $</label>
              <input className="input" type="number" value={form.impuesto_inmobiliario || ''} onChange={set('impuesto_inmobiliario')} />
            </div>
            <div>
              <label className="label">Tasa municipal $</label>
              <input className="input" type="number" value={form.tasa_municipal || ''} onChange={set('tasa_municipal')} />
            </div>
            <div>
              <label className="label">ID Tokko (venta)</label>
              <input className="input" placeholder="TKO-0000" value={form.tokko_id || ''} onChange={set('tokko_id')} />
            </div>
          </div>

          <div>
            <label className="label">Descripción</label>
            <textarea className="input resize-none" rows={2} value={form.descripcion || ''} onChange={set('descripcion')} />
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : initial ? 'Guardar cambios' : 'Crear propiedad'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
