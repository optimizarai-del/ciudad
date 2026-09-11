import { useEffect, useState } from 'react'
import { Bookmark, Trash2, ExternalLink, Building2, User, MapPin } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const FUENTE_LABEL = { instagram: 'Instagram', web: 'Web', tokko: 'Red Tokko', catalogo: 'Catálogo' }

export default function Seleccionadas() {
  const [clientes, setClientes] = useState([])
  const [clienteId, setClienteId] = useState('')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const cargarClientes = async () => {
    try { const { data } = await api.get('/api/ventas-crm/clientes?limit=500'); setClientes(Array.isArray(data) ? data : []) }
    catch { setClientes([]) }
  }
  const cargar = async () => {
    setLoading(true)
    try {
      const qs = clienteId ? `?cliente_id=${clienteId}` : ''
      const { data } = await api.get(`/api/ventas-crm/selecciones${qs}`)
      setItems(Array.isArray(data) ? data : [])
    } catch { setItems([]) } finally { setLoading(false) }
  }

  useEffect(() => { cargarClientes() }, [])
  useEffect(() => { cargar() }, [clienteId])

  const borrar = async (id) => {
    try { await api.delete(`/api/ventas-crm/selecciones/${id}`); setItems(items.filter(i => i.id !== id)) } catch {}
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-5">
          <div className="hero-eyebrow">Propiedades guardadas por cliente</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2 flex items-center gap-2">
            <Bookmark className="text-[#B8893A]" size={28} /> Seleccionadas
          </h1>
          <p className="hero-sub">Propiedades que asociaste a cada cliente desde Instagram, Webs, Red Tokko o el catálogo.</p>
        </header>

        <div className="card p-3 mb-4 flex flex-wrap items-end gap-2">
          <div className="min-w-[220px]">
            <label className="label">Cliente</label>
            <select className="input !py-2 text-[13px]" value={clienteId} onChange={e => setClienteId(e.target.value)}>
              <option value="">Todos los clientes</option>
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
          <p className="text-[12px] text-muted ml-auto">{items.length} propiedad{items.length === 1 ? '' : 'es'} seleccionada{items.length === 1 ? '' : 's'}</p>
        </div>

        {loading ? (
          <div className="card text-center py-20 text-muted text-[14px]">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="card text-center py-20">
            <Bookmark size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">
              No hay propiedades seleccionadas{clienteId ? ' para este cliente' : ''}. Usá el botón «Asociar a cliente» en Instagram, Webs, Red Tokko o Propiedades.
            </p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {items.map(s => (
              <div key={s.id} className="card p-0 overflow-hidden flex flex-col">
                <div className="aspect-[16/10] bg-neutral-100 dark:bg-[#141414] relative">
                  {s.imagen_url
                    ? <img src={s.imagen_url} alt="" className="w-full h-full object-cover" loading="lazy"
                        onError={e => { e.currentTarget.style.display = 'none' }} />
                    : <div className="grid place-items-center h-full"><Building2 size={28} className="text-muted/30" /></div>}
                  <span className="absolute top-2 left-2 chip-muted text-[10px]">{FUENTE_LABEL[s.fuente] || s.fuente}</span>
                  {s.operacion && <span className="absolute top-2 right-2 chip-success capitalize text-[10px]">{s.operacion}</span>}
                </div>
                <div className="p-3 flex-1 flex flex-col">
                  <p className="font-medium text-[13px] truncate">{s.titulo || s.direccion || 'Propiedad'}</p>
                  {s.direccion && s.titulo && (
                    <p className="text-[11px] text-muted flex items-center gap-1 mt-0.5"><MapPin size={10} />{s.direccion}</p>
                  )}
                  {s.precio_texto && <p className="stat-value text-lg mt-1">{s.precio_texto}</p>}
                  <p className="text-[12px] text-[#B8893A] flex items-center gap-1 mt-2"><User size={12} /> {s.cliente_nombre || `Cliente #${s.cliente_id}`}</p>
                  {s.notas && <p className="text-[11px] text-muted mt-1 line-clamp-2">{s.notas}</p>}
                  <div className="flex gap-1.5 mt-3 pt-2.5 border-t border-border">
                    {s.link_externo && (
                      <a href={s.link_externo} target="_blank" rel="noreferrer" className="btn-ghost !p-1.5 flex-1 justify-center text-[12px]">
                        <ExternalLink size={13} /> Ver
                      </a>
                    )}
                    <button onClick={() => borrar(s.id)} className="btn-ghost !p-1.5 text-muted hover:text-danger" title="Quitar de seleccionadas">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
