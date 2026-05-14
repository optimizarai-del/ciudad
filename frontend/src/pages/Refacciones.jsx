import { useEffect, useMemo, useState } from 'react'
import {
  Wrench, Plus, X, Trash2, Pencil, Filter, RefreshCw,
  User, Home as HomeIcon, AlertCircle, CheckCircle2,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import SearchBar, { match } from '../components/SearchBar'
import api from '../utils/api'

const PAGADOR = { inquilino: 'Inquilino paga', propietario: 'Propietario paga' }
const ESTADO_CHIP = {
  pendiente: 'chip-warn',
  aplicada:  'chip-success',
  cancelada: 'chip-muted',
}

const empty = {
  propiedad_id: '',
  contrato_id: '',
  fecha: new Date().toISOString().slice(0, 10),
  descripcion: '',
  monto: '',
  pagador: 'inquilino',
  estado: 'pendiente',
  notas: '',
}

/**
 * Refacciones / arreglos de las propiedades. Las que paga el inquilino
 * quedan listas para descontarse del próximo cobro de su contrato; las del
 * propietario quedan como gasto que se ve en la liquidación.
 */
export default function Refacciones() {
  const [list, setList]         = useState([])
  const [propiedades, setProp]  = useState([])
  const [contratos, setContr]   = useState([])
  const [resumen, setResumen]   = useState(null)
  const [filtroEstado, setFE]   = useState('todos')
  const [filtroPagador, setFP]  = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [open, setOpen]         = useState(false)
  const [editing, setEditing]   = useState(null)
  const [loading, setLoading]   = useState(true)

  const cargar = () => {
    setLoading(true)
    Promise.allSettled([
      api.get('/api/refacciones'),
      api.get('/api/propiedades'),
      api.get('/api/contratos/'),
      api.get('/api/refacciones/resumen'),
    ]).then(([r, p, c, s]) => {
      if (r.status === 'fulfilled') setList(r.value.data || [])
      if (p.status === 'fulfilled') setProp(p.value.data || [])
      if (c.status === 'fulfilled') setContr(c.value.data || [])
      if (s.status === 'fulfilled') setResumen(s.value.data)
    }).finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [])

  const filtradas = useMemo(() => {
    let r = list
    if (filtroEstado !== 'todos') r = r.filter(x => x.estado === filtroEstado)
    if (filtroPagador !== 'todos') r = r.filter(x => x.pagador === filtroPagador)
    if (busqueda.trim()) {
      r = r.filter(x => match(busqueda,
        x.descripcion, x.propiedad_direccion, x.contrato_codigo, x.notas,
      ))
    }
    return r
  }, [list, filtroEstado, filtroPagador, busqueda])

  const del = async (r) => {
    if (!confirm(`¿Eliminar refacción "${r.descripcion}"?`)) return
    try {
      await api.delete(`/api/refacciones/${r.id}`)
      cargar()
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo eliminar.')
    }
  }

  const fmt = v => `$ ${Number(v || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`

  return (
    <Layout>
      <div className="max-w-7xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Mantenimiento</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3 flex items-center gap-3">
                <Wrench className="text-[#B8893A]" /> Refacciones.
              </h1>
              <p className="hero-sub">
                Arreglos en propiedades. Las que paga el inquilino se descuentan del próximo alquiler.
              </p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nueva refacción
            </button>
          </div>
        </header>

        {/* Stats */}
        {resumen && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            <div className="card p-4">
              <p className="stat-label">Total refacciones</p>
              <p className="stat-value text-lg mt-1">{list.length}</p>
            </div>
            <div className="card p-4 border-l-4 !border-l-warn">
              <p className="stat-label flex items-center gap-1.5"><User size={11} /> Pendientes — inquilino</p>
              <p className="stat-value text-lg mt-1 text-warn">
                {resumen.pendientes_inquilino.cantidad}
                <span className="text-[12px] text-muted font-normal ml-2">{fmt(resumen.pendientes_inquilino.monto)}</span>
              </p>
            </div>
            <div className="card p-4 border-l-4 !border-l-warn">
              <p className="stat-label flex items-center gap-1.5"><HomeIcon size={11} /> Pendientes — propietario</p>
              <p className="stat-value text-lg mt-1 text-warn">
                {resumen.pendientes_propietario.cantidad}
                <span className="text-[12px] text-muted font-normal ml-2">{fmt(resumen.pendientes_propietario.monto)}</span>
              </p>
            </div>
          </div>
        )}

        {/* Filtros */}
        <div className="card p-3 mb-4 flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[200px]">
            <SearchBar value={busqueda} onChange={setBusqueda}
              placeholder="Buscar por descripción, propiedad, contrato…" />
          </div>
          <div className="flex items-center gap-1.5 text-[12px] text-muted">
            <Filter size={11} /> Estado:
          </div>
          {['todos','pendiente','aplicada','cancelada'].map(s => (
            <FilterPill key={s} active={filtroEstado === s}
              onClick={() => setFE(s)}
              label={s === 'todos' ? 'Todos' : s}
            />
          ))}
          <div className="w-px h-5 bg-border" />
          {['todos','inquilino','propietario'].map(p => (
            <FilterPill key={p} active={filtroPagador === p}
              onClick={() => setFP(p)}
              label={p === 'todos' ? 'Cualquiera' : `Paga ${p}`}
            />
          ))}
          <button className="btn-ghost py-1.5 px-2 text-[11px]" onClick={cargar} disabled={loading}>
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Lista */}
        <div className="card overflow-hidden">
          {loading ? (
            <p className="text-center text-muted py-16 text-[13px]">Cargando…</p>
          ) : filtradas.length === 0 ? (
            <p className="text-center text-muted py-16 text-[13px]">
              No hay refacciones. Cargá la primera tocando "Nueva refacción".
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border dark:border-[#2A2A2A]">
                  <tr>
                    <th className="th w-28">Fecha</th>
                    <th className="th">Propiedad / descripción</th>
                    <th className="th hidden md:table-cell">Contrato</th>
                    <th className="th text-right w-32">Monto</th>
                    <th className="th text-center w-32">Paga</th>
                    <th className="th text-center w-28">Estado</th>
                    <th className="th w-24" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border dark:divide-[#2A2A2A]">
                  {filtradas.map(r => (
                    <tr key={r.id} className="hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition">
                      <td className="td text-[12px] text-muted">
                        {r.fecha ? new Date(r.fecha).toLocaleDateString('es-AR') : '—'}
                      </td>
                      <td className="td">
                        <p className="font-medium text-[13px]">{r.descripcion}</p>
                        <p className="text-[11px] text-muted">{r.propiedad_direccion}</p>
                        {r.notas && (
                          <p className="text-[10px] text-muted dark:text-gray-600 italic mt-0.5 truncate max-w-[420px]">
                            {r.notas}
                          </p>
                        )}
                      </td>
                      <td className="td hidden md:table-cell text-[12px]">
                        {r.contrato_codigo || <span className="text-muted">—</span>}
                      </td>
                      <td className="td text-right tabular-nums font-semibold">{fmt(r.monto)}</td>
                      <td className="td text-center">
                        <span className={`chip-${r.pagador === 'inquilino' ? 'gray' : 'muted'}`}>
                          {PAGADOR[r.pagador] || r.pagador}
                        </span>
                      </td>
                      <td className="td text-center">
                        <span className={ESTADO_CHIP[r.estado] || 'chip-muted'}>{r.estado}</span>
                        {r.estado === 'aplicada' && r.pago_id && (
                          <p className="text-[10px] text-muted mt-0.5">pago #{r.pago_id}</p>
                        )}
                      </td>
                      <td className="td">
                        <div className="flex gap-1 justify-end">
                          <button className="btn-ghost py-1.5 px-2"
                            title="Editar"
                            disabled={r.estado === 'aplicada'}
                            onClick={() => { setEditing(r); setOpen(true) }}>
                            <Pencil size={11} />
                          </button>
                          <button className="btn-danger py-1.5 px-2"
                            onClick={() => del(r)}
                            disabled={r.estado === 'aplicada'}>
                            <Trash2 size={11} />
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

        <p className="text-[11px] text-muted dark:text-gray-500 mt-4 text-center">
          💡 Las refacciones pendientes del inquilino aparecen como descuento sugerido al registrar el pago del alquiler.
        </p>
      </div>

      {open && (
        <Modal
          initial={editing}
          propiedades={propiedades}
          contratos={contratos}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); cargar() }}
        />
      )}
    </Layout>
  )
}

function FilterPill({ active, onClick, label }) {
  return (
    <button onClick={onClick}
      className={`px-3 py-1 rounded-full text-[11px] font-medium capitalize transition
        ${active
          ? 'bg-[#0A0A0A] dark:bg-white text-white dark:text-[#0A0A0A]'
          : 'bg-white dark:bg-[#1A1A1A] border border-border dark:border-[#2A2A2A] text-muted hover:bg-neutral-50 dark:hover:bg-[#252525]'
        }`}>
      {label}
    </button>
  )
}

function Modal({ initial, propiedades, contratos, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...initial, fecha: initial.fecha || '' } : { ...empty })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  // Contratos sugeridos: los vigentes de la propiedad seleccionada.
  const contratosDePropiedad = useMemo(() => {
    if (!form.propiedad_id) return []
    return contratos.filter(c =>
      String(c.propiedad_id) === String(form.propiedad_id)
      && c.estado === 'vigente'
    )
  }, [contratos, form.propiedad_id])

  // Si solo hay 1 contrato vigente, lo seleccionamos automáticamente.
  useEffect(() => {
    if (form.propiedad_id && !form.contrato_id && contratosDePropiedad.length === 1) {
      setForm(f => ({ ...f, contrato_id: contratosDePropiedad[0].id }))
    }
  }, [form.propiedad_id, contratosDePropiedad])

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = {
      ...form,
      propiedad_id: Number(form.propiedad_id),
      contrato_id: form.contrato_id ? Number(form.contrato_id) : null,
      monto: Number(form.monto) || 0,
    }
    if (!payload.propiedad_id) {
      setErr('Elegí la propiedad.'); setLoading(false); return
    }
    if (!payload.descripcion?.trim()) {
      setErr('Poné una descripción.'); setLoading(false); return
    }
    if (payload.monto <= 0) {
      setErr('El monto debe ser mayor a 0.'); setLoading(false); return
    }
    try {
      if (initial) await api.patch(`/api/refacciones/${initial.id}`, payload)
      else await api.post('/api/refacciones', payload)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  // Propiedades en alquiler — las de venta no aplican.
  const propsAlq = propiedades.filter(p => p.modalidad !== 'venta')

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-xl shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">{initial ? 'Editar refacción' : 'Nueva refacción'}.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Propiedad *</label>
            <select className="input" value={form.propiedad_id || ''}
              onChange={set('propiedad_id')} required>
              <option value="">Seleccionar propiedad…</option>
              {propsAlq.map(p => (
                <option key={p.id} value={p.id}>{p.direccion}</option>
              ))}
            </select>
          </div>

          {contratosDePropiedad.length > 0 && (
            <div>
              <label className="label">Contrato (para descontar)</label>
              <select className="input" value={form.contrato_id || ''} onChange={set('contrato_id')}>
                <option value="">Sin asignar</option>
                {contratosDePropiedad.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.codigo || `Contrato #${c.id}`}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Fecha</label>
              <input className="input" type="date" value={form.fecha || ''} onChange={set('fecha')} />
            </div>
            <div>
              <label className="label">Monto $ *</label>
              <input className="input" type="number" min="0" value={form.monto || ''} onChange={set('monto')} required />
            </div>
          </div>

          <div>
            <label className="label">Descripción *</label>
            <input className="input" value={form.descripcion || ''} onChange={set('descripcion')}
              placeholder="ej. Reparación de termotanque" required />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">¿Quién paga? *</label>
              <select className="input" value={form.pagador} onChange={set('pagador')}>
                <option value="inquilino">Inquilino — se descuenta del alquiler</option>
                <option value="propietario">Propietario — sale de la liquidación</option>
              </select>
            </div>
            <div>
              <label className="label">Estado</label>
              <select className="input" value={form.estado} onChange={set('estado')}
                disabled={initial?.estado === 'aplicada'}>
                <option value="pendiente">Pendiente</option>
                <option value="aplicada">Aplicada</option>
                <option value="cancelada">Cancelada</option>
              </select>
            </div>
          </div>

          <div>
            <label className="label">Notas</label>
            <textarea className="input resize-none" rows={2} value={form.notas || ''} onChange={set('notas')} />
          </div>

          {/* Hint según pagador */}
          <div className="rounded-xl p-3 text-[11px] flex gap-2 items-start
            border border-[#B8893A]/20 bg-[#B8893A]/5">
            {form.pagador === 'inquilino' ? (
              <>
                <AlertCircle size={12} className="text-[#B8893A] shrink-0 mt-0.5" />
                <p className="text-muted">
                  Al quedar <strong>pendiente</strong>, esta refacción se mostrará como descuento sugerido cuando registres el próximo pago del alquiler del contrato vinculado.
                </p>
              </>
            ) : (
              <>
                <CheckCircle2 size={12} className="text-[#B8893A] shrink-0 mt-0.5" />
                <p className="text-muted">
                  Esta refacción la paga el propietario — saldrá como gasto en la próxima liquidación que le emitas.
                </p>
              </>
            )}
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : initial ? 'Guardar cambios' : 'Crear refacción'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
