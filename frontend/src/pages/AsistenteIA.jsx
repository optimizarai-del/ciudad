import { useState, useRef, useEffect } from 'react'
import { Sparkles, Send, User, Bot, Loader2 } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { useAuth } from '../context/AuthContext'

const SUGERENCIAS = [
  '¿Cuántos pedidos activos hay?',
  'Mostrame las mejores oportunidades (matches)',
  'Propiedades en venta de menos de USD 100.000',
  'Resumen general del área',
]

export default function AsistenteIA() {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [texto, setTexto] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  const enviar = async (preset) => {
    const msg = (preset ?? texto).trim()
    if (!msg || loading) return
    setTexto('')
    setMessages(m => [...m, { rol: 'user', contenido: msg }])
    setLoading(true)
    try {
      const { data } = await api.post('/api/agente/asistente', { mensaje: msg })
      setMessages(m => [...m, { rol: 'assistant', contenido: data.respuesta }])
    } catch (e) {
      setMessages(m => [...m, { rol: 'assistant', contenido: 'Hubo un error al consultar. Probá de nuevo.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="max-w-3xl mx-auto h-[calc(100vh-6rem)] flex flex-col animate-fade-in">
        <header className="mb-4 shrink-0">
          <div className="hero-eyebrow">Asistente interno</div>
          <h1 className="hero-title text-3xl sm:text-4xl mb-1 flex items-center gap-2">
            <Sparkles className="text-[#B8893A]" size={28} /> Asistente IA
          </h1>
          <p className="hero-sub">
            Preguntá en lenguaje natural sobre tus datos. Te respondo según tu rol
            ({user?.role || '—'}).
          </p>
        </header>

        {/* Conversación */}
        <div className="flex-1 min-h-0 overflow-y-auto card p-4 space-y-4">
          {messages.length === 0 && !loading && (
            <div className="h-full grid place-items-center text-center">
              <div>
                <Bot size={40} className="mx-auto text-muted/30 mb-3" />
                <p className="text-muted text-[14px] mb-4">Preguntame lo que necesites. Por ejemplo:</p>
                <div className="flex flex-wrap gap-2 justify-center max-w-md mx-auto">
                  {SUGERENCIAS.map(s => (
                    <button key={s} onClick={() => enviar(s)}
                      className="px-3 py-1.5 rounded-full text-[12px] border border-border text-muted hover:border-[#B8893A] hover:text-[#B8893A] transition">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2.5 ${m.rol === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full grid place-items-center shrink-0 ${
                m.rol === 'user' ? 'bg-primary text-white' : 'bg-[#B8893A]/15 text-[#B8893A]'}`}>
                {m.rol === 'user' ? <User size={15} /> : <Bot size={15} />}
              </div>
              <div className={`rounded-2xl px-4 py-2.5 max-w-[80%] text-[14px] whitespace-pre-wrap leading-relaxed ${
                m.rol === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-neutral-100 dark:bg-[#1A1A1A]'}`}>
                {m.contenido}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-2.5">
              <div className="w-8 h-8 rounded-full grid place-items-center shrink-0 bg-[#B8893A]/15 text-[#B8893A]">
                <Bot size={15} />
              </div>
              <div className="rounded-2xl px-4 py-3 bg-neutral-100 dark:bg-[#1A1A1A]">
                <Loader2 size={16} className="animate-spin text-[#B8893A]" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input */}
        <form onSubmit={e => { e.preventDefault(); enviar() }} className="mt-3 flex gap-2 shrink-0">
          <input className="input flex-1" placeholder="Escribí tu consulta…"
            value={texto} onChange={e => setTexto(e.target.value)} disabled={loading} />
          <button className="btn-primary px-5" disabled={loading || !texto.trim()}>
            <Send size={16} />
          </button>
        </form>
      </div>
    </Layout>
  )
}
