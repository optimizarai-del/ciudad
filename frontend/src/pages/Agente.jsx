import { useState, useEffect, useRef } from 'react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { MessageCircle, Instagram, Send, RefreshCw, User, Bot, CheckCircle, Clock, AlertCircle, Settings, Zap } from 'lucide-react'

const ESTADO_CONFIG = {
  nuevo:        { label: 'Nuevo',        color: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300' },
  interesado:   { label: 'Interesado',   color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  a_contactar:  { label: 'A contactar',  color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300', pulse: true },
  descartado:   { label: 'Descartado',   color: 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-300' },
}

function timeAgo(iso) {
  if (!iso) return ''
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return 'ahora'
  if (diff < 3600) return `${Math.floor(diff/60)}m`
  if (diff < 86400) return `${Math.floor(diff/3600)}h`
  return `${Math.floor(diff/86400)}d`
}

function EstadoBadge({ estado }) {
  const cfg = ESTADO_CONFIG[estado] || ESTADO_CONFIG.nuevo
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${cfg.color}`}>
      {cfg.pulse && <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />}
      {cfg.label}
    </span>
  )
}

function LeadCard({ lead, selected, onClick }) {
  const isIG = lead.canal === 'instagram'
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-xl border transition-all ${
        selected
          ? 'border-black dark:border-white bg-black/5 dark:bg-white/10'
          : 'border-gray-100 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-600'
      }`}
    >
      <div className="flex items-start gap-2">
        <div className={`mt-0.5 w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
          isIG ? 'bg-gradient-to-br from-purple-500 to-pink-500' : 'bg-[#229ED9]'
        }`}>
          {isIG
            ? <Instagram size={14} className="text-white" />
            : <MessageCircle size={14} className="text-white" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span className="text-sm font-medium truncate">
              {lead.nombre || lead.canal_username || `Lead #${lead.id}`}
            </span>
            <span className="text-xs text-gray-400 flex-shrink-0">{timeAgo(lead.ultima_actividad)}</span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">{lead.ultimo_mensaje || '—'}</p>
          <div className="mt-1.5"><EstadoBadge estado={lead.estado} /></div>
        </div>
      </div>
    </button>
  )
}

function ConversationPanel({ lead, onEstadoChange }) {
  const bottomRef = useRef(null)
  const [detalle, setDetalle] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!lead) return
    setLoading(true)
    api.get(`/api/agente/leads/${lead.id}`)
      .then(r => setDetalle(r.data))
      .finally(() => setLoading(false))
  }, [lead?.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [detalle?.conversacion])

  if (!lead) return (
    <div className="flex-1 flex items-center justify-center text-gray-400">
      <div className="text-center">
        <MessageCircle size={40} className="mx-auto mb-3 opacity-20" />
        <p className="text-sm">Seleccioná un lead para ver la conversación</p>
      </div>
    </div>
  )

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-sm">{detalle?.nombre || detalle?.canal_username || `Lead #${lead.id}`}</h3>
          <p className="text-xs text-gray-400">{detalle?.telefono || detalle?.canal_id || ''}</p>
        </div>
        <div className="flex items-center gap-2">
          <EstadoBadge estado={lead.estado} />
          <select
            value={lead.estado}
            onChange={e => onEstadoChange(lead.id, e.target.value)}
            className="text-xs border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-transparent"
          >
            {Object.entries(ESTADO_CONFIG).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {loading && <p className="text-center text-xs text-gray-400">Cargando...</p>}
        {detalle?.conversacion?.map((m, i) => (
          <div key={i} className={`flex ${m.rol === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm ${
              m.rol === 'user'
                ? 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-br-sm'
                : 'bg-black dark:bg-white text-white dark:text-black rounded-bl-sm'
            }`}>
              <p className="whitespace-pre-wrap">{m.contenido}</p>
              <p className={`text-[10px] mt-1 ${m.rol === 'user' ? 'text-gray-400' : 'opacity-50'}`}>
                {new Date(m.created_at).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* CRM notes */}
      {detalle?.notas_crm && (
        <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-t border-amber-100 dark:border-amber-900/40">
          <p className="text-xs text-amber-700 dark:text-amber-400 font-medium mb-1">Notas CRM</p>
          <p className="text-xs text-amber-600 dark:text-amber-500 whitespace-pre-wrap">{detalle.notas_crm}</p>
        </div>
      )}
    </div>
  )
}

function TestChat() {
  const [messages, setMessages] = useState([
    { rol: 'assistant', contenido: '¡Hola! Soy el asistente virtual de Ciudad. ¿En qué puedo ayudarte hoy?' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => 'test_' + Date.now())
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const texto = input.trim()
    setInput('')
    setMessages(m => [...m, { rol: 'user', contenido: texto }])
    setLoading(true)
    try {
      const { data } = await api.post('/api/agente/chat', {
        mensaje: texto,
        canal_id: sessionId,
        canal: 'web'
      })
      setMessages(m => [...m, { rol: 'assistant', contenido: data.respuesta }])
    } catch {
      setMessages(m => [...m, { rol: 'assistant', contenido: 'Error al conectar con el agente.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 dark:border-gray-800">
        <Zap size={14} className="text-amber-500" />
        <span className="text-sm font-semibold">Probar agente</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.rol === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${
              m.rol === 'user'
                ? 'bg-gray-100 dark:bg-gray-800'
                : 'bg-black dark:bg-white text-white dark:text-black'
            }`}>
              {m.contenido}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-black dark:bg-white px-4 py-2 rounded-xl">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-white dark:bg-black rounded-full animate-bounce" style={{animationDelay:'0ms'}} />
                <span className="w-1.5 h-1.5 bg-white dark:bg-black rounded-full animate-bounce" style={{animationDelay:'150ms'}} />
                <span className="w-1.5 h-1.5 bg-white dark:bg-black rounded-full animate-bounce" style={{animationDelay:'300ms'}} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="p-3 border-t border-gray-100 dark:border-gray-800">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
            placeholder="Escribí un mensaje..."
            className="flex-1 text-sm px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-transparent outline-none focus:border-black dark:focus:border-white"
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            className="p-2 bg-black dark:bg-white text-white dark:text-black rounded-xl disabled:opacity-30"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function ChannelCard({ name, icon: Icon, active, description, badge }) {
  return (
    <div className={`p-3 rounded-xl border ${active ? 'border-green-200 dark:border-green-900' : 'border-gray-100 dark:border-gray-800'}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon size={16} className={active ? 'text-green-500' : 'text-gray-400'} />
          <span className="text-sm font-medium">{name}</span>
        </div>
        {active
          ? <span className="text-xs bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full">Activo</span>
          : <span className="text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded-full">{badge || 'Pendiente config.'}</span>
        }
      </div>
      <p className="text-xs text-gray-400 mt-1">{description}</p>
    </div>
  )
}

export default function Agente() {
  const [leads, setLeads] = useState([])
  const [stats, setStats] = useState(null)
  const [selectedLead, setSelectedLead] = useState(null)
  const [filtroEstado, setFiltroEstado] = useState('')
  const [loading, setLoading] = useState(true)

  const cargar = async () => {
    try {
      const [leadsRes, statsRes] = await Promise.all([
        api.get('/api/agente/leads' + (filtroEstado ? `?estado=${filtroEstado}` : '')),
        api.get('/api/agente/stats')
      ])
      setLeads(leadsRes.data)
      setStats(statsRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { cargar() }, [filtroEstado])

  const cambiarEstado = async (leadId, nuevoEstado) => {
    await api.patch(`/api/agente/leads/${leadId}`, { estado: nuevoEstado })
    cargar()
    if (selectedLead?.id === leadId) setSelectedLead(l => ({ ...l, estado: nuevoEstado }))
  }

  const noKey = stats && !stats.canales?.telegram?.activo && !stats.canales?.instagram?.activo

  return (
    <Layout>
      <div className="p-6 h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-1">Agente IA</p>
            <h1 className="text-3xl font-black">Leads & Conversaciones</h1>
          </div>
          <button onClick={cargar} className="btn-ghost p-2"><RefreshCw size={16} /></button>
        </div>

        {/* Aviso sin API key */}
        {noKey && (
          <div className="mb-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900 flex items-start gap-3">
            <AlertCircle size={18} className="text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">Configuración pendiente</p>
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                Agregá <code className="bg-amber-100 dark:bg-amber-900/50 px-1 rounded">ANTHROPIC_API_KEY</code> y{' '}
                <code className="bg-amber-100 dark:bg-amber-900/50 px-1 rounded">TELEGRAM_BOT_TOKEN</code> en el archivo{' '}
                <code className="bg-amber-100 dark:bg-amber-900/50 px-1 rounded">backend/.env</code> para activar el agente.
              </p>
            </div>
          </div>
        )}

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: 'Total leads', value: stats.total_leads, icon: User },
              { label: 'Nuevos', value: stats.nuevos, icon: Clock },
              { label: 'Interesados', value: stats.interesados, icon: CheckCircle },
              { label: 'A contactar', value: stats.a_contactar, icon: AlertCircle },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="card p-3">
                <p className="text-xs text-gray-400 mb-1">{label}</p>
                <p className="text-2xl font-black">{value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Main 3-column layout */}
        <div className="flex-1 grid grid-cols-[280px_1fr_280px] gap-4 min-h-0">

          {/* LEFT: Leads list */}
          <div className="flex flex-col min-h-0 card overflow-hidden">
            <div className="p-3 border-b border-gray-100 dark:border-gray-800">
              <select
                value={filtroEstado}
                onChange={e => setFiltroEstado(e.target.value)}
                className="w-full text-xs border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 bg-transparent"
              >
                <option value="">Todos los leads</option>
                {Object.entries(ESTADO_CONFIG).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
              {loading && <p className="text-center text-xs text-gray-400 mt-4">Cargando...</p>}
              {!loading && leads.length === 0 && (
                <p className="text-center text-xs text-gray-400 mt-8">No hay leads aún.<br />Empezá a usar el bot de Telegram.</p>
              )}
              {leads.map(lead => (
                <LeadCard
                  key={lead.id}
                  lead={lead}
                  selected={selectedLead?.id === lead.id}
                  onClick={() => setSelectedLead(lead)}
                />
              ))}
            </div>
          </div>

          {/* CENTER: Conversation */}
          <div className="card flex flex-col min-h-0 overflow-hidden">
            <ConversationPanel lead={selectedLead} onEstadoChange={cambiarEstado} />
          </div>

          {/* RIGHT: Test + Channels */}
          <div className="flex flex-col gap-4 min-h-0">
            {/* Test chat */}
            <div className="flex-1 card flex flex-col min-h-0 overflow-hidden">
              <TestChat />
            </div>

            {/* Canales */}
            <div className="card p-4 space-y-2">
              <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-2">Canales</p>
              <ChannelCard
                name="Telegram"
                icon={MessageCircle}
                active={stats?.canales?.telegram?.activo}
                description="Bot activo vía webhook"
              />
              <ChannelCard
                name="Instagram"
                icon={Instagram}
                active={stats?.canales?.instagram?.activo}
                description="Requires Meta Business Suite"
                badge="Listo para conectar"
              />
            </div>
          </div>

        </div>
      </div>
    </Layout>
  )
}
