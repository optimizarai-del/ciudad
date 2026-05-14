import { useEffect, useState, useCallback } from 'react'
import { Bell, AlertTriangle, RefreshCw, Calendar, Clock, TrendingUp, FileText, Sparkles, CheckCircle2 } from 'lucide-react'
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

const TIPO_LABEL = {
  vencimiento: 'Vencimiento',
  ajuste: 'Ajuste',
  pago: 'Pago',
  alta: 'Alta',
  consulta_ia: 'Consulta IA',
  nota: 'Nota',
}

/**
 * Página de Recordatorios = activity log de los chequeos automáticos.
 *
 * El loop background (services/recordatorios.py) corre cada hora si
 * RECORDATORIOS_ENABLED=true en el .env del backend; crea Eventos cuando
 * detecta contratos por vencer, pagos en mora o ajustes próximos.
 *
 * Si la lista está vacía y nunca corrió, ofrecemos el botón "Correr ahora"
 * bien visible para que el operador pueda forzarlo.
 */
export default function Recordatorios() {
  const [eventos, setEventos] = useState([])
  const [resumen, setResumen] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [running, setRunning] = useState(false)
  const [filtroCritico, setFiltroCritico] = useState(false)
  const [ultimoRun, setUltimo] = useState(null)

  const cargar = useCallback(() => {
    setLoading(true); setErr(null)
    Promise.allSettled([
      api.get(`/api/recordatorios/eventos?limit=100${filtroCritico ? '&es_critico=true' : ''}`, { timeout: 15000 }),
      api.get('/api/recordatorios/resumen', { timeout: 10000 }),
    ]).then(([e, r]) => {
      if (e.status === 'fulfilled') setEventos(e.value.data || [])
      else setErr(e.reason?.message || 'No se pudieron cargar los eventos.')
      if (r.status === 'fulfilled') setResumen(r.value.data)
    }).finally(() => setLoading(false))
  }, [filtroCritico])

  useEffect(() => { cargar() }, [cargar])

  const correrAhora = async () => {
    setRunning(true); setErr(null)
    try {
      const r = await api.post('/api/recordatorios/run', null, { timeout: 60000 })
      setUltimo(r.data)
      cargar()
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || 'Error al correr ciclo.')
    } finally { setRunning(false) }
  }

  const fmtFecha = (s) => {
    if (!s) return '—'
    try { return new Date(s).toLocaleString('es-AR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
    catch { return s }
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-8">
          <div className="hero-eyebrow">Operaciones</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3 flex items-center gap-3">
                <Bell size={36} /> Recordatorios
              </h1>
              <p className="hero-sub">
                Vencimientos próximos, mora y ajustes detectados automáticamente.
              </p>
            </div>
            <button className="btn-primary" onClick={correrAhora} disabled={running}>
              <RefreshCw size={13} className={running ? 'animate-spin' : ''} />
              {running ? 'Procesando…' : 'Correr ciclo ahora'}
            </button>
          </div>
        </header>

        {/* Stats */}
        {resumen && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            <div className="card p-4">
              <p className="stat-label">Eventos totales</p>
              <p className="stat-value text-2xl mt-1">{resumen.total}</p>
            </div>
            <div className={`card p-4 border-l-4 ${resumen.criticos > 0 ? '!border-l-danger' : '!border-l-success'}`}>
              <p className="stat-label flex items-center gap-1.5">
                <AlertTriangle size={11} /> Críticos pendientes
              </p>
              <p className={`stat-value text-2xl mt-1 ${resumen.criticos > 0 ? 'text-danger' : 'text-success'}`}>
                {resumen.criticos}
              </p>
            </div>
            <div className="card p-4">
              <p className="stat-label flex items-center gap-1.5">
                <Clock size={11} /> Último evento
              </p>
              <p className="text-[13px] mt-1.5 font-medium">
                {resumen.ultimo ? fmtFecha(resumen.ultimo) : 'Nunca'}
              </p>
            </div>
          </div>
        )}

        {/* Resultado del último run */}
        {ultimoRun && (
          <div className="card p-4 mb-4 border-l-4 !border-l-[#B8893A] bg-[#B8893A]/5">
            <div className="flex items-start gap-3">
              <Sparkles size={16} className="text-[#B8893A] shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold mb-1">
                  Ciclo ejecutado · {ultimoRun.fecha}
                </p>
                <p className="text-[12px] text-muted">
                  {ultimoRun.eventos_creados.length} evento{ultimoRun.eventos_creados.length !== 1 ? 's' : ''} nuevo{ultimoRun.eventos_creados.length !== 1 ? 's' : ''}
                  {ultimoRun.mensajes.length > 0 && `, ${ultimoRun.mensajes.length} aviso${ultimoRun.mensajes.length !== 1 ? 's' : ''} generado${ultimoRun.mensajes.length !== 1 ? 's' : ''}`}
                  {ultimoRun.eventos_creados.length === 0 && ' — todo al día.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error banner */}
        {err && (
          <div className="card p-3 mb-4 border-l-4 !border-l-danger bg-danger/5 text-[12px] text-danger flex items-start gap-2">
            <AlertTriangle size={13} className="shrink-0 mt-0.5" />
            <div className="flex-1">{err}</div>
            <button onClick={cargar} className="underline hover:no-underline">Reintentar</button>
          </div>
        )}

        {/* Filtros */}
        <div className="flex items-center gap-2 mb-4">
          <button onClick={() => setFiltroCritico(false)}
            className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
              !filtroCritico
                ? 'bg-black dark:bg-white text-white dark:text-black'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
            }`}>Todos {!loading && `(${eventos.length})`}</button>
          <button onClick={() => setFiltroCritico(true)}
            className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
              filtroCritico
                ? 'bg-red-600 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
            }`}>Solo críticos {!loading && resumen?.criticos !== undefined && `(${resumen.criticos})`}</button>
        </div>

        {/* Lista */}
        <div className="card overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <RefreshCw size={24} className="mx-auto text-muted/40 mb-2 animate-spin" />
              <p className="text-sm text-muted">Cargando eventos…</p>
            </div>
          ) : eventos.length === 0 ? (
            <div className="p-12 text-center">
              <Bell size={36} className="mx-auto text-gray-300 dark:text-gray-700 mb-3" />
              <p className="text-[14px] font-medium mb-1">
                {filtroCritico ? 'Sin eventos críticos' : 'No hay eventos aún'}
              </p>
              <p className="text-[12px] text-muted mb-4">
                {filtroCritico
                  ? 'Probá ver todos para ver el log completo.'
                  : 'Tocá "Correr ciclo ahora" para revisar vencimientos, mora y ajustes pendientes.'
                }
              </p>
              {!filtroCritico && (
                <button onClick={correrAhora} disabled={running} className="btn-primary">
                  <Sparkles size={13} className={running ? 'animate-spin' : ''} />
                  {running ? 'Procesando…' : 'Revisar ahora'}
                </button>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-border dark:divide-[#2A2A2A]">
              {eventos.map(e => {
                const Icon = TIPO_ICONO[e.tipo] || FileText
                return (
                  <li key={e.id} className="px-5 py-4 flex items-start gap-3 hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition">
                    <div className={`w-9 h-9 rounded-xl grid place-items-center shrink-0 ${
                      e.es_critico
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                        : 'bg-neutral-100 dark:bg-[#1E1E1E] text-muted dark:text-gray-500'
                    }`}>
                      {e.es_critico ? <AlertTriangle size={14} /> : <Icon size={14} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[13px] font-semibold leading-snug">{e.titulo}</p>
                        {e.es_critico && (
                          <span className="chip-danger text-[9px] !py-0 shrink-0">Crítico</span>
                        )}
                      </div>
                      {e.descripcion && (
                        <p className="text-[12px] text-muted dark:text-gray-500 mt-0.5">{e.descripcion}</p>
                      )}
                      <p className="text-[10px] text-gray-400 dark:text-gray-600 mt-1.5 flex items-center gap-2">
                        <Clock size={9} />
                        {fmtFecha(e.created_at)}
                        <span className="text-muted/60">·</span>
                        <span>{TIPO_LABEL[e.tipo] || e.tipo}</span>
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <p className="text-[11px] text-muted dark:text-gray-500 mt-4 text-center">
          💡 El loop revisa automáticamente cada hora si <code className="text-[10px]">RECORDATORIOS_ENABLED=true</code> está activo.
          Tocá "Correr ciclo ahora" para forzarlo cuando quieras.
        </p>
      </div>
    </Layout>
  )
}
