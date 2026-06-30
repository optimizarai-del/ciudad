import { useEffect, useState } from 'react'
import { Network, Download, Check, MapPin, Building2, RefreshCw, ExternalLink, Play, Settings2 } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import { useRole } from '../../context/RoleContext'
import api from '../../utils/api'

const OPERACIONES = [['venta', 'Venta'], ['alquiler', 'Alquiler']]

export default function Webs() {
  const { isAdmin, role } = useRole()
  const esAdmin = isAdmin || role === 'ventas_admin' || role === 'gerencia'

  const [filtros, setFiltros] = useState({ fuente: '', zona: '', operacion: 'venta', precio_min: '', precio_max: '', dorm_min: '' })
  const [props, setProps] = useState([])
  const [fuentes, setFuentes] = useState([])
  const [nota, setNota] = useState('')
  const [loading, setLoading] = useState(false)
  const [sel, setSel] = useState(new Set())
  const [importando, setImportando] = useState(false)
  const [msg, setMsg] = useState('')

  // Panel admin
  const [showAdmin, setShowAdmin] = useState(false)
  const [config, setConfig] = useState([])
  const [jobs, setJobs] = useState([])
  const [sync, setSync] = useState({ fuente: 'argenprop', ciudad: 'santa-rosa-la-pampa', operacion: 'venta', max_paginas: 5 })
  const [syncing, setSyncing] = useState(false)

  const cargarFuentes = async () => {
    try { const { data } = await api.get('/api/ventas-scraping/fuentes'); setFuentes(data.fuentes || []) } catch {}
  }

  const buscar = async () => {
    setLoading(true); setMsg(''); setSel(new Set())
    try {
      const qs = new URLSearchParams()
      Object.entries(filtros).forEach(([k, v]) => { if (v) qs.set(k, v) })
      qs.set('limit', '60')
      const { data } = await api.get(`/api/ventas-scraping/propiedades?${qs}`)
      setProps(data.propiedades || [])
      setNota(data.propiedades?.length ? '' : 'Sin resultados. Corré un sync desde el panel de admin o ajustá los filtros.')
    } catch (e) {
      setNota('No se pudo consultar. Verificá que el backend esté arriba.')
      setProps([])
    } finally { setLoading(false) }
  }

  const cargarAdmin = async () => {
    if (!esAdmin) return
    try {
      const [c, j] = await Promise.all([
        api.get('/api/ventas-scraping/config'),
        api.get('/api/ventas-scraping/jobs'),
      ])
      setConfig(c.data.config || [])
      setJobs(j.data.jobs || [])
    } catch {}
  }

  useEffect(() => { cargarFuentes(); buscar() }, [])  // carga inicial
  useEffect(() => { if (showAdmin) cargarAdmin() }, [showAdmin])

  const toggle = (ref) => setSel(s => { const n = new Set(s); n.has(ref) ? n.delete(ref) : n.add(ref); return n })
  const importables = props.filter(p => !p.ya_importada)
  const todosSel = importables.length > 0 && importables.every(p => sel.has(p.referencia))
  const toggleTodos = () => setSel(todosSel ? new Set() : new Set(importables.map(p => p.referencia)))

  const importar = async (refs) => {
    if (!refs.length) return
    setImportando(true); setMsg('')
    try {
      const { data } = await api.post('/api/ventas-scraping/importar', { referencias: refs })
      const mt = data.matches_generados ? ` · ${data.matches_generados} match${data.matches_generados > 1 ? 'es' : ''} nuevo${data.matches_generados > 1 ? 's' : ''}` : ''
      setMsg(`✓ Importadas ${data.creadas} · ya existían ${data.saltadas_ya_existentes}${mt} · ya están en el mapa`)
      setSel(new Set()); buscar()
    } catch { setMsg('Error al importar.') } finally { setImportando(false) }
  }

  const correrSync = async () => {
    setSyncing(true); setMsg('')
    try {
      const { data } = await api.post('/api/ventas-scraping/sync', sync)
      if (data.modo === 'cola') setMsg(`✓ Job encolado (#${data.job_id}). Mirá el estado abajo.`)
      else setMsg(`✓ Sync ${data.fuente}: ${data.nuevas} nuevas · ${data.actualizadas} act. · ${data.sin_cambio} sin cambio · ${data.bajas} bajas`)
      cargarAdmin(); buscar()
    } catch (e) {
      setMsg(e?.response?.data?.detail || 'Error al sincronizar.')
    } finally { setSyncing(false) }
  }

  const set = k => e => setFiltros(f => ({ ...f, [k]: e.target.value }))
  const setS = k => e => setSync(s => ({ ...s, [k]: e.target.value }))

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-5">
          <div className="hero-eyebrow">Catálogo externo · Fase 4</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2 flex items-center gap-2">
                <Network className="text-[#B8893A]" size={30} /> Webs inmobiliarias
              </h1>
              <p className="hero-sub">Propiedades scrapeadas de portales (Argenprop, Zonaprop). Importá las que te sirvan.</p>
            </div>
            <div className="flex gap-2">
              {esAdmin && (
                <button className="btn-secondary" onClick={() => setShowAdmin(v => !v)}>
                  <Settings2 size={15} /> {showAdmin ? 'Ocultar' : 'Admin'}
                </button>
              )}
              {sel.size > 0 && (
                <button className="btn-primary" disabled={importando} onClick={() => importar([...sel])}>
                  <Download size={15} /> Importar {sel.size}
                </button>
              )}
            </div>
          </div>
        </header>

        {/* Panel admin: sync + config + jobs */}
        {esAdmin && showAdmin && (
          <div className="card p-4 mb-4 space-y-4">
            <div>
              <p className="text-[13px] font-semibold mb-2">Sincronizar una fuente</p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 items-end">
                <div>
                  <label className="label">Fuente</label>
                  <select className="input !py-2 text-[13px]" value={sync.fuente} onChange={setS('fuente')}>
                    {fuentes.map(f => <option key={f.id} value={f.id}>{f.nombre}</option>)}
                  </select>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <label className="label">Ciudad (slug)</label>
                  <input className="input !py-2 text-[13px]" value={sync.ciudad} onChange={setS('ciudad')} placeholder="santa-rosa-la-pampa" />
                </div>
                <div>
                  <label className="label">Operación</label>
                  <select className="input !py-2 text-[13px]" value={sync.operacion} onChange={setS('operacion')}>
                    {OPERACIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Páginas</label>
                  <input className="input !py-2 text-[13px]" type="number" value={sync.max_paginas} onChange={setS('max_paginas')} />
                </div>
                <button className="btn-primary !py-2 text-[13px]" onClick={correrSync} disabled={syncing}>
                  <Play size={13} className={syncing ? 'animate-pulse' : ''} /> {syncing ? 'Corriendo…' : 'Sincronizar'}
                </button>
              </div>
              <p className="text-[11px] text-muted mt-1">
                Zonaprop usa Playwright (anti-bot). Si no hay Redis configurado, el sync corre al instante (modo dev).
              </p>
            </div>

            {jobs.length > 0 && (
              <div>
                <p className="text-[13px] font-semibold mb-2">Últimos jobs</p>
                <div className="space-y-1">
                  {jobs.slice(0, 6).map(j => (
                    <div key={j.id} className="flex items-center justify-between text-[12px] border-b border-border py-1">
                      <span className="text-muted">#{j.id} · {j.fuente} · {j.ciudad} · {j.operacion}</span>
                      <span className={`chip-muted ${j.estado === 'ok' ? 'chip-success' : j.estado === 'error' ? 'chip-danger' : ''}`}>
                        {j.estado}{j.resultado ? ` (${j.resultado.nuevas}n/${j.resultado.actualizadas}a)` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filtros */}
        <div className="card p-3 mb-4 grid grid-cols-2 sm:grid-cols-6 gap-2 items-end">
          <div>
            <label className="label">Fuente</label>
            <select className="input !py-2 text-[13px]" value={filtros.fuente} onChange={set('fuente')}>
              <option value="">Todas</option>
              {fuentes.map(f => <option key={f.id} value={f.id}>{f.nombre}</option>)}
            </select>
          </div>
          <div className="col-span-2 sm:col-span-1">
            <label className="label">Zona</label>
            <input className="input !py-2 text-[13px]" placeholder="Santa Rosa…" value={filtros.zona} onChange={set('zona')} />
          </div>
          <div>
            <label className="label">Operación</label>
            <select className="input !py-2 text-[13px]" value={filtros.operacion} onChange={set('operacion')}>
              <option value="">Todas</option>
              {OPERACIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div><label className="label">USD mín</label><input className="input !py-2 text-[13px]" type="number" value={filtros.precio_min} onChange={set('precio_min')} /></div>
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
          <div className="card text-center py-20 text-muted text-[14px]">Consultando…</div>
        ) : props.length === 0 ? (
          <div className="card text-center py-20">
            <Building2 size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">{nota || 'Sin resultados.'}</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {props.map(p => {
              const elegida = sel.has(p.referencia)
              return (
                <div key={`${p.fuente}-${p.referencia}`}
                  className={`card p-0 overflow-hidden flex flex-col transition ${elegida ? 'ring-2 ring-[#B8893A]' : ''}`}>
                  <div className="aspect-[16/10] bg-neutral-100 dark:bg-[#141414] relative">
                    {p.foto
                      ? <img src={p.foto} alt="" className="w-full h-full object-cover" loading="lazy" />
                      : <div className="grid place-items-center h-full"><Building2 size={28} className="text-muted/30" /></div>}
                    <span className="absolute top-2 left-2 chip-muted text-[10px] capitalize">{p.fuente}</span>
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
