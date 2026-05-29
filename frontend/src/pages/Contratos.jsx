import { useEffect, useMemo, useState } from 'react'
import { Plus, FileText, Pencil, Trash2, X, Calendar, TrendingUp, Download, DollarSign, FileType2, Upload, FileCheck2, Sparkles, Eye, Archive, ArchiveRestore } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import HistorialPagos from '../components/HistorialPagos'
import SearchBar, { match } from '../components/SearchBar'
import ImportarContratoPDF from '../components/ImportarContratoPDF'
import ProgresoContrato from '../components/ProgresoContrato'
import api from '../utils/api'

const TIPOS = ['alquiler_vivienda','alquiler_comercial','boleto_compraventa','sena_alquiler']
const ESTADOS = ['borrador','vigente','vencido','rescindido','reservado']
const INDICES = ['ipc','icl','fijo','sin_ajuste']

const ESTADO_CHIP = {
  vigente:    'chip-dark',
  borrador:   'chip-gray',
  vencido:    'chip-warn',
  rescindido: 'chip-danger',
  reservado:  'chip-muted',
}

const TIPO_LABEL = {
  alquiler_vivienda:  'Alq. Vivienda',
  alquiler_comercial: 'Alq. Comercial',
  boleto_compraventa: 'Boleto C/V',
  sena_alquiler:      'Seña Alquiler',
}

const empty = {
  // Default 'vigente' porque es lo más usado por inmobiliarias: cuando creás
  // un contrato típicamente ya está activo. Para que aparezca en Cobranza,
  // Liquidaciones y demás flujos operativos, el estado tiene que ser 'vigente'.
  // 'borrador' es para guardar un draft que todavía no se firmó.
  codigo:'', tipo:'alquiler_vivienda', estado:'vigente',
  propiedad_id:'',
  // Lista de inquilinos firmantes (compat con multi-inquilino). El primer
  // elemento es siempre el titular principal. El campo inquilino_id legacy
  // queda en sync con inquilinos_ids[0] al hacer el submit.
  inquilinos_ids: [],
  inquilino_id:'',
  fecha_inicio:'', fecha_fin:'',
  monto_inicial:'', deposito:'',
  indice_ajuste:'ipc', periodicidad_meses:'3', porcentaje_fijo:'',
  comision_porc:'', notas:''
}

async function descargarPDF(c) {
  // Pide el PDF al backend (plantilla legal con cláusulas).
  try {
    const r = await api.get(`/api/contratos/${c.id}/pdf`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `contrato-${c.codigo || c.id}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    alert(e.response?.data?.detail || 'Error al generar el PDF.')
  }
}

async function descargarDocx(c) {
  try {
    const r = await api.get(`/api/contratos/${c.id}/docx`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }))
    const a = document.createElement('a')
    a.href = url
    a.download = `contrato-${c.codigo || c.id}.docx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    alert(e.response?.data?.detail || 'Error al generar el Word.')
  }
}

async function descargarArchivo(c) {
  // Archivo subido manualmente — el backend devuelve 307 a Storage signed URL.
  try {
    const r = await api.get(`/api/contratos/${c.id}/archivo`, { responseType: 'blob' })
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = c.archivo_nombre || `contrato-${c.codigo || c.id}.docx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) {
    alert(e.response?.data?.detail || 'No se pudo descargar el archivo.')
  }
}

export default function Contratos() {
  const [list, setList]         = useState([])
  const [propiedades, setProp]  = useState([])
  const [clientes, setClientes] = useState([])
  const [filtro, setFiltro]     = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [open, setOpen]         = useState(false)
  const [editing, setEditing]   = useState(null)
  const [historialContrato, setHistorialContrato] = useState(null)
  const [importOpen, setImportOpen] = useState(false)
  const [incluirArchivados, setIncluirArchivados] = useState(false)

  const load = () => {
    const url = `/api/contratos${incluirArchivados ? '?incluir_archivados=true' : ''}`
    api.get(url).then(r => setList(r.data))
    api.get('/api/propiedades').then(r => setProp(r.data))
    api.get('/api/clientes').then(r => setClientes(r.data))
  }
  useEffect(() => { load() }, [incluirArchivados])

  // "Por vencer": contrato vigente cuyo fecha_fin cae dentro de los próximos
  // 60 días (incluye los ya vencidos en los últimos 0 días si estado sigue
  // vigente — el ajuste no se hizo todavía).
  const diasParaVencer = (c) => {
    if (!c.fecha_fin) return null
    const fin = new Date(c.fecha_fin)
    const hoy = new Date(); hoy.setHours(0,0,0,0)
    return Math.round((fin - hoy) / 86400000)
  }
  const esPorVencer = (c) => {
    if (c.estado !== 'vigente') return false
    const d = diasParaVencer(c)
    return d !== null && d <= 60
  }
  const porVencerCount = useMemo(() => list.filter(esPorVencer).length, [list])

  const filtered = useMemo(() => {
    let r
    if (filtro === 'por_vencer') r = list.filter(esPorVencer)
    else if (filtro === 'todos') r = list
    else r = list.filter(c => c.estado === filtro)
    if (busqueda.trim()) {
      r = r.filter(c => {
        const prop = propiedades.find(p => p.id === c.propiedad_id)
        const inq = clientes.find(cl => cl.id === c.inquilino_id)
        return match(
          busqueda,
          c.codigo, c.tipo, c.estado, c.notas,
          prop?.direccion, prop?.ciudad, prop?.codigo,
          inq?.nombre, inq?.apellido, inq?.razon_social, inq?.documento,
        )
      })
    }
    return r
  }, [list, filtro, busqueda, propiedades, clientes])

  const del = async id => {
    if (!confirm('¿Eliminar contrato?')) return
    await api.delete(`/api/contratos/${id}`)
    load()
  }

  const subirArchivo = async (c, file) => {
    if (!file) return
    const fd = new FormData()
    fd.append('archivo', file)
    try {
      await api.post(`/api/contratos/${c.id}/archivo`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      load()
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo subir el archivo.')
    }
  }

  const propName = id => propiedades.find(p => p.id === id)?.direccion || `Propiedad #${id}`
  const clienteName = id => {
    const c = clientes.find(c => c.id === id)
    return c ? `${c.nombre} ${c.apellido || ''}`.trim() : null
  }

  // Devuelve el nombre del propietario principal de la propiedad del contrato
  const propietarioName = (contrato) => {
    const prop = propiedades.find(p => p.id === contrato.propiedad_id)
    if (!prop) return null
    // M2M nueva
    if (prop.propietarios_lista?.length > 0) {
      const ppal = prop.propietarios_lista.find(p => p.es_principal) || prop.propietarios_lista[0]
      const extras = prop.propietarios_lista.length - 1
      return extras > 0
        ? `${ppal.nombre} + ${extras}`
        : ppal.nombre
    }
    // Legacy
    return prop.propietario_nombre || null
  }

  // Ver el PDF del contrato en nueva pestaña (sin descargar)
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
    const accion = c.archivado ? 'desarchivar' : 'archivar'
    if (!confirm(`¿${accion[0].toUpperCase() + accion.slice(1)} este contrato?`)) return
    try {
      await api.post(`/api/contratos/${c.id}/${accion}`)
      load()
    } catch (e) {
      alert(e.response?.data?.detail || 'No se pudo realizar la acción.')
    }
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Gestión contractual</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Contratos</h1>
              <p className="hero-sub">Alquileres y boletos de compraventa.</p>
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setImportOpen(true)}
                title="Importar contrato desde PDF — la IA crea propietario, inquilino, propiedad y contrato">
                <Sparkles size={14} /> Importar PDF
              </button>
              <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
                <Plus size={14} /> Nuevo contrato
              </button>
            </div>
          </div>
        </header>

        <div className="mb-4 max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda}
            placeholder="Buscar por código, propiedad, inquilino..." />
        </div>

        <div className="flex flex-wrap gap-2 mb-8">
          <FilterPill active={filtro === 'todos'} onClick={() => setFiltro('todos')} label={`Todos (${list.length})`} />
          <FilterPill active={filtro === 'por_vencer'} onClick={() => setFiltro('por_vencer')}
            label={`Por vencer · ≤60 días (${porVencerCount})`} />
          {ESTADOS.map(e => (
            <FilterPill key={e} active={filtro === e} onClick={() => setFiltro(e)}
              label={`${e} (${list.filter(c => c.estado === e).length})`} />
          ))}
          <label className="ml-2 flex items-center gap-1.5 text-[11px] text-muted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={incluirArchivados}
              onChange={e => setIncluirArchivados(e.target.checked)}
              className="accent-[#B8893A]"
            />
            Incluir archivados
          </label>
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
              <div key={c.id} className={`card p-6 card-hover ${c.archivado ? 'opacity-60' : ''}`}>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="w-10 h-10 rounded-2xl bg-[#F0F0F0] dark:bg-[#1E1E1E] grid place-items-center shrink-0">
                      <FileText size={16} className="text-[#737373] dark:text-[#9A9A9A]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-[14px] tracking-tight truncate">
                        {propietarioName(c) || c.codigo || `Contrato #${c.id}`}
                      </p>
                      <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">
                        {TIPO_LABEL[c.tipo] || c.tipo}
                        {c.codigo && <span className="text-muted/60 ml-1.5">· {c.codigo}</span>}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    <div className="flex items-center gap-1.5">
                      {c.archivado && <span className="chip-muted">archivado</span>}
                      <span className={ESTADO_CHIP[c.estado] || 'chip-muted'}>{c.estado}</span>
                    </div>
                    <ProgresoContrato inicio={c.fecha_inicio} fin={c.fecha_fin} estado={c.estado} />
                  </div>
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

                {c.archivo_nombre && (
                  <div className="mt-3 px-3 py-2 rounded-xl bg-success/5 border border-success/20 text-[11px] text-success flex items-center gap-2">
                    <FileCheck2 size={12} />
                    <span className="truncate flex-1">{c.archivo_nombre}</span>
                    <button className="underline" onClick={() => descargarArchivo(c)}>Descargar</button>
                  </div>
                )}

                <div className="flex flex-wrap gap-2 mt-4">
                  <button className="btn-secondary flex-1 text-[12px] py-2"
                    onClick={() => setHistorialContrato(c)}>
                    <DollarSign size={12} /> Pagos
                  </button>
                  <button className="btn-ghost py-2 px-3 text-[12px]" title="Ver PDF del contrato"
                    onClick={() => verPDF(c)}>
                    <Eye size={12} />
                  </button>
                  <button className="btn-ghost py-2 px-3 text-[12px]" title="Editar"
                    onClick={() => { setEditing(c); setOpen(true) }}>
                    <Pencil size={12} />
                  </button>
                  <button className="btn-ghost py-2 px-3 text-[12px]" title="Descargar PDF legal"
                    onClick={() => descargarPDF(c)}>
                    <Download size={12} />
                  </button>
                  <button className="btn-ghost py-2 px-3 text-[12px]" title="Descargar Word editable"
                    onClick={() => descargarDocx(c)}>
                    <FileType2 size={12} />
                  </button>
                  <label className="btn-ghost py-2 px-3 text-[12px] cursor-pointer" title="Subir contrato firmado / actualizado">
                    <Upload size={12} />
                    <input type="file" className="hidden"
                      accept=".docx,.doc,.pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf"
                      onChange={e => { subirArchivo(c, e.target.files?.[0]); e.target.value = '' }} />
                  </label>
                  <button className="btn-ghost py-2 px-3 text-[12px]"
                    title={c.archivado ? 'Desarchivar' : 'Archivar'}
                    onClick={() => archivar(c)}>
                    {c.archivado ? <ArchiveRestore size={12} /> : <Archive size={12} />}
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

      {importOpen && (
        <ImportarContratoPDF
          onClose={() => setImportOpen(false)}
          onSaved={() => { setImportOpen(false); load() }}
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
  // Cuando se edita un contrato existente, normalizar inquilinos_ids desde
  // initial.inquilinos_lista (formato del backend) o desde el legacy inquilino_id.
  const _normalizeInitial = (i) => {
    if (!i) return { ...empty }
    const inquilinos_ids = Array.isArray(i.inquilinos_lista) && i.inquilinos_lista.length
      ? i.inquilinos_lista
          .slice()
          .sort((a, b) => (b.es_principal ? 1 : 0) - (a.es_principal ? 1 : 0))
          .map(x => x.cliente_id)
      : (i.inquilino_id ? [i.inquilino_id] : [])
    return {
      ...empty,
      ...i,
      fecha_inicio: i.fecha_inicio || '',
      fecha_fin:    i.fecha_fin || '',
      inquilinos_ids,
      inquilino_id: inquilinos_ids[0] || '',
    }
  }
  const [form, setForm]   = useState(_normalizeInitial(initial))
  const [loading, setLoading] = useState(false)
  const [err, setErr]     = useState('')
  const [propsLocal, setPropsLocal] = useState(propiedades)
  const [clientesLocal, setClientesLocal] = useState(clientes)
  const [creando, setCreando] = useState(null)  // 'propiedad' | 'propietario' | 'inquilino' | null
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  useEffect(() => { setPropsLocal(propiedades) }, [propiedades])
  useEffect(() => { setClientesLocal(clientes) }, [clientes])

  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    ;['propiedad_id','inquilino_id','monto_inicial','deposito','periodicidad_meses','porcentaje_fijo','comision_porc'].forEach(k => {
      if (payload[k] === '' || payload[k] == null) payload[k] = null
      else payload[k] = Number(payload[k]) || null
    })
    if (!payload.fecha_inicio) payload.fecha_inicio = null
    if (!payload.fecha_fin)    payload.fecha_fin    = null

    // Mapear inquilinos_ids → inquilinos[] (el backend lo espera así).
    // El primero es el principal. Quitamos el array auxiliar y mandamos
    // ambos campos para que el backend pueda hacer compat con clientes viejos.
    const ids = (form.inquilinos_ids || []).filter(Boolean)
    if (ids.length > 0) {
      payload.inquilinos = ids.map((cid, idx) => ({
        cliente_id: Number(cid),
        es_principal: idx === 0,
      }))
      payload.inquilino_id = Number(ids[0])
    } else {
      payload.inquilinos = []
    }
    delete payload.inquilinos_ids
    delete payload.inquilinos_lista  // solo lectura

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
          <h2 className="hero-title text-xl sm:text-2xl">{initial ? 'Editar contrato' : 'Nuevo contrato'}</h2>
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
            <div className="flex items-center justify-between">
              <label className="label">Propiedad *</label>
              <button type="button" onClick={() => setCreando('propiedad')}
                className="text-[11px] text-primary dark:text-white hover:underline font-medium">
                + Nueva propiedad
              </button>
            </div>
            <select className="input" value={form.propiedad_id || ''} onChange={set('propiedad_id')} required>
              <option value="">Seleccionar propiedad…</option>
              {propsLocal.map(p => <option key={p.id} value={p.id}>{p.direccion}</option>)}
            </select>
          </div>

          <InquilinosMulti
            inquilinos_ids={form.inquilinos_ids}
            clientes={clientesLocal}
            onChange={(ids) => setForm(f => ({
              ...f,
              inquilinos_ids: ids,
              inquilino_id: ids[0] || '',
            }))}
            onNuevoInquilino={() => setCreando('inquilino')}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Fecha inicio</label>
              <input className="input" type="date" value={form.fecha_inicio || ''} onChange={set('fecha_inicio')} />
            </div>
            <div>
              <label className="label">Fecha fin</label>
              <input className="input" type="date" value={form.fecha_fin || ''} onChange={set('fecha_fin')} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Comisión %</label>
              <input className="input" type="number" step="0.1" value={form.comision_porc || ''} onChange={set('comision_porc')} />
            </div>
            <div>
              <label className="label">Estado</label>
              <select className="input" value={form.estado} onChange={set('estado')}>
                {ESTADOS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <p className="text-[11px] text-muted mt-1">
                {form.estado === 'vigente'
                  ? '✓ Aparecerá en Cobros para gestionar pagos.'
                  : form.estado === 'borrador'
                  ? '⚠ Como borrador NO aparece en Cobros. Cambialo a "vigente" cuando se firme.'
                  : form.estado === 'vencido'
                  ? 'Cerrado por vencimiento. No genera nuevos cobros.'
                  : form.estado === 'rescindido'
                  ? 'Cerrado anticipadamente. No genera nuevos cobros.'
                  : 'Reservado pero no firmado.'}
              </p>
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

      {creando === 'propiedad' && (
        <ModalQuickPropiedad
          onClose={() => setCreando(null)}
          onSaved={p => {
            setPropsLocal(prev => [p, ...prev])
            setForm(f => ({ ...f, propiedad_id: p.id }))
            setCreando(null)
          }}
        />
      )}
      {creando === 'inquilino' && (
        <ModalQuickCliente
          rol="inquilino"
          onClose={() => setCreando(null)}
          onSaved={c => {
            setClientesLocal(prev => [c, ...prev])
            // Agregar al final de la lista de inquilinos del contrato.
            // Si es el primero, queda como principal automáticamente.
            setForm(f => {
              const ids = [...(f.inquilinos_ids || []), c.id]
              return { ...f, inquilinos_ids: ids, inquilino_id: ids[0] }
            })
            setCreando(null)
          }}
        />
      )}
    </div>
  )
}


/**
 * Multi-select de inquilinos firmantes del contrato.
 *
 * El primer item de la lista es siempre el TITULAR PRINCIPAL — se marca
 * visualmente con un chip "PRINCIPAL" en cobre y queda en sync con el campo
 * legacy `inquilino_id` del backend.
 *
 * Para agregar co-inquilinos (matrimonios, sociedades, hermanos que firman
 * juntos): elegirlos del select de abajo o crear nuevos con "+ Nuevo inquilino".
 */
function InquilinosMulti({ inquilinos_ids, clientes, onChange, onNuevoInquilino }) {
  const ids = inquilinos_ids || []
  const elegibles = (clientes || []).filter(
    c => c.rol === 'inquilino' || c.rol === 'comprador'
  )
  const disponibles = elegibles.filter(c => !ids.includes(c.id))
  const seleccionados = ids
    .map(id => elegibles.find(c => c.id === id))
    .filter(Boolean)

  const agregar = (id) => {
    const numId = Number(id)
    if (!numId || ids.includes(numId)) return
    onChange([...ids, numId])
  }
  const quitar = (id) => onChange(ids.filter(x => x !== id))
  const hacerPrincipal = (id) => {
    // Mover el id elegido al inicio de la lista
    const restantes = ids.filter(x => x !== id)
    onChange([id, ...restantes])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="label !mb-0">
          Inquilino{ids.length > 1 ? `s (${ids.length})` : ''} / Comprador
        </label>
        <button type="button" onClick={onNuevoInquilino}
          className="text-[11px] text-primary dark:text-white hover:underline font-medium">
          + Nuevo inquilino
        </button>
      </div>

      {/* Lista de inquilinos ya seleccionados */}
      {seleccionados.length > 0 && (
        <div className="space-y-2 mb-2">
          {seleccionados.map((c, idx) => (
            <div key={c.id}
              className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-neutral-50 dark:bg-[#141414] border border-border dark:border-[#2A2A2A]">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[13px] font-medium truncate">
                  {c.nombre} {c.apellido || ''}
                </span>
                {idx === 0 && (
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-[#B8893A] bg-[#B8893A]/10 px-1.5 py-0.5 rounded-full">
                    PRINCIPAL
                  </span>
                )}
                {c.documento && (
                  <span className="text-[11px] text-muted font-mono">{c.documento}</span>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {idx > 0 && (
                  <button type="button" onClick={() => hacerPrincipal(c.id)}
                    className="text-[10px] text-muted hover:text-primary dark:hover:text-white underline">
                    hacer principal
                  </button>
                )}
                <button type="button" onClick={() => quitar(c.id)}
                  className="text-[10px] text-danger hover:underline">
                  Quitar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Select para agregar más */}
      <select className="input" value="" onChange={e => agregar(e.target.value)}>
        <option value="">
          {seleccionados.length === 0
            ? 'Sin asignar — elegí un inquilino'
            : '+ Agregar otro inquilino firmante'}
        </option>
        {disponibles.map(c => (
          <option key={c.id} value={c.id}>
            {c.nombre} {c.apellido || ''} {c.documento ? `· ${c.documento}` : ''}
          </option>
        ))}
      </select>

      {ids.length > 1 && (
        <p className="text-[10px] text-muted mt-1.5">
          {ids.length} firmantes. Los co-inquilinos son solidariamente responsables del alquiler.
        </p>
      )}
    </div>
  )
}


function ModalQuickPropiedad({ onClose, onSaved }) {
  const [form, setForm] = useState({
    direccion: '', tipo: 'departamento', ciudad: '', provincia: '',
    modalidad: 'alquiler', estado: 'disponible',
    precio_alquiler: '', expensas: '',
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    const payload = { ...form }
    ;['precio_alquiler','expensas'].forEach(k => {
      payload[k] = payload[k] === '' ? null : Number(payload[k]) || null
    })
    try {
      const r = await api.post('/api/propiedades', payload)
      onSaved(r.data)
    } catch (e) { setErr(e.response?.data?.detail || 'Error al crear propiedad.') }
    finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-md shadow-lift animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="hero-title text-xl">Nueva propiedad</h3>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="label">Dirección *</label>
            <input className="input" required value={form.direccion} onChange={set('direccion')} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Tipo</label>
              <select className="input" value={form.tipo} onChange={set('tipo')}>
                {['departamento','casa','local','oficina','galpon','campo'].map(t =>
                  <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Ciudad</label>
              <input className="input" value={form.ciudad} onChange={set('ciudad')} />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Alquiler $</label>
              <input className="input" type="number" value={form.precio_alquiler} onChange={set('precio_alquiler')} />
            </div>
            <div>
              <label className="label">Expensas $</label>
              <input className="input" type="number" value={form.expensas} onChange={set('expensas')} />
            </div>
          </div>
          {err && <p className="text-[12px] text-danger">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>{loading ? 'Creando…' : 'Crear'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}


function ModalQuickCliente({ rol, onClose, onSaved }) {
  const [form, setForm] = useState({
    nombre: '', apellido: '', razon_social: '',
    documento: '', email: '', telefono: '', rol, notas: '',
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      const r = await api.post('/api/clientes', form)
      onSaved(r.data)
    } catch (e) { setErr(e.response?.data?.detail || 'Error al crear.') }
    finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-md shadow-lift animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="hero-title text-xl">Nuevo {rol}</h3>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Nombre *</label>
              <input className="input" required value={form.nombre} onChange={set('nombre')} />
            </div>
            <div>
              <label className="label">Apellido</label>
              <input className="input" value={form.apellido} onChange={set('apellido')} />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
          {err && <p className="text-[12px] text-danger">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>{loading ? 'Creando…' : 'Crear'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
