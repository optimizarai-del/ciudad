import { useState, useEffect } from 'react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { CheckCircle, Clock, AlertCircle, ChevronLeft, ChevronRight, DollarSign, Phone } from 'lucide-react'

const ESTADO_CONFIG = {
  pagado:   { label: 'Cobrado',   bg: 'bg-green-100 dark:bg-green-900/30',  text: 'text-green-700 dark:text-green-400', icon: CheckCircle },
  pendiente:{ label: 'Pendiente', bg: 'bg-amber-50 dark:bg-amber-900/20',   text: 'text-amber-700 dark:text-amber-400', icon: Clock },
  vencido:  { label: 'Vencido',   bg: 'bg-red-50 dark:bg-red-900/20',       text: 'text-red-600 dark:text-red-400',     icon: AlertCircle },
  sin_pago: { label: 'Sin pago',  bg: 'bg-gray-50 dark:bg-gray-900',        text: 'text-gray-500',                      icon: Clock },
  parcial:  { label: 'Parcial',   bg: 'bg-blue-50 dark:bg-blue-900/20',     text: 'text-blue-700 dark:text-blue-400',   icon: Clock },
}

function fmtMoney(n) {
  if (!n) return '$0'
  return '$' + Number(n).toLocaleString('es-AR', { maximumFractionDigits: 0 })
}

function prevMes(mes) {
  const [y, m] = mes.split('-').map(Number)
  return m === 1 ? `${y-1}-12` : `${y}-${String(m-1).padStart(2,'0')}`
}
function nextMes(mes) {
  const [y, m] = mes.split('-').map(Number)
  return m === 12 ? `${y+1}-01` : `${y}-${String(m+1).padStart(2,'0')}`
}
function mesLabel(mes) {
  const [y, m] = mes.split('-').map(Number)
  return new Date(y, m-1, 1).toLocaleString('es-AR', { month: 'long', year: 'numeric' })
}

export default function Cobranza() {
  const hoy = new Date()
  const [mes, setMes] = useState(`${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}`)
  const [pagos, setPagos] = useState([])
  const [resumen, setResumen] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filtro, setFiltro] = useState('todos')
  const [marcando, setMarcando] = useState(null)

  const cargar = async () => {
    setLoading(true)
    try {
      const [p, r] = await Promise.all([
        api.get(`/api/cobranza/mensual?mes=${mes}`),
        api.get(`/api/cobranza/resumen?mes=${mes}`),
      ])
      setPagos(p.data)
      setResumen(r.data)
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { cargar() }, [mes])

  const marcarCobrado = async (pagoId) => {
    if (!pagoId) return
    setMarcando(pagoId)
    try {
      await api.patch(`/api/cobranza/${pagoId}/cobrar`)
      await cargar()
    } finally { setMarcando(null) }
  }

  const pagosFiltrados = filtro === 'todos' ? pagos : pagos.filter(p => p.estado === filtro)

  return (
    <Layout>
      <div className="p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-1">Alquileres</p>
            <h1 className="text-3xl font-black">Cobranza</h1>
          </div>
          {/* Navegación de mes */}
          <div className="flex items-center gap-2">
            <button onClick={() => setMes(prevMes(mes))} className="btn-ghost p-2"><ChevronLeft size={16} /></button>
            <span className="text-sm font-semibold capitalize min-w-[160px] text-center">{mesLabel(mes)}</span>
            <button onClick={() => setMes(nextMes(mes))} className="btn-ghost p-2"><ChevronRight size={16} /></button>
          </div>
        </div>

        {/* Resumen */}
        {resumen && (
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Total esperado', value: fmtMoney(resumen.total_esperado), color: '' },
              { label: 'Cobrado', value: fmtMoney(resumen.cobrado), color: 'text-green-600 dark:text-green-400' },
              { label: 'Pendiente', value: fmtMoney(resumen.pendiente), color: 'text-amber-600' },
              { label: 'Vencido', value: fmtMoney(resumen.vencido), color: resumen.vencido > 0 ? 'text-red-500' : '' },
            ].map(({ label, value, color }) => (
              <div key={label} className="card p-4">
                <p className="text-xs text-gray-400 mb-1">{label}</p>
                <p className={`text-2xl font-black ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Progress bar */}
        {resumen && resumen.total_esperado > 0 && (
          <div className="card px-5 py-4">
            <div className="flex justify-between text-xs text-gray-400 mb-2">
              <span>{resumen.porcentaje_cobrado}% cobrado</span>
              <span>{resumen.contratos_activos} contratos activos</span>
            </div>
            <div className="h-2.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-black dark:bg-white rounded-full transition-all duration-700"
                style={{ width: `${resumen.porcentaje_cobrado}%` }} />
            </div>
          </div>
        )}

        {/* Filtros */}
        <div className="flex gap-2">
          {['todos', 'pendiente', 'pagado', 'vencido'].map(f => (
            <button
              key={f}
              onClick={() => setFiltro(f)}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
                filtro === f
                  ? 'bg-black dark:bg-white text-white dark:text-black'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {f === 'todos' ? 'Todos' : ESTADO_CONFIG[f]?.label}
              {f !== 'todos' && (
                <span className="ml-1 opacity-60">
                  {pagos.filter(p => p.estado === f).length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tabla */}
        <div className="card overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-sm text-gray-400">Cargando...</div>
          ) : pagosFiltrados.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">No hay pagos para este período.</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <th className="th text-left">Propiedad</th>
                  <th className="th text-left">Inquilino</th>
                  <th className="th text-right">Monto</th>
                  <th className="th text-center">Vencimiento</th>
                  <th className="th text-center">Estado</th>
                  <th className="th text-center">Acción</th>
                </tr>
              </thead>
              <tbody>
                {pagosFiltrados.map((p, i) => {
                  const cfg = ESTADO_CONFIG[p.estado] || ESTADO_CONFIG.pendiente
                  const Icon = cfg.icon
                  return (
                    <tr key={p.pago_id || i} className="border-b border-gray-50 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                      <td className="td">
                        <p className="font-medium text-sm">{p.propiedad}</p>
                        <p className="text-xs text-gray-400">{p.contrato_codigo}</p>
                      </td>
                      <td className="td">
                        <p className="text-sm">{p.inquilino}</p>
                        {p.inquilino_telefono && (
                          <p className="text-xs text-gray-400 flex items-center gap-1">
                            <Phone size={10} />{p.inquilino_telefono}
                          </p>
                        )}
                      </td>
                      <td className="td text-right">
                        <p className="font-semibold text-sm">{fmtMoney(p.monto_total)}</p>
                      </td>
                      <td className="td text-center">
                        <p className="text-sm text-gray-500">
                          {p.fecha_vencimiento
                            ? new Date(p.fecha_vencimiento).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })
                            : '—'}
                        </p>
                      </td>
                      <td className="td text-center">
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>
                          <Icon size={11} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="td text-center">
                        {p.estado !== 'pagado' && p.pago_id && (
                          <button
                            onClick={() => marcarCobrado(p.pago_id)}
                            disabled={marcando === p.pago_id}
                            className="text-xs bg-black dark:bg-white text-white dark:text-black px-3 py-1.5 rounded-lg font-medium hover:opacity-80 transition-opacity disabled:opacity-40"
                          >
                            {marcando === p.pago_id ? '...' : 'Marcar cobrado'}
                          </button>
                        )}
                        {p.estado === 'pagado' && (
                          <span className="text-xs text-green-600 dark:text-green-400">
                            {p.fecha_pago ? new Date(p.fecha_pago).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' }) : '✓'}
                          </span>
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
    </Layout>
  )
}
