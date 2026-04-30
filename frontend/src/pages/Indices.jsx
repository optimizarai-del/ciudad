import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, RefreshCw, AlertCircle, DollarSign, BarChart2 } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

export default function Indices() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)

  const load = () => {
    setLoading(true)
    api.get('/api/indices')
      .then(r => {
        setData(r.data)
        setLastUpdate(new Date())
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">
        <header className="mb-10">
          <div className="hero-eyebrow">Datos económicos</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Índices.</h1>
              <p className="hero-sub">IPC, ICL, UVA y tipo de cambio en tiempo real.</p>
            </div>
            <div className="flex items-center gap-3">
              {lastUpdate && (
                <span className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">
                  Actualizado {lastUpdate.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
              <button onClick={load} disabled={loading}
                className="btn-secondary gap-2">
                <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                Actualizar
              </button>
            </div>
          </div>
        </header>

        {loading && !data ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="card p-6 animate-pulse">
                <div className="h-3 bg-[#E5E5E5] dark:bg-[#2A2A2A] rounded w-24 mb-4" />
                <div className="h-8 bg-[#E5E5E5] dark:bg-[#2A2A2A] rounded w-32 mb-2" />
                <div className="h-3 bg-[#E5E5E5] dark:bg-[#2A2A2A] rounded w-20" />
              </div>
            ))}
          </div>
        ) : (
          <>
            {/* Índices de ajuste */}
            <section className="mb-8">
              <h2 className="text-[11px] uppercase tracking-[0.14em] text-[#737373] dark:text-[#7A7A7A] font-semibold mb-4">
                Índices de ajuste de alquileres
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                <IndiceCard
                  titulo="IPC"
                  subtitulo="Índice de Precios al Consumidor"
                  dato={data?.ipc}
                  formatValue={v => v?.toFixed(2)}
                  unidad="puntos"
                  color="blue"
                  icon={<BarChart2 size={18} />}
                />
                <IndiceCard
                  titulo="ICL"
                  subtitulo="Índice de Contratos de Locación"
                  dato={data?.icl}
                  formatValue={v => v?.toFixed(4)}
                  unidad="puntos"
                  color="purple"
                  icon={<TrendingUp size={18} />}
                />
                <IndiceCard
                  titulo="UVA"
                  subtitulo="Unidad de Valor Adquisitivo"
                  dato={data?.uva}
                  formatValue={v => `$${v?.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                  unidad="$ arg"
                  color="amber"
                  icon={<BarChart2 size={18} />}
                />
              </div>
            </section>

            {/* Tipo de cambio */}
            <section>
              <h2 className="text-[11px] uppercase tracking-[0.14em] text-[#737373] dark:text-[#7A7A7A] font-semibold mb-4">
                Tipo de cambio
              </h2>
              <div className="grid md:grid-cols-2 gap-4">
                <DolarCard titulo="Dólar Oficial" dato={data?.dolar_oficial} />
                <DolarCard titulo="Dólar Blue" dato={data?.dolar_blue} blue />
              </div>
            </section>

            {/* Info fuentes */}
            <div className="mt-8 p-4 rounded-2xl border border-[#E5E5E5] dark:border-[#2A2A2A] bg-[#FAFAFA] dark:bg-[#141414]">
              <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A] leading-relaxed">
                <strong className="text-[#0A0A0A] dark:text-[#E0E0E0]">Fuentes:</strong>{' '}
                IPC — INDEC (Series de Tiempo) · ICL y UVA — BCRA API v2.0 · Tipo de cambio — DolarAPI.
                Los datos se actualizan en tiempo real al cargar la página o al presionar "Actualizar".
              </p>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}

function IndiceCard({ titulo, subtitulo, dato, formatValue, color, icon }) {
  const colors = {
    blue:   { bg: 'bg-blue-500/10 dark:bg-blue-500/10',   icon: 'text-blue-600 dark:text-blue-400',   pill: 'bg-blue-500/10 text-blue-700 dark:text-blue-400' },
    purple: { bg: 'bg-purple-500/10',                      icon: 'text-purple-600 dark:text-purple-400', pill: 'bg-purple-500/10 text-purple-700 dark:text-purple-400' },
    amber:  { bg: 'bg-amber-500/10',                       icon: 'text-amber-600 dark:text-amber-400',  pill: 'bg-amber-500/10 text-amber-700 dark:text-amber-400' },
  }
  const c = colors[color] || colors.blue

  if (!dato || dato.ok === false) {
    return (
      <div className="card p-6 opacity-60">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-9 h-9 rounded-2xl ${c.bg} grid place-items-center ${c.icon}`}>{icon}</div>
          <div>
            <p className="font-semibold text-[15px] tracking-tight">{titulo}</p>
            <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">{subtitulo}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[#737373] dark:text-[#7A7A7A] text-[12px]">
          <AlertCircle size={13} />
          No disponible en este momento
        </div>
      </div>
    )
  }

  const sube = dato.variacion_mensual > 0
  const baja = dato.variacion_mensual < 0

  return (
    <div className="card p-6 card-hover">
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-9 h-9 rounded-2xl ${c.bg} grid place-items-center ${c.icon}`}>{icon}</div>
        <div>
          <p className="font-semibold text-[15px] tracking-tight">{titulo}</p>
          <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">{subtitulo}</p>
        </div>
      </div>

      <div className="stat-value text-3xl mb-1">
        {formatValue(dato.valor)}
      </div>

      <div className="flex items-center gap-2 mt-2">
        {dato.variacion_mensual != null && (
          <span className={`inline-flex items-center gap-1 text-[12px] font-medium px-2 py-0.5 rounded-full
            ${sube ? 'bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400' : baja ? 'bg-green-50 dark:bg-green-950/30 text-green-600 dark:text-green-400' : 'bg-[#F0F0F0] dark:bg-[#2A2A2A] text-[#737373]'}`}>
            {sube ? <TrendingUp size={11} /> : baja ? <TrendingDown size={11} /> : null}
            {sube ? '+' : ''}{dato.variacion_mensual?.toFixed(2)}%
          </span>
        )}
        <span className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">
          {dato.periodo || dato.fecha || ''}
        </span>
      </div>

      <div className="mt-3 pt-3 border-t border-[#F0F0F0] dark:border-[#2A2A2A] flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.12em] text-[#9A9A9A] dark:text-[#555555]">
          Fuente: {dato.fuente}
        </span>
      </div>
    </div>
  )
}

function DolarCard({ titulo, dato, blue }) {
  const accentClass = blue
    ? 'text-sky-600 dark:text-sky-400'
    : 'text-emerald-600 dark:text-emerald-400'

  if (!dato || dato.ok === false) {
    return (
      <div className="card p-6 opacity-60">
        <div className="flex items-center gap-3 mb-2">
          <DollarSign size={16} className="text-[#737373] dark:text-[#7A7A7A]" />
          <p className="font-semibold text-[14px]">{titulo}</p>
        </div>
        <p className="text-[12px] text-[#737373] dark:text-[#7A7A7A]">No disponible</p>
      </div>
    )
  }

  return (
    <div className="card p-6 card-hover">
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-9 h-9 rounded-2xl ${blue ? 'bg-sky-500/10' : 'bg-emerald-500/10'} grid place-items-center ${accentClass}`}>
          <DollarSign size={16} />
        </div>
        <div>
          <p className="font-semibold text-[15px] tracking-tight">{titulo}</p>
          <p className="text-[11px] text-[#737373] dark:text-[#7A7A7A]">{dato.fecha || ''}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="stat-label mb-1">Compra</p>
          <p className={`text-2xl font-semibold tracking-tight ${accentClass}`}>
            ${Number(dato.compra || 0).toLocaleString('es-AR')}
          </p>
        </div>
        <div>
          <p className="stat-label mb-1">Venta</p>
          <p className={`text-2xl font-semibold tracking-tight ${accentClass}`}>
            ${Number(dato.venta || 0).toLocaleString('es-AR')}
          </p>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-[#F0F0F0] dark:border-[#2A2A2A]">
        <span className="text-[10px] uppercase tracking-[0.12em] text-[#9A9A9A] dark:text-[#555555]">
          Fuente: {dato.fuente}
        </span>
      </div>
    </div>
  )
}
