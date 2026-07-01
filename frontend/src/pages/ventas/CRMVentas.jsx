import { useEffect, useState, useMemo } from 'react'
import {
  Flame, Thermometer, Snowflake, LayoutGrid, X, Clock, Plus,
  AlertTriangle, MapPin, Send, ChevronRight, History, ShieldAlert, Gauge
} from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import { useRole } from '../../context/RoleContext'
import api from '../../utils/api'

// ── Etapas del pipeline (10, doc §3.4). El CRM ES el pipeline de cliente. ──
const ETAPAS = [
  ['nuevo_lead', 'Nuevo lead'],
  ['en_calificacion', 'En calificación'],
  ['calificado_activo', 'Calificado · activo'],
  ['presentacion_opciones', 'Presentación de opciones'],
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
  nuevo_lead: 'bg-slate-500', en_calificacion: 'bg-sky-500', calificado_activo: 'bg-indigo-500',
  presentacion_opciones: 'bg-violet-500', en_visitas: 'bg-amber-500', oferta_negociacion: 'bg-orange-500',
  reserva_sena: 'bg-teal-500', escritura_cierre: 'bg-emerald-500', caido_perdido: 'bg-rose-500', frio_espera: 'bg-blue-400',
}

const TEMP = {
  caliente: { label: 'Caliente', icon: Flame, dot: 'bg-red-500', bg: 'bg-red-50 dark:bg-red-950/30' },
  tibio: { label: 'Tibio', icon: Thermometer, dot: 'bg-amber-500', bg: 'bg-amber-50 dark:bg-amber-950/30' },
  frio: { label: 'Frío', icon: Snowflake, dot: 'bg-blue-500', bg: 'bg-blue-50 dark:bg-blue-950/30' },
}
const PERFILES = [['', '—'], ['contado', 'Contado'], ['credito', 'Crédito'], ['inversor', 'Inversor'], ['espera_vender', 'Espera vender'], ['oportunista', 'Oportunista']]
const TIPO_OP = [['', '—'], ['venta_propia', 'Venta propia'], ['inversion', 'Inversión'], ['colega', 'Colega']]
const ACCIONES = [['llamada', 'Llamada'], ['whatsapp', 'WhatsApp'], ['visita', 'Visita'], ['envio', 'Envío de propiedades'], ['reunion', 'Reunión'], ['seguimiento', 'Seguimiento pasivo']]

const usd = n => n ? `USD ${Number(n).toLocaleString('es-AR')}` : null

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
  const [nuevo, setNuevo] = useState(null)           // {nombre, telefono} o null

  const cargar = async () => {
    setLoading(true)
    try { const { data } = await api.get('/api/ventas-crm/pipeline'); setData(data) }
    catch { setData({ clientes: [] }) } finally { setLoading(false) }
    if (esAdmin) {
      try { const { data } = await api.get('/api/ventas-crm/pipeline/consultas'); setConsultas(data.consultas || []) } catch {}
    }
  }
  useEffect(() => { cargar() }, [])

  const porEtapa = useMemo(() => {
    const m = {}; ETAPAS.forEach(([k]) => { m[k] = [] })
    data.clientes.forEach(c => { (m[c.etapa] || (m[c.etapa] = [])).push(c) })
    return m
  }, [data])

  const moverEtapa = async (etapa) => {
    setOverCol(null)
    const id = dragId; setDragId(null)
    if (id == null) return
    const cli = data.clientes.find(c => c.id === id)
    if (!cli || cli.etapa === etapa) return
    // Optimista
    setData(d => ({ ...d, clientes: d.clientes.map(c => c.id === id ? { ...c, etapa } : c) }))
    try {
      await api.patch(`/api/ventas-crm/clientes/${id}/etapa`, { etapa })
      cargar()
    } catch (e) {
      // 400 → falta perfil (para Calificado-activo) o motivo (pausa): revertir y abrir ficha
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
        <header className="mb-4">
          <div className="hero-eyebrow">CRM · Pipeline de cliente</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl mb-1">CRM de Ventas</h1>
              <p className="hero-sub">Cada cliente en su etapa. Arrastrá las fichas entre columnas.</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex gap-1 bg-neutral-100 dark:bg-[#141414] rounded-xl p-1">
                <button onClick={() => setVista('etapas')}
                  className={`px-3 py-1.5 rounded-lg text-[13px] flex items-center gap-1.5 ${vista === 'etapas' ? 'bg-white dark:bg-black shadow-sm font-medium' : 'text-muted'}`}>
                  <LayoutGrid size={14} /> Etapas
                </button>
                <button onClick={() => setVista('temperatura')}
                  className={`px-3 py-1.5 rounded-lg text-[13px] flex items-center gap-1.5 ${vista === 'temperatura' ? 'bg-white dark:bg-black shadow-sm font-medium' : 'text-muted'}`}>
                  <Thermometer size={14} /> Temperatura
                </button>
              </div>
              <button className="btn-primary" onClick={() => setNuevo({ nombre: '', telefono: '' })}>
                <Plus size={14} /> Nuevo cliente
              </button>
            </div>
          </div>
        </header>

        {banner && <div className="mb-3 px-4 py-2 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 text-[13px]">{banner}</div>}

        {/* Consultas de degradación (líder) */}
        {esAdmin && consultas.length > 0 && (
          <div className="card p-3 mb-4 border-purple-300 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20">
            <p className="text-[13px] font-semibold flex items-center gap-1.5 mb-2 text-purple-700 dark:text-purple-300">
              <ShieldAlert size={15} /> {consultas.length} lead{consultas.length > 1 ? 's' : ''} por degradar — necesitan tu decisión
            </p>
            <div className="space-y-1.5">
              {consultas.map(q => (
                <div key={q.id} className="flex flex-wrap items-center gap-2 text-[12px] border-b border-border/50 pb-1.5">
                  <span className="font-medium">{q.cliente_nombre}</span>
                  <span className="text-muted">{q.de_temp} → {q.a_temp} por inactividad</span>
                  <div className="flex gap-1 ml-auto">
                    <button onClick={() => resolver(q.id, 'confirmar')} className="px-2 py-1 rounded-lg bg-red-500/10 text-red-600 text-[11px] hover:bg-red-500/20">Confirmar baja</button>
                    <button onClick={() => resolver(q.id, 'posponer')} className="px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-600 text-[11px] hover:bg-emerald-500/20">Posponer</button>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-muted mt-1.5">Si no respondés en 24h, el sistema degrada automáticamente.</p>
          </div>
        )}

        {loading ? (
          <div className="card text-center py-24 text-muted">Cargando CRM…</div>
        ) : data.clientes.length === 0 ? (
          <div className="card text-center py-24 text-muted">Todavía no hay clientes. Creá el primero con "Nuevo cliente".</div>
        ) : vista === 'temperatura' ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.clientes.map(c => <CardLead key={c.id} c={c} onOpen={setSel} grande />)}
          </div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-3">
            {ETAPAS.map(([k, label]) => {
              const isOver = overCol === k
              return (
                <div key={k} className="min-w-[250px] w-[250px] shrink-0"
                  onDragOver={e => { e.preventDefault(); setOverCol(k) }}
                  onDragLeave={() => setOverCol(c => c === k ? null : c)}
                  onDrop={() => moverEtapa(k)}>
                  <div className={`flex items-center justify-between px-2.5 py-2 mb-2 rounded-lg text-[12px] font-semibold ${PAUSA.includes(k) ? 'bg-neutral-200 dark:bg-neutral-800 text-muted' : 'bg-white dark:bg-[#161616] border border-border'}`}>
                    <span className="flex items-center gap-1.5 truncate"><span className={`w-2 h-2 rounded-full ${ETAPA_BAR[k]}`} />{label}</span>
                    <span className="chip-muted text-[10px]">{porEtapa[k]?.length || 0}</span>
                  </div>
                  <div className={`space-y-2 min-h-[120px] rounded-xl p-1 transition ${isOver ? 'bg-[#B8893A]/5 ring-1 ring-[#B8893A]/40' : ''}`}>
                    {(porEtapa[k] || []).map(c => (
                      <div key={c.id} draggable onDragStart={() => setDragId(c.id)}>
                        <CardLead c={c} onOpen={setSel} arrastrable />
                      </div>
                    ))}
                    {(porEtapa[k] || []).length === 0 && <p className="text-[11px] text-muted/50 text-center py-3">—</p>}
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
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative card p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold mb-3">Nuevo cliente</h3>
            <label className="label">Nombre *</label>
            <input className="input mb-2" value={nuevo.nombre} onChange={e => setNuevo(n => ({ ...n, nombre: e.target.value }))} autoFocus />
            <label className="label">Teléfono</label>
            <input className="input mb-4" value={nuevo.telefono} onChange={e => setNuevo(n => ({ ...n, telefono: e.target.value }))} />
            <div className="flex gap-2 justify-end">
              <button className="btn-secondary" onClick={() => setNuevo(null)}>Cancelar</button>
              <button className="btn-primary" onClick={crearCliente}>Crear</button>
            </div>
            <p className="text-[11px] text-muted mt-2">Entra en "Nuevo lead". Completá el perfil desde su ficha.</p>
          </div>
        </div>
      )}
    </Layout>
  )
}

function fmtFecha(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' }) + ' ' +
    d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

function CardLead({ c, onOpen, grande, arrastrable }) {
  const t = TEMP[c.temperatura] || TEMP.tibio
  const Icon = t.icon
  return (
    <button onClick={() => onOpen(c)}
      className={`w-full text-left rounded-xl border border-border p-3 transition hover:shadow-md ${t.bg} ${arrastrable ? 'cursor-grab active:cursor-grabbing' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-[13px] truncate flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${t.dot}`} /> {c.nombre}
        </span>
        <Icon size={14} className="text-muted shrink-0" />
      </div>
      {(c.sla_vencido || c.en_consulta_lider) && (
        <div className="flex flex-wrap gap-1 mt-1">
          {c.sla_vencido && <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-600 flex items-center gap-0.5"><Gauge size={9} /> SLA vencido</span>}
          {c.en_consulta_lider && <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-600 flex items-center gap-0.5"><ShieldAlert size={9} /> en consulta</span>}
        </div>
      )}
      {grande && <p className="text-[11px] text-muted mt-0.5">{ETAPA_LABEL[c.etapa] || c.etapa}{c.dias_en_etapa != null ? ` · ${c.dias_en_etapa}d en etapa` : ''}</p>}
      {(c.presupuesto_max_usd || c.zona_interes) && (
        <p className="text-[11px] text-muted mt-1 flex items-center gap-1 truncate">
          {usd(c.presupuesto_max_usd) || ''} {c.zona_interes ? <><MapPin size={9} />{c.zona_interes}</> : null}
        </p>
      )}
      <div className="mt-2 pt-2 border-t border-border/60">
        {c.sin_proxima_accion ? (
          <span className="text-[11px] text-red-600 flex items-center gap-1 font-medium"><AlertTriangle size={11} /> Sin próxima acción</span>
        ) : (
          <span className={`text-[11px] flex items-center gap-1 ${c.proxima_accion_vencida ? 'text-red-600 font-medium' : 'text-emerald-600'}`}>
            <Clock size={11} /> {c.proxima_accion_tipo} · {fmtFecha(c.proxima_accion_fecha)}
          </span>
        )}
        {c.dias_sin_contacto != null && <span className="text-[10px] text-muted block mt-0.5">{c.dias_sin_contacto}d sin contacto</span>}
      </div>
    </button>
  )
}

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
  const [msg, setMsg] = useState(cliente._etapaDestino ? 'Completá lo que falta para mover a esta etapa.' : '')
  const [busy, setBusy] = useState(false)

  const recargarEventos = () => api.get(`/api/ventas-crm/clientes/${cliente.id}/eventos`).then(r => setEventos(r.data || [])).catch(() => {})
  useEffect(() => { recargarEventos() }, [cliente.id])

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
      setMsg('⚠ La próxima acción es obligatoria: completá fecha y contexto.'); return
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

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-md bg-white dark:bg-[#0A0A0A] h-full overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="sticky top-0 bg-white dark:bg-[#0A0A0A] border-b border-border px-4 py-3 flex items-center justify-between z-10">
          <div>
            <h2 className="font-semibold text-[15px]">{cliente.nombre}</h2>
            <p className="text-[11px] text-muted">{ETAPA_LABEL[cliente.etapa]} · {TEMP[cliente.temperatura]?.label}</p>
          </div>
          <button onClick={onClose} className="btn-ghost !p-1.5"><X size={18} /></button>
        </div>

        {msg && <div className="mx-4 mt-3 px-3 py-2 rounded-lg bg-[#B8893A]/10 text-[#B8893A] text-[12px]">{msg}</div>}

        <div className="flex gap-1 px-4 pt-3 text-[12px]">
          {[['accion', 'Próxima acción'], ['perfil', 'Perfil'], ['etapa', 'Etapa'], ['historial', 'Historial']].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`px-2.5 py-1.5 rounded-lg ${tab === k ? 'bg-[#B8893A]/10 text-[#B8893A] font-medium' : 'text-muted'}`}>{l}</button>
          ))}
        </div>

        <div className="p-4 space-y-3">
          {tab === 'accion' && (
            <>
              <p className="text-[12px] text-muted">Registrá la interacción. <b>La próxima acción es obligatoria.</b></p>
              <div><label className="label">Nota de lo conversado</label>
                <textarea className="input text-[13px]" rows={2} value={accion.texto} onChange={setA('texto')} placeholder="Qué se habló…" /></div>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="label">Tipo de acción</label>
                  <select className="input !py-2 text-[13px]" value={accion.proxima_accion_tipo} onChange={setA('proxima_accion_tipo')}>
                    {ACCIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><label className="label">Fecha y hora *</label>
                  <input type="datetime-local" className="input !py-2 text-[13px]" value={accion.proxima_accion_fecha} onChange={setA('proxima_accion_fecha')} /></div>
              </div>
              <div><label className="label">Qué se va a hacer/decir *</label>
                <input className="input !py-2 text-[13px]" value={accion.proxima_accion_contexto} onChange={setA('proxima_accion_contexto')} placeholder="Contexto de la próxima acción" /></div>
              <button className="btn-primary w-full" disabled={busy} onClick={registrarAccion}><Send size={14} /> Registrar interacción</button>
            </>
          )}

          {tab === 'perfil' && (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="label">Temperatura</label>
                  <select className="input !py-2 text-[13px]" value={perfil.temperatura} onChange={set('temperatura')}>
                    {Object.entries(TEMP).map(([k, t]) => <option key={k} value={k}>{t.label}</option>)}</select></div>
                <div><label className="label">Perfil comprador</label>
                  <select className="input !py-2 text-[13px]" value={perfil.perfil_comprador} onChange={set('perfil_comprador')}>
                    {PERFILES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><label className="label">Tipo de operación</label>
                  <select className="input !py-2 text-[13px]" value={perfil.tipo_operacion} onChange={set('tipo_operacion')}>
                    {TIPO_OP.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                <div><label className="label">Zona de interés</label>
                  <input className="input !py-2 text-[13px]" value={perfil.zona_interes} onChange={set('zona_interes')} /></div>
                <div><label className="label">Presupuesto mín USD</label>
                  <input type="number" className="input !py-2 text-[13px]" value={perfil.presupuesto_min_usd} onChange={set('presupuesto_min_usd')} /></div>
                <div><label className="label">Presupuesto máx USD</label>
                  <input type="number" className="input !py-2 text-[13px]" value={perfil.presupuesto_max_usd} onChange={set('presupuesto_max_usd')} /></div>
              </div>
              <p className="text-[11px] text-muted">El perfil base (perfil + presupuesto + zona) es obligatorio para avanzar a "Calificado · activo".</p>
              <button className="btn-primary w-full" disabled={busy} onClick={guardarPerfil}>Guardar perfil</button>
            </>
          )}

          {tab === 'etapa' && (
            <>
              <div><label className="label">Mover a etapa</label>
                <select className="input !py-2 text-[13px]" value={nuevaEtapa} onChange={e => setNuevaEtapa(e.target.value)}>
                  {ETAPAS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              {esPausa && (
                <div><label className="label">Motivo (obligatorio)</label>
                  <textarea className="input text-[13px]" rows={2} value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Por qué se pausa/pierde el lead" /></div>
              )}
              <button className="btn-primary w-full" disabled={busy} onClick={cambiarEtapa}>Actualizar etapa</button>
            </>
          )}

          {tab === 'historial' && (
            <div className="space-y-2">
              {eventos.length === 0 ? <p className="text-[12px] text-muted">Sin eventos todavía.</p> :
                eventos.map(ev => (
                  <div key={ev.id} className="flex gap-2 text-[12px] border-b border-border/60 pb-2">
                    <History size={13} className="text-muted shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium capitalize">{ev.tipo}{ev.automatico ? ' (auto)' : ''}
                        {ev.de || ev.a ? <span className="text-muted font-normal"> · {ev.de || '—'} <ChevronRight size={10} className="inline" /> {ev.a || '—'}</span> : null}</p>
                      {ev.detalle && <p className="text-muted">{ev.detalle}</p>}
                      <p className="text-[10px] text-muted">{fmtFecha(ev.created_at)}</p>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
