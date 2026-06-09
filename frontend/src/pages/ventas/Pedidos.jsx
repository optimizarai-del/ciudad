import { useEffect, useState } from 'react'
import { Plus, Trash2, ClipboardList } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import SearchBar from '../../components/SearchBar'
import PedidoModal from '../../components/ventas/PedidoModal'
import api from '../../utils/api'

const COL_LABEL = {
  nuevo: 'Nuevo', contactado: 'Contactado', en_seguimiento: 'En seguimiento',
  esperando_respuesta: 'Esperando respuesta', negociando: 'Negociando',
  cerrado: 'Cerrado', perdido: 'Perdido',
}
// Presets guardables: combinan filtros frecuentes en un clic.
const PRESETS = [
  { key: 'todos', label: 'Todos', params: {} },
  { key: 'activos', label: 'Activos', params: { _activos: true } },
  { key: 'alta', label: 'Alta prioridad', params: { prioridad: 'alta' } },
  { key: 'esperando', label: 'Esperando respuesta', params: { estado: 'esperando_respuesta' } },
  { key: 'negociando', label: 'En negociación', params: { estado: 'negociando' } },
]
const PAGE = 20

export default function Pedidos() {
  const [pedidos, setPedidos] = useState([])
  const [clientes, setClientes] = useState([])
  const [preset, setPreset] = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [visibles, setVisibles] = useState(PAGE)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = () => {
    const p = PRESETS.find(x => x.key === preset)?.params || {}
    const qs = new URLSearchParams()
    if (p.estado) qs.set('estado', p.estado)
    if (p.prioridad) qs.set('prioridad', p.prioridad)
    api.get(`/api/ventas-crm/pedidos?${qs.toString()}`).then(r => {
      let data = r.data || []
      if (p._activos) data = data.filter(x => !['cerrado', 'perdido'].includes(x.estado))
      setPedidos(data)
    })
    api.get('/api/ventas-crm/clientes').then(r => setClientes(r.data || []))
  }
  useEffect(() => { load(); setVisibles(PAGE) }, [preset])

  const clienteNombre = id => clientes.find(c => c.id === id)?.nombre || `Cliente #${id}`
  const filtrados = pedidos.filter(p => {
    if (!busqueda.trim()) return true
    const b = busqueda.toLowerCase()
    return [clienteNombre(p.cliente_id), p.zona, p.tipo, p.detalle]
      .some(v => (v || '').toLowerCase().includes(b))
  })
  const pagina = filtrados.slice(0, visibles)

  const del = async (p) => { if (!confirm('¿Eliminar este pedido?')) return; await api.delete(`/api/ventas-crm/pedidos/${p.id}`); load() }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Búsquedas activas</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Pedidos</h1>
              <p className="hero-sub">Listado de búsquedas de los clientes. El funnel visual está en CRM de Ventas.</p>
            </div>
            <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}>
              <Plus size={14} /> Nuevo pedido
            </button>
          </div>
        </header>

        <div className="flex flex-wrap gap-2 mb-3">
          {PRESETS.map(p => (
            <button key={p.key} onClick={() => setPreset(p.key)}
              className={`px-4 py-1.5 rounded-full text-[12px] font-medium transition ${
                preset === p.key ? 'bg-primary text-white' : 'bg-white dark:bg-[#1A1A1A] border border-border text-muted'
              }`}>{p.label}</button>
          ))}
        </div>
        <div className="mb-4 max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda} placeholder="Buscar por cliente, zona, tipo…" />
        </div>

        {filtrados.length === 0 ? (
          <div className="card text-center py-20">
            <ClipboardList size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">No hay pedidos para este filtro.</p>
          </div>
        ) : (
          <>
            <div className="card overflow-hidden">
              <table className="w-full">
                <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border">
                  <tr>
                    <th className="th">Cliente</th><th className="th">Tipo</th><th className="th">Zona</th>
                    <th className="th">Presupuesto</th><th className="th text-center">Estado</th>
                    <th className="th text-center">Prioridad</th><th className="th w-20" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {pagina.map(p => (
                    <tr key={p.id} className="hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] cursor-pointer"
                      onClick={() => { setEditing(p); setOpen(true) }}>
                      <td className="td font-medium text-[13px]">{clienteNombre(p.cliente_id)}</td>
                      <td className="td capitalize text-[12px] text-muted">{p.tipo || '—'}</td>
                      <td className="td text-[12px] text-muted">{p.zona || '—'}</td>
                      <td className="td text-[12px] text-muted">{p.precio_max_usd ? `hasta USD ${p.precio_max_usd.toLocaleString('es-AR')}` : '—'}</td>
                      <td className="td text-center"><span className="chip-muted">{COL_LABEL[p.estado]}</span></td>
                      <td className="td text-center"><span className={p.prioridad === 'alta' ? 'chip-warn' : 'chip-muted'}>{p.prioridad}</span></td>
                      <td className="td text-right" onClick={e => e.stopPropagation()}>
                        <button onClick={() => del(p)} className="p-1 text-muted hover:text-danger"><Trash2 size={13} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {visibles < filtrados.length && (
              <div className="text-center mt-4">
                <button className="btn-secondary" onClick={() => setVisibles(v => v + PAGE)}>
                  Ver más ({filtrados.length - visibles} restantes)
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {open && (
        <PedidoModal initial={editing} clientes={clientes}
          onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />
      )}
    </Layout>
  )
}
