import { useEffect, useState, useMemo } from 'react'
import {
  Flame, Thermometer, Snowflake, LayoutGrid, X, Clock, Plus,
  AlertTriangle, MapPin, Send, ChevronRight, History, ShieldAlert, Gauge, CalendarClock,
  Search, BedDouble, Building2
} from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import PedidoModal from '../../components/ventas/PedidoModal'
import { useRole } from '../../context/RoleContext'
import api from '../../utils/api'

// ── Etapas del pipeline (10, doc §3.4). El CRM ES el pipeline de cliente. ──
const ETAPAS = [
  ['nuevo_lead', 'Nuevo lead'],
  ['en_calificacion', 'En calificación'],
  ['calificado_activo', 'Calificado · activo'],
  ['presentacion_opciones', 'Presentación'],
  ['en_visitas', 'En visitas'],
  ['oferta_negociacion', 'Oferta / negociación'],
  ['reserva_sena', 'Reserva / seña'],
  ['escritura_cierre', 'Escritura / cierre'],
  ['caido_perdido', 'Caído / perdido'],
  ['frio_espera', 'Frío / en espera'],
]
const ETAPA_LABEL = Object.fromEntries(ETAPAS)
const PAUSA = ['caido_perdido', 'frio_espera']
const ETAPA_BAR = {
  nuevo_lead: 'bg-slate-400', en_calificacion: 'bg-sky-500', calificado_activo: 'bg-indigo-500',
  presentacion_opciones: 'bg-violet-500', en_visitas: 'bg-amber-500', oferta_negociacion: 'bg-orange-500',
  reserva_sena: 'bg-teal-500', escritura_cierre: 'bg-emerald-500', caido_perdido: 'bg-rose-400', frio_espera: 'bg-blue-400',
}

// La signature del CRM: temperatura como "espina de calor" en cada ficha.
const TEMP = {
  caliente: { label: 'Caliente', icon: Flame, spine: 'bg-red-500', dot: 'bg-red-500', tint: 'text-red-600 dark:text-red-400', soft: 'bg-red-500/10' },
  tibio: { label: 'Tibio', icon: Thermometer, spine: 'bg-amber-500', dot: 'bg-amber-500', tint: 'text-amber-600 dark:text-amber-400', soft: 'bg-amber-500/10' },
  frio: { label: 'Frío', icon: Snowflake, spine: 'bg-blue-400', dot: 'bg-blue-400', tint: 'text-blue-500 dark:text-blue-400', soft: 'bg-blue-500/10' },
}
const TEMP_ORDEN = ['caliente', 'tibio', 'frio']
const PEDIDO_ESTADO = {
  nuevo: 'Nuevo', contactado: 'Contactado', en_seguimiento: 'En seguimiento',
  esperando_respuesta: 'Esperando', negociando: 'Negociando', cerrado: 'Cerrado', perdido: 'Perdido',
}
const PERFILES = [['', '—'], ['contado', 'Contado'], ['credito', 'Crédito'], ['inversor', 'Inversor'], ['espera_vender', 'Espera vender'], ['oportunista', 'Oportunista']]
const TIPO_OP = [['', '—'], ['venta_propia', 'Venta propia'], ['inversion', 'Inversión'], ['colega', 'Colega']]
const ACCIONES = [['llamada', 'Llamada'], ['whatsapp', 'WhatsApp'], ['visita', 'Visita'], ['envio', 'Envío de propiedades'], ['reunion', 'Reunión'], ['seguimiento', 'Seguimiento pasivo']]

const usd = n => n ? `USD ${Number(n).toLocaleString('es-AR')}` : null
const esHoy = iso => {
  if (!iso) return false
  const d = new Date(iso), h = new Date()
  return d.getFullYear() === h.getFullYear() && d.getMonth() === h.getMonth() && d.getDate() === h.getDate()
}

export default function CRMVentas() {
  const { isAdmin, role } = useRole()
  const esAdmin = isAdmin || role === 'ventas_admin' || role === 'gerencia'
  const [vista, setVista] = useState('etapas')       // etapas | temperatura
  const [data, setData] = useState({ clientes: [] })
  const [consultas, setConsultas] = useState([])
  const [loading, setLoading] = useState(true)
  const [sel, setSel] = useState(null)
  const [dragId, setDragId] = useState(null)
  const [overCol, setOverCol] = useState(null)
  const [banner, setBanner] = useState('')
  const [nuevo, setNuevo] = useState(null)

  const cargar = async () => {
    setLoading(true)
    try { const { data } = await api.get('/api/ventas-crm/pipeline'); setData(data) }
    catch { setData({ clientes: [] }) } finally { setLoading(false) }
    if (esAdmin) {
      try { const { data } = await api.get('/api/ventas-crm/pipeline/consultas'); setConsultas(data.consultas || []) } catch {}
    }
  }
  useEffect(() => { cargar() }, [])

  const activos = useMemo(() => data.clientes.filter(c => !PAUSA.includes(c.etapa)), [data])
  const pulso = useMemo(() => ({
    calientes: activos.filter(c => c.temperatura === 'caliente').length,
    sinAccion: activos.filter(c => c.sin_proxima_accion).length,
    slaVencido: activos.filter(c => c.sla_vencido).length,
    hoy: activos.filter(c => c.proxima_accion_vencida || esHoy(c.proxima_accion_fecha)).length,
  }), [activos])

  const porEtapa = useMemo(() => {
    const m = {}; ETAPAS.forEach(([k]) => { m[k] = [] })
    data.clientes.forEach(c => { (m[c.etapa] || (m[c.etapa] = [])).push(c) })
    return m
  }, [data])

  const porTemp = useMemo(() => {
    const m = { caliente: [], tibio: [], frio: [] }
    data.clientes.forEach(c => { (m[c.temperatura] || m.tibio).push(c) })
    return m
  }, [data])

  const moverEtapa = async (etapa) => {
    setOverCol(null)
    const id = dragId; setDragId(null)
    if (id == null) return
    const cli = data.clientes.find(c => c.id === id)
    if (!cli || cli.etapa === etapa) return
    setData(d => ({ ...d, clientes: d.clientes.map(c => c.id === id ? { ...c, etapa } : c) }))
    try {
      await api.patch(`/api/ventas-crm/clientes/${id}/etapa`, { etapa })
      cargar()
    } catch (e) {
      setBanner(e?.response?.data?.detail || 'No se pudo mover la etapa.')
      setTimeout(() => setBanner(''), 5000)
      cargar()
      setSel({ ...cli, _etapaDestino: etapa })
    }
  }

  const resolver = async (qid, accion) => {
    try { await api.post(`/api/ventas-crm/pipeline/consultas/${qid}/resolver`, { accion }); cargar() } catch {}
  }

  const crearCliente = async () => {
    if (!nuevo?.nombre?.trim()) return
    try {
      await api.post('/api/ventas-crm/clientes', { nombre: nuevo.nombre, telefono: nuevo.telefono || null })
      setNuevo(null); cargar()
    } catch { setBanner('No se pudo crear el cliente.'); setTimeout(() => setBanner(''), 4000) }
  }

  return (
    <Layout>
      <div className="max-w-[1500px] mx-auto animate-fade-in">
        <header className="mb-5">
          <div className="hero-eyebrow !mb-2">Pipeline comercial</div>
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl mb-1.5">CRM de Ventas</h1>
              <p className="hero-sub !text-base">Cada cliente en su etapa. Quién necesita atención hoy, primero.</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex gap-1 bg-neutral-200/70 dark:bg-[#161616] rounded-full p-1">
                <button onClick={() => setVista('etapas')}
                  className={`px-3.5 py-1.5 rounded-full text-[13px] font-medium flex items-center gap-1.5 transition ${vista === 'etapas' ? 'bg-white dark:bg-[#2A2A2A] shadow-soft text-text dark:text-white' : 'text-muted hover:text-text dark:hover:text-white'}`}>
                  <LayoutGrid size={14} /> Etapas
                </button>
                <button onClick={() => setVista('temperatura')}
                  className={`px-3.5 py-1.5 rounded-full text-[13px] font-medium flex items-center gap-1.5 transition ${vista === 'temperatura' ? 'bg-white dark:bg-[#2A2A2A] shadow-soft text-text dark:text-white' : 'text-muted hover:text-text dark:hover:text-white'}`}>
                  <Thermometer size={14} /> Temperatura
                </button>
              </div>
              <button className="btn-primary" onClick={() => setNuevo({ nombre: '', telefono: '' })}>
                <Plus size={15} /> Nuevo cliente
              </button>
            </div>
          </div>
        </header>

        {/* Tira de pulso: la tensión del pipeline hoy */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 mb-5">
          <PulseTile icon={Flame} label="Calientes activos" value={pulso.calientes}
            tone={pulso.calientes > 0 ? 'red' : 'idle'} />
          <PulseTile icon={AlertTriangle} label="Sin próxima acción" value={pulso.sinAccion}
            tone={pulso.sinAccion > 0 ? 'danger' : 'ok'} />
          <PulseTile icon={Gauge} label="SLA vencido" value={pulso.slaVencido}
            tone={pulso.slaVencido > 0 ? 'orange' : 'ok'} />
          <PulseTile icon={CalendarClock} label="Acción para hoy" value={pulso.hoy}
            tone={pulso.hoy > 0 ? 'gold' : 'idle'} />
        </div>

        {banner && (
          <div className="mb-4 px-4 py-2.5 rounded-2xl bg-danger/8 border border-danger/25 text-danger text-[13px] flex items-center gap-2 animate-scale-in">
            <AlertTriangle size={15} /> {banner}
          </div>
        )}

        {/* Consultas de degradación (líder) */}
        {esAdmin && consultas.length > 0 && (
          <div className="card p-4 mb-5 border-[#B8893A]/30 dark:border-[#B8893A]/25 bg-[#B8893A]/[0.04]">
            <p className="text-[13px] font-semibold flex items-center gap-2 mb-3 text-[#B8893A]">
              <ShieldAlert size={16} /> {consultas.length} lead{consultas.length > 1 ? 's' : ''} por enfriarse — tu decisión
            </p>
            <div className="space-y-2">
              {consultas.map(q => (
                <div key={q.id} className="flex flex-wrap items-center gap-2 text-[12.5px] pb-2 border-b border-border/60 dark:border-[#2A2A2A] last:border-0 last:pb-0">
                  <span className="font-medium">{q.cliente_nombre}</span>
                  <span className="chip-muted !text-[11px]">{q.de_temp} <ChevronRight size={10} className="inline -mx-0.5" /> {q.a_temp}</span>
                  <span className="text-muted text-[11px]">por inactividad</span>
                  <div className="flex gap-1.5 ml-auto">
                    <button onClick={() => resolver(q.id, 'confirmar')} className="px-2.5 py-1 rounded-full bg-danger/10 text-danger text-[11px] font-medium hover:bg-danger/15 transition">Confirmar baja</button>
                    <button onClick={() => resolver(q.id, 'posponer')} className="px-2.5 py-1 rounded-full bg-success/10 text-success text-[11px] font-medium hover:bg-success/15 transition">Posponer</button>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-muted mt-2.5">Sin respuesta en 24 h, el sistema degrada automáticamente.</p>
          </div>
        )}

        {loading ? (
          <div className="card card-flat text-center py-24 text-muted">Cargando CRM…</div>
        ) : data.clientes.length === 0 ? (
          <div className="card text-center py-24">
            <div className="w-14 h-14 rounded-2xl bg-[#B8893A]/10 grid place-items-center mx-auto mb-4">
              <Plus size={24} className="text-[#B8893A]" />
            </div>
            <p className="text-muted text-[14px]">Todavía no hay clientes.</p>
            <button className="btn-primary mt-4" onClick={() => setNuevo({ nombre: '', telefono: '' })}>
              <Plus size={15} /> Crear el primero
            </button>
          </div>
        ) : vista === 'temperatura' ? (
          <div className="space-y-6">
            {TEMP_ORDEN.map(tk => {
              const grupo = porTemp[tk]
              if (!grupo.length) return null
              const t = TEMP[tk]
              return (
                <section key={tk}>
                  <div className="flex items-center gap-2 mb-2.5">
                    <span className={`w-2.5 h-2.5 rounded-full ${t.dot}`} />
                    <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted">{t.label}</h2>
                    <span className="text-[12px] font-semibold tabular-nums text-muted/70">{grupo.length}</span>
                    <span className="flex-1 h-px bg-border dark:bg-[#242424]" />
                  </div>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {grupo.map(c => <CardLead key={c.id} c={c} onOpen={setSel} mostrarEtapa />)}
                  </div>
                </section>
              )
            })}
          </div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-4 -mx-1 px-1">
            {ETAPAS.map(([k, label]) => {
              const isOver = overCol === k
              const pausa = PAUSA.includes(k)
              const items = porEtapa[k] || []
              return (
                <div key={k} className="min-w-[248px] w-[248px] shrink-0"
                  onDragOver={e => { e.preventDefault(); setOverCol(k) }}
                  onDragLeave={() => setOverCol(c => c === k ? null : c)}
                  onDrop={() => moverEtapa(k)}>
                  <div className="mb-2.5 px-0.5">
                    <div className={`h-[3px] w-full rounded-full mb-2 ${pausa ? 'bg-border dark:bg-[#2A2A2A]' : ETAPA_BAR[k]} ${pausa ? '' : 'opacity-90'}`} />
                    <div className="flex items-center justify-between">
                      <span className={`text-[11px] font-semibold uppercase tracking-[0.1em] truncate ${pausa ? 'text-muted/60' : 'text-text/70 dark:text-white/70'}`}>{label}</span>
                      <span className="text-[12px] font-semibold tabular-nums text-muted">{items.length}</span>
                    </div>
                  </div>
                  <div className={`space-y-2 min-h-[120px] rounded-2xl p-1.5 transition-colors ${isOver ? 'bg-[#B8893A]/8 ring-2 ring-[#B8893A]/40' : pausa ? 'bg-neutral-200/40 dark:bg-[#0E0E0E]' : ''}`}>
                    {items.map(c => (
                      <div key={c.id} draggable onDragStart={() => setDragId(c.id)}>
                        <CardLead c={c} onOpen={setSel} arrastrable />
                      </div>
                    ))}
                    {items.length === 0 && <p className="text-[11px] text-muted/40 text-center py-5 select-none">Soltá una ficha</p>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {sel && <FichaDrawer cliente={sel} onClose={() => setSel(null)} onChange={cargar} />}

      {nuevo && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4" onClick={() => setNuevo(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="relative card p-6 w-full max-w-sm shadow-lift animate-scale-in" onClick={e => e.stopPropagation()}>
            <h3 className="hero-title text-xl mb-4">Nuevo cliente</h3>
            <label className="label">Nombre</label>
            <input className="input mb-3" value={nuevo.nombre} placeholder="Nombre y apellido"
              onChange={e => setNuevo(n => ({ ...n, nombre: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && crearCliente()} autoFocus />
            <label className="label">Teléfono</label>
            <input className="input mb-5" value={nuevo.telefono} placeholder="Opcional"
              onChange={e => setNuevo(n => ({ ...n, telefono: e.target.value }))} />
            <div className="flex gap-2 justify-end">
              <button className="btn-secondary" onClick={() => setNuevo(null)}>Cancelar</button>
              <button className="btn-primary" onClick={crearCliente}>Crear cliente</button>
            </div>
            <p className="text-[11px] text-muted mt-3">Entra en "Nuevo lead". Completá el perfil desde su ficha.</p>
          </div>
        </div>
      )}
    </Layout>
  )
}

// ── Tira de pulso ──
function PulseTile({ icon: Icon, label, value, tone }) {
  const tones = {
    red: 'bg-red-500/12 text-red-600 dark:text-red-400',
    danger: 'bg-danger/12 text-danger',
    orange: 'bg-orange-500/12 text-orange-600 dark:text-orange-400',
    gold: 'bg-[#B8893A]/12 text-[#B8893A]',
    ok: 'bg-success/10 text-success',
    idle: 'bg-neutral-200 text-muted dark:bg-[#242424] dark:text-[#8A8A8A]',
  }
  const alerta = tone === 'danger' || tone === 'orange'
  return (
    <div className={`card ${alerta ? 'border-current/20' : ''} px-4 py-3.5 flex items-center gap-3.5`}>
      <div className={`w-10 h-10 rounded-2xl grid place-items-center shrink-0 ${tones[tone]}`}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <div className="stat-value text-[26px] leading-none tabular-nums">{value}</div>
        <div className="stat-label mt-1 truncate">{label}</div>
      </div>
    </div>
  )
}

function fmtFecha(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' }) + ' · ' +
    d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

// ── Ficha de lead con espina de calor ──
function CardLead({ c, onOpen, mostrarEtapa, arrastrable }) {
  const t = TEMP[c.temperatura] || TEMP.tibio
  const Icon = t.icon
  const alerta = c.sin_proxima_accion
  return (
    <button onClick={() => onOpen(c)}
      className={`group relative w-full text-left rounded-2xl border bg-surface dark:bg-[#161616] pl-4 pr-3 py-3 overflow-hidden
        transition-all duration-200 hover:shadow-card hover:-translate-y-0.5 hover:border-[#B8893A]/40
        ${alerta ? 'border-danger/30 dark:border-danger/30' : 'border-border dark:border-[#2A2A2A]'}
        ${arrastrable ? 'cursor-grab active:cursor-grabbing' : ''}`}>
      {/* Espina de calor: temperatura del lead */}
      <span className={`absolute left-0 top-0 bottom-0 w-[3px] ${t.spine}`} />

      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold text-[13.5px] tracking-tight truncate">{c.nombre}</span>
        <span className={`w-6 h-6 rounded-lg grid place-items-center shrink-0 ${t.soft}`}>
          <Icon size={13} className={t.tint} />
        </span>
      </div>

      {mostrarEtapa && (
        <p className="text-[11px] text-muted mt-0.5">
          {ETAPA_LABEL[c.etapa] || c.etapa}{c.dias_en_etapa != null ? ` · ${c.dias_en_etapa}d` : ''}
        </p>
      )}

      {(c.presupuesto_max_usd || c.zona_interes) && (
        <p className="text-[11.5px] text-muted mt-1.5 flex items-center gap-1.5 truncate">
          {c.presupuesto_max_usd && <span className="tabular-nums">{usd(c.presupuesto_max_usd)}</span>}
          {c.zona_interes && <span className="flex items-center gap-0.5 truncate"><MapPin size={10} className="shrink-0" />{c.zona_interes}</span>}
        </p>
      )}

      {(c.sla_vencido || c.en_consulta_lider) && (
        <div className="flex flex-wrap gap-1 mt-2">
          {c.sla_vencido && <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-orange-500/12 text-orange-600 dark:text-orange-400 flex items-center gap-1 font-medium"><Gauge size={9} /> SLA</span>}
          {c.en_consulta_lider && <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-[#B8893A]/12 text-[#B8893A] flex items-center gap-1 font-medium"><ShieldAlert size={9} /> en consulta</span>}
        </div>
      )}

      <div className="mt-2.5 pt-2.5 border-t border-border/70 dark:border-[#242424]">
        {alerta ? (
          <span className="text-[11px] text-danger flex items-center gap-1.5 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" /> Sin próxima acción
          </span>
        ) : (
          <span className={`text-[11px] flex items-center gap-1.5 ${c.proxima_accion_vencida ? 'text-danger font-medium' : 'text-muted'}`}>
            <Clock size={11} className="shrink-0" />
            <span className="capitalize">{c.proxima_accion_tipo}</span>
            <span className="opacity-70">· {fmtFecha(c.proxima_accion_fecha)}</span>
          </span>
        )}
        {c.dias_sin_contacto != null && (
          <span className="text-[10px] text-muted/70 block mt-1">{c.dias_sin_contacto}d sin contacto</span>
        )}
      </div>
    </button>
  )
}

// ── Drawer de ficha ──
function FichaDrawer({ cliente, onClose, onChange }) {
  const [tab, setTab] = useState(cliente._etapaDestino ? 'etapa' : 'accion')
  const [perfil, setPerfil] = useState({
    perfil_comprador: cliente.perfil_comprador || '', tipo_operacion: cliente.tipo_operacion || '',
    presupuesto_min_usd: cliente.presupuesto_min_usd || '', presupuesto_max_usd: cliente.presupuesto_max_usd || '',
    zona_interes: cliente.zona_interes || '', temperatura: cliente.temperatura || 'tibio',
  })
  const [accion, setAccion] = useState({ texto: '', proxima_accion_tipo: 'llamada', proxima_accion_fecha: '', proxima_accion_contexto: '' })
  const [nuevaEtapa, setNuevaEtapa] = useState(cliente._etapaDestino || cliente.etapa)
  const [motivo, setMotivo] = useState('')
  const [eventos, setEventos] = useState([])
  const [busquedas, setBusquedas] = useState([])
  const [pedidoModal, setPedidoModal] = useState(null)   // {initial} | null
  const [msg, setMsg] = useState(cliente._etapaDestino ? 'Completá lo que falta para mover a esta etapa.' : '')
  const [busy, setBusy] = useState(false)
  const t = TEMP[cliente.temperatura] || TEMP.tibio

  const recargarEventos = () => api.get(`/api/ventas-crm/clientes/${cliente.id}/eventos`).then(r => setEventos(r.data || [])).catch(() => {})
  const recargarBusquedas = () => api.get(`/api/ventas-crm/pedidos?cliente_id=${cliente.id}`).then(r => setBusquedas(r.data || [])).catch(() => setBusquedas([]))
  useEffect(() => { recargarEventos(); recargarBusquedas() }, [cliente.id])
  useEffect(() => {
    const onEsc = e => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [onClose])

  const guardarPerfil = async () => {
    setBusy(true); setMsg('')
    try {
      const payload = { ...perfil }
      payload.presupuesto_min_usd = perfil.presupuesto_min_usd || null
      payload.presupuesto_max_usd = perfil.presupuesto_max_usd || null
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null })
      await api.patch(`/api/ventas-crm/clientes/${cliente.id}`, payload)
      setMsg('✓ Perfil guardado'); onChange()
    } catch (e) { setMsg(e?.response?.data?.detail || 'Error al guardar') } finally { setBusy(false) }
  }

  const registrarAccion = async () => {
    if (!accion.proxima_accion_contexto.trim() || !accion.proxima_accion_fecha) {
      setMsg('⚠ Definí la próxima acción: fecha y contexto son obligatorios.'); return
    }
    setBusy(true); setMsg('')
    try {
      await api.post(`/api/ventas-crm/clientes/${cliente.id}/interaccion`, {
        texto: accion.texto || '(sin nota)', origen: 'web', temperatura: perfil.temperatura,
        proxima_accion_tipo: accion.proxima_accion_tipo,
        proxima_accion_fecha: new Date(accion.proxima_accion_fecha).toISOString(),
        proxima_accion_contexto: accion.proxima_accion_contexto,
      })
      setMsg('✓ Interacción registrada'); setAccion({ texto: '', proxima_accion_tipo: 'llamada', proxima_accion_fecha: '', proxima_accion_contexto: '' })
      onChange(); recargarEventos()
    } catch (e) { setMsg(e?.response?.data?.detail || 'Error') } finally { setBusy(false) }
  }

  const cambiarEtapa = async () => {
    setBusy(true); setMsg('')
    try {
      await api.patch(`/api/ventas-crm/clientes/${cliente.id}/etapa`, { etapa: nuevaEtapa, motivo: motivo || null })
      setMsg('✓ Etapa actualizada'); onChange(); recargarEventos()
    } catch (e) { setMsg(e?.response?.data?.detail || 'Error') } finally { setBusy(false) }
  }

  const set = k => e => setPerfil(p => ({ ...p, [k]: e.target.value }))
  const setA = k => e => setAccion(a => ({ ...a, [k]: e.target.value }))
  const esPausa = PAUSA.includes(nuevaEtapa)
  const TIcon = t.icon

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div className="relative w-full max-w-md bg-surface dark:bg-[#0E0E0E] h-full overflow-y-auto shadow-lift animate-slide-up" onClick={e => e.stopPropagation()}>
        {/* Cabecera con la temperatura como protagonista */}
        <div className="sticky top-0 z-10 glass border-b border-border dark:border-[#242424] px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <span className={`w-10 h-10 rounded-2xl grid place-items-center shrink-0 ${t.soft}`}>
                <TIcon size={18} className={t.tint} />
              </span>
              <div className="min-w-0">
                <h2 className="font-semibold text-[16px] tracking-tight truncate">{cliente.nombre}</h2>
                <p className="text-[11px] text-muted">{ETAPA_LABEL[cliente.etapa]} · {t.label}</p>
              </div>
            </div>
            <button onClick={onClose} className="btn-ghost !p-2 shrink-0"><X size={18} /></button>
          </div>
        </div>

        {msg && (
          <div className={`mx-5 mt-4 px-3.5 py-2.5 rounded-2xl text-[12px] flex items-center gap-2 ${msg.startsWith('⚠') ? 'bg-danger/8 text-danger' : msg.startsWith('✓') ? 'bg-success/10 text-success' : 'bg-[#B8893A]/10 text-[#B8893A]'}`}>
            {msg}
          </div>
        )}

        {/* Tabs como segmented control */}
        <div className="px-5 pt-4">
          <div className="flex gap-0.5 bg-neutral-200/70 dark:bg-[#181818] rounded-full p-1 text-[11.5px]">
            {[['accion', 'Acción'], ['busquedas', 'Búsquedas'], ['perfil', 'Perfil'], ['etapa', 'Etapa'], ['historial', 'Historial']].map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)}
                className={`flex-1 px-1.5 py-1.5 rounded-full font-medium transition whitespace-nowrap ${tab === k ? 'bg-white dark:bg-[#2A2A2A] shadow-soft text-text dark:text-white' : 'text-muted hover:text-text dark:hover:text-white'}`}>{l}</button>
            ))}
          </div>
        </div>

        <div className="p-5 space-y-3.5">
          {tab === 'accion' && (
            <>
              <p className="text-[12px] text-muted leading-relaxed">Registrá lo que pasó y <b className="text-text dark:text-white font-medium">definí la próxima acción</b> — no se cierra sin ella.</p>
              <div><label className="label">Nota de lo conversado</label>
                <textarea className="input text-[13px]" rows={2} value={accion.texto} onChange={setA('texto')} placeholder="Qué se habló…" /></div>
              <div className="grid grid-cols-2 gap-2.5">
                <div><label className="label">Tipo de acción</label>
                  <select className="select !py-2.5 text-[13px]" value={accion.proxima_accion_tipo} onChange={setA('proxima_accion_tipo')}>
                    {ACCIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><label className="label">Fecha y hora</label>
                  <input type="datetime-local" className="input !py-2.5 text-[13px]" value={accion.proxima_accion_fecha} onChange={setA('proxima_accion_fecha')} /></div>
              </div>
              <div><label className="label">Qué se va a hacer</label>
                <input className="input !py-2.5 text-[13px]" value={accion.proxima_accion_contexto} onChange={setA('proxima_accion_contexto')} placeholder="Contexto de la próxima acción" /></div>
              <button className="btn-primary w-full" disabled={busy} onClick={registrarAccion}><Send size={14} /> Registrar interacción</button>
            </>
          )}

          {tab === 'busquedas' && (
            <>
              <div className="flex items-center justify-between">
                <p className="text-[12px] text-muted">Lo que este cliente está buscando.</p>
                <button className="btn-secondary !py-1.5 !px-3 text-[12px]"
                  onClick={() => setPedidoModal({ initial: { cliente_id: cliente.id } })}>
                  <Plus size={13} /> Nueva búsqueda
                </button>
              </div>
              {busquedas.length === 0 ? (
                <div className="text-center py-8">
                  <Search size={26} className="mx-auto text-muted/30 mb-2" />
                  <p className="text-[12px] text-muted">Sin búsquedas cargadas.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {busquedas.map(b => (
                    <button key={b.id} onClick={() => setPedidoModal({ initial: b })}
                      className="w-full text-left rounded-2xl border border-border dark:border-[#2A2A2A] bg-surface dark:bg-[#161616] p-3 hover:border-[#B8893A]/40 hover:shadow-soft transition">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-[13px] capitalize flex items-center gap-1.5">
                          <Building2 size={13} className="text-[#B8893A]" /> {b.tipo || 'Propiedad'}
                        </span>
                        <span className="chip-muted !text-[10px]">{PEDIDO_ESTADO[b.estado] || b.estado}</span>
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-2 text-[11.5px] text-muted">
                        {b.zona && <span className="flex items-center gap-1"><MapPin size={10} />{b.zona}</span>}
                        {(b.precio_min_usd || b.precio_max_usd) && (
                          <span className="tabular-nums">
                            {b.precio_min_usd ? `USD ${Number(b.precio_min_usd).toLocaleString('es-AR')}` : '0'}
                            {' – '}
                            {b.precio_max_usd ? `USD ${Number(b.precio_max_usd).toLocaleString('es-AR')}` : '∞'}
                          </span>
                        )}
                        {b.dormitorios_min ? <span className="flex items-center gap-1"><BedDouble size={10} />{b.dormitorios_min}+</span> : null}
                      </div>
                      {b.detalle && <p className="text-[11px] text-muted/80 mt-1.5 line-clamp-2">{b.detalle}</p>}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === 'perfil' && (
            <>
              <div className="grid grid-cols-2 gap-2.5">
                <div><label className="label">Temperatura</label>
                  <select className="select !py-2.5 text-[13px]" value={perfil.temperatura} onChange={set('temperatura')}>
                    {Object.entries(TEMP).map(([k, tt]) => <option key={k} value={k}>{tt.label}</option>)}</select></div>
                <div><label className="label">Perfil comprador</label>
                  <select className="select !py-2.5 text-[13px]" value={perfil.perfil_comprador} onChange={set('perfil_comprador')}>
                    {PERFILES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><label className="label">Tipo de operación</label>
                  <select className="select !py-2.5 text-[13px]" value={perfil.tipo_operacion} onChange={set('tipo_operacion')}>
                    {TIPO_OP.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><label className="label">Zona de interés</label>
                  <input className="input !py-2.5 text-[13px]" value={perfil.zona_interes} onChange={set('zona_interes')} /></div>
                <div><label className="label">Presupuesto mín USD</label>
                  <input type="number" className="input !py-2.5 text-[13px]" value={perfil.presupuesto_min_usd} onChange={set('presupuesto_min_usd')} /></div>
                <div><label className="label">Presupuesto máx USD</label>
                  <input type="number" className="input !py-2.5 text-[13px]" value={perfil.presupuesto_max_usd} onChange={set('presupuesto_max_usd')} /></div>
              </div>
              <p className="text-[11px] text-muted leading-relaxed">El perfil base — perfil, presupuesto y zona — es obligatorio para avanzar a "Calificado · activo".</p>
              <button className="btn-primary w-full" disabled={busy} onClick={guardarPerfil}>Guardar perfil</button>
            </>
          )}

          {tab === 'etapa' && (
            <>
              <div><label className="label">Mover a etapa</label>
                <select className="select !py-2.5 text-[13px]" value={nuevaEtapa} onChange={e => setNuevaEtapa(e.target.value)}>
                  {ETAPAS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              {esPausa && (
                <div><label className="label">Motivo (obligatorio)</label>
                  <textarea className="input text-[13px]" rows={2} value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Por qué se pausa o se pierde el lead" /></div>
              )}
              <button className="btn-primary w-full" disabled={busy} onClick={cambiarEtapa}>Actualizar etapa</button>
            </>
          )}

          {tab === 'historial' && (
            <div className="space-y-0">
              {eventos.length === 0 ? <p className="text-[12px] text-muted py-4 text-center">Sin eventos todavía.</p> :
                eventos.map((ev, i) => (
                  <div key={ev.id} className="flex gap-3 text-[12px] relative pb-4">
                    {i < eventos.length - 1 && <span className="absolute left-[6px] top-4 bottom-0 w-px bg-border dark:bg-[#2A2A2A]" />}
                    <span className="w-3 h-3 rounded-full bg-[#B8893A]/20 border-2 border-[#B8893A] shrink-0 mt-0.5 z-10" />
                    <div className="min-w-0 pb-1">
                      <p className="font-medium capitalize">{ev.tipo}{ev.automatico ? ' · auto' : ''}
                        {ev.de || ev.a ? <span className="text-muted font-normal"> · {ev.de || '—'} <ChevronRight size={10} className="inline -mx-0.5" /> {ev.a || '—'}</span> : null}</p>
                      {ev.detalle && <p className="text-muted mt-0.5 leading-snug">{ev.detalle}</p>}
                      <p className="text-[10px] text-muted/70 mt-0.5">{fmtFecha(ev.created_at)}</p>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>

      {pedidoModal && (
        <div onClick={e => e.stopPropagation()}>
          <PedidoModal
            initial={pedidoModal.initial}
            clientes={[{ id: cliente.id, nombre: cliente.nombre }]}
            onClose={() => setPedidoModal(null)}
            onSaved={() => { setPedidoModal(null); recargarBusquedas(); onChange() }}
          />
        </div>
      )}
    </div>
  )
}
