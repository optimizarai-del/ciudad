import { useEffect, useMemo, useState } from 'react'
import { Plus, MapPin, DollarSign, BedDouble } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import PedidoModal from '../../components/ventas/PedidoModal'
import api from '../../utils/api'

const COLUMNAS = ['nuevo', 'contactado', 'en_seguimiento', 'esperando_respuesta', 'negociando', 'cerrado', 'perdido']
const COL_LABEL = {
  nuevo: 'Nuevo', contactado: 'Contactado', en_seguimiento: 'En seguimiento',
  esperando_respuesta: 'Esperando respuesta', negociando: 'Negociando',
  cerrado: 'Cerrado', perdido: 'Perdido',
}
// Colores fuertes por columna para dar contraste (header + borde superior).
const COL_THEME = {
  nuevo:               { bar: 'bg-slate-500',   head: 'bg-slate-100 dark:bg-slate-900/40',     text: 'text-slate-700 dark:text-slate-300' },
  contactado:          { bar: 'bg-sky-500',     head: 'bg-sky-100 dark:bg-sky-900/40',         text: 'text-sky-700 dark:text-sky-300' },
  en_seguimiento:      { bar: 'bg-indigo-500',  head: 'bg-indigo-100 dark:bg-indigo-900/40',   text: 'text-indigo-700 dark:text-indigo-300' },
  esperando_respuesta: { bar: 'bg-amber-500',   head: 'bg-amber-100 dark:bg-amber-900/40',     text: 'text-amber-700 dark:text-amber-300' },
  negociando:          { bar: 'bg-orange-500',  head: 'bg-orange-100 dark:bg-orange-900/40',   text: 'text-orange-700 dark:text-orange-300' },
  cerrado:             { bar: 'bg-emerald-500', head: 'bg-emerald-100 dark:bg-emerald-900/40', text: 'text-emerald-700 dark:text-emerald-300' },
  perdido:             { bar: 'bg-rose-500',    head: 'bg-rose-100 dark:bg-rose-900/40',       text: 'text-rose-700 dark:text-rose-300' },
}
const PRIORIDAD_CHIP = { alta: 'chip-warn', media: 'chip-muted', baja: 'chip-muted' }

export default function CRMVentas() {
  const [pedidos, setPedidos] = useState([])
  const [clientes, setClientes] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [dragId, setDragId] = useState(null)
  const [overCol, setOverCol] = useState(null)

  const load = () => {
    api.get('/api/ventas-crm/pedidos').then(r => setPedidos(r.data || []))
    api.get('/api/ventas-crm/clientes').then(r => setClientes(r.data || []))
  }
  useEffect(() => { load() }, [])
  const clienteNombre = id => clientes.find(c => c.id === id)?.nombre || `Cliente #${id}`

  const porColumna = useMemo(() => {
    const acc = Object.fromEntries(COLUMNAS.map(c => [c, []]))
    for (const p of pedidos) (acc[p.estado] || acc.nuevo).push(p)
    return acc
  }, [pedidos])

  const onDrop = async (estado) => {
    setOverCol(null)
    if (dragId == null) return
    const ped = pedidos.find(p => p.id === dragId)
    setDragId(null)
    if (!ped || ped.estado === estado) return
    setPedidos(prev => prev.map(p => p.id === dragId ? { ...p, estado } : p))
    try { await api.patch(`/api/ventas-crm/pedidos/${dragId}/mover`, { estado, orden_kanban: 0 }) }
    catch { load() }
  }

  return (
    <Layout>
      <div className="max-w-[1400px] mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Funnel comercial</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">CRM de Ventas</h1>
              <p className="hero-sub">Arrastrá las tarjetas entre etapas: nuevo → contactado → mostrando → negociando → cerrado.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo pedido
            </button>
          </div>
        </header>

        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
          {COLUMNAS.map(col => {
            const th = COL_THEME[col]
            const isOver = overCol === col
            return (
              <div key={col}
                onDragOver={e => { e.preventDefault(); setOverCol(col) }}
                onDragLeave={() => setOverCol(c => c === col ? null : c)}
                onDrop={() => onDrop(col)}
                className={`rounded-2xl border-2 transition-colors min-h-[140px] overflow-hidden ${
                  isOver ? 'border-[#B8893A] bg-[#B8893A]/5' : 'border-border dark:border-[#262626] bg-neutral-100/70 dark:bg-[#0E0E0E]'
                }`}>
                {/* Header de columna con color y título grande */}
                <div className={`${th.head} px-3 py-2.5 flex items-center justify-between border-b-2 border-border dark:border-[#262626]`}>
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${th.bar}`} />
                    <p className={`text-[14px] font-bold ${th.text}`}>{COL_LABEL[col]}</p>
                  </div>
                  <span className={`text-[13px] font-bold ${th.text}`}>{porColumna[col].length}</span>
                </div>
                {/* Tarjetas */}
                <div className="p-2 space-y-2">
                  {porColumna[col].map(p => (
                    <div key={p.id} draggable
                      onDragStart={() => setDragId(p.id)}
                      onClick={() => { setEditing(p); setOpen(true) }}
                      className="bg-white dark:bg-[#1A1A1A] rounded-xl border border-border dark:border-[#2A2A2A] p-3 cursor-grab active:cursor-grabbing hover:shadow-lift hover:border-[#B8893A]/50 transition">
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-semibold text-[13px] truncate">{clienteNombre(p.cliente_id)}</p>
                        <span className={PRIORIDAD_CHIP[p.prioridad]}>{p.prioridad}</span>
                      </div>
                      {p.tipo && <p className="text-[11px] text-muted capitalize mt-1">{p.tipo}</p>}
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[11px] text-muted">
                        {p.zona && <span className="flex items-center gap-1"><MapPin size={10} />{p.zona}</span>}
                        {p.precio_max_usd && <span className="flex items-center gap-1"><DollarSign size={10} />{(p.precio_max_usd / 1000)}k</span>}
                        {p.dormitorios_min && <span className="flex items-center gap-1"><BedDouble size={10} />{p.dormitorios_min}+</span>}
                      </div>
                    </div>
                  ))}
                  {porColumna[col].length === 0 && (
                    <p className="text-[11px] text-muted/60 text-center py-4">Arrastrá aquí</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {open && (
        <PedidoModal initial={editing} clientes={clientes}
          onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />
      )}
    </Layout>
  )
}
