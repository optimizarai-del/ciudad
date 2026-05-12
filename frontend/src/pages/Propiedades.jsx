import { useEffect, useMemo, useState } from 'react'
import { Plus, Building2, Trash2, Pencil, X, MapPin, Home, RefreshCw, Image as ImageIcon, FileDown } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import SearchBar, { match } from '../components/SearchBar'
import AdjuntosModal from '../components/AdjuntosModal'
import api from '../utils/api'

const TIPOS = ['departamento','casa','local','oficina','galpon','campo']
const TIPO_LABEL = {
  departamento: 'Departamento',
  casa: 'Casa',
  local: 'Local',
  oficina: 'Oficina / Consultorio',
  galpon: 'Galpón',
  campo: 'Campo',
}
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
  direccion:'', ciudad:'', provincia:'', tipo:'departamento',
  modalidad:'alquiler', estado:'disponible', superficie_m2:'', ambientes:'',
  descripcion:'', precio_alquiler:'', expensas:'',
  tasa_municipal:'', propietario_id:'',
}

export default function Propiedades() {
  const [list, setList] = useState([])
  const [filtered, setFiltered] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [filtroTipo, setFiltroTipo] = useState('todos')
  const [filtroPropietario, setFiltroPropietario] = useState('todos')
  const [clientes, setClientes] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [adjPropiedad, setAdjPropiedad] = useState(null)

  const load = () => {
    // Solo alquileres en esta página. Las propiedades de venta (incluyendo
    // las importadas de Tokko) viven en /ventas/propiedades.
    api.get('/api/propiedades').then(r =>
      setList((r.data || []).filter(p => p.modalidad !== 'venta' && !p.tokko_id))
    )
    api.get('/api/clientes').then(r => setClientes(r.data))
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    let r = [...list]
    if (filtroTipo !== 'todos') r = r.filter(p => p.tipo === filtroTipo)
    if (filtroPropietario !== 'todos') {
      r = r.filter(p => String(p.propietario_id || '') === String(filtroPropietario))
    }
    if (busqueda.trim()) {
      r = r.filter(p => match(busqueda,
        p.direccion, p.ciudad, p.provincia, p.tipo, p.propietario_nombre,
      ))
    }
    setFiltered(r)
  }, [list, filtroTipo, filtroPropietario, busqueda])

  // Lista de propietarios que aparecen en las propiedades — para el filtro.
  const propietariosEnLista = useMemo(() => {
    const map = new Map()
    list.forEach(p => {
      if (p.propietario_id && p.propietario_nombre) {
        map.set(p.propietario_id, p.propietario_nombre)
      }
    })
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]))
  }, [list])

  const del = async id => {
    if (!confirm('¿Eliminar propiedad?')) return
    await api.delete(`/api/propiedades/${id}`)
    load()
  }

  const descargarFicha = async (p) => {
    try {
      const r = await api.post(`/api/propiedades/${p.id}/ficha-pdf`, {}, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `ficha-${(p.direccion || `propiedad-${p.id}`).replace(/\s+/g, '-')}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo generar la ficha PDF.')
    }
  }

  return (
    <Layout>
      <div className="max-w-7xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Cartera de alquileres</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Propiedades.</h1>
              <p className="hero-sub">Inmuebles en alquiler — gestión, propietarios y disponibilidad.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nueva propiedad
            </button>
          </div>
        </header>

        {/* Búsqueda */}
        <div className="mb-4 max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda}
            placeholder="Buscar por dirección, ciudad, tipo o propietario…" />
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-2 mb-8">
          <FilterPill active={filtroTipo === 'todos'} onClick={() => setFiltroTipo('todos')}
            label={`Todos (${list.length})`} />
          {TIPOS.map(t => (
            <FilterPill key={t} active={filtroTipo === t} onClick={() => setFiltroTipo(t)}
              label={`${TIPO_LABEL[t]} (${list.filter(p => p.tipo === t).length})`} />
          ))}
          {propietariosEnLista.length > 0 && (
            <>
              <div className="w-px h-6 bg-border mx-1" />
              <select
                className="input !w-auto !py-1.5 text-[12px]"
                value={filtroPropietario}
                onChange={e => setFiltroPropietario(e.target.value)}
              >
                <option value="todos">Todos los propietarios</option>
                {propietariosEnLista.map(([id, nombre]) => (
                  <option key={id} value={id}>{nombre}</option>
                ))}
              </select>
            </>
          )}
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
                  <div className="w-10 h-10 rounded-2xl bg-neutral-100 dark:bg-[#1E1E1E] grid place-items-center shrink-0">
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
                  <p className="text-[11px] text-muted mt-1">{TIPO_LABEL[p.tipo] || p.tipo} {p.superficie_m2 ? `· ${p.superficie_m2} m²` : ''} {p.ambientes ? `· ${p.ambientes} amb.` : ''}</p>
                  {p.propietario_nombre && (
                    <p className="text-[11px] text-muted mt-1 flex items-center gap-1">
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary/40" />
                      <span className="font-medium">Propietario:</span> {p.propietario_nombre}
                    </p>
                  )}
                </div>

                {/* Precios */}
                <div className="border-t border-border pt-3 flex gap-4 flex-wrap">
                  {p.precio_alquiler > 0 && (
                    <div>
                      <p className="stat-label">Alquiler</p>
                      <p className="stat-value text-lg">${p.precio_alquiler?.toLocaleString('es-AR')}</p>
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
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#B8893A]/10 text-[#8F6A2A] border border-[#B8893A]/30">
                      <RefreshCw size={9} /> Tokko · {p.tokko_id}
                    </span>
                  </div>
                )}

                {/* Acciones */}
                <div className="flex gap-2 mt-auto">
                  <button className="btn-secondary flex-1 text-[12px] py-2"
                    onClick={() => { setEditing(p); setOpen(true) }}>
                    <Pencil size={12} /> Editar
                  </button>
                  <button className="btn-ghost py-2 px-3" title="Fotos y documentos"
                    onClick={() => setAdjPropiedad(p)}>
                    <ImageIcon size={12} />
                  </button>
                  <button className="btn-ghost py-2 px-3" title="Descargar ficha PDF"
                    onClick={() => descargarFicha(p)}>
                    <FileDown size={12} />
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

      {adjPropiedad && (
        <AdjuntosModal
          propiedad={adjPropiedad}
          onClose={() => setAdjPropiedad(null)}
        />
      )}
    </Layout>
  )
}

function FilterPill({ active, onClick, label }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[12px] font-medium tracking-tight transition
        ${active ? 'bg-primary text-white dark:bg-white dark:text-primary' : 'bg-white dark:bg-[#141414] border border-border dark:border-[#2A2A2A] text-muted hover:bg-neutral-50 dark:hover:bg-[#1A1A1A]'}`}>
      {label}
    </button>
  )
}

function Modal({ initial, clientes, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...initial } : { ...empty })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [clientesLocal, setClientesLocal] = useState(clientes)
  const [creandoProp, setCreandoProp] = useState(false)
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  // Mantener sincronizado si el padre recarga la lista
  useEffect(() => { setClientesLocal(clientes) }, [clientes])

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    // Convertir numéricos
    ;['superficie_m2','ambientes','precio_alquiler','precio_venta','expensas',
      'tasa_municipal','propietario_id'].forEach(k => {
      if (payload[k] === '' || payload[k] === null) payload[k] = null
      else payload[k] = Number(payload[k]) || null
    })
    // Si la propiedad fue cargada antes de la unificación, sumamos lo que tuviera en
    // impuesto_inmobiliario al campo de tasas municipales y dejamos el otro en 0.
    if (payload.impuesto_inmobiliario) {
      payload.tasa_municipal = (Number(payload.tasa_municipal) || 0) + Number(payload.impuesto_inmobiliario)
      payload.impuesto_inmobiliario = 0
    }
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
          <div>
            <label className="label">Tipo *</label>
            <select className="input" value={form.tipo} onChange={set('tipo')} required>
              {TIPOS.map(t => <option key={t} value={t}>{TIPO_LABEL[t]}</option>)}
            </select>
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

          <div className="grid grid-cols-2 gap-3">
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
              <div className="flex items-center justify-between">
                <label className="label">Propietario</label>
                <button type="button"
                  onClick={() => setCreandoProp(true)}
                  className="text-[11px] text-primary dark:text-white hover:underline font-medium">
                  + Nuevo propietario
                </button>
              </div>
              <select className="input" value={form.propietario_id || ''} onChange={set('propietario_id')}>
                <option value="">Sin asignar</option>
                {clientesLocal.filter(c => c.rol === 'propietario').map(c => (
                  <option key={c.id} value={c.id}>{c.nombre} {c.apellido}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="divider !my-1" />
          <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">Costos mensuales</p>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Alquiler base $</label>
              <input className="input" type="number" value={form.precio_alquiler || ''} onChange={set('precio_alquiler')} />
            </div>
            <div>
              <label className="label">Expensas $</label>
              <input className="input" type="number" value={form.expensas || ''} onChange={set('expensas')} />
            </div>
            <div>
              <label className="label">Tasas municipales $</label>
              <input className="input" type="number"
                value={form.tasa_municipal || ''}
                onChange={set('tasa_municipal')}
                placeholder="Inmobiliario + ABL + alumbrado…" />
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

      {creandoProp && (
        <ModalNuevoPropietario
          onClose={() => setCreandoProp(false)}
          onSaved={nuevo => {
            setClientesLocal(prev => [...prev, nuevo])
            setForm(f => ({ ...f, propietario_id: nuevo.id }))
            setCreandoProp(false)
          }}
        />
      )}
    </div>
  )
}


function ModalNuevoPropietario({ onClose, onSaved }) {
  const [form, setForm] = useState({
    nombre: '', apellido: '', razon_social: '',
    documento: '', email: '', telefono: '',
    rol: 'propietario', notas: '',
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      const r = await api.post('/api/clientes', form)
      onSaved(r.data)
    } catch (ex) {
      setErr(ex.response?.data?.detail || 'Error al crear el propietario.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-md shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">Nuevo propietario.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" required value={form.nombre} onChange={set('nombre')} />
            </div>
            <div>
              <label className="label">Apellido</label>
              <input className="input" value={form.apellido} onChange={set('apellido')} />
            </div>
          </div>
          <div>
            <label className="label">Razón social (opcional)</label>
            <input className="input" value={form.razon_social} onChange={set('razon_social')} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">DNI / CUIT</label>
              <input className="input" value={form.documento} onChange={set('documento')} />
            </div>
            <div>
              <label className="label">Teléfono</label>
              <input className="input" value={form.telefono} onChange={set('telefono')} />
            </div>
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" value={form.email} onChange={set('email')} />
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Creando…' : 'Crear propietario'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
