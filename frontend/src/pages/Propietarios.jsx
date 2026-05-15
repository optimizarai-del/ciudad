import { useEffect, useMemo, useState } from 'react'
import { Plus, KeyRound, Mail, Phone, Building2, Search, X, Pencil, Trash2, FileText, Archive, ArchiveRestore, Calendar, Eye } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import { match } from '../components/SearchBar'
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
  const [verContratos, setVerContratos] = useState(null)   // propietario al que abrir el historial

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

  const del = async (id) => {
    if (!confirm('¿Eliminar propietario?')) return
    try {
      await api.delete(`/api/clientes/${id}`)
      load()
    } catch (e) {
      const msg = e.response?.data?.detail || 'No se pudo eliminar.'
      // Si tiene propiedades asignadas, el backend devuelve 409 y nos sugiere forzar.
      if (e.response?.status === 409 && /forzar/i.test(msg)) {
        if (confirm(`${msg}\n\n¿Desvincular las propiedades y eliminarlo igual?`)) {
          try {
            await api.delete(`/api/clientes/${id}?forzar=true`)
            load()
          } catch (e2) {
            alert(e2.response?.data?.detail || 'No se pudo forzar.')
          }
        }
      } else {
        alert(msg)
      }
    }
  }

  const filtrados = useMemo(() => {
    if (!busqueda.trim()) return propietarios
    return propietarios.filter(p => {
      // Permitir buscar también por dirección de las propiedades del propietario
      // (ej: "Av. Gaona 3100" debe traer al dueño de esa propiedad).
      const props = propsPorPropietario[p.id] || []
      const direcciones = props.map(pr => `${pr.direccion} ${pr.ciudad || ''} ${pr.codigo || ''}`).join(' ')
      return match(
        busqueda,
        p.nombre, p.apellido, p.razon_social, p.documento, p.email, p.telefono,
        direcciones,
      )
    })
  }, [propietarios, busqueda, propsPorPropietario])

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Cartera</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Propietarios</h1>
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
            placeholder="Buscar por nombre, DNI, email o dirección..."
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
                    <div className="flex gap-1 shrink-0">
                      <button className="btn-ghost p-1.5"
                        title="Ver historial de contratos"
                        onClick={() => setVerContratos(p)}>
                        <FileText size={12} />
                      </button>
                      <button className="btn-ghost p-1.5"
                        title="Editar"
                        onClick={() => { setEditing(p); setOpen(true) }}>
                        <Pencil size={12} />
                      </button>
                      <button
                        className="p-1.5 rounded-lg hover:bg-danger/10 text-muted hover:text-danger transition"
                        title="Eliminar propietario"
                        onClick={() => del(p.id)}>
                        <Trash2 size={12} />
                      </button>
                    </div>
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
      {verContratos && (
        <ModalContratosPropietario
          propietario={verContratos}
          onClose={() => setVerContratos(null)}
        />
      )}
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
          <h2 className="hero-title text-xl sm:text-2xl">{initial ? 'Editar propietario' : 'Nuevo propietario'}</h2>
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
              <label className="label">Razón social (si aplica)</label>
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


/**
 * Historial de contratos de un propietario. Incluye archivados con toggle
 * para los más viejos. Permite archivar/desarchivar y ver el PDF.
 */
function ModalContratosPropietario({ propietario, onClose }) {
  const [contratos, setContratos] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [incluirArchivados, setIncluirArchivados] = useState(true)

  const cargar = () => {
    setLoading(true); setErr('')
    api.get(`/api/contratos?propietario_id=${propietario.id}&incluir_archivados=${incluirArchivados}`)
      .then(r => setContratos(r.data || []))
      .catch(e => setErr(e.response?.data?.detail || 'No se pudieron cargar los contratos.'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [incluirArchivados])

  const verPDF = async (c) => {
    try {
      const r = await api.get(`/api/contratos/${c.id}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
      window.open(url, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo abrir el PDF.')
    }
  }

  const archivar = async (c) => {
    try {
      await api.post(`/api/contratos/${c.id}/${c.archivado ? 'desarchivar' : 'archivar'}`)
      cargar()
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo realizar la acción.')
    }
  }

  const fmtFecha = s => s ? new Date(s).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'
  const nombre = propietario.razon_social || `${propietario.nombre} ${propietario.apellido || ''}`.trim()

  const activos = contratos.filter(c => !c.archivado)
  const archivados = contratos.filter(c => c.archivado)

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card w-full max-w-3xl shadow-lift animate-scale-in flex flex-col max-h-[90vh] my-6"
        onClick={e => e.stopPropagation()}>
        <div className="px-6 py-5 border-b border-border dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div className="min-w-0">
            <h2 className="hero-title text-xl sm:text-2xl mb-0.5 truncate">Historial de contratos</h2>
            <p className="text-[12px] text-muted truncate">{nombre}</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2 shrink-0"><X size={16} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
          {loading ? (
            <p className="text-center text-muted py-8 text-[13px]">Cargando…</p>
          ) : err ? (
            <div className="rounded-xl p-3 bg-danger/5 border border-danger/20 text-[12px] text-danger">{err}</div>
          ) : contratos.length === 0 ? (
            <p className="text-center text-muted py-8 text-[13px]">
              Este propietario aún no tiene contratos cargados.
            </p>
          ) : (
            <>
              {activos.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted font-semibold mb-2">
                    Activos ({activos.length})
                  </p>
                  <div className="space-y-2">
                    {activos.map(c => (
                      <ContratoCard key={c.id} contrato={c} onVerPDF={verPDF} onArchivar={archivar} />
                    ))}
                  </div>
                </div>
              )}

              {archivados.length > 0 && (
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-muted font-semibold mb-2 mt-4">
                    Archivados ({archivados.length})
                  </p>
                  <div className="space-y-2">
                    {archivados.map(c => (
                      <ContratoCard key={c.id} contrato={c} onVerPDF={verPDF} onArchivar={archivar} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}


function ContratoCard({ contrato, onVerPDF, onArchivar }) {
  const fmtFecha = s => s ? new Date(s).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'
  const ESTADO_CHIP = {
    vigente: 'chip-dark', borrador: 'chip-gray', vencido: 'chip-warn',
    rescindido: 'chip-danger', reservado: 'chip-muted',
  }
  return (
    <div className={`card p-3 ${contrato.archivado ? 'opacity-60' : ''}`}>
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl bg-neutral-100 dark:bg-[#1E1E1E] grid place-items-center shrink-0">
          <FileText size={14} className="text-muted" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-[13px] font-semibold">{contrato.codigo || `Contrato #${contrato.id}`}</p>
            <span className={ESTADO_CHIP[contrato.estado] || 'chip-muted'}>{contrato.estado}</span>
            {contrato.archivado && <span className="chip-muted">archivado</span>}
          </div>
          <p className="text-[11px] text-muted mt-0.5 flex items-center gap-1.5">
            <Calendar size={10} />
            {fmtFecha(contrato.fecha_inicio)} → {fmtFecha(contrato.fecha_fin)}
            {contrato.monto_inicial > 0 && (
              <span className="ml-2">$ {Number(contrato.monto_inicial).toLocaleString('es-AR')}/mes</span>
            )}
          </p>
        </div>
        <div className="flex gap-1 shrink-0">
          <button className="btn-ghost p-1.5" title="Ver PDF" onClick={() => onVerPDF(contrato)}>
            <Eye size={12} />
          </button>
          <button className="btn-ghost p-1.5"
            title={contrato.archivado ? 'Desarchivar' : 'Archivar'}
            onClick={() => onArchivar(contrato)}>
            {contrato.archivado ? <ArchiveRestore size={12} /> : <Archive size={12} />}
          </button>
        </div>
      </div>
    </div>
  )
}
