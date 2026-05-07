import { useEffect, useState } from 'react'
import { Plus, FileText, Pencil, Trash2, X, Calendar, TrendingUp, Download, DollarSign } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import HistorialPagos from '../components/HistorialPagos'
import api from '../utils/api'
import { generarPDFContrato } from '../utils/pdfContracts'

const TIPOS = ['alquiler_vivienda','alquiler_comercial','boleto_compraventa']
const ESTADOS = ['borrador','vigente','vencido','rescindido','cerrado']
const INDICES = ['ipc','icl','fijo','sin_ajuste']

const ESTADO_CHIP = {
  vigente:    'chip-dark',
  borrador:   'chip-gray',
  vencido:    'chip-warn',
  rescindido: 'chip-danger',
  cerrado:    'chip-muted',
}

const TIPO_LABEL = {
  alquiler_vivienda:  'Alq. Vivienda',
  alquiler_comercial: 'Alq. Comercial',
  boleto_compraventa: 'Boleto C/V',
}

const empty = {
  codigo:'', tipo:'alquiler_vivienda', estado:'borrador',
  propiedad_id:'', inquilino_id:'', fiador_id:'', fiador2_id:'',
  fecha_inicio:'', fecha_fin:'',
  monto_inicial:'', deposito:'',
  indice_ajuste:'icl', periodicidad_meses:'3', porcentaje_fijo:'',
  comision_porc:'', notas:'',
  pagare_refuerzo:'', inventario:'',
  seguro_obligatorio:true, permite_mascotas:false,
  punicion_diaria_porc:'1', dia_pago_desde:'1', dia_pago_hasta:'7',
}

// PDF generation moved to ../utils/pdfContracts.js (legal templates per type).

export default function Contratos() {
  const [list, setList]         = useState([])
  const [propiedades, setProp]  = useState([])
  const [clientes, setClientes] = useState([])
  const [filtro, setFiltro]     = useState('todos')
  const [open, setOpen]         = useState(false)
  const [editing, setEditing]   = useState(null)
  const [historialContrato, setHistorialContrato] = useState(null)

  const load = () => {
    api.get('/api/contratos').then(r => setList(r.data))
    api.get('/api/propiedades').then(r => setProp(r.data))
    api.get('/api/clientes').then(r => setClientes(r.data))
  }
  useEffect(() => { load() }, [])

  const filtered = filtro === 'todos' ? list : list.filter(c => c.estado === filtro)

  const del = async id => {
    if (!confirm('¿Eliminar contrato?')) return
    await api.delete(`/api/contratos/${id}`)
    load()
  }

  const propName = id => propiedades.find(p => p.id === id)?.direccion || `Propiedad #${id}`
  const clienteName = id => {
    const c = clientes.find(c => c.id === id)
    return c ? `${c.nombre} ${c.apellido || ''}`.trim() : null
  }

  const descargarPDF = (c) => {
    const propiedad = propiedades.find(p => p.id === c.propiedad_id) || null
    const propietario = propiedad?.propietario_id
      ? clientes.find(cl => cl.id === propiedad.propietario_id)
      : null
    const inquilino = c.inquilino_id ? clientes.find(cl => cl.id === c.inquilino_id) : null
    const fiador  = c.fiador_id  ? clientes.find(cl => cl.id === c.fiador_id)  : null
    const fiador2 = c.fiador2_id ? clientes.find(cl => cl.id === c.fiador2_id) : null
    generarPDFContrato({ contrato: c, propiedad, propietario, inquilino, fiador, fiador2 })
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Gestión contractual</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Contratos.</h1>
              <p className="hero-sub">Alquileres y boletos de compraventa.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo contrato
            </button>
          </div>
        </header>

        <div className="flex flex-wrap gap-2 mb-8">
          <FilterPill active={filtro === 'todos'} onClick={() => setFiltro('todos')} label={`Todos (${list.length})`} />
          {ESTADOS.map(e => (
            <FilterPill key={e} active={filtro === e} onClick={() => setFiltro(e)}
              label={`${e} (${list.filter(c => c.estado === e).length})`} />
          ))}
        </div>

        {filtered.length === 0 ? (
          <div className="card text-center py-24">
            <FileText size={40} className="mx-auto text-[#C8C8C8] dark:text-[#3A3A3A] mb-4" />
            <p className="text-[#737373] dark:text-[#9A9A9A] text-[15px] mb-4">No hay contratos en esta categoría.</p>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Crear contrato
            </button>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-4">
            {filtered.map(c => (
              <div key={c.id} className="card p-6 card-hover">
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-[#F0F0F0] dark:bg-[#1E1E1E] grid place-items-center shrink-0">
                      <FileText size={16} className="text-[#737373] dark:text-[#9A9A9A]" />
                    </div>
                    <div>
                      <p className="font-semibold text-[14px] tracking-tight">{c.codigo || `Contrato #${c.id}`}</p>
                      <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">{TIPO_LABEL[c.tipo] || c.tipo}</p>
                    </div>
                  </div>
                  <span className={ESTADO_CHIP[c.estado] || 'chip-muted'}>{c.estado}</span>
                </div>

                <div className="space-y-2 text-[13px]">
                  <Row label="Propiedad" value={propName(c.propiedad_id)} />
                  {c.inquilino_id && <Row label="Inquilino / Comprador" value={clienteName(c.inquilino_id)} />}
                  {c.monto_inicial > 0 && <Row label="Monto inicial" value={`$${Number(c.monto_inicial).toLocaleString('es-AR')}`} bold />}
                  {c.deposito > 0 && <Row label="Depósito" value={`$${Number(c.deposito).toLocaleString('es-AR')}`} />}
                </div>

                <div className="flex items-center gap-3 mt-4 border-t border-[#E5E5E5] dark:border-[#2A2A2A] pt-4 text-[12px] text-[#737373] dark:text-[#9A9A9A]">
                  <Calendar size={12} />
                  <span>{c.fecha_inicio || '—'} → {c.fecha_fin || '—'}</span>
                  <span className="ml-auto flex items-center gap-1">
                    <TrendingUp size={12} />
                    {c.indice_ajuste?.toUpperCase()} / {c.periodicidad_meses}m
                  </span>
                </div>

                <div className="flex gap-2 mt-4">
                  <button className="btn-secondary flex-1 text-[12px] py-2"
                    onClick={() => setHistorialContrato(c)}>
                    <DollarSign size={12} /> Pagos
                  </button>
                  <button className="btn-ghost py-2 px-3 text-[12px]"
                    onClick={() => { setEditing(c); setOpen(true) }}>
                    <Pencil size={12} />
                  </button>
                  <button className="btn-ghost py-2 px-3 text-[12px]" title="Descargar PDF legal"
                    onClick={() => descargarPDF(c)}>
                    <Download size={12} />
                  </button>
                  <button className="btn-danger py-2 px-3" onClick={() => del(c.id)}>
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
          propiedades={propiedades}
          clientes={clientes}
          onClose={() => setOpen(false)}
          onSaved={() => { setOpen(false); load() }}
        />
      )}

      {historialContrato && (
        <HistorialPagos
          contrato={historialContrato}
          onClose={() => setHistorialContrato(null)}
        />
      )}
    </Layout>
  )
}

function Row({ label, value, bold }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[#737373] dark:text-[#9A9A9A]">{label}</span>
      <span className={`${bold ? 'font-semibold text-[#0A0A0A] dark:text-[#F5F5F5]' : 'text-[#0A0A0A] dark:text-[#E0E0E0]'} truncate max-w-[55%] text-right`}>{value}</span>
    </div>
  )
}

function FilterPill({ active, onClick, label }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[12px] font-medium capitalize tracking-tight transition
        ${active
          ? 'bg-[#0A0A0A] dark:bg-white text-white dark:text-[#0A0A0A]'
          : 'bg-white dark:bg-[#1A1A1A] border border-[#E5E5E5] dark:border-[#2A2A2A] text-[#737373] dark:text-[#9A9A9A] hover:bg-[#F5F5F5] dark:hover:bg-[#252525]'
        }`}>
      {label}
    </button>
  )
}

function Modal({ initial, propiedades, clientes, onClose, onSaved }) {
  const [form, setForm]   = useState(initial ? { ...initial, fecha_inicio: initial.fecha_inicio || '', fecha_fin: initial.fecha_fin || '' } : { ...empty })
  const [loading, setLoading] = useState(false)
  const [err, setErr]     = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    ;[
      'propiedad_id','inquilino_id','fiador_id','fiador2_id',
      'monto_inicial','deposito','periodicidad_meses','porcentaje_fijo','comision_porc',
      'pagare_refuerzo','punicion_diaria_porc','dia_pago_desde','dia_pago_hasta',
    ].forEach(k => {
      if (payload[k] === '' || payload[k] == null) payload[k] = null
      else payload[k] = Number(payload[k])
      if (Number.isNaN(payload[k])) payload[k] = null
    })
    if (!payload.fecha_inicio) payload.fecha_inicio = null
    if (!payload.fecha_fin)    payload.fecha_fin    = null
    try {
      if (initial) await api.patch(`/api/contratos/${initial.id}`, payload)
      else await api.post('/api/contratos', payload)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-xl shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-2xl">{initial ? 'Editar contrato' : 'Nuevo contrato'}.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Código</label>
              <input className="input" placeholder="ALQ-2026-001" value={form.codigo || ''} onChange={set('codigo')} />
            </div>
            <div>
              <label className="label">Tipo *</label>
              <select className="input" value={form.tipo} onChange={set('tipo')} required>
                {TIPOS.map(t => <option key={t} value={t}>{TIPO_LABEL[t]}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Propiedad *</label>
            <select className="input" value={form.propiedad_id || ''} onChange={set('propiedad_id')} required>
              <option value="">Seleccionar propiedad…</option>
              {propiedades.map(p => <option key={p.id} value={p.id}>{p.direccion}</option>)}
            </select>
          </div>

          <div>
            <label className="label">Inquilino / Comprador</label>
            <select className="input" value={form.inquilino_id || ''} onChange={set('inquilino_id')}>
              <option value="">Sin asignar</option>
              {clientes.filter(c => ['inquilino','comprador'].includes(c.rol)).map(c => (
                <option key={c.id} value={c.id}>{c.nombre} {c.apellido} {c.documento ? `· ${c.documento}` : ''}</option>
              ))}
            </select>
          </div>

          {(form.tipo === 'alquiler_vivienda' || form.tipo === 'alquiler_comercial') && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Fiador 1 (garante)</label>
                <select className="input" value={form.fiador_id || ''} onChange={set('fiador_id')}>
                  <option value="">Sin asignar</option>
                  {clientes.filter(c => c.rol === 'garante').map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} {c.apellido} {c.documento ? `· ${c.documento}` : ''}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Fiador 2 (opcional)</label>
                <select className="input" value={form.fiador2_id || ''} onChange={set('fiador2_id')}>
                  <option value="">Sin asignar</option>
                  {clientes.filter(c => c.rol === 'garante').map(c => (
                    <option key={c.id} value={c.id}>{c.nombre} {c.apellido} {c.documento ? `· ${c.documento}` : ''}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Fecha inicio</label>
              <input className="input" type="date" value={form.fecha_inicio || ''} onChange={set('fecha_inicio')} />
            </div>
            <div>
              <label className="label">Fecha fin</label>
              <input className="input" type="date" value={form.fecha_fin || ''} onChange={set('fecha_fin')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Monto inicial $</label>
              <input className="input" type="number" value={form.monto_inicial || ''} onChange={set('monto_inicial')} />
            </div>
            <div>
              <label className="label">Depósito $</label>
              <input className="input" type="number" value={form.deposito || ''} onChange={set('deposito')} />
            </div>
          </div>

          <div className="divider !my-1" />
          <p className="text-[11px] uppercase tracking-[0.12em] text-[#737373] dark:text-[#7A7A7A] font-semibold">Ajuste de precio</p>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Índice</label>
              <select className="input" value={form.indice_ajuste} onChange={set('indice_ajuste')}>
                {INDICES.map(i => <option key={i} value={i}>{i.toUpperCase()}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Periodicidad (meses)</label>
              <select className="input" value={form.periodicidad_meses} onChange={set('periodicidad_meses')}>
                {[1,2,3,4,6,12].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div>
              <label className="label">% fijo (si aplica)</label>
              <input className="input" type="number" step="0.01"
                disabled={form.indice_ajuste !== 'fijo'}
                value={form.porcentaje_fijo || ''} onChange={set('porcentaje_fijo')} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Comisión %</label>
              <input className="input" type="number" step="0.1" value={form.comision_porc || ''} onChange={set('comision_porc')} />
            </div>
            <div>
              <label className="label">Estado</label>
              <select className="input" value={form.estado} onChange={set('estado')}>
                {ESTADOS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {(form.tipo === 'alquiler_vivienda' || form.tipo === 'alquiler_comercial') && (
            <>
              <div className="divider !my-1" />
              <p className="text-[11px] uppercase tracking-[0.12em] text-[#737373] dark:text-[#7A7A7A] font-semibold">Cláusulas modelo CIUDAD</p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Pagaré refuerzo $</label>
                  <input className="input" type="number" placeholder="8000000"
                    value={form.pagare_refuerzo || ''} onChange={set('pagare_refuerzo')} />
                </div>
                <div>
                  <label className="label">Punición diaria %</label>
                  <input className="input" type="number" step="0.1" placeholder="1"
                    value={form.punicion_diaria_porc || ''} onChange={set('punicion_diaria_porc')} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Día pago desde</label>
                  <input className="input" type="number" min="1" max="28"
                    value={form.dia_pago_desde || ''} onChange={set('dia_pago_desde')} />
                </div>
                <div>
                  <label className="label">Día pago hasta</label>
                  <input className="input" type="number" min="1" max="28"
                    value={form.dia_pago_hasta || ''} onChange={set('dia_pago_hasta')} />
                </div>
              </div>

              <div>
                <label className="label">Inventario y bienes incorporados</label>
                <textarea className="input resize-none" rows={3}
                  placeholder="SPLIT, termotanque, cocina, etc. — pintura latex blanco a devolver igual."
                  value={form.inventario || ''} onChange={set('inventario')} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center gap-2 text-[13px] cursor-pointer">
                  <input type="checkbox" checked={!!form.seguro_obligatorio}
                    onChange={e => setForm({ ...form, seguro_obligatorio: e.target.checked })} />
                  <span>Seguro incendio/robo/RC obligatorio</span>
                </label>
                <label className="flex items-center gap-2 text-[13px] cursor-pointer">
                  <input type="checkbox" checked={!!form.permite_mascotas}
                    onChange={e => setForm({ ...form, permite_mascotas: e.target.checked })} />
                  <span>Permite mascotas</span>
                </label>
              </div>
            </>
          )}

          <div>
            <label className="label">Notas</label>
            <textarea className="input resize-none" rows={2} value={form.notas || ''} onChange={set('notas')} />
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : initial ? 'Guardar' : 'Crear contrato'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
