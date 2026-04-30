import { useEffect, useRef, useState } from 'react'
import { Send, Bot, User, Zap, MessageSquare, Phone } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const SUGERENCIAS = [
  '¿Cuántas propiedades tenemos?',
  '¿Cuántos contratos vigentes hay?',
  'Mostrame el resumen del sistema',
]

export default function Agente() {
  const [mensajes, setMensajes] = useState([
    {
      rol: 'bot',
      texto: '¡Hola! Soy el asistente de CIUDAD. Puedo responder preguntas sobre propiedades, contratos y clientes. ¿En qué te ayudo?',
      hora: new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }),
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [historial, setHistorial] = useState([])
  const bottomRef = useRef(null)

  useEffect(() => {
    api.get('/api/agente/historial').then(r => setHistorial(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes])

  const enviar = async (texto) => {
    const msg = texto || input.trim()
    if (!msg) return
    setInput('')

    const hora = new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
    setMensajes(prev => [...prev, { rol: 'user', texto: msg, hora }])
    setLoading(true)

    try {
      const r = await api.post('/api/agente/consultar', { mensaje: msg })
      setMensajes(prev => [...prev, {
        rol: 'bot',
        texto: r.data.respuesta,
        intent: r.data.intent,
        hora: new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }),
      }])
      api.get('/api/agente/historial').then(r => setHistorial(r.data)).catch(() => {})
    } catch {
      setMensajes(prev => [...prev, {
        rol: 'bot', texto: 'Ocurrió un error. Intentá de nuevo.', hora,
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">

        <header className="mb-10">
          <div className="hero-eyebrow">Inteligencia artificial</div>
          <h1 className="hero-title text-5xl md:text-6xl mb-3">Agente IA.</h1>
          <p className="hero-sub">Consultá sobre tu cartera en lenguaje natural. También disponible por WhatsApp.</p>
        </header>

        <div className="grid lg:grid-cols-[1fr_320px] gap-6">

          {/* Chat */}
          <div className="card flex flex-col overflow-hidden" style={{ height: 'calc(100vh - 280px)', minHeight: '500px' }}>

            {/* Header del chat */}
            <div className="px-6 py-4 border-b border-border flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-primary grid place-items-center">
                <Bot size={16} className="text-white" />
              </div>
              <div>
                <p className="font-semibold text-[13px]">Asistente CIUDAD</p>
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-success" />
                  <p className="text-[11px] text-muted">En línea · Fase 1 (demo)</p>
                </div>
              </div>
            </div>

            {/* Mensajes */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {mensajes.map((m, i) => (
                <div key={i} className={`flex gap-3 ${m.rol === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-7 h-7 rounded-full grid place-items-center shrink-0 mt-0.5
                    ${m.rol === 'bot' ? 'bg-primary' : 'bg-neutral-200'}`}>
                    {m.rol === 'bot'
                      ? <Bot size={13} className="text-white" />
                      : <User size={13} className="text-muted" />
                    }
                  </div>
                  <div className={`max-w-[75%] ${m.rol === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                    <div className={`px-4 py-3 rounded-2xl text-[13px] leading-relaxed
                      ${m.rol === 'bot'
                        ? 'bg-neutral-100 text-primary rounded-tl-sm'
                        : 'bg-primary text-white rounded-tr-sm'
                      }`}>
                      {m.texto}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted">{m.hora}</span>
                      {m.intent && m.intent !== 'desconocido' && (
                        <span className="chip-muted text-[10px]">{m.intent}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex gap-3">
                  <div className="w-7 h-7 rounded-full bg-primary grid place-items-center">
                    <Bot size={13} className="text-white" />
                  </div>
                  <div className="bg-neutral-100 rounded-2xl rounded-tl-sm px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-muted/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 bg-muted/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 bg-muted/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Sugerencias */}
            <div className="px-6 py-3 border-t border-border flex gap-2 overflow-x-auto">
              {SUGERENCIAS.map((s, i) => (
                <button key={i} onClick={() => enviar(s)}
                  className="shrink-0 px-3 py-1.5 rounded-full bg-neutral-100 text-[11px] text-muted
                             hover:bg-neutral-200 hover:text-primary transition">
                  {s}
                </button>
              ))}
            </div>

            {/* Input */}
            <div className="px-4 pb-4">
              <div className="flex gap-2 bg-neutral-100 rounded-2xl p-2">
                <input
                  className="flex-1 bg-transparent px-3 py-2 text-[13px] outline-none placeholder:text-muted/50"
                  placeholder="Escribí tu consulta…"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && enviar()}
                  disabled={loading}
                />
                <button
                  onClick={() => enviar()}
                  disabled={loading || !input.trim()}
                  className="w-9 h-9 rounded-xl bg-primary text-white grid place-items-center
                             hover:bg-primary-700 disabled:opacity-40 transition">
                  <Send size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Panel lateral */}
          <div className="space-y-4">

            {/* Estado WhatsApp */}
            <div className="card p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-full bg-[#25D366]/10 grid place-items-center">
                  <Phone size={16} className="text-[#25D366]" />
                </div>
                <div>
                  <p className="font-semibold text-[13px]">WhatsApp Bot</p>
                  <p className="text-[11px] text-muted">Integración Fase 3</p>
                </div>
              </div>
              <div className="space-y-3 text-[12px] text-muted">
                <Feature icon="○" label="Webhook WhatsApp (Meta/Twilio)" done={false} />
                <Feature icon="○" label="Tool-calling sobre API interna" done={false} />
                <Feature icon="○" label="Memoria por número de teléfono" done={false} />
                <Feature icon="●" label="Consultas básicas (demo activo)" done />
              </div>
              <div className="mt-4 p-3 bg-neutral-50 rounded-xl border border-border text-[11px] text-muted">
                Las consultas en este chat se loguean igual que las de WhatsApp.
              </div>
            </div>

            {/* Capacidades */}
            <div className="card p-5">
              <p className="text-[11px] uppercase tracking-[0.14em] text-muted font-semibold mb-3">Puede responder</p>
              <div className="space-y-2 text-[12px] text-muted">
                {[
                  'Cantidad de propiedades / disponibles',
                  'Contratos vigentes',
                  'Total de clientes',
                  'Calcular costo de alquiler',
                  'Buscar por dirección',
                ].map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Zap size={11} className="shrink-0 text-primary" />
                    {c}
                  </div>
                ))}
              </div>
            </div>

            {/* Historial reciente */}
            {historial.length > 0 && (
              <div className="card p-5">
                <p className="text-[11px] uppercase tracking-[0.14em] text-muted font-semibold mb-3">
                  Historial reciente
                </p>
                <div className="space-y-2">
                  {historial.slice(0, 5).map(h => (
                    <div key={h.id} className="text-[11px] border-b border-border pb-2 last:border-0 last:pb-0">
                      <p className="font-medium text-primary truncate">{h.input}</p>
                      <p className="text-muted truncate">{h.respuesta}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </Layout>
  )
}

function Feature({ icon, label, done }) {
  return (
    <div className={`flex items-center gap-2 ${done ? 'text-success' : ''}`}>
      <span className="text-[10px] w-3 text-center">{icon}</span>
      {label}
    </div>
  )
}
