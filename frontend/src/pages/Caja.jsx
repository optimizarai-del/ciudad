import { useEffect, useState, useCallback } from 'react'
import { Wallet, TrendingUp, TrendingDown, Coins, ChevronLeft, ChevronRight } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const fmt = (n) => '$ ' + Number(n || 0).toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })

const RANGOS = [
  { key: 'diaria', label: 'Diaria' },
  { key: 'semanal', label: 'Semanal' },
  { key: 'mensual', label: 'Mensual' },
  { key: 'anual', label: 'Anual' },
]

// Mueve la fecha de referencia un período hacia adelante/atrás según el rango.
function mover(fechaISO, rango, dir) {
  const d = new Date(fechaISO + 'T00:00:00')
  if (rango === 'diaria') d.setDate(d.getDate() + dir)
  else if (rango === 'semanal') d.setDate(d.getDate() + 7 * dir)
  else if (rango === 'anual') d.setFullYear(d.getFullYear() + dir)
  else d.setMonth(d.getMonth() + dir)
  return d.toISOString().slice(0, 10)
}

export default function Caja() {
  const [rango, setRango] = useState('mensual')
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10))
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const cargar = useCallback(() => {
    setLoading(true); setErr('')
    api.get(`/api/caja?rango=${rango}&fecha=${fecha}`, { timeout: 30000 })
      .then(r => setData(r.data))
      .catch(e => setErr(e.response?.data?.detail || e.message || 'Error al cargar la caja.'))
      .finally(() => setLoading(false))
  }, [rango, fecha])

  useEffect(() => { cargar() }, [cargar])

  const ing = data?.ingresos || {}
  const egr = data?.egresos || {}

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Operación de caja</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Caja</h1>
          <p className="hero-sub">Ingresos, egresos y ganancia por período.</p>
        </header>

        {/* Controles: rango + navegación de fecha */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-6">
          <div className="flex gap-1.5 flex-wrap">
            {RANGOS.map(r => (
              <button key={r.key} onClick={() => setRango(r.key)}
                className={`px-4 py-1.5 rounded-full text-[13px] font-medium transition ${
                  rango === r.key ? 'bg-[#0A0A0A] text-white dark:bg-white dark:text-[#0A0A0A]'
                                  : 'bg-neutral-100 dark:bg-[#1A1A1A] text-muted hover:text-primary'
                }`}>
                {r.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 sm:ml-auto">
            <button onClick={() => setFecha(f => mover(f, rango, -1))}
              className="btn-ghost !p-2" title="Período anterior"><ChevronLeft size={16} /></button>
            <input type="date" className="input !py-1.5 text-[13px] w-auto"
              value={fecha} onChange={e => setFecha(e.target.value)} />
            <button onClick={() => setFecha(f => mover(f, rango, 1))}
              className="btn-ghost !p-2" title="Período siguiente"><ChevronRight size={16} /></button>
          </div>
        </div>

        {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl mb-4">{err}</p>}
        {loading ? (
          <div className="card text-center py-20 text-muted text-[14px]">Cargando…</div>
        ) : data && (
          <>
            <p className="text-[13px] text-muted mb-4">Período: <b className="text-text dark:text-white">{data.etiqueta}</b></p>

            {/* Tarjetas principales */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <KPI icon={TrendingUp} tono="pos" label="Ingresos (cobros a inquilinos)"
                   valor={fmt(ing.total)} sub={`${ing.cantidad || 0} cobro(s)`} />
              <KPI icon={TrendingDown} tono="neg" label="Egresos (entregado a propietarios)"
                   valor={fmt(egr.total)} sub={`${egr.cantidad || 0} liquidación(es)`} />
              <KPI icon={Coins} tono="cobre" label="Ganancia (comisiones)"
                   valor={fmt(data.ganancia)} sub="alquiler × comisión %" />
              <KPI icon={Wallet} tono="neutro" label="Saldo de caja"
                   valor={fmt(data.saldo_caja)} sub="ingresos − egresos" />
            </div>

            {/* Desglose de ingresos */}
            <div className="card p-6">
              <p className="text-[11px] uppercase tracking-widest font-semibold text-muted mb-4">
                Desglose de ingresos
              </p>
              <div className="space-y-2.5 text-[14px]">
                <Fila label="Alquileres" valor={ing.alquiler} />
                <Fila label="Expensas" valor={ing.expensas} />
                <Fila label="Tasas municipales" valor={ing.municipal} />
                <Fila label="Otros conceptos" valor={ing.otros} />
                <div className="border-t border-border pt-2.5 flex justify-between font-semibold">
                  <span>Total ingresos</span>
                  <span className="tabular-nums">{fmt(ing.total)}</span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-muted mt-4 leading-relaxed">
              Los <b>ingresos</b> son lo cobrado a inquilinos en el período (por fecha de pago).
              Los <b>egresos</b> son lo entregado a propietarios (por fecha de liquidación).
              La <b>ganancia</b> de la inmobiliaria es la comisión sobre el alquiler.
            </p>
          </>
        )}
      </div>
    </Layout>
  )
}

function KPI({ icon: Icon, label, valor, sub, tono }) {
  const color = {
    pos: 'text-emerald-500', neg: 'text-rose-500', cobre: 'text-[#B8893A]', neutro: 'text-text dark:text-white',
  }[tono] || 'text-text'
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={15} className={color} />
        <p className="text-[11px] uppercase tracking-wider text-muted leading-tight">{label}</p>
      </div>
      <p className={`text-2xl font-bold tabular-nums ${color}`}>{valor}</p>
      {sub && <p className="text-[11px] text-muted mt-1">{sub}</p>}
    </div>
  )
}

function Fila({ label, valor }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className="tabular-nums">{fmt(valor)}</span>
    </div>
  )
}
