import { useEffect, useState } from 'react'
import { Bell, AlertTriangle, RefreshCw, Calendar, Clock, TrendingUp, FileText } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const TIPO_ICONO = {
  vencimiento: Calendar,
  ajuste: TrendingUp,
  pago: FileText,
  alta: FileText,
  consulta_ia: FileText,
  nota: FileText,
}

export default function Recordatorios() {
  const [eventos, setEventos] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [filtroCritico, setFiltroCritico] = useState(false)
  const [ultimoRun, setUltimo] = useState(null)

  const cargar = () => {
    setLoading(true)
    api.get(`/api/recordatorios/eventos?limit=100${filtroCritico ? '&es_critico=true' : ''}`)
      .then(r => setEventos(r.data || []))
      .finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [filtroCritico])

  const correrAhora = async () => {
    setRunning(true)
    try {
      const r = await api.post('/api/recordatorios/run')
      setUltimo(r.data)
      cargar()
    } catch (e) {
      alert(e.response?.data?.detail || 'Error al correr ciclo')
    } finally { setRunning(false) }
  }

  return (
    <Layout>
      <div className="p-6 space-y-5 max-w-5xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 dark:text-gray-500 uppercase mb-1">Operaciones</p>
            <h1 className="hero-title text-5xl md:text-6xl mb-3 flex items-center gap-3">
              <Bell size={28} /> Recordatorios
            </h1>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
              Vencimientos próximos, mora y ajustes de canon. El loop corre automáticamente
              si <code className="text-[11px]">RECORDATORIOS_ENABLED=true</code> en el .env.
            </p>
          </div>
          <button className="btn-primary" onClick={correrAhora} disabled={running}>
            <RefreshCw size={13} className={running ? 'animate-spin' : ''} />
            {running ? 'Corriendo…' : 'Correr ciclo ahora'}
          </button>
        </div>

        {ultimoRun && (
          <div className="card p-4 border-l-4 border-[#B8893A]">
            <p className="text-sm font-semibold mb-1">Último ciclo · {ultimoRun.fecha}</p>
            <p className="text-[12px] text-muted dark:text-gray-500">
              {ultimoRun.eventos_creados.length} evento(s) creado(s), {ultimoRun.mensajes.length} aviso(s) generado(s).
            </p>
          </div>
        )}

        <div className="flex items-center gap-2">
          <button onClick={() => setFiltroCritico(false)}
            className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
              !filtroCritico
                ? 'bg-black dark:bg-white text-white dark:text-black'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
            }`}>Todos ({eventos.length})</button>
          <button onClick={() => setFiltroCritico(true)}
            className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
              filtroCritico
                ? 'bg-red-600 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
            }`}>Solo críticos</button>
        </div>

        <div className="card overflow-hidden">
          {loading ? (
            <div className="p-8 text-sm text-gray-400 dark:text-gray-500 text-center">Cargando…</div>
          ) : eventos.length === 0 ? (
            <div className="p-12 text-center">
              <Bell size={32} className="mx-auto text-gray-300 dark:text-gray-700 mb-2" />
              <p className="text-sm text-gray-400 dark:text-gray-500">
                Sin eventos. Corré un ciclo para revisar vencimientos y mora.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-border dark:divide-[#2A2A2A]">
              {eventos.map(e => {
                const Icon = TIPO_ICONO[e.tipo] || FileText
                return (
                  <li key={e.id} className="px-5 py-4 flex items-start gap-3 hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition">
                    <div className={`w-8 h-8 rounded-xl grid place-items-center shrink-0 ${
                      e.es_critico
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                        : 'bg-neutral-100 dark:bg-[#1E1E1E] text-muted dark:text-gray-500'
                    }`}>
                      {e.es_critico ? <AlertTriangle size={14} /> : <Icon size={14} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-semibold">{e.titulo}</p>
                      {e.descripcion && (
                        <p className="text-[12px] text-muted dark:text-gray-500 mt-0.5">{e.descripcion}</p>
                      )}
                      <p className="text-[10px] text-gray-400 dark:text-gray-600 mt-1 flex items-center gap-2">
                        <Clock size={9} />
                        {new Date(e.created_at).toLocaleString('es-AR')}
                        {' · '}
                        <span className="capitalize">{e.tipo}</span>
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </Layout>
  )
}
