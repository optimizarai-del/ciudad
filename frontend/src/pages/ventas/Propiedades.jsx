import { useEffect, useState } from 'react'
import { Plus, X, Pencil, Trash2, Building2, Handshake, Calculator } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import SearchBar from '../../components/SearchBar'
import api from '../../utils/api'

const TIPOS = ['casa', 'departamento', 'lote', 'local', 'oficina', 'galpon', 'campo', 'otro']
const ESTADOS = ['disponible', 'reservada', 'vendida', 'inactiva']
const empty = {
  titulo: '', tipo: 'casa', estado: 'disponible', fuente: 'propia', direccion: '', ciudad: '',
  precio_usd: '', superficie_m2: '', dormitorios: '', banos: '', antiguedad_anios: '',
  descripcion: '', apreciacion: '', link_externo: '', inmobiliaria: '',
}
const num = v => v === '' || v == null ? null : Number(v)
const fmtUSD = n => n ? 'USD ' + n.toLocaleString('es-AR') : '—'

export default function Propiedades() {
  const [list, setList] = useState([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [ofertasDe, setOfertasDe] = useState(null)
  const [tasarOpen, setTasarOpen] = useState(false)
  const [busqueda, setBusqueda] = useState('')

  const load = () => api.get('/api/ventas-crm/propiedades').then(r => setList(r.data || []))
  useEffect(() => { load() }, [])

  const filtrados = list.filter(p => {
    if (!busqueda.trim()) return true
    const b = busqueda.toLowerCase()
    return [p.titulo, p.direccion, p.ciudad, p.descripcion, p.inmobiliaria].some(v => (v || '').toLowerCase().includes(b))
  })

  const del = async (p) => { if (!confirm('¿Eliminar propiedad?')) return; await api.delete(`/api/ventas-crm/propiedades/${p.id}`); load() }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Catálogo vivo</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Propiedades</h1>
              <p className="hero-sub">Catálogo de venta. Ofertas y tasación por propiedad.</p>
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary" onClick={() => setTasarOpen(true)}><Calculator size={14} /> Tasar</button>
              <button className="btn-primary" onClick={() => { setEditing(null); setOpen(true) }}><Plus size={14} /> Nueva</button>
            </div>
          </div>
        </header>

        <div className="mb-4 max-w-md">
          <SearchBar value={busqueda} onChange={setBusqueda} placeholder="Buscar por dirección, ciudad, inmobiliaria…" />
        </div>

        {filtrados.length === 0 ? (
          <div className="card text-center py-20">
            <Building2 size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">{busqueda ? 'Sin resultados para la búsqueda.' : 'Catálogo vacío. Cargá la primera propiedad.'}</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtrados.map(p => (
              <div key={p.id} className="card p-4 flex flex-col">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-[14px] truncate">{p.titulo || p.direccion || `Propiedad #${p.id}`}</p>
                  <span className="chip-muted capitalize">{p.estado}</span>
                </div>
                <p className="text-[12px] text-muted capitalize mt-0.5">{p.tipo} · {p.ciudad || 's/ciudad'}</p>
                <p className="stat-value text-xl mt-2">{fmtUSD(p.precio_usd)}</p>
                <div className="flex flex-wrap gap-x-3 text-[11px] text-muted mt-1">
                  {p.superficie_m2 && <span>{p.superficie_m2} m²</span>}
                  {p.dormitorios && <span>{p.dormitorios} dorm</span>}
                  {p.banos && <span>{p.banos} baños</span>}
                </div>
                {p.fuente !== 'propia' && <span className="chip-muted mt-2 w-fit capitalize">{p.fuente}</span>}
                <div className="flex gap-1 mt-3 pt-3 border-t border-border">
                  <button onClick={() => setOfertasDe(p)} className="flex-1 flex items-center justify-center gap-1 text-[12px] text-[#B8893A]"><Handshake size={13} /> Negociación</button>
                  <button onClick={() => { setEditing(p); setOpen(true) }} className="p-1.5 text-muted hover:text-primary"><Pencil size={13} /></button>
                  <button onClick={() => del(p)} className="p-1.5 text-muted hover:text-danger"><Trash2 size={13} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {open && <PropModal initial={editing} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
      {ofertasDe && <OfertasModal propiedad={ofertasDe} onClose={() => setOfertasDe(null)} />}
      {tasarOpen && <TasarModal onClose={() => setTasarOpen(false)} />}
    </Layout>
  )
}

function PropModal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState(initial ? { ...empty, ...initial } : { ...empty })
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(false)
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setErr(''); setLoading(true)
    const payload = {
      titulo: form.titulo || null, tipo: form.tipo, estado: form.estado, fuente: form.fuente,
      direccion: form.direccion || null, ciudad: form.ciudad || null,
      precio_usd: num(form.precio_usd), superficie_m2: num(form.superficie_m2),
      dormitorios: num(form.dormitorios), banos: num(form.banos), antiguedad_anios: num(form.antiguedad_anios),
      descripcion: form.descripcion || null, apreciacion: form.apreciacion || null,
      link_externo: form.link_externo || null, inmobiliaria: form.inmobiliaria || null,
    }
    try {
      if (initial) await api.patch(`/api/ventas-crm/propiedades/${initial.id}`, payload)
      else await api.post('/api/ventas-crm/propiedades', payload)
      onSaved()
    } catch (e) { setErr(e.response?.data?.detail || 'Error.') } finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-2xl shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-xl sm:text-2xl">{initial ? 'Editar propiedad' : 'Nueva propiedad'}</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div><label className="label">Título</label><input className="input" value={form.titulo || ''} onChange={set('titulo')} /></div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div><label className="label">Tipo</label><select className="input" value={form.tipo} onChange={set('tipo')}>{TIPOS.map(t => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label">Estado</label><select className="input" value={form.estado} onChange={set('estado')}>{ESTADOS.map(t => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label">Fuente</label><select className="input" value={form.fuente} onChange={set('fuente')}>{['propia', 'tokko', 'scraping', 'instagram'].map(t => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label">Precio USD</label><input className="input" type="number" value={form.precio_usd ?? ''} onChange={set('precio_usd')} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Dirección</label><input className="input" value={form.direccion || ''} onChange={set('direccion')} /></div>
            <div><label className="label">Ciudad</label><input className="input" value={form.ciudad || ''} onChange={set('ciudad')} /></div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div><label className="label">m²</label><input className="input" type="number" value={form.superficie_m2 ?? ''} onChange={set('superficie_m2')} /></div>
            <div><label className="label">Dorm.</label><input className="input" type="number" value={form.dormitorios ?? ''} onChange={set('dormitorios')} /></div>
            <div><label className="label">Baños</label><input className="input" type="number" value={form.banos ?? ''} onChange={set('banos')} /></div>
            <div><label className="label">Antigüedad</label><input className="input" type="number" value={form.antiguedad_anios ?? ''} onChange={set('antiguedad_anios')} /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Link externo</label><input className="input" value={form.link_externo || ''} onChange={set('link_externo')} /></div>
            <div><label className="label">Inmobiliaria (quién la tiene)</label><input className="input" value={form.inmobiliaria || ''} onChange={set('inmobiliaria')} /></div>
          </div>
          <div><label className="label">Descripción</label><textarea className="input resize-none" rows={2} value={form.descripcion || ''} onChange={set('descripcion')} /></div>
          <div><label className="label">Apreciación personal</label><textarea className="input resize-none" rows={2} value={form.apreciacion || ''} onChange={set('apreciacion')} /></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : 'Guardar'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function OfertasModal({ propiedad, onClose }) {
  const [ofertas, setOfertas] = useState([])
  const [form, setForm] = useState({ monto_usd: '', tipo: 'oferta', parte: 'comprador', nota: '' })
  const load = () => api.get(`/api/ventas-crm/propiedades/${propiedad.id}/ofertas`).then(r => setOfertas(r.data || []))
  useEffect(() => { load() }, [])
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const enviar = async e => {
    e.preventDefault()
    if (!form.monto_usd) return
    await api.post('/api/ventas-crm/ofertas', {
      propiedad_id: propiedad.id, monto_usd: Number(form.monto_usd),
      tipo: form.tipo, parte: form.parte, nota: form.nota || null,
    })
    setForm({ monto_usd: '', tipo: 'oferta', parte: 'comprador', nota: '' }); load()
  }
  const cambiar = async (o, estado) => { await api.patch(`/api/ventas-crm/ofertas/${o.id}?estado=${estado}`); load() }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6 flex flex-col max-h-[85vh]" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div><h2 className="hero-title text-xl">Negociación</h2><p className="hero-sub text-[12px]">{propiedad.titulo || propiedad.direccion}</p></div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <div className="flex-1 overflow-auto space-y-2 mb-4">
          {ofertas.length === 0 && <p className="text-muted text-[13px] text-center py-6">Sin ofertas aún.</p>}
          {ofertas.map(o => (
            <div key={o.id} className={`rounded-xl p-3 ${o.parte === 'comprador' ? 'bg-neutral-50 dark:bg-[#141414]' : 'bg-[#B8893A]/10'}`}>
              <div className="flex items-center justify-between">
                <p className="font-medium text-[14px]">{fmtUSD(o.monto_usd)}</p>
                <span className="chip-muted capitalize">{o.estado}</span>
              </div>
              <p className="text-[11px] text-muted capitalize">{o.tipo} · {o.parte}</p>
              {o.nota && <p className="text-[12px] mt-1">{o.nota}</p>}
              {o.estado === 'pendiente' && (
                <div className="flex gap-2 mt-2">
                  <button onClick={() => cambiar(o, 'aceptada')} className="text-[11px] text-green-600 underline">Aceptar</button>
                  <button onClick={() => cambiar(o, 'rechazada')} className="text-[11px] text-danger underline">Rechazar</button>
                </div>
              )}
            </div>
          ))}
        </div>
        <form onSubmit={enviar} className="space-y-2 border-t border-border pt-3">
          <div className="grid grid-cols-3 gap-2">
            <input className="input" type="number" placeholder="Monto USD" value={form.monto_usd} onChange={set('monto_usd')} />
            <select className="input" value={form.tipo} onChange={set('tipo')}><option value="oferta">Oferta</option><option value="contraoferta">Contraoferta</option></select>
            <select className="input" value={form.parte} onChange={set('parte')}><option value="comprador">Comprador</option><option value="vendedor">Vendedor</option></select>
          </div>
          <div className="flex gap-2">
            <input className="input flex-1" placeholder="Nota (opcional)" value={form.nota} onChange={set('nota')} />
            <button className="btn-primary px-4">Agregar</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function TasarModal({ onClose }) {
  const [form, setForm] = useState({ tipo: 'casa', superficie_m2: '', dormitorios: '', banos: '', antiguedad_anios: '', estado_conservacion: 'bueno' })
  const [res, setRes] = useState(null); const [loading, setLoading] = useState(false); const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const tasar = async e => {
    e.preventDefault(); setErr(''); setLoading(true); setRes(null)
    if (!form.superficie_m2) { setErr('Ingresá la superficie.'); setLoading(false); return }
    try {
      const r = await api.post('/api/ventas-crm/tasaciones', {
        tipo: form.tipo, superficie_m2: Number(form.superficie_m2),
        dormitorios: num(form.dormitorios), banos: num(form.banos),
        antiguedad_anios: num(form.antiguedad_anios), estado_conservacion: form.estado_conservacion,
      })
      setRes(r.data)
    } catch (e) { setErr(e.response?.data?.detail || 'Error.') } finally { setLoading(false) }
  }
  const comps = res?.comparables_json ? JSON.parse(res.comparables_json) : []
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <div><h2 className="hero-title text-xl">Tasación automática</h2><p className="hero-sub text-[12px]">Estimación por comparables del catálogo</p></div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>
        <form onSubmit={tasar} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Tipo</label><select className="input" value={form.tipo} onChange={set('tipo')}>{TIPOS.map(t => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label">Superficie m² *</label><input className="input" type="number" value={form.superficie_m2} onChange={set('superficie_m2')} /></div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><label className="label">Dorm.</label><input className="input" type="number" value={form.dormitorios} onChange={set('dormitorios')} /></div>
            <div><label className="label">Baños</label><input className="input" type="number" value={form.banos} onChange={set('banos')} /></div>
            <div><label className="label">Antigüedad</label><input className="input" type="number" value={form.antiguedad_anios} onChange={set('antiguedad_anios')} /></div>
          </div>
          <div><label className="label">Estado</label><select className="input" value={form.estado_conservacion} onChange={set('estado_conservacion')}>
            <option value="nuevo">Nuevo</option><option value="bueno">Bueno</option><option value="a_refaccionar">A refaccionar</option></select></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <button className="btn-primary w-full" disabled={loading}>{loading ? 'Calculando…' : 'Tasar'}</button>
        </form>

        {res && (
          <div className="mt-5 pt-5 border-t border-border">
            {res.confianza === 'sin_datos' ? (
              <p className="text-[13px] text-muted text-center">No hay comparables suficientes en el catálogo para tasar este inmueble.</p>
            ) : (
              <>
                <p className="stat-label">Valor estimado</p>
                <p className="stat-value text-3xl mt-1">{fmtUSD(res.valor_medio_usd)}</p>
                <p className="text-[12px] text-muted">Rango {fmtUSD(res.valor_min_usd)} – {fmtUSD(res.valor_max_usd)}</p>
                <div className="flex gap-2 mt-2">
                  <span className="chip-muted">{res.valor_m2_usado} USD/m²</span>
                  <span className="chip-muted capitalize">confianza {res.confianza}</span>
                  <span className="chip-muted capitalize">{res.metodo}</span>
                </div>
                {comps.length > 0 && (
                  <p className="text-[11px] text-muted mt-3">Basado en {comps.length} comparable{comps.length !== 1 ? 's' : ''} del catálogo.</p>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
