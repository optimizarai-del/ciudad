import { useEffect, useState } from 'react'
import {
  Instagram, Plus, Trash2, RefreshCw, ExternalLink, Search,
  Heart, MessageCircle, AlertTriangle, Loader2, Power,
  Filter, StickyNote, X, Bookmark, BedDouble, Ruler,
} from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import AsociarCliente from '../../components/ventas/AsociarCliente'
import api from '../../utils/api'

const ORO = '#B8893A'
const OPERACIONES = [['', 'Todas'], ['venta', 'Venta'], ['alquiler', 'Alquiler'], ['venta/alquiler', 'Ambas']]

const fechaCorta = iso => {
  if (!iso) return ''
  try { return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'short' }) }
  catch { return '' }
}

export default function RadarInstagram() {
  const [cuentas, setCuentas] = useState([])
  const [pubs, setPubs] = useState([])
  const [totalPubs, setTotalPubs] = useState(0)
  const [nuevoUser, setNuevoUser] = useState('')
  const [filtroCuenta, setFiltroCuenta] = useState('')
  const [filtroOper, setFiltroOper] = useState('')
  const [busqueda, setBusqueda] = useState('')
  // Filtros de listado adicionales (zona / dormitorios / m²) + ver guardadas
  const [filtroZona, setFiltroZona] = useState('')
  const [filtroDorm, setFiltroDorm] = useState('')
  const [filtroM2, setFiltroM2] = useState('')
  const [verGuardadas, setVerGuardadas] = useState(false)
  const [corriendo, setCorriendo] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [toast, setToast] = useState(null)   // {kind, text}
  const [usandoMock, setUsandoMock] = useState(false)
  // Filtros de búsqueda del scraping (se aplican antes de guardar).
  // Por defecto SOLO VENTA (el radar es para prospectar propiedades en venta).
  const [scrOper, setScrOper] = useState('venta')
  const [scrQ, setScrQ] = useState('')
  const [scrZona, setScrZona] = useState('')
  const [scrDorm, setScrDorm] = useState('')
  const [scrM2, setScrM2] = useState('')
  const [scrLimite, setScrLimite] = useState(12)
  // Ficha de una publicación
  const [ficha, setFicha] = useState(null)
  const [notasEdit, setNotasEdit] = useState('')
  const [guardando, setGuardando] = useState(false)

  const abrirFicha = (p) => { setFicha(p); setNotasEdit(p.notas || '') }

  const aviso = (kind, text) => setToast({ kind, text })
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 4500); return () => clearTimeout(t) }, [toast])

  const cargarCuentas = async () => {
    try { const { data } = await api.get('/api/ventas-instagram/cuentas'); setCuentas(data) }
    catch { /* noop */ }
  }
  const cargarPubs = async () => {
    setCargando(true)
    try {
      const params = new URLSearchParams()
      if (filtroCuenta) params.set('cuenta_id', filtroCuenta)
      if (filtroOper) params.set('operacion', filtroOper)
      if (busqueda.trim()) params.set('q', busqueda.trim())
      if (filtroZona.trim()) params.set('zona', filtroZona.trim())
      if (filtroDorm) params.set('dorm_min', filtroDorm)
      if (filtroM2) params.set('m2_min', filtroM2)
      if (verGuardadas) params.set('guardada', 'true')
      const { data } = await api.get(`/api/ventas-instagram/publicaciones?${params}`)
      setPubs(data.publicaciones || [])
      setTotalPubs(data.total || 0)
    } finally { setCargando(false) }
  }

  useEffect(() => { cargarCuentas() }, [])
  useEffect(() => { cargarPubs() }, [filtroCuenta, filtroOper, verGuardadas])

  const agregar = async () => {
    const u = nuevoUser.trim().replace(/^@/, '').toLowerCase()
    if (!u) return
    try {
      await api.post('/api/ventas-instagram/cuentas', { username: u })
      setNuevoUser('')
      cargarCuentas()
      aviso('success', `@${u} agregada al radar.`)
    } catch (e) {
      aviso('error', e?.response?.data?.detail || 'No se pudo agregar la cuenta.')
    }
  }

  const toggleActiva = async (c) => {
    try { await api.patch(`/api/ventas-instagram/cuentas/${c.id}`, { activa: !c.activa }); cargarCuentas() }
    catch (e) { aviso('error', e?.response?.data?.detail || 'No se pudo actualizar.') }
  }

  const borrar = async (c) => {
    try {
      await api.delete(`/api/ventas-instagram/cuentas/${c.id}`)
      cargarCuentas(); cargarPubs()
      aviso('success', `@${c.username} eliminada.`)
    } catch (e) { aviso('error', e?.response?.data?.detail || 'No se pudo eliminar.') }
  }

  // Filtros que se aplican AL TRAER (solo se guardan los posts que matchean).
  const correr = async (cuentaId) => {
    setCorriendo(true)
    try {
      const params = new URLSearchParams()
      if (scrOper) params.set('operacion', scrOper)
      if (scrQ.trim()) params.set('q', scrQ.trim())
      if (scrZona.trim()) params.set('zona', scrZona.trim())
      if (scrDorm) params.set('dorm_min', scrDorm)
      if (scrM2) params.set('m2_min', scrM2)
      if (scrLimite) params.set('limite', scrLimite)
      const base = cuentaId
        ? `/api/ventas-instagram/cuentas/${cuentaId}/scrapear`
        : '/api/ventas-instagram/scrapear'
      const { data } = await api.post(`${base}?${params}`)
      setUsandoMock(!!data.usando_mock)
      const desc = data.descartados_por_filtro
        ? ` · ${data.descartados_por_filtro} descartadas por el filtro`
        : ''
      aviso('success', `Listo: ${data.nuevas} publicaciones nuevas de ${data.cuentas} cuenta(s)${desc}.${data.usando_mock ? ' (modo demo)' : ''}`)
      cargarCuentas(); cargarPubs()
    } catch (e) {
      aviso('error', e?.response?.data?.detail || 'Error al correr el scraper.')
    } finally { setCorriendo(false) }
  }

  const toggleGuardar = async (p, ev) => {
    if (ev) ev.stopPropagation()
    try {
      const { data } = await api.patch(`/api/ventas-instagram/publicaciones/${p.id}`, { guardada: !p.guardada })
      // Si estamos viendo SOLO guardadas y la acabo de quitar, la saco de la lista.
      if (verGuardadas && !data.guardada) setPubs(ps => ps.filter(x => x.id !== p.id))
      else setPubs(ps => ps.map(x => (x.id === data.id ? data : x)))
      if (ficha && ficha.id === data.id) setFicha(data)
    } catch (e) {
      aviso('error', e?.response?.data?.detail || 'No se pudo actualizar guardadas.')
    }
  }

  const guardarNotas = async () => {
    if (!ficha) return
    setGuardando(true)
    try {
      const { data } = await api.patch(`/api/ventas-instagram/publicaciones/${ficha.id}`, { notas: notasEdit })
      setPubs(ps => ps.map(p => (p.id === data.id ? data : p)))
      setFicha(data)
      aviso('success', 'Notas guardadas.')
    } catch (e) {
      aviso('error', e?.response?.data?.detail || 'No se pudieron guardar las notas.')
    } finally { setGuardando(false) }
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Ventas · Prospección</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2 flex items-center gap-2">
                <Instagram style={{ color: ORO }} size={28} /> Radar Instagram
              </h1>
              <p className="hero-sub">Seguí cuentas que publican propiedades y traé sus publicaciones para analizar.</p>
            </div>
            <button className="btn-primary shrink-0" disabled={corriendo || cuentas.length === 0} onClick={() => correr()}>
              {corriendo ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              Correr todas
            </button>
          </div>
        </header>

        {usandoMock && (
          <div className="card p-3 mb-4 border-[#B8893A]/40 flex items-center gap-2 text-[12px] text-muted">
            <AlertTriangle size={14} style={{ color: ORO }} />
            Modo demo: sin <code className="mx-1">APIFY_TOKEN</code> se traen publicaciones de ejemplo. Cargá el token en las variables de entorno para scrapear de verdad.
          </div>
        )}

        {/* Filtros de la búsqueda — se aplican AL TRAER */}
        <div className="card p-4 mb-5 border-[#B8893A]/30">
          <div className="flex items-center gap-2 mb-3">
            <Filter size={14} style={{ color: ORO }} />
            <p className="font-semibold text-[13px] tracking-tight">Qué traer</p>
            <span className="text-[11px] text-muted">— se aplica al correr el scraper: solo se guardan las publicaciones que matcheen</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            <div>
              <label className="label">Operación</label>
              <select className="input" value={scrOper} onChange={e => setScrOper(e.target.value)}>
                <option value="venta">Solo Venta</option>
                <option value="alquiler">Solo Alquiler</option>
                <option value="">Todas</option>
              </select>
            </div>
            <div>
              <label className="label">Zona</label>
              <input className="input" placeholder="ej: Toay"
                value={scrZona} onChange={e => setScrZona(e.target.value)} />
            </div>
            <div>
              <label className="label">Dorm. mín</label>
              <input className="input" type="number" min="0" placeholder="—"
                value={scrDorm} onChange={e => setScrDorm(e.target.value)} />
            </div>
            <div>
              <label className="label">m² mín</label>
              <input className="input" type="number" min="0" placeholder="—"
                value={scrM2} onChange={e => setScrM2(e.target.value)} />
            </div>
            <div>
              <label className="label">Palabra clave</label>
              <input className="input" placeholder="ej: USD, pileta…"
                value={scrQ} onChange={e => setScrQ(e.target.value)} />
            </div>
            <div>
              <label className="label">Posts por cuenta</label>
              <input className="input" type="number" min="1" max="50"
                value={scrLimite}
                onChange={e => setScrLimite(Math.max(1, Math.min(50, Number(e.target.value) || 12)))} />
            </div>
          </div>
          <p className="text-[11px] text-muted mt-2">
            La operación, dormitorios y m² se leen de la descripción de cada
            publicación. Si un post no declara el dato, no pasa el filtro.
          </p>
        </div>

        {/* Cuentas seguidas */}
        <div className="card p-5 mb-5">
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold text-[14px] tracking-tight">Cuentas seguidas</p>
            <span className="chip-muted">{cuentas.length}</span>
          </div>

          <div className="flex gap-2 mb-4 max-w-md">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted">@</span>
              <input className="input !pl-7" placeholder="usuario_de_instagram"
                value={nuevoUser}
                onChange={e => setNuevoUser(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && agregar()} />
            </div>
            <button className="btn-primary !py-2 text-[13px] shrink-0" onClick={agregar}>
              <Plus size={14} /> Agregar
            </button>
          </div>

          {cuentas.length === 0 ? (
            <p className="text-muted text-[13px]">Todavía no seguís ninguna cuenta. Agregá el usuario de una inmobiliaria o vendedor.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {cuentas.map(c => (
                <div key={c.id} className={`rounded-xl border p-3 flex items-center gap-3 ${c.activa ? 'border-border dark:border-[#2A2A2A]' : 'border-dashed border-muted/30 opacity-60'}`}>
                  <div className="w-9 h-9 rounded-full grid place-items-center shrink-0"
                    style={{ background: `${ORO}22`, color: ORO }}>
                    <Instagram size={16} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-[13px] truncate">@{c.username}</p>
                    <p className="text-[11px] text-muted truncate">
                      {c.ultima_corrida
                        ? `${fechaCorta(c.ultima_corrida)} · ${c.ultimo_estado === 'ok' ? `${c.ultimo_nuevas} nuevas` : (c.ultimo_estado || '')}`
                        : 'sin correr aún'}
                    </p>
                  </div>
                  <button onClick={() => toggleActiva(c)} title={c.activa ? 'Pausar' : 'Activar'}
                    className={`p-1.5 rounded-lg transition ${c.activa ? 'text-success' : 'text-muted'} hover:bg-neutral-100 dark:hover:bg-[#1E1E1E]`}>
                    <Power size={13} />
                  </button>
                  <button onClick={() => correr(c.id)} disabled={corriendo} title="Scrapear ahora"
                    className="p-1.5 rounded-lg text-muted hover:text-primary dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-[#1E1E1E] transition">
                    <RefreshCw size={13} />
                  </button>
                  <button onClick={() => borrar(c)} title="Eliminar"
                    className="p-1.5 rounded-lg text-muted hover:text-danger hover:bg-danger/10 transition">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Publicaciones */}
        <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
          <p className="font-semibold text-[14px] tracking-tight">Publicaciones <span className="text-muted font-normal">({totalPubs})</span></p>
          <div className="flex rounded-xl border border-border overflow-hidden text-[12px]">
            <button onClick={() => setVerGuardadas(false)}
              className={`px-3 py-1.5 transition ${!verGuardadas ? 'bg-[#B8893A] text-white' : 'text-muted hover:text-[#B8893A]'}`}>
              Todas
            </button>
            <button onClick={() => setVerGuardadas(true)}
              className={`px-3 py-1.5 flex items-center gap-1 transition ${verGuardadas ? 'bg-[#B8893A] text-white' : 'text-muted hover:text-[#B8893A]'}`}>
              <Bookmark size={12} /> Guardadas
            </button>
          </div>
        </div>

        {/* Filtros del listado */}
        <div className="card p-3 mb-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 items-end">
          <div>
            <label className="label">Cuenta</label>
            <select className="input" value={filtroCuenta} onChange={e => setFiltroCuenta(e.target.value)}>
              <option value="">Todas</option>
              {cuentas.map(c => <option key={c.id} value={c.id}>@{c.username}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Operación</label>
            <select className="input" value={filtroOper} onChange={e => setFiltroOper(e.target.value)}>
              {OPERACIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Zona</label>
            <input className="input" placeholder="ej: Toay"
              value={filtroZona} onChange={e => setFiltroZona(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && cargarPubs()} />
          </div>
          <div>
            <label className="label">Dorm. mín</label>
            <input className="input" type="number" min="0" placeholder="—"
              value={filtroDorm} onChange={e => setFiltroDorm(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && cargarPubs()} />
          </div>
          <div>
            <label className="label">m² mín</label>
            <input className="input" type="number" min="0" placeholder="—"
              value={filtroM2} onChange={e => setFiltroM2(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && cargarPubs()} />
          </div>
          <div>
            <label className="label">Buscar</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input className="input !pl-8" placeholder="texto o autor…"
                value={busqueda}
                onChange={e => setBusqueda(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && cargarPubs()} />
            </div>
          </div>
          <button className="btn-secondary !py-2 text-[13px] col-span-2 sm:col-span-1" onClick={cargarPubs} disabled={cargando}>
            <Filter size={13} /> Aplicar filtros
          </button>
        </div>

        {cargando ? (
          <div className="card text-center py-20 text-muted text-[14px]">Cargando publicaciones…</div>
        ) : pubs.length === 0 ? (
          <div className="card text-center py-20">
            <Instagram size={34} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">
              {verGuardadas
                ? 'No guardaste ninguna publicación todavía. Tocá el marcador en una publicación para guardarla acá.'
                : 'No hay publicaciones todavía. Agregá cuentas y tocá «Correr todas».'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {pubs.map(p => (
              <div key={p.id} onClick={() => abrirFicha(p)} title="Ver ficha"
                className="card overflow-hidden flex flex-col cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-lift">
                {p.imagen_url && (
                  <div className="relative aspect-square bg-neutral-100 dark:bg-[#141414] overflow-hidden">
                    <img src={p.imagen_url} alt="" loading="lazy" className="w-full h-full object-cover"
                      onError={e => { e.currentTarget.style.display = 'none' }} />
                    {p.operacion && (
                      <span className="absolute top-2 left-2 chip-success capitalize text-[11px]">{p.operacion}</span>
                    )}
                    <button onClick={e => toggleGuardar(p, e)} title={p.guardada ? 'Quitar de guardadas' : 'Guardar'}
                      className={`absolute top-2 right-2 grid place-items-center w-7 h-7 rounded-full backdrop-blur transition ${
                        p.guardada ? 'bg-[#B8893A] text-white' : 'bg-black/35 text-white hover:bg-[#B8893A]'}`}>
                      <Bookmark size={13} fill={p.guardada ? 'currentColor' : 'none'} />
                    </button>
                    {p.precio_texto && (
                      <span className="absolute bottom-2 left-2 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-black/70 text-white">{p.precio_texto}</span>
                    )}
                  </div>
                )}
                <div className="p-3 flex flex-col gap-2 flex-1">
                  <div className="flex items-center gap-2">
                    {p.autor_foto
                      ? <img src={p.autor_foto} alt="" className="w-6 h-6 rounded-full object-cover" onError={e => { e.currentTarget.style.display = 'none' }} />
                      : <span className="w-6 h-6 rounded-full grid place-items-center text-[10px]" style={{ background: `${ORO}22`, color: ORO }}><Instagram size={11} /></span>}
                    <div className="min-w-0">
                      <p className="text-[12px] font-medium truncate">@{p.autor_username}</p>
                      {p.autor_nombre && <p className="text-[10px] text-muted truncate leading-none">{p.autor_nombre}</p>}
                    </div>
                    <span className="text-[10px] text-muted ml-auto shrink-0">{fechaCorta(p.fecha_post)}</span>
                  </div>
                  <p className="text-[12px] text-muted line-clamp-3 whitespace-pre-wrap">{p.caption}</p>
                  {(p.dormitorios || p.superficie_m2) && (
                    <div className="flex flex-wrap gap-1.5">
                      {p.dormitorios ? <span className="chip-muted text-[10px] flex items-center gap-1"><BedDouble size={10} /> {p.dormitorios} dorm</span> : null}
                      {p.superficie_m2 ? <span className="chip-muted text-[10px] flex items-center gap-1"><Ruler size={10} /> {Math.round(p.superficie_m2)} m²</span> : null}
                    </div>
                  )}
                  <div className="flex items-center gap-3 text-[11px] text-muted mt-auto pt-1">
                    <span className="flex items-center gap-1"><Heart size={11} /> {p.likes}</span>
                    <span className="flex items-center gap-1"><MessageCircle size={11} /> {p.comentarios}</span>
                    {p.notas && <span title="Tiene notas"><StickyNote size={11} style={{ color: ORO }} /></span>}
                    <span className="ml-auto flex items-center gap-2">
                      <AsociarCliente
                        propiedad={{
                          fuente: 'instagram', ref_externa: String(p.id),
                          titulo: (p.caption || '').slice(0, 60), precio_texto: p.precio_texto,
                          operacion: p.operacion || null, imagen_url: p.imagen_url, link_externo: p.url,
                        }}
                        className="flex items-center gap-1 hover:text-[#B8893A] transition" label="Asociar" />
                      {p.url && (
                        <a href={p.url} target="_blank" rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()}
                          className="flex items-center gap-1 hover:text-primary dark:hover:text-white transition">
                          <ExternalLink size={11} /> Ver post
                        </a>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ficha de la publicación */}
      {ficha && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
          onClick={() => setFicha(null)}>
          <div className="card w-full max-w-3xl shadow-lift animate-scale-in my-6 overflow-hidden"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between p-4 pb-3 border-b border-border dark:border-[#2A2A2A]">
              <div className="flex items-center gap-2 min-w-0">
                {ficha.autor_foto
                  ? <img src={ficha.autor_foto} alt="" className="w-9 h-9 rounded-full object-cover" onError={e => { e.currentTarget.style.display = 'none' }} />
                  : <span className="w-9 h-9 rounded-full grid place-items-center" style={{ background: `${ORO}22`, color: ORO }}><Instagram size={15} /></span>}
                <div className="min-w-0">
                  <p className="font-semibold text-[14px] truncate">@{ficha.autor_username}</p>
                  <p className="text-[11px] text-muted truncate">{ficha.autor_nombre || '—'}</p>
                </div>
              </div>
              <button onClick={() => setFicha(null)} className="btn-ghost p-2 shrink-0"><X size={16} /></button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-0">
              {ficha.imagen_url && (
                <div className="bg-neutral-100 dark:bg-[#141414] aspect-square">
                  <img src={ficha.imagen_url} alt="" className="w-full h-full object-cover"
                    onError={e => { e.currentTarget.style.display = 'none' }} />
                </div>
              )}
              <div className="p-4 flex flex-col gap-3 min-w-0">
                <div className="flex flex-wrap gap-1.5 items-center">
                  {ficha.operacion && <span className="chip-success capitalize">{ficha.operacion}</span>}
                  {ficha.precio_texto && <span className="chip-dark">{ficha.precio_texto}</span>}
                  {ficha.dormitorios ? <span className="chip-muted flex items-center gap-1"><BedDouble size={11} /> {ficha.dormitorios} dorm</span> : null}
                  {ficha.superficie_m2 ? <span className="chip-muted flex items-center gap-1"><Ruler size={11} /> {Math.round(ficha.superficie_m2)} m²</span> : null}
                  <button onClick={() => toggleGuardar(ficha)} title={ficha.guardada ? 'Quitar de guardadas' : 'Guardar'}
                    className={`ml-auto flex items-center gap-1 text-[12px] px-2.5 py-1 rounded-full border transition ${
                      ficha.guardada ? 'bg-[#B8893A] text-white border-[#B8893A]' : 'border-border text-muted hover:border-[#B8893A]'}`}>
                    <Bookmark size={12} fill={ficha.guardada ? 'currentColor' : 'none'} /> {ficha.guardada ? 'Guardada' : 'Guardar'}
                  </button>
                </div>

                <div className="text-[12px] text-muted flex flex-wrap gap-x-4 gap-y-1">
                  <span className="flex items-center gap-1"><Heart size={11} /> {ficha.likes}</span>
                  <span className="flex items-center gap-1"><MessageCircle size={11} /> {ficha.comentarios}</span>
                  <span>Publicado: {fechaCorta(ficha.fecha_post) || '—'}</span>
                </div>

                <div className="min-w-0">
                  <p className="label mb-1">Texto de la publicación</p>
                  <p className="text-[12.5px] whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto">
                    {ficha.caption || '— sin texto —'}
                  </p>
                </div>

                <div>
                  <label className="label">Notas del equipo</label>
                  <textarea rows={4} className="input resize-none"
                    placeholder="Ej: llamé al vendedor, pide USD 120k, coordinar visita…"
                    value={notasEdit} onChange={e => setNotasEdit(e.target.value)} />
                </div>

                <div className="flex gap-2 mt-auto">
                  {ficha.url && (
                    <a href={ficha.url} target="_blank" rel="noopener noreferrer" className="btn-secondary flex-1 text-center">
                      <ExternalLink size={14} /> Ver en Instagram
                    </a>
                  )}
                  <button className="btn-primary flex-1" onClick={guardarNotas} disabled={guardando}>
                    {guardando ? 'Guardando…' : 'Guardar notas'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-2xl shadow-lift animate-fade-in text-[13px] text-white max-w-md
          ${toast.kind === 'success' ? 'bg-success' : 'bg-danger'}`}>
          {toast.text}
        </div>
      )}
    </Layout>
  )
}
