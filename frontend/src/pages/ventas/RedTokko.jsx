import { useEffect, useState } from 'react'
import { Globe, Download, Check, MapPin, Building2, RefreshCw, ExternalLink } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const OPERACIONES = [['', 'Todas'], ['venta', 'Venta'], ['alquiler', 'Alquiler']]

export default function RedTokko() {
  const [filtros, setFiltros] = useState({ zona: '', operacion: 'venta', precio_min: '', precio_max: '', dorm_min: '' })
  const [props, setProps] = useState([])
  const [nota, setNota] = useState('')
  const [loading, setLoading] = useState(false)
  const [sel, setSel] = useState(new Set())
  const [importando, setImportando] = useState(false)
  const [msg, setMsg] = useState('')

  const buscar = async () => {
    setLoading(true); setMsg(''); setSel(new Set())
    try {
      const qs = new URLSearchParams()
      Object.entries(filtros).forEach(([k, v]) => { if (v) qs.set(k, v) })
      qs.set('limit', '60')
      const { data } = await api.get(`/api/ventas-crm/red-tokko?${qs}`)
      setProps(data.propiedades || [])
      setNota(data.nota || '')
    } catch (e) {
      setNota('No se pudo consultar la red. Verificá que haya datos cargados.')
      setProps([])
    } finally { setLoading(false) }
  }
  useEffect(() => { buscar() }, [])  // carga inicial

  const toggle = (ref) => setSel(s => {
    const n = new Set(s); n.has(ref) ? n.delete(ref) : n.add(ref); return n
  })
  const importables = props.filter(p => !p.ya_importada)
  const todosSel = importables.length > 0 && importables.every(p => sel.has(p.referencia))
  const toggleTodos = () => setSel(todosSel ? new Set() : new Set(importables.map(p => p.referencia)))

  const importar = async (refs) => {
    if (!refs.length) return
    setImportando(true); setMsg('')
    try {
      const { data } = await api.post('/api/ventas-crm/red-tokko/importar', { referencias: refs })
      setMsg(`✓ Importadas ${data.creadas} · ya existían ${data.saltadas_ya_existentes}`)
      setSel(new Set())
      buscar()
    } catch (e) {
      setMsg('Error al importar.')
    } finally { setImportando(false) }
  }

  const set = k => e => setFiltros(f => ({ ...f, [k]: e.target.value }))

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-5">
          <div className="hero-eyebrow">Catálogo externo</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2 flex items-center gap-2">
                <Globe className="text-[#B8893A]" size={30} /> Red Tokko
              </h1>
              <p className="hero-sub">Propiedades de la red de colegas. Importá las que te sirvan a tu catálogo.</p>
            </div>
            {sel.size > 0 && (
              <button className="btn-primary" disabled={importando} onClick={() => importar([...sel])}>
                <Download size={15} /> Importar {sel.size} seleccionada{sel.size > 1 ? 's' : ''}
              </button>
            )}
          </div>
        </header>

        {/* Filtros */}
        <div className="card p-3 mb-4 grid grid-cols-2 sm:grid-cols-6 gap-2 items-end">
          <div className="col-span-2 sm:col-span-1">
            <label className="label">Zona</label>
            <input className="input !py-2 text-[13px]" placeholder="Santa Rosa…" value={filtros.zona} onChange={set('zona')} />
          </div>
          <div>
            <label className="label">Operación</label>
            <select className="input !py-2 text-[13px]" value={filtros.operacion} onChange={set('operacion')}>
              {OPERACIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div><label className="label">USD mín</label><input className="input !py-2 text-[13px]" type="number" value={filtros.precio_min} onChange={set('precio_min')} /></div>
          <div><label className="label">USD máx</label><input className="input !py-2 text-[13px]" type="number" value={filtros.precio_max} onChange={set('precio_max')} /></div>
          <div><label className="label">Dorm. mín</label><input className="input !py-2 text-[13px]" type="number" value={filtros.dorm_min} onChange={set('dorm_min')} /></div>
          <button className="btn-secondary !py-2 text-[13px]" onClick={buscar} disabled={loading}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Buscar
          </button>
        </div>

        {msg && <div className="mb-3 px-4 py-2 rounded-xl bg-[#B8893A]/10 border border-[#B8893A]/30 text-[13px] text-[#B8893A]">{msg}</div>}

        {props.length > 0 && (
          <div className="flex items-center justify-between mb-2 px-1">
            <p className="text-[12px] text-muted">{props.length} propiedades · {importables.length} importables</p>
            {importables.length > 0 && (
              <button className="text-[12px] text-[#B8893A] hover:underline" onClick={toggleTodos}>
                {todosSel ? 'Deseleccionar todo' : 'Seleccionar todas las importables'}
              </button>
            )}
          </div>
        )}

        {loading ? (
          <div className="card text-center py-20 text-muted text-[14px]">Consultando la red…</div>
        ) : props.length === 0 ? (
          <div className="card text-center py-20">
            <Building2 size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">{nota || 'Sin resultados. Ajustá los filtros.'}</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {props.map(p => {
              const elegida = sel.has(p.referencia)
              return (
                <div key={p.referencia}
                  className={`card p-0 overflow-hidden flex flex-col transition ${elegida ? 'ring-2 ring-[#B8893A]' : ''}`}>
                  <div className="aspect-[16/10] bg-neutral-100 dark:bg-[#141414] relative">
                    {p.foto
                      ? <img src={p.foto} alt="" className="w-full h-full object-cover" loading="lazy" />
                      : <div className="grid place-items-center h-full"><Building2 size={28} className="text-muted/30" /></div>}
                    {p.ya_importada && (
                      <span className="absolute top-2 right-2 chip-success flex items-center gap-1 text-[11px]"><Check size={11} /> Importada</span>
                    )}
                  </div>
                  <div className="p-3 flex-1 flex flex-col">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-[13px] truncate">{p.direccion || '—'}</p>
                      <span className="chip-muted capitalize text-[11px] shrink-0">{p.tipo}</span>
                    </div>
                    <p className="text-[11px] text-muted flex items-center gap-1 mt-0.5"><MapPin size={10} />{p.ubicacion || '—'}</p>
                    <p className="stat-value text-lg mt-1.5">{p.precio_display || '—'}</p>
                    <div className="flex flex-wrap gap-x-3 text-[11px] text-muted mt-1">
                      {p.m2_cubierta_num ? <span>{p.m2_cubierta_num} m²</span> : null}
                      {p.dormitorios_num ? <span>{p.dormitorios_num} dorm</span> : null}
                      {p.banos_num ? <span>{p.banos_num} baños</span> : null}
                    </div>
                    {p.publicado_por && <p className="text-[11px] text-muted mt-1 truncate">por {p.publicado_por}</p>}
                    {p.detalles && <p className="text-[11px] text-muted mt-1 line-clamp-2">{p.detalles}</p>}

                    <div className="flex gap-1.5 mt-3 pt-2.5 border-t border-border">
                      {p.ficha_url && (
                        <a href={p.ficha_url} target="_blank" rel="noreferrer"
                          className="btn-ghost !p-1.5" title="Ver ficha"><ExternalLink size={14} /></a>
                      )}
                      {p.ya_importada ? (
                        <button disabled className="btn-secondary flex-1 text-[12px] opacity-60">Ya en catálogo</button>
                      ) : (
                        <>
                          <button onClick={() => toggle(p.referencia)}
                            className={`flex-1 text-[12px] rounded-xl py-1.5 border transition ${
                              elegida ? 'bg-[#B8893A] text-white border-[#B8893A]' : 'border-border text-muted hover:border-[#B8893A]'}`}>
                            {elegida ? 'Seleccionada' : 'Seleccionar'}
                          </button>
                          <button onClick={() => importar([p.referencia])} disabled={importando}
                            className="btn-primary !px-3 text-[12px]" title="Importar ahora"><Download size={13} /></button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Layout>
  )
}
