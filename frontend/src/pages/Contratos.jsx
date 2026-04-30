import { useEffect, useState } from 'react'
import { Plus, FileText, Pencil, Trash2, X, Calendar, TrendingUp, Download, DollarSign } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import HistorialPagos from '../components/HistorialPagos'
import api from '../utils/api'
import { jsPDF } from 'jspdf'

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
  propiedad_id:'', inquilino_id:'',
  fecha_inicio:'', fecha_fin:'',
  monto_inicial:'', deposito:'',
  indice_ajuste:'ipc', periodicidad_meses:'3', porcentaje_fijo:'',
  comision_porc:'', notas:''
}

function generarPDF(c, propName, clienteName) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const W = 210, M = 20

  doc.setFillColor(10, 10, 10)
  doc.rect(0, 0, W, 32, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFontSize(22)
  doc.setFont('helvetica', 'bold')
  doc.text('CIUDAD.', M, 14)
  doc.setFontSize(9)
  doc.setFont('helvetica', 'normal')
  doc.text('Inmuebles · Contratos · Gestion', M, 21)
  doc.setFontSize(11)
  doc.setFont('helvetica', 'bold')
  doc.text(c.codigo || `CONTRATO #${c.id}`, W - M, 16, { align: 'right' })
  doc.setFontSize(8)
  doc.setFont('helvetica', 'normal')
  doc.text(TIPO_LABEL[c.tipo] || c.tipo, W - M, 23, { align: 'right' })

  doc.setTextColor(10, 10, 10)
  let y = 44

  const section = (titulo) => {
    doc.setFillColor(247, 247, 247)
    doc.rect(M, y, W - M * 2, 7, 'F')
    doc.setFontSize(8)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(115, 115, 115)
    doc.text(titulo.toUpperCase(), M + 3, y + 4.5)
    doc.setTextColor(10, 10, 10)
    y += 11
  }

  const row = (label, value) => {
    doc.setFontSize(9)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(115, 115, 115)
    doc.text(label, M, y)
    doc.setTextColor(10, 10, 10)
    doc.setFont('helvetica', 'bold')
    doc.text(String(value || '—'), M + 55, y)
    y += 7
  }

  section('Partes')
  row('Propiedad', propName)
  row('Inquilino / Comprador', clienteName || 'Sin asignar')
  y += 2

  section('Vigencia')
  row('Fecha inicio', c.fecha_inicio || '—')
  row('Fecha fin', c.fecha_fin || '—')
  y += 2

  section('Condiciones economicas')
  row('Monto inicial', c.monto_inicial > 0 ? `$${Number(c.monto_inicial).toLocaleString('es-AR')}` : '—')
  row('Deposito', c.deposito > 0 ? `$${Number(c.deposito).toLocaleString('es-AR')}` : '—')
  row('Indice de ajuste', c.indice_ajuste?.toUpperCase())
  row('Periodicidad', `${c.periodicidad_meses} meses`)
  if (c.porcentaje_fijo > 0) row('% fijo', `${c.porcentaje_fijo}%`)
  if (c.comision_porc > 0) row('Comision', `${c.comision_porc}%`)
  y += 2

  if (c.notas) {
    section('Notas')
    const lines = doc.splitTextToSize(c.notas, W - M * 2 - 6)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text(lines, M, y)
    y += lines.length * 5 + 4
  }

  y = Math.max(y + 10, 215)
  doc.setDrawColor(200, 200, 200)
  doc.line(M, y, M + 60, y)
  doc.line(W - M - 60, y, W - M, y)
  doc.setFontSize(8)
  doc.setTextColor(115, 115, 115)
  doc.setFont('helvetica', 'normal')
  doc.text('Firma Locador / Vendedor', M + 30, y + 5, { align: 'center' })
  doc.text('Firma Locatario / Comprador', W - M - 30, y + 5, { align: 'center' })

  doc.setFillColor(247, 247, 247)
  doc.rect(0, 287, W, 10, 'F')
  doc.setFontSize(7)
  doc.setTextColor(160, 160, 160)
  doc.text(`CIUDAD. · Generado el ${new Date().toLocaleDateString('es-AR')}`, M, 293)
  doc.text(`${c.codigo || `Contrato #${c.id}`} · Documento no oficial`, W - M, 293, { align: 'right' })

  doc.save(`contrato-${c.codigo || c.id}.pdf`)
}

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
                  <button className="btn-ghost py-2 px-3 text-[12px]" title="Descargar PDF"
                    onClick={() => generarPDF(c, propName(c.propiedad_id), clienteName(c.inquilino_id))}>
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
    ;['propiedad_id','inquilino_id','monto_inicial','deposito','periodicidad_meses','porcentaje_fijo','comision_porc'].forEach(k => {
      if (payload[k] === '' || payload[k] == null) payload[k] = null
      else payload[k] = Number(payload[k]) || null
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
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre} {c.apellido}</option>)}
            </select>
          </div>

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
