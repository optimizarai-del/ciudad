import { useEffect, useMemo, useState } from 'react'
import { Plus, Building2, Trash2, Pencil, X, MapPin, Home, RefreshCw, Image as ImageIcon, FileDown, Landmark, Eye } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import SearchBar, { match } from '../components/SearchBar'
import AdjuntosModal from '../components/AdjuntosModal'
import ModalTasaMSR from '../components/ModalTasaMSR'
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
  tasa_municipal:'', propietario_id:'', numero_referencia:'',
}

export default function Propiedades() {
  const [list, setList] = useState([])
  const [filtered, setFiltered] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [filtroTipo, setFiltroTipo] = useState('todos')
  const [filtroEstado, setFiltroEstado] = useState('todos')
  const [filtroPropietario, setFiltroPropietario] = useState('todos')
  const [clientes, setClientes] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [adjPropiedad, setAdjPropiedad] = useState(null)
  const [tasaMSR, setTasaMSR] = useState(null)  // {propiedad, modo: 'consultar'|'ver'}

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
    if (filtroEstado !== 'todos') r = r.filter(p => p.estado === filtroEstado)
    if (filtroPropietario !== 'todos') {
      r = r.filter(p => String(p.propietario_id || '') === String(filtroPropietario))
    }
    if (busqueda.trim()) {
      r = r.filter(p => match(busqueda,
        p.direccion, p.ciudad, p.provincia, p.tipo, p.propietario_nombre,
      ))
    }
    setFiltered(r)
  }, [list, filtroTipo, filtroEstado, filtroPropietario, busqueda])

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

  // Subconjunto que respeta búsqueda y propietario, pero NO el filtro de tipo.
  // Lo usamos para que los contadores de los tabs reflejen el resultado real
  // de tocar cada tab dado el resto de filtros activos.
  const subsetParaTabs = useMemo(() => {
    let r = [...list]
    if (filtroPropietario !== 'todos') {
      r = r.filter(p => String(p.propietario_id || '') === String(filtroPropietario))
    }
    if (busqueda.trim()) {
      r = r.filter(p => match(busqueda,
        p.direccion, p.ciudad, p.provincia, p.tipo, p.propietario_nombre,
      ))
    }
    return r
  }, [list, filtroPropietario, busqueda])

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
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Propiedades</h1>
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

        {/* Filtros por estado (disponibilidad) */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <FilterPill active={filtroEstado === 'todos'} onClick={() => setFiltroEstado('todos')}
            label={`Todas (${list.length})`} />
          {ESTADOS.map(e => (
            <FilterPill key={e} active={filtroEstado === e} onClick={() => setFiltroEstado(e)}
              label={`${e[0].toUpperCase() + e.slice(1)} (${list.filter(p => p.estado === e).length})`} />
          ))}
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-2 mb-8">
          <FilterPill active={filtroTipo === 'todos'} onClick={() => setFiltroTipo('todos')}
            label={`Todos (${subsetParaTabs.length})`} />
          {TIPOS.map(t => (
            <FilterPill key={t} active={filtroTipo === t} onClick={() => setFiltroTipo(t)}
              label={`${TIPO_LABEL[t]} (${subsetParaTabs.filter(p => p.tipo === t).length})`} />
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

                {/* Padrón municipal (si está cargado) */}
                {p.numero_referencia && (
                  <div className="text-[10px] text-muted dark:text-gray-500 flex items-center gap-1.5 -mt-1">
                    <Landmark size={10} />
                    <span>Padrón <span className="font-mono">{p.numero_referencia}</span></span>
                    {p.tasa_consultada_at && (
                      <span className="chip-success !text-[9px] !py-0">
                        Tasa al {new Date(p.tasa_consultada_at).toLocaleDateString('es-AR')}
                      </span>
                    )}
                  </div>
                )}

                {/* Acciones */}
                <div className="flex flex-wrap gap-2 mt-auto">
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
                  <button
                    className="btn-ghost py-2 px-3"
                    title={p.numero_referencia ? "Buscar tasa en Municipalidad de Santa Rosa" : "Cargá el Nº de referencia para usar este botón"}
                    onClick={() => setTasaMSR({ propiedad: p, modo: 'consultar' })}
                    disabled={!p.numero_referencia}
                  >
                    <Landmark size={12} />
                  </button>
                  {p.tasa_consultada_at && (
                    <button
                      className="btn-ghost py-2 px-3"
                      title="Ver última consulta de deuda"
                      onClick={() => setTasaMSR({ propiedad: p, modo: 'ver' })}
                    >
                      <Eye size={12} />
                    </button>
                  )}
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

      {tasaMSR && tasaMSR.modo === 'consultar' && (
        <ModalTasaMSR
          propiedad={tasaMSR.propiedad}
          onClose={() => setTasaMSR(null)}
          onActualizado={() => load()}
        />
      )}

      {tasaMSR && tasaMSR.modo === 'ver' && (
        <ModalTasaMSRCache
          propiedad={tasaMSR.propiedad}
          onClose={() => setTasaMSR(null)}
          onRefresh={() => setTasaMSR({ propiedad: tasaMSR.propiedad, modo: 'consultar' })}
        />
      )}
    </Layout>
  )
}


// Modal liviano que solo muestra el último resultado guardado, sin pedir
// captcha. Tiene un botón "Actualizar" que cambia al ModalTasaMSR pleno.
function ModalTasaMSRCache({ propiedad, onClose, onRefresh }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/api/propiedades/${propiedad.id}/tasa-msr-cache`)
      .then(r => setData(r.data))
      .finally(() => setLoading(false))
  }, [propiedad.id])

  const fmt = v => v == null ? '—' : `$ ${Number(v).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card w-full max-w-2xl shadow-lift animate-scale-in flex flex-col max-h-[90vh] my-6"
        onClick={e => e.stopPropagation()}>
        <div className="px-6 py-5 border-b border-border dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-2xl mb-0.5">Tasa MSR — Cache</h2>
            <p className="text-[12px] text-muted dark:text-gray-500">
              {propiedad.direccion}
              {data?.detalle?.consultado_at && (
                <> · Consultado: {new Date(data.detalle.consultado_at).toLocaleString('es-AR')}</>
              )}
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
          {loading ? (
            <p className="text-center text-muted py-8 text-[13px]">Cargando…</p>
          ) : !data?.disponible ? (
            <p className="text-center text-muted py-8 text-[13px]">No hay consulta previa.</p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="card p-4">
                  <p className="stat-label">Cuotas</p>
                  <p className="stat-value text-lg mt-1">{data.detalle.cantidad}</p>
                </div>
                <div className="card p-4">
                  <p className="stat-label">Total adeudado</p>
                  <p className="stat-value text-lg mt-1">{fmt(data.detalle.total)}</p>
                </div>
                <div className="card p-4">
                  <p className="stat-label">Tasa actual</p>
                  <p className="stat-value text-lg mt-1">{fmt(data.tasa_municipal_actual)}</p>
                </div>
              </div>

              {data.detalle.cuotas?.length > 0 && (
                <div className="card overflow-hidden">
                  <ul className="divide-y divide-border dark:divide-[#2A2A2A]">
                    {data.detalle.cuotas.slice(0, 20).map((c, i) => (
                      <li key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-[12px] font-medium">{c.periodo || c.concepto || `Cuota ${i + 1}`}</p>
                          <p className="text-[10px] text-muted dark:text-gray-500">
                            {c.vencimiento || ''} {c.estado ? `· ${c.estado}` : ''}
                          </p>
                        </div>
                        <p className="text-[13px] font-semibold tabular-nums">{fmt(c.importe)}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>

        <div className="px-6 py-3 border-t border-border dark:border-[#2A2A2A] flex justify-between items-center shrink-0">
          <button className="btn-secondary text-[12px] py-1.5 px-4" onClick={onClose}>Cerrar</button>
          <button className="btn-primary text-[12px] py-1.5 px-4" onClick={onRefresh}>
            <RefreshCw size={11} /> Actualizar
          </button>
        </div>
      </div>
    </div>
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
  const [errors, setErrors] = useState({})
  const [clientesLocal, setClientesLocal] = useState(clientes)
  const [creandoProp, setCreandoProp] = useState(false)
  const set = k => e => {
    setForm({ ...form, [k]: e.target.value })
    if (errors[k]) {
      setErrors(prev => {
        const n = { ...prev }
        delete n[k]
        return n
      })
    }
  }

  // Mantener sincronizado si el padre recarga la lista
  useEffect(() => { setClientesLocal(clientes) }, [clientes])

  const validate = () => {
    const e = {}
    if (!form.direccion || !form.direccion.trim()) {
      e.direccion = 'La dirección es obligatoria.'
    }
    if (!form.precio_alquiler || Number(form.precio_alquiler) <= 0) {
      e.precio_alquiler = 'El alquiler base es obligatorio y debe ser mayor a 0.'
    }
    return e
  }

  const submit = async e => {
    e.preventDefault()
    const v = validate()
    if (Object.keys(v).length) {
      setErrors(v)
      setErr('Revisá los campos marcados — hay datos obligatorios sin completar.')
      return
    }
    setErrors({})
    setLoading(true); setErr('')
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

  const errClass = 'mt-1 text-[12px] text-danger'
  const inputErr = '!border-danger !bg-danger/5 focus:!border-danger focus:!ring-danger/10'

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-2xl shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">{initial ? 'Editar propiedad' : 'Nueva propiedad'}</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="prop-tipo">Tipo *</label>
              <select id="prop-tipo" name="tipo" className="input" value={form.tipo} onChange={set('tipo')} required>
                {TIPOS.map(t => <option key={t} value={t}>{TIPO_LABEL[t]}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="prop-modalidad">Modalidad *</label>
              <select id="prop-modalidad" name="modalidad" className="input" value={form.modalidad} onChange={set('modalidad')} required>
                {MODALIDADES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label" htmlFor="prop-direccion">Dirección *</label>
            <input id="prop-direccion" name="direccion" className={`input ${errors.direccion ? inputErr : ''}`}
              placeholder="Av. Corrientes 1234, 5°A" value={form.direccion || ''}
              onChange={set('direccion')}
              aria-invalid={!!errors.direccion}
              aria-describedby={errors.direccion ? 'prop-direccion-err' : undefined}
              required />
            {errors.direccion && <p id="prop-direccion-err" className={errClass}>{errors.direccion}</p>}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="prop-ciudad">Ciudad</label>
              <input id="prop-ciudad" name="ciudad" className="input" placeholder="CABA" value={form.ciudad || ''} onChange={set('ciudad')} />
            </div>
            <div>
              <label className="label" htmlFor="prop-provincia">Provincia</label>
              <input id="prop-provincia" name="provincia" className="input" placeholder="Buenos Aires" value={form.provincia || ''} onChange={set('provincia')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="prop-estado">Estado</label>
              <select id="prop-estado" name="estado" className="input" value={form.estado} onChange={set('estado')}>
                {ESTADOS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="prop-ambientes">Ambientes</label>
              <input id="prop-ambientes" name="ambientes" className="input" type="number" min="0" value={form.ambientes || ''} onChange={set('ambientes')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="prop-superficie">Superficie m²</label>
              <input id="prop-superficie" name="superficie_m2" className="input" type="number" value={form.superficie_m2 || ''} onChange={set('superficie_m2')} />
            </div>
            <div>
              <div className="flex items-center justify-between">
                <label className="label" htmlFor="prop-propietario">Propietario</label>
                <button type="button"
                  onClick={() => setCreandoProp(true)}
                  className="text-[11px] text-primary dark:text-white hover:underline font-medium">
                  + Nuevo propietario
                </button>
              </div>
              <select id="prop-propietario" name="propietario_id" className="input" value={form.propietario_id || ''} onChange={set('propietario_id')}>
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
              <label className="label" htmlFor="prop-alquiler-base">Alquiler base $ *</label>
              <input id="prop-alquiler-base" name="precio_alquiler"
                className={`input ${errors.precio_alquiler ? inputErr : ''}`}
                type="number" min="0"
                value={form.precio_alquiler || ''}
                onChange={set('precio_alquiler')}
                aria-invalid={!!errors.precio_alquiler}
                aria-describedby={errors.precio_alquiler ? 'prop-alquiler-base-err' : undefined}
                required />
              {errors.precio_alquiler && <p id="prop-alquiler-base-err" className={errClass}>{errors.precio_alquiler}</p>}
            </div>
            <div>
              <label className="label" htmlFor="prop-expensas">Expensas $</label>
              <input id="prop-expensas" name="expensas" className="input" type="number" value={form.expensas || ''} onChange={set('expensas')} />
            </div>
            <div>
              <label className="label" htmlFor="prop-tasa">Ref. municipal $</label>
              <input id="prop-tasa" name="tasa_municipal" className="input" type="number"
                value={form.tasa_municipal || ''}
                onChange={set('tasa_municipal')}
                placeholder="Inmobiliario + ABL + alumbrado…" />
            </div>
          </div>

          <div>
            <label className="label flex items-center gap-1.5" htmlFor="prop-padron">
              <Landmark size={11} /> Nº de referencia municipal (padrón Santa Rosa)
            </label>
            <input
              id="prop-padron"
              name="numero_referencia"
              className="input font-mono"
              placeholder="ej. 123456"
              value={form.numero_referencia || ''}
              onChange={set('numero_referencia')}
            />
            <p className="text-[11px] text-muted dark:text-gray-500 mt-1">
              Permite consultar la deuda y la tasa actual desde el portal de la municipalidad con 1 click.
            </p>
          </div>

          <div>
            <label className="label" htmlFor="prop-descripcion">Descripción</label>
            <textarea id="prop-descripcion" name="descripcion" className="input resize-none" rows={2} value={form.descripcion || ''} onChange={set('descripcion')} />
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
          <h2 className="hero-title text-2xl">Nuevo propietario</h2>
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
