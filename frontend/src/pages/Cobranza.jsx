import { useEffect, useMemo, useState } from 'react'
import Layout from '../components/Layout/Layout'
import SearchBar, { match } from '../components/SearchBar'
import api from '../utils/api'
import ModalTasaMSR from '../components/ModalTasaMSR'
import {
  CheckCircle, Clock, AlertCircle, ChevronLeft, ChevronRight,
  Phone, Mail, X, FileText, Download, Send, AlertTriangle, Wrench, Landmark, Check,
} from 'lucide-react'

const ESTADO_CONFIG = {
  pagado:    { label: 'Cobrado',   bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', icon: CheckCircle },
  pendiente: { label: 'Pendiente', bg: 'bg-amber-50 dark:bg-amber-900/20',  text: 'text-amber-700 dark:text-amber-400', icon: Clock },
  vencido:   { label: 'Vencido',   bg: 'bg-red-50 dark:bg-red-900/20',      text: 'text-red-600 dark:text-red-400',     icon: AlertCircle },
  parcial:   { label: 'Parcial',   bg: 'bg-blue-50 dark:bg-blue-900/20',    text: 'text-blue-700 dark:text-blue-400',   icon: Clock },
}

const fmtMoney = n => '$' + Number(n || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 })
const prevMes = m => { const [y,mm]=m.split('-').map(Number); return mm===1?`${y-1}-12`:`${y}-${String(mm-1).padStart(2,'0')}` }
const nextMes = m => { const [y,mm]=m.split('-').map(Number); return mm===12?`${y+1}-01`:`${y}-${String(mm+1).padStart(2,'0')}` }
const mesLabel = m => { const [y,mm]=m.split('-').map(Number); return new Date(y,mm-1,1).toLocaleString('es-AR',{month:'long',year:'numeric'}) }

export default function Cobranza() {
  const hoy = new Date()
  const [mes, setMes]           = useState(`${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}`)
  const [items, setItems]       = useState([])
  const [resumen, setResumen]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const [filtro, setFiltro]     = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [registroOpen, setRegistroOpen] = useState(null)   // item activo
  const [resultado, setResultado] = useState(null)         // resultado del POST registrar-pago

  const cargar = async () => {
    setLoading(true)
    try {
      const [m, r] = await Promise.all([
        api.get(`/api/cobranza/mensual?mes=${mes}`),
        api.get(`/api/cobranza/resumen?mes=${mes}`),
      ])
      setItems(m.data)
      setResumen(r.data)
    } finally { setLoading(false) }
  }
  useEffect(() => { cargar() }, [mes])

  const filtrados = useMemo(() => {
    let r = filtro === 'todos' ? items : items.filter(p => p.estado === filtro)
    if (busqueda.trim()) {
      r = r.filter(p => match(
        busqueda,
        p.propiedad, p.propiedad_ciudad,
        p.inquilino, p.inquilino_email, p.inquilino_telefono,
        p.propietario, p.propietario_email,
        p.contrato_codigo,
      ))
    }
    return r
  }, [items, filtro, busqueda])

  const cuentas = useMemo(() => ({
    todos: items.length,
    pendiente: items.filter(p => p.estado === 'pendiente').length,
    pagado: items.filter(p => p.estado === 'pagado').length,
    vencido: items.filter(p => p.estado === 'vencido').length,
  }), [items])

  return (
    <Layout>
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 dark:text-gray-500 uppercase mb-1">Alquileres</p>
            <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Cobranza</h1>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Atajo a la web de la muni para consultar la deuda municipal en vivo */}
            <a
              href="https://consultadeuda.santarosa.gob.ar/"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost gap-1.5 text-[12px]"
              title="Abrir el portal de la Municipalidad de Santa Rosa para consultar tasas/deuda municipal"
            >
              <Landmark size={14} /> Consultar tasas (Muni)
            </a>
            <button onClick={() => setMes(prevMes(mes))} className="btn-ghost p-2"><ChevronLeft size={16} /></button>
            <span className="text-sm font-semibold capitalize min-w-[160px] text-center">{mesLabel(mes)}</span>
            <button onClick={() => setMes(nextMes(mes))} className="btn-ghost p-2"><ChevronRight size={16} /></button>
          </div>
        </div>

        {/* Resumen */}
        {resumen && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Total esperado" value={fmtMoney(resumen.total_esperado)} />
            <Stat label="Cobrado"        value={fmtMoney(resumen.cobrado)}    color="text-green-600 dark:text-green-400" />
            <Stat label="Pendiente"      value={fmtMoney(resumen.pendiente)}  color="text-amber-600" />
            <Stat label="Vencido"        value={fmtMoney(resumen.vencido)}    color={resumen.vencido > 0 ? 'text-red-500' : ''} />
          </div>
        )}

        {/* Búsqueda */}
        <div className="max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda}
            placeholder="Buscar por propiedad, inquilino, propietario..." />
        </div>

        {/* Filtros */}
        <div className="flex gap-2 flex-wrap">
          {['todos','pendiente','pagado','vencido'].map(f => (
            <button key={f} onClick={() => setFiltro(f)}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors
                ${filtro === f
                  ? 'bg-black dark:bg-white text-white dark:text-black'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}>
              {f === 'todos' ? 'Todos' : (ESTADO_CONFIG[f]?.label || f)}
              <span className="ml-1 opacity-60">{cuentas[f] ?? 0}</span>
            </button>
          ))}
        </div>

        {/* Tabla */}
        <div className="card overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-sm text-gray-400 dark:text-gray-500">Cargando...</div>
          ) : filtrados.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400 dark:text-gray-500">No hay contratos para este período.</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <th className="th text-left">Propiedad</th>
                  <th className="th text-left">Inquilino</th>
                  <th className="th text-left hidden lg:table-cell">Propietario</th>
                  <th className="th text-right">Monto</th>
                  <th className="th text-center">Estado</th>
                  <th className="th text-center">Acción</th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map((p, i) => {
                  const cfg = ESTADO_CONFIG[p.estado] || ESTADO_CONFIG.pendiente
                  const Icon = cfg.icon
                  return (
                    <tr key={p.contrato_id} className="border-b border-gray-50 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                      <td className="td">
                        <p className="font-medium text-sm">{p.propiedad}</p>
                        <p className="text-xs text-gray-400 dark:text-gray-500">{p.contrato_codigo} · {p.propiedad_ciudad}</p>
                      </td>
                      <td className="td">
                        <p className="text-sm">{p.inquilino}</p>
                        {p.inquilino_email && (
                          <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1 truncate max-w-[180px]">
                            <Mail size={10} />{p.inquilino_email}
                          </p>
                        )}
                      </td>
                      <td className="td hidden lg:table-cell">
                        <p className="text-sm">{p.propietario || '—'}</p>
                        {p.comision_porc > 0 && (
                          <p className="text-xs text-gray-400 dark:text-gray-500">Comisión {p.comision_porc}%</p>
                        )}
                      </td>
                      <td className="td text-right">
                        <p className="font-semibold text-sm">{fmtMoney(p.monto_total)}</p>
                      </td>
                      <td className="td text-center">
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>
                          <Icon size={11} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="td text-center">
                        {p.estado === 'pagado' ? (
                          <span className="text-xs text-green-600 dark:text-green-400">
                            ✓ {p.fecha_pago ? new Date(p.fecha_pago).toLocaleDateString('es-AR') : ''}
                          </span>
                        ) : (
                          <button onClick={() => setRegistroOpen(p)}
                            className="text-xs bg-black dark:bg-white text-white dark:text-black px-3 py-1.5 rounded-lg font-medium hover:opacity-80 transition">
                            Registrar pago
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {registroOpen && (
        <RegistrarPagoModal
          item={registroOpen}
          mes={mes}
          onClose={() => setRegistroOpen(null)}
          onSaved={(res) => { setRegistroOpen(null); setResultado(res); cargar() }}
        />
      )}
      {resultado && <ResultadoModal data={resultado} onClose={() => setResultado(null)} />}
    </Layout>
  )
}

function Stat({ label, value, color = '' }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-black ${color}`}>{value}</p>
    </div>
  )
}

/**
 * Tabla de cobro al inquilino.
 *
 * Modelo por fila: { label, monto, ya_pagado, fijo?, _arrastre? }
 *   - monto:     importe del concepto.
 *   - ya_pagado: true  → el inquilino ya lo pagó directamente (no se cobra ahora).
 *                false → se cobra al inquilino en este período.
 *
 * 3 filas fijas: Alquiler, Expensas, Tasas municipales (no se pueden eliminar).
 * Se pueden agregar conceptos extra (Luz, Gas, Agua, Internet, ABL, Seguro, etc.)
 */
const CONCEPTOS_FIJOS = ['Alquiler', 'Expensas', 'Tasas municipales']

function TablaConceptos({ conceptos, onUpdate, onRemove, onAdd }) {
  const SUGERENCIAS = [
    'Luz', 'Gas', 'Agua', 'Internet', 'ABL', 'Seguro', 'Servicios varios',
  ]
  const yaUsados = new Set((conceptos || []).map(c => c.label?.toLowerCase()))
  const disponibles = SUGERENCIAS.filter(s => !yaUsados.has(s.toLowerCase()))

  // Toggle mutex: clickear "pagado" o "cobrar" cancela el otro
  const setEstado = (i, nuevo) => onUpdate(i, 'estado', nuevo)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="label !mb-0">Conceptos del cobro</label>
        <span className="text-[10px] text-muted">Marcá quién paga cada cosa</span>
      </div>

      {/* Header de columnas */}
      <div className="grid grid-cols-[1fr_100px_58px_58px_24px] gap-2 px-2 mb-1 text-[10px] uppercase tracking-wider text-muted font-semibold">
        <span>Concepto</span>
        <span className="text-right">Monto</span>
        <span className="text-center">Pagado</span>
        <span className="text-center">A cobrar</span>
        <span></span>
      </div>

      {/* Filas */}
      <div className="space-y-1.5">
        {(conceptos || []).map((c, i) => {
          const estado = c.estado || null     // 'pagado' | 'cobrar' | null
          const activo = estado !== null
          return (
            <div key={i}
              className={`grid grid-cols-[1fr_100px_58px_58px_24px] gap-2 items-center p-2 rounded-xl border transition-all ${
                c._arrastre
                  ? 'bg-amber-50 dark:bg-amber-900/10 border-amber-300/50 dark:border-amber-700/40'
                  : estado === 'cobrar'
                    ? 'bg-neutral-50 dark:bg-[#1A1A1A] border-[#0A0A0A]/30 dark:border-white/30'
                    : estado === 'pagado'
                      ? 'bg-green-50/60 dark:bg-green-900/10 border-green-300/40 dark:border-green-700/30'
                      : 'bg-white dark:bg-[#0F0F0F] border-border/40 dark:border-[#1E1E1E] opacity-50'
              }`}
              title={c._arrastre ? `Arrastrado de ${c._arrastre} (quedó pendiente)` : undefined}>

              {/* Concepto */}
              {c.fijo ? (
                <div className="min-w-0 px-1">
                  <p className="text-[13px] font-medium">{c.label}</p>
                  {c.label === 'Tasas municipales' && estado === 'cobrar' && (
                    <p className="text-[10px] text-muted">100% al propietario</p>
                  )}
                  {c._arrastre && (
                    <p className="text-[10px] text-amber-600 dark:text-amber-400">arrastre de {c._arrastre}</p>
                  )}
                </div>
              ) : (
                <div className="min-w-0">
                  <input type="text" placeholder="Ej: Luz"
                    className="input !py-1.5 !px-2 text-[12px]"
                    value={c.label || ''}
                    onChange={e => onUpdate(i, 'label', e.target.value)} />
                  {c.label?.toLowerCase().includes('municipal') && estado === 'cobrar' && (
                    <p className="text-[10px] text-muted mt-0.5 px-1">100% al propietario</p>
                  )}
                </div>
              )}

              {/* Monto */}
              <input type="number" placeholder="0"
                className="input !py-1.5 !px-2 text-right tabular-nums text-[12px]"
                value={c.monto || ''}
                onChange={e => onUpdate(i, 'monto', e.target.value === '' ? 0 : Number(e.target.value))} />

              {/* Checkbox "Pagado" — el inquilino lo abonó directo (no se cobra acá) */}
              <div className="flex justify-center">
                <button type="button"
                  onClick={() => setEstado(i, estado === 'pagado' ? null : 'pagado')}
                  title="El inquilino ya lo pagó directo (no se le rinde al propietario)"
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center shrink-0 transition-all ${
                    estado === 'pagado'
                      ? 'bg-green-500 border-green-500 text-white'
                      : 'border-[#0A0A0A] dark:border-white bg-white dark:bg-[#0A0A0A] hover:bg-neutral-100 dark:hover:bg-[#1A1A1A]'
                  }`}>
                  {estado === 'pagado' && <Check size={12} />}
                </button>
              </div>

              {/* Checkbox "A cobrar" — la inmobiliaria lo cobra y lo rinde al propietario */}
              <div className="flex justify-center">
                <button type="button"
                  onClick={() => setEstado(i, estado === 'cobrar' ? null : 'cobrar')}
                  title="Lo cobra la inmobiliaria y se le rinde al propietario"
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center shrink-0 transition-all ${
                    estado === 'cobrar'
                      ? 'bg-[#0A0A0A] dark:bg-white border-[#0A0A0A] dark:border-white text-white dark:text-[#0A0A0A]'
                      : 'border-[#0A0A0A] dark:border-white bg-white dark:bg-[#0A0A0A] hover:bg-neutral-100 dark:hover:bg-[#1A1A1A]'
                  }`}>
                  {estado === 'cobrar' && <Check size={12} />}
                </button>
              </div>

              {/* Quitar (sólo extras) */}
              {c.fijo ? (
                <span />
              ) : (
                <button type="button"
                  onClick={() => onRemove(i)}
                  className="p-1 text-muted hover:text-danger rounded-lg"
                  title="Quitar">
                  <X size={13} />
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* Botones para agregar */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="text-[10px] text-muted uppercase tracking-widest mt-1.5 mr-1">Agregar:</span>
        {disponibles.map(s => (
          <button key={s} type="button"
            onClick={() => onAdd({ label: s, monto: 0, estado: null })}
            className="text-[11px] px-2.5 py-1 rounded-full bg-white dark:bg-[#1A1A1A] border border-border dark:border-[#2A2A2A] text-muted hover:bg-neutral-50 dark:hover:bg-[#252525] hover:text-primary dark:hover:text-white transition">
            + {s}
          </button>
        ))}
        <button type="button"
          onClick={() => onAdd({ label: '', monto: 0, estado: null })}
          className="text-[11px] px-2.5 py-1 rounded-full bg-white dark:bg-[#1A1A1A] border border-dashed border-border dark:border-[#2A2A2A] text-muted hover:bg-neutral-50 dark:hover:bg-[#252525] hover:text-primary dark:hover:text-white transition">
          + Otro…
        </button>
      </div>
    </div>
  )
}


function RegistrarPagoModal({ item, mes, onClose, onSaved }) {
  // Refacciones pendientes del inquilino para este contrato. Por defecto
  // las pre-seleccionamos todas para que el descuento aparezca calculado.
  const refsPend = item.refacciones_pendientes || []
  const [refsSelected, setRefsSelected] = useState(
    () => new Set(refsPend.map(r => r.id))
  )
  const toggleRef = (id) => {
    setRefsSelected(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }
  const descuentoRefs = refsPend
    .filter(r => refsSelected.has(r.id))
    .reduce((s, r) => s + (Number(r.monto) || 0), 0)

  // Precarga: 3 filas fijas (Alquiler, Expensas, Tasas municipales) con
  // monto sugerido desde el contrato/propiedad en columna "A cobrar".
  // Después se suman los arrastres de períodos anteriores (que quedaron
  // pendientes y se cobran ahora) y luego servicios extra que se agreguen.
  const pendientesArrastre = item.conceptos_pendientes || []
  const labelsArrastre = new Set(pendientesArrastre.map(p => p.label.toLowerCase()))

  // Helper: si hay arrastre para este label fijo, sumamos el monto al a_cobrar.
  const arrastreFor = (lbl) => {
    const a = pendientesArrastre.find(p => p.label.toLowerCase() === lbl.toLowerCase())
    return a ? Number(a.monto) || 0 : 0
  }
  const extraSug = (lbl, sug) => (Number(sug) || 0) + arrastreFor(lbl)

  const [form, setForm] = useState({
    fecha_pago: new Date().toISOString().slice(0, 10),
    notas: '',
    conceptos: [
      { label: 'Alquiler',          fijo: true, monto: Number(item.monto_alquiler_sug ?? item.monto_total ?? 0) || 0, estado: null },
      { label: 'Expensas',          fijo: true, monto: extraSug('Expensas', item.monto_expensas_sug),               estado: null },
      { label: 'Tasas municipales', fijo: false, monto: extraSug('Tasas municipales', item.monto_tasas_sug),         estado: null },
      // Arrastres de OTROS conceptos (no Expensas / Tasas que ya están arriba)
      ...pendientesArrastre
        .filter(p => !CONCEPTOS_FIJOS.some(f => f.toLowerCase() === p.label.toLowerCase()))
        .map(p => ({
          label: p.label, monto: Number(p.monto) || 0, estado: null, _arrastre: p.desde_periodo,
        })),
    ],
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const setFecha = (val) => setForm(f => ({ ...f, fecha_pago: val }))
  const setNotas = (val) => setForm(f => ({ ...f, notas: val }))

  const [msrOpen, setMsrOpen] = useState(false)

  const updateConcepto = (idx, campo, valor) => {
    setForm(f => ({
      ...f,
      conceptos: f.conceptos.map((c, i) => i === idx ? { ...c, [campo]: valor } : c),
    }))
  }
  const eliminarConcepto = (idx) => {
    setForm(f => ({ ...f, conceptos: f.conceptos.filter((_, i) => i !== idx) }))
  }
  const agregarConcepto = (preset) => {
    setForm(f => ({ ...f, conceptos: [...f.conceptos, preset] }))
  }

  // Total a cobrar al inquilino: suma de montos donde estado='cobrar',
  // menos descuento de refacciones. Los 'pagado' se asientan pero no se cobran.
  const aCobrarInq = (form.conceptos || [])
    .filter(c => c.estado === 'cobrar')
    .reduce((s, c) => s + (Number(c.monto) || 0), 0)
  const total = Math.max(0, aCobrarInq - descuentoRefs)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true); setErr('')
    try {
      // Mapeo al backend:
      // - Alquiler: va en monto_alquiler solo si estado='cobrar' (la inmobiliaria lo cobra)
      // - Filas con estado='cobrar'  → backend: estado='cobrar' (se le rinde al propietario)
      // - Filas con estado='pagado'  → backend: estado='pagado_directo'
      //   (el inquilino lo pagó por su cuenta — informativo, NO se le rinde al propietario)
      // - Filas con estado=null (sin marcar) → se ignoran (no van en este pago)
      const filaAlquiler = form.conceptos.find(c => c.label === 'Alquiler' && c.estado === 'cobrar') || { monto: 0 }
      const montoAlquilerTotal = Number(filaAlquiler.monto) || 0

      const conceptos = []
      for (const c of form.conceptos) {
        if (!c.estado) continue                       // sin marcar: no va
        if (c.label === 'Alquiler' || !c.label?.trim()) continue
        const label = c.label.trim()
        const monto = Number(c.monto) || 0
        if (monto <= 0) continue
        const estadoBackend = c.estado === 'pagado' ? 'pagado_directo' : 'cobrar'
        conceptos.push({ label, monto, estado: estadoBackend })
      }

      const payload = {
        periodo: mes,
        fecha_pago: form.fecha_pago || null,
        monto_alquiler: montoAlquilerTotal,
        conceptos,
        monto_descuento_refacciones: descuentoRefs,
        refacciones_aplicadas: Array.from(refsSelected),
        monto_total: total,
        notas: form.notas || null,
      }
      const r = await api.post(`/api/cobranza/${item.contrato_id}/registrar-pago`, payload)
      onSaved(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al registrar el pago.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-7 w-full max-w-2xl shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="hero-title text-xl sm:text-2xl mb-0.5">Cobrar al inquilino</h2>
            <p className="text-[12px] text-[#737373]">{item.propiedad} · {item.contrato_codigo}</p>
            {item.numero_referencia && (
              <p className="text-[11px] text-muted/70">
                Ref. municipal: <span className="font-mono font-semibold">{item.numero_referencia}</span>
              </p>
            )}
            <p className="text-[12px] text-[#737373]">Inquilino: {item.inquilino}</p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button"
              onClick={() => setMsrOpen(true)}
              disabled={!item.numero_referencia}
              title={item.numero_referencia ? 'Consultar tasas municipales (MSR)' : 'Cargá el Nº de referencia en la propiedad para usar este botón'}
              className="btn-ghost p-2 disabled:opacity-40 disabled:cursor-not-allowed">
              <Landmark size={16} />
            </button>
            <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
          </div>
        </div>

        {msrOpen && (
          <ModalTasaMSR
            propiedad={{ id: item.propiedad_id, numero_referencia: item.numero_referencia, direccion: item.propiedad }}
            onClose={() => setMsrOpen(false)}
            onActualizado={() => setMsrOpen(false)}
          />
        )}

        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Período</label>
              <input className="input bg-neutral-50 dark:bg-[#1A1A1A]" value={mes} disabled />
            </div>
            <div>
              <label className="label">Fecha de pago</label>
              <input className="input" type="date" value={form.fecha_pago}
                onChange={e => setFecha(e.target.value)} />
            </div>
          </div>

          {/* Tabla de conceptos con columnas Pagado / A cobrar */}
          <TablaConceptos
            conceptos={form.conceptos}
            onUpdate={updateConcepto}
            onRemove={eliminarConcepto}
            onAdd={agregarConcepto}
          />

          <div>
            <label className="label">Notas</label>
            <textarea rows={2} className="input resize-none" value={form.notas}
              onChange={e => setNotas(e.target.value)} />
          </div>

          {/* Refacciones pendientes a descontar */}
          {refsPend.length > 0 && (
            <div className="rounded-2xl border border-[#B8893A]/30 bg-[#B8893A]/5 p-3">
              <div className="flex items-center gap-2 mb-2">
                <Wrench size={13} className="text-[#B8893A]" />
                <p className="text-[12px] font-semibold">
                  Refacciones a descontar <span className="text-muted font-normal">({refsPend.length} pendientes)</span>
                </p>
              </div>
              <div className="space-y-1.5">
                {refsPend.map(r => (
                  <label key={r.id}
                    className="flex items-center gap-2 text-[12px] cursor-pointer hover:bg-white/40 dark:hover:bg-black/20 rounded-lg px-2 py-1">
                    <input type="checkbox"
                      checked={refsSelected.has(r.id)}
                      onChange={() => toggleRef(r.id)}
                      className="accent-[#B8893A]" />
                    <span className="flex-1 truncate">
                      {r.descripcion}
                      <span className="text-muted ml-1">
                        · {r.fecha ? new Date(r.fecha).toLocaleDateString('es-AR') : ''}
                      </span>
                    </span>
                    <span className="font-semibold tabular-nums">− {fmtMoney(r.monto)}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Total a cobrar — único bloque visible al operador. Comisión y neto
              al propietario se calculan en backend y aparecen sólo en el PDF. */}
          <div className="rounded-2xl bg-[#0A0A0A] text-white dark:bg-white dark:text-[#0A0A0A] p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-widest opacity-60">Total a cobrar al inquilino</p>
                {descuentoRefs > 0 && (
                  <p className="text-[11px] opacity-60 mt-0.5">
                    {fmtMoney(aCobrarInq)} − {fmtMoney(descuentoRefs)} refacciones
                  </p>
                )}
              </div>
              <span className="text-3xl font-bold tabular-nums">{fmtMoney(total)}</span>
            </div>
          </div>

          <div className="text-[11px] text-muted bg-[#FAF8F3] dark:bg-[#141414] border border-[#E5E5E5] dark:border-[#2A2A2A] rounded-xl p-3 flex gap-2">
            <Send size={12} className="text-[#B8893A] shrink-0 mt-0.5" />
            <div>
              Al confirmar se generan dos comprobantes en PDF (recibo para el inquilino y
              liquidación para el propietario) y se intentan enviar por email a:
              <ul className="mt-1 space-y-0.5 list-disc list-inside opacity-80">
                <li><strong>Inquilino:</strong> {item.inquilino_email || 'sin email cargado'}</li>
                <li><strong>Propietario:</strong> {item.propietario_email || 'sin email cargado'}</li>
              </ul>
            </div>
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading || (form.conceptos || []).filter(c => c.estado).every(c => (Number(c.monto) || 0) === 0)}>
              {loading ? 'Procesando…' : 'Confirmar y emitir comprobantes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ResultadoModal({ data, onClose }) {
  const descargar = async (id) => {
    try {
      const r = await api.get(`/api/comprobantes/${id}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url; a.download = `comprobante-${id}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch {
      alert('No se pudo descargar el comprobante.')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[55] grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-7 w-full max-w-md shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="text-center mb-5">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 grid place-items-center mx-auto mb-3">
            <CheckCircle size={24} className="text-green-600 dark:text-green-400" />
          </div>
          <h3 className="hero-title text-xl sm:text-2xl mb-0.5">Pago registrado</h3>
          <p className="text-[12px] text-muted">
            Período {data.periodo} · {fmtMoney(data.monto_total)}
          </p>
        </div>

        <div className="rounded-2xl bg-[#F5F5F5] dark:bg-[#1A1A1A] p-4 mb-4 text-[13px] space-y-1">
          <div className="flex justify-between"><span className="text-muted">Total cobrado</span><span className="font-semibold">{fmtMoney(data.monto_total)}</span></div>
          <div className="flex justify-between"><span className="text-muted">Comisión</span><span>− {fmtMoney(data.comision)}</span></div>
          <div className="border-t border-border pt-1 flex justify-between font-semibold"><span>Neto al propietario</span><span className="text-[#B8893A]">{fmtMoney(data.neto_propietario)}</span></div>
        </div>

        <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-2">
          Comprobantes generados
        </p>
        <div className="space-y-2 mb-4">
          {data.comprobantes?.map(c => (
            <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl border border-[#E5E5E5] dark:border-[#2A2A2A]">
              <FileText size={16} className="text-[#737373] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium">
                  {c.tipo === 'inquilino' ? 'Recibo para el inquilino' : 'Liquidación para el propietario'}
                </p>
                <p className="text-[11px] text-muted truncate">
                  {c.destinatario}{c.email ? ` · ${c.email}` : ''}
                </p>
                <div className="flex items-center gap-1 mt-1">
                  {c.enviado_email ? (
                    <span className="inline-flex items-center gap-1 text-[10px] text-green-600 dark:text-green-400">
                      <Send size={9} /> Email enviado
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] text-amber-600">
                      <AlertTriangle size={9} /> {c.error || 'No enviado'}
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => descargar(c.id)}
                className="btn-secondary text-[11px] py-1.5 px-2.5 shrink-0">
                <Download size={11} /> PDF
              </button>
            </div>
          ))}
        </div>

        {!data.smtp_configurado && (
          <p className="text-[11px] text-muted bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900 rounded-xl p-3 mb-3">
            <strong>Email no configurado:</strong> los comprobantes quedaron guardados en la base
            y se pueden descargar en cualquier momento. Configurá SMTP_HOST/SMTP_USER/SMTP_PASS
            en <code>backend/.env</code> para activar el envío automático.
          </p>
        )}

        <button className="btn-primary w-full" onClick={onClose}>Cerrar</button>
      </div>
    </div>
  )
}
