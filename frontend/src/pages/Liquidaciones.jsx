import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  Receipt, CheckCircle2, Clock, RefreshCw, Search, X, AlertCircle,
  RotateCcw, ChevronDown, ChevronRight, ListChecks,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'


const fmt = (n) => '$ ' + Number(n || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 })
const fmtFecha = (s) => {
  if (!s) return '—'
  try { return new Date(s).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }) }
  catch { return s }
}


/**
 * Liquidaciones a propietarios.
 *
 * Flujo: cuando el inquilino paga, el pago queda "pendiente de liquidar".
 * Cuando el propietario viene a buscar su parte, lo marcamos como liquidado
 * y queda registrado en la DB con fecha y monto entregado.
 *
 * Vista por default: pendientes agrupados por propietario para que el
 * operador pueda rápidamente buscar al dueño que llega y marcar todos los
 * pagos que se le entregan.
 */
export default function Liquidaciones() {
  const [estado, setEstado] = useState('pendientes')   // pendientes | liquidadas | todas
  const [busqueda, setBusqueda] = useState('')
  const [data, setData] = useState(null)
  const [resumen, setResumen] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [marcando, setMarcando] = useState(null)       // pago activo en modal "marcar"
  const [revertiendo, setRevertiendo] = useState(null)
  const [expandidos, setExpandidos] = useState({})     // {propietarioId: true}

  const cargar = useCallback(() => {
    setLoading(true); setErr('')
    Promise.allSettled([
      api.get(`/api/liquidaciones?estado=${estado}`, { timeout: 15000 }),
      api.get('/api/liquidaciones/resumen', { timeout: 10000 }),
    ]).then(([l, r]) => {
      if (l.status === 'fulfilled') setData(l.value.data)
      else setErr(l.reason?.response?.data?.detail || l.reason?.message || 'Error al cargar.')
      if (r.status === 'fulfilled') setResumen(r.value.data)
    }).finally(() => setLoading(false))
  }, [estado])

  useEffect(() => { cargar() }, [cargar])

  // Búsqueda sobre los grupos
  const gruposFiltrados = useMemo(() => {
    if (!data?.agrupado_por_propietario) return []
    if (!busqueda.trim()) return data.agrupado_por_propietario
    const q = busqueda.toLowerCase()
    return data.agrupado_por_propietario.filter(g => {
      if (g.propietario?.nombre?.toLowerCase().includes(q)) return true
      if (g.propietario?.documento?.includes(busqueda)) return true
      return g.items.some(it =>
        it.propiedad_direccion?.toLowerCase().includes(q) ||
        it.inquilino_nombre?.toLowerCase().includes(q) ||
        it.contrato_codigo?.toLowerCase().includes(q)
      )
    })
  }, [data, busqueda])

  const toggleGrupo = (id) => {
    setExpandidos(prev => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Operación de caja</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3 flex items-center gap-3">
                <Receipt className="text-[#B8893A]" /> Liquidaciones
              </h1>
              <p className="hero-sub">
                Pagos cobrados al inquilino, esperando ser entregados al propietario.
              </p>
            </div>
            <button onClick={cargar} className="btn-ghost p-2 self-end" title="Recargar">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </header>

        {/* Stats */}
        {resumen && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <Stat
              icon={Clock}
              label="Pendientes de entregar"
              value={resumen.pendientes}
              sub={fmt(resumen.total_neto_pendiente) + ' total'}
              color={resumen.pendientes > 0 ? 'amber' : 'green'}
            />
            <Stat
              icon={CheckCircle2}
              label="Liquidados"
              value={resumen.liquidados}
              sub={fmt(resumen.total_neto_liquidado) + ' entregado'}
              color="green"
            />
            <Stat
              label="Total neto pendiente"
              value={fmt(resumen.total_neto_pendiente)}
              sub="suma a pagar"
              color={resumen.total_neto_pendiente > 0 ? 'amber' : 'green'}
              big
            />
            <Stat
              label="Total entregado"
              value={fmt(resumen.total_neto_liquidado)}
              sub="histórico"
              color="green"
              big
            />
          </div>
        )}

        {/* Filtros + búsqueda */}
        <div className="card p-3 mb-4 flex flex-wrap items-center gap-3">
          <div className="flex gap-1.5">
            <Pill active={estado === 'pendientes'} onClick={() => setEstado('pendientes')}
              label="Pendientes" color="warn" />
            <Pill active={estado === 'liquidadas'} onClick={() => setEstado('liquidadas')}
              label="Liquidadas" color="success" />
            <Pill active={estado === 'todas'} onClick={() => setEstado('todas')}
              label="Todas" />
          </div>
          <div className="flex-1 min-w-[200px] relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              className="input pl-9 !py-2 text-[13px]"
              placeholder="Buscar por propietario, propiedad o inquilino…"
              value={busqueda}
              onChange={e => setBusqueda(e.target.value)}
            />
            {busqueda && (
              <button onClick={() => setBusqueda('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-primary">
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {err && (
          <div className="card p-3 mb-4 border-l-4 !border-l-danger bg-danger/5 text-[12px] text-danger flex items-start gap-2">
            <AlertCircle size={13} className="shrink-0 mt-0.5" /> <span className="flex-1">{err}</span>
            <button onClick={cargar} className="underline hover:no-underline">Reintentar</button>
          </div>
        )}

        {/* Lista agrupada por propietario */}
        {loading ? (
          <div className="card p-12 text-center">
            <RefreshCw size={24} className="mx-auto text-muted/40 mb-2 animate-spin" />
            <p className="text-sm text-muted">Cargando liquidaciones…</p>
          </div>
        ) : gruposFiltrados.length === 0 ? (
          <div className="card p-12 text-center">
            <CheckCircle2 size={36} className="mx-auto text-success/60 mb-3" />
            <p className="text-[14px] font-medium mb-1">
              {estado === 'pendientes'
                ? 'No hay pagos pendientes de liquidar'
                : 'No hay liquidaciones que coincidan'}
            </p>
            <p className="text-[12px] text-muted">
              {estado === 'pendientes'
                ? 'Cuando un inquilino pague, va a aparecer acá esperando que el propietario venga a buscar su parte.'
                : 'Probá cambiar el filtro o limpiar la búsqueda.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {gruposFiltrados.map(g => (
              <GrupoPropietario
                key={g.propietario.id || 0}
                grupo={g}
                expandido={expandidos[g.propietario.id || 0]}
                onToggle={() => toggleGrupo(g.propietario.id || 0)}
                onMarcar={(item) => setMarcando(item)}
                onRevertir={(item) => setRevertiendo(item)}
              />
            ))}
          </div>
        )}

        <p className="text-[11px] text-muted dark:text-gray-500 mt-6 text-center">
          💡 Las liquidaciones quedan registradas con fecha y monto en la base de datos para auditoría.
        </p>
      </div>

      {marcando && (
        <ModalMarcar
          pago={marcando}
          onClose={() => setMarcando(null)}
          onSaved={() => { setMarcando(null); cargar() }}
        />
      )}
      {revertiendo && (
        <ModalRevertir
          pago={revertiendo}
          onClose={() => setRevertiendo(null)}
          onSaved={() => { setRevertiendo(null); cargar() }}
        />
      )}
    </Layout>
  )
}


function Stat({ icon: Icon, label, value, sub, color = 'black', big }) {
  const colors = {
    black:  'text-black dark:text-white',
    green:  'text-success',
    amber:  'text-warn',
  }
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-1.5">
        <p className="stat-label">{label}</p>
        {Icon && <Icon size={13} className="text-muted/60" />}
      </div>
      <p className={`stat-value ${big ? 'text-xl sm:text-2xl' : 'text-2xl'} mt-1 ${colors[color] || ''}`}>
        {value}
      </p>
      {sub && <p className="text-[10px] text-muted dark:text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}


function Pill({ active, onClick, label, color }) {
  const bg = active
    ? color === 'warn'    ? 'bg-warn text-white'
    : color === 'success' ? 'bg-success text-white'
    : 'bg-[#0A0A0A] dark:bg-white text-white dark:text-[#0A0A0A]'
    : 'bg-white dark:bg-[#1A1A1A] border border-border dark:border-[#2A2A2A] text-muted hover:bg-neutral-50 dark:hover:bg-[#252525]'
  return (
    <button onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[12px] font-medium transition ${bg}`}>
      {label}
    </button>
  )
}


function GrupoPropietario({ grupo, expandido, onToggle, onMarcar, onRevertir }) {
  const tienePendientes = grupo.pendientes > 0
  return (
    <div className="card overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-3 p-4 hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {expandido
            ? <ChevronDown size={16} className="text-muted shrink-0" />
            : <ChevronRight size={16} className="text-muted shrink-0" />
          }
          <div className="text-left min-w-0 flex-1">
            <p className="font-semibold text-[14px] truncate">
              {grupo.propietario.nombre}
            </p>
            <p className="text-[11px] text-muted truncate">
              {grupo.propietario.documento && `${grupo.propietario.documento} · `}
              {grupo.pendientes > 0 && `${grupo.pendientes} pendiente${grupo.pendientes !== 1 ? 's' : ''}`}
              {grupo.pendientes > 0 && grupo.liquidados > 0 && ' · '}
              {grupo.liquidados > 0 && `${grupo.liquidados} liquidado${grupo.liquidados !== 1 ? 's' : ''}`}
            </p>
          </div>
        </div>
        <div className="text-right shrink-0">
          {tienePendientes ? (
            <>
              <p className="text-[10px] text-muted uppercase tracking-widest">A entregar</p>
              <p className="text-[16px] font-bold text-warn tabular-nums">
                {fmt(grupo.total_neto_pendiente)}
              </p>
            </>
          ) : (
            <span className="chip-success">Todo entregado</span>
          )}
        </div>
      </button>

      {expandido && (
        <div className="border-t border-border dark:border-[#2A2A2A] divide-y divide-border dark:divide-[#2A2A2A]">
          {grupo.items.map(it => (
            <ItemLiquidacion
              key={it.pago_id}
              item={it}
              onMarcar={() => onMarcar(it)}
              onRevertir={() => onRevertir(it)}
            />
          ))}
        </div>
      )}
    </div>
  )
}


function ItemLiquidacion({ item, onMarcar, onRevertir }) {
  const [verDesglose, setVerDesglose] = useState(false)
  // Parsear el JSON granular si existe en el pago
  let conceptos = []
  if (item.detalle_conceptos) {
    try { conceptos = JSON.parse(item.detalle_conceptos) } catch {}
  }
  // Compat: modelo nuevo usa `estado` (cobrar/pagado_directo/pendiente),
  // modelo viejo usa `paga` (inquilino/propietario).
  const _estadoDe = c => c.estado || (c.paga === 'propietario' ? 'pagado_directo' : 'cobrar')
  const conceptosInquilino = conceptos.filter(c => _estadoDe(c) === 'cobrar')
  const conceptosPropietario = conceptos.filter(c => _estadoDe(c) === 'pagado_directo')

  return (
    <div>
      <div className="px-4 py-3 flex items-center gap-3 hover:bg-neutral-50/50 dark:hover:bg-[#141414] transition">
      <button
        onClick={() => setVerDesglose(v => !v)}
        className="shrink-0 p-1 text-muted hover:text-primary dark:hover:text-white rounded"
        title="Ver desglose"
      >
        {verDesglose ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-[13px] truncate">
          {item.propiedad_direccion || `Propiedad #${item.propiedad_id}`}
          <span className="text-muted font-normal ml-2 text-[11px]">
            {item.contrato_codigo || ''}
          </span>
        </p>
        <p className="text-[11px] text-muted truncate">
          Período {item.periodo} · Inquilino: {item.inquilino_nombre || '—'} · Cobrado el {fmtFecha(item.fecha_pago_inquilino)}
        </p>
        {item.liquidado && (
          <p className="text-[10px] text-success mt-0.5 flex items-center gap-1.5">
            <CheckCircle2 size={10} />
            Entregado al propietario el {fmtFecha(item.fecha_liquidacion)}
            {item.monto_liquidado && ` · ${fmt(item.monto_liquidado)}`}
          </p>
        )}
      </div>

      <div className="text-right shrink-0">
        <p className="text-[10px] text-muted uppercase tracking-widest">Su parte</p>
        <p className={`text-[15px] font-bold tabular-nums ${item.liquidado ? 'text-success' : 'text-[#B8893A]'}`}>
          {fmt(item.liquidado
            ? Math.round((item.monto_liquidado || item.neto_a_pagar) * (item.mi_porcentaje || 100) / 100)
            : (item.mi_parte ?? item.neto_a_pagar))}
        </p>
        {item.mi_porcentaje != null && item.mi_porcentaje < 100 && (
          <p className="text-[10px] text-muted">
            {item.mi_porcentaje}% de {fmt(item.neto_a_pagar)}
          </p>
        )}
        {item.comision_porc > 0 && (!item.mi_porcentaje || item.mi_porcentaje >= 100) && (
          <p className="text-[10px] text-muted">comisión {item.comision_porc}%</p>
        )}
      </div>

      <div className="shrink-0">
        {item.liquidado ? (
          <button
            onClick={onRevertir}
            className="btn-ghost py-1.5 px-2 text-[11px]"
            title="Revertir (corregir error)"
          >
            <RotateCcw size={11} />
          </button>
        ) : (
          <button onClick={onMarcar} className="btn-primary text-[12px] py-1.5 px-3">
            <CheckCircle2 size={12} /> Marcar entregado
          </button>
        )}
      </div>
      </div>

      {/* Desglose desplegable: cómo se calculó el neto */}
      {verDesglose && (
        <div className="px-4 pb-4 -mt-1 bg-neutral-50/50 dark:bg-[#141414]">
          <div className="rounded-xl p-4 border border-border dark:border-[#2A2A2A] bg-white dark:bg-[#0F0F0F]">
            <p className="text-[10px] uppercase tracking-widest font-semibold text-muted mb-3 flex items-center gap-1.5">
              <ListChecks size={11} /> Cálculo del neto al propietario
            </p>
            <div className="space-y-1.5 text-[12px]">
              <div className="flex justify-between">
                <span className="text-muted">Alquiler base</span>
                <span className="tabular-nums">{fmt(item.monto_alquiler)}</span>
              </div>
              <div className="flex justify-between text-warn">
                <span>Comisión inmobiliaria ({item.comision_porc}% s/alquiler)</span>
                <span className="tabular-nums">− {fmt((item.monto_alquiler || 0) * (item.comision_porc || 0) / 100)}</span>
              </div>
              <div className="border-t border-border my-1.5 pt-1.5 flex justify-between font-semibold">
                <span>Neto al propietario</span>
                <span className="text-success tabular-nums">{fmt(item.neto_a_pagar)}</span>
              </div>
              {item.mi_porcentaje != null && item.mi_porcentaje < 100 && (
                <div className="border-t border-border my-1.5 pt-1.5 flex justify-between font-semibold">
                  <span>Su parte ({item.mi_porcentaje}%)</span>
                  <span className="text-[#B8893A] tabular-nums">{fmt(item.mi_parte)}</span>
                </div>
              )}
            </div>

            {/* Conceptos cobrados al inquilino (pasantes - no afectan neto) */}
            {conceptosInquilino.length > 0 && (
              <>
                <p className="text-[10px] uppercase tracking-widest font-semibold text-muted mt-4 mb-2">
                  Conceptos pasantes (cobrados al inquilino)
                </p>
                <div className="space-y-1 text-[11px] text-muted">
                  {conceptosInquilino.map((c, i) => (
                    <div key={i} className="flex justify-between">
                      <span>{c.label}</span>
                      <span className="tabular-nums">{fmt(c.monto)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-muted/60 italic mt-1">
                  Se derivan a quien corresponda (consorcio, municipio, etc.) — no integran el neto.
                </p>
              </>
            )}

            {/* Conceptos a cargo del propietario */}
            {conceptosPropietario.length > 0 && (
              <>
                <p className="text-[10px] uppercase tracking-widest font-semibold text-[#B8893A] mt-4 mb-2">
                  A cargo del propietario
                </p>
                <div className="space-y-1 text-[11px]">
                  {conceptosPropietario.map((c, i) => (
                    <div key={i} className="flex justify-between text-[#B8893A]">
                      <span>{c.label}</span>
                      <span className="tabular-nums">{fmt(c.monto)}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {item.liquidado && item.notas_liquidacion && (
              <p className="text-[10px] text-muted italic mt-3 pt-3 border-t border-border">
                <strong>Notas de la entrega:</strong> {item.notas_liquidacion}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}


function ModalMarcar({ pago, onClose, onSaved }) {
  const _fmtMonto = (n) =>
    Number(n || 0).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const _parseMonto = (str) =>
    parseFloat(String(str).replace(/\./g, '').replace(',', '.')) || 0

  const [form, setForm] = useState({
    fecha: new Date().toISOString().slice(0, 10),
    monto: pago.neto_a_pagar,
    notas: '',
  })
  const [montoDisplay, setMontoDisplay] = useState(_fmtMonto(pago.neto_a_pagar))
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault(); setLoading(true); setErr('')
    try {
      await api.post(`/api/liquidaciones/${pago.pago_id}/marcar`, {
        fecha: form.fecha,
        monto: Number(form.monto),
        notas: form.notas || null,
      })
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'No se pudo registrar la liquidación.')
    } finally { setLoading(false) }
  }

  // Parsear conceptos del JSON granular (si existe). Si el pago es viejo
  // (no tiene detalle_conceptos), reconstruir desde los campos legacy
  // monto_expensas/municipal/otros para que el desglose se vea SIEMPRE.
  let conceptos = []
  if (pago.detalle_conceptos) {
    try { conceptos = JSON.parse(pago.detalle_conceptos) } catch {}
  }
  if (conceptos.length === 0) {
    // Fallback legacy: cualquier monto > 0 lo asumimos como pasante del inquilino
    if (pago.monto_expensas > 0) conceptos.push({ label: 'Expensas', monto: pago.monto_expensas, estado: 'cobrar' })
    if (pago.monto_municipal > 0) conceptos.push({ label: 'Tasas municipales', monto: pago.monto_municipal, estado: 'cobrar' })
    if (pago.monto_otros > 0) conceptos.push({ label: 'Otros conceptos', monto: pago.monto_otros, estado: 'cobrar' })
  }
  // Compat: modelo nuevo usa `estado`, viejo usa `paga`.
  const _estadoDe = c => c.estado || (c.paga === 'propietario' ? 'pagado_directo' : 'cobrar')

  // Construimos las filas para la tabla "Concepto | Pagado | A rendir":
  //   - Pagado     = lo que el inquilino ya pagó (directo al ente o adelantado)
  //   - A rendir   = lo que la inmobiliaria le tiene que dar al propietario
  //     Alquiler: a_rendir = alquiler − comisión.
  //     Resto (expensas/tasas/etc cobrados): pasante, se rinde igual al monto cobrado.
  //     Si fue "pagado_directo": pagado>0, a_rendir=0 (no toca a la inmobiliaria).
  const totalCobradoAlquiler = pago.monto_alquiler || 0
  const comision = (totalCobradoAlquiler * (pago.comision_porc || 0)) / 100

  const filasDesglose = []
  filasDesglose.push({
    label: 'Alquiler',
    pagado: totalCobradoAlquiler,         // el inquilino lo pagó
    a_rendir: totalCobradoAlquiler,        // se muestra entero; la comisión se resta abajo
  })
  // Agrupamos por label (Expensas, Tasas municipales, Otros…) — todos pasan
  // 100 % al propietario porque ya los abonó previamente
  const grupos = {}
  for (const c of conceptos) {
    const lbl = c.label || 'Otro'
    const key = lbl.toLowerCase()
    if (!grupos[key]) grupos[key] = { label: lbl, pagado: 0, a_rendir: 0 }
    const estado = _estadoDe(c)
    const monto = Number(c.monto) || 0
    if (estado === 'cobrar') {
      // Se cobró al inquilino → es plata de paso, va 100% al propietario
      grupos[key].pagado += monto
      grupos[key].a_rendir += monto
    } else if (estado === 'pagado_directo') {
      // Inquilino lo pagó directo al ente → ya está saldado, no se rinde
      grupos[key].pagado += monto
    }
  }
  Object.values(grupos).forEach(g => filasDesglose.push(g))

  // Fila de comisión (descuento) — sólo se aplica al alquiler
  if (pago.comision_porc && comision > 0) {
    filasDesglose.push({
      label: `Comisión adm. ${pago.comision_porc}% s/ alquiler`,
      a_rendir: -comision,
      descuento: true,
    })
  }

  const totalPagado = filasDesglose.reduce((s, f) => s + (f.pagado || 0), 0)
  const totalARendir = filasDesglose.reduce((s, f) => s + (f.a_rendir || 0), 0)
  const totalAEntregar = pago.mi_parte ?? pago.neto_a_pagar
  // Para compat con el resto del modal (refacciones, etc.)
  const conceptosPropietario = conceptos.filter(c => _estadoDe(c) === 'pagado_directo')

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-5">
          <div>
            <h2 className="hero-title text-xl sm:text-2xl mb-0.5">Marcar como entregado</h2>
            <p className="text-[12px] text-muted">
              {pago.propietario?.nombre} · Período {pago.periodo}
            </p>
            <p className="text-[11px] text-muted/70">{pago.propiedad_direccion}</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        {/* Desglose en tabla: Concepto | Pagado (por inquilino) | A rendir (al propietario) */}
        <div className="rounded-2xl border border-border dark:border-[#2A2A2A] bg-neutral-50 dark:bg-[#141414] p-4 mb-5">
          <p className="text-[10px] uppercase tracking-widest font-semibold text-muted mb-3">
            Desglose
          </p>

          {/* Header */}
          <div className="grid grid-cols-[1fr_110px_110px] gap-2 px-1 text-[10px] uppercase tracking-wider text-muted font-semibold mb-1">
            <span>Concepto</span>
            <span className="text-right">Pagado</span>
            <span className="text-right">A rendir</span>
          </div>

          <div className="space-y-1 text-[12px]">
            {filasDesglose.map((f, i) => (
              <div key={i} className={`grid grid-cols-[1fr_110px_110px] gap-2 px-1 py-1 rounded-lg hover:bg-white/40 dark:hover:bg-black/20 ${
                f.descuento ? 'text-red-600 dark:text-red-400' : ''
              }`}>
                <div className="min-w-0">
                  <p className="truncate">{f.label}</p>
                  {f.nota && (
                    <p className="text-[10px] text-muted/70 italic truncate">{f.nota}</p>
                  )}
                </div>
                <span className={`text-right tabular-nums ${f.descuento ? '' : 'text-muted'}`}>
                  {f.pagado > 0 ? fmt(f.pagado) : '—'}
                </span>
                <span className="text-right tabular-nums">
                  {f.descuento
                    ? `− ${fmt(Math.abs(f.a_rendir))}`
                    : (f.a_rendir > 0 ? fmt(f.a_rendir) : '—')}
                </span>
              </div>
            ))}

            {/* Totales */}
            <div className="grid grid-cols-[1fr_110px_110px] gap-2 px-1 pt-2 border-t border-border font-semibold">
              <span>Totales</span>
              <span className="text-right tabular-nums text-muted">{fmt(totalPagado)}</span>
              <span className="text-right tabular-nums">{fmt(totalARendir)}</span>
            </div>

            {/* Total a entregar destacado */}
            <div className="border-t-2 border-[#B8893A]/40 pt-2 mt-2 flex justify-between text-[14px] font-bold">
              <span>TOTAL A ENTREGAR</span>
              <span className="text-[#B8893A] tabular-nums">{fmt(totalAEntregar)}</span>
            </div>

            {pago.mi_porcentaje != null && pago.mi_porcentaje < 100 && (
              <p className="text-[10px] text-muted text-right">
                {pago.mi_porcentaje}% de {fmt(pago.neto_a_pagar)} (neto total)
              </p>
            )}

            {/* Refacciones aplicadas a este pago */}
            {(pago.refacciones_aplicadas || []).length > 0 && (
              <div className="border-t border-border pt-2 mt-2">
                <p className="text-[10px] uppercase tracking-widest font-semibold text-success mb-1">
                  Refacciones aplicadas en este pago
                </p>
                {pago.refacciones_aplicadas.map((r, i) => (
                  <div key={i} className="flex justify-between text-success">
                    <span className="truncate">{r.descripcion}</span>
                    <span className="tabular-nums">− {fmt(r.monto)}</span>
                  </div>
                ))}
                <p className="text-[10px] text-muted/70 italic mt-1">
                  Las refacciones del inquilino ya descontadas del monto cobrado.
                </p>
              </div>
            )}
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Fecha de entrega</label>
              <input type="date" className="input"
                value={form.fecha}
                onChange={e => setForm({ ...form, fecha: e.target.value })} />
            </div>
            <div>
              <label className="label">Monto entregado $</label>
              <input type="text" inputMode="decimal" className="input"
                value={montoDisplay}
                onChange={e => {
                  setMontoDisplay(e.target.value)
                  setForm({ ...form, monto: _parseMonto(e.target.value) })
                }}
                onBlur={() => setMontoDisplay(_fmtMonto(form.monto))}
                onFocus={e => e.target.select()} />
            </div>
          </div>

          <div>
            <label className="label">Notas (opcional)</label>
            <textarea className="input resize-none" rows={2}
              placeholder="Ej: Entregado en efectivo, firma José Pérez"
              value={form.notas}
              onChange={e => setForm({ ...form, notas: e.target.value })} />
          </div>

          {pago.co_propietarios?.length > 1 && (
            <div className="rounded-xl p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-900 text-[12px] flex items-start gap-2">
              <AlertCircle size={13} className="text-blue-600 shrink-0 mt-0.5" />
              <div className="text-blue-700 dark:text-blue-300">
                Esta propiedad tiene <strong>{pago.co_propietarios.length} co-propietarios</strong>.
                Al marcar este pago como entregado, se asume que ya pagaste la parte a todos.
                <ul className="mt-1.5 space-y-0.5 list-disc list-inside text-[11px] opacity-90">
                  {pago.co_propietarios.map((co, i) => (
                    <li key={i}>
                      {co.nombre} — {co.porcentaje_efectivo}% ({fmt(co.neto_parte)})
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div className="rounded-xl p-3 bg-[#B8893A]/5 border border-[#B8893A]/20 text-[12px] text-muted flex items-start gap-2">
            <AlertCircle size={13} className="text-[#B8893A] shrink-0 mt-0.5" />
            <div>
              Al confirmar queda registrado quién, cuándo y cuánto. Si te equivocás,
              podés revertirlo después con el botón ↩.
            </div>
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : 'Confirmar entrega'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


function ModalRevertir({ pago, onClose, onSaved }) {
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const confirmar = async () => {
    setLoading(true); setErr('')
    try {
      await api.post(`/api/liquidaciones/${pago.pago_id}/revertir`)
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'No se pudo revertir.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-6 w-full max-w-md shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-warn/10 grid place-items-center">
            <RotateCcw size={18} className="text-warn" />
          </div>
          <h3 className="hero-title text-xl">Revertir liquidación</h3>
        </div>
        <p className="text-[13px] text-muted mb-5">
          El pago va a volver a aparecer como pendiente de entregar al propietario.
          Las notas quedan registradas para auditoría.
        </p>
        <p className="text-[12px] text-muted mb-5 bg-neutral-50 dark:bg-[#1A1A1A] rounded-xl p-3">
          <strong>{pago.propietario?.nombre}</strong> · Período {pago.periodo}<br />
          {pago.propiedad_direccion}
        </p>

        {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl mb-3">{err}</p>}

        <div className="flex gap-3">
          <button className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
          <button className="btn-danger flex-1" onClick={confirmar} disabled={loading}>
            {loading ? 'Revirtiendo…' : 'Sí, revertir'}
          </button>
        </div>
      </div>
    </div>
  )
}
