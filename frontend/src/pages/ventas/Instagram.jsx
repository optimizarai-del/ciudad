import { useEffect, useState } from 'react'
import {
  Instagram, Plus, Trash2, RefreshCw, ExternalLink, Search,
  Heart, MessageCircle, AlertTriangle, Loader2, Power,
} from 'lucide-react'
import Layout from '../../components/Layout/Layout'
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
  const [corriendo, setCorriendo] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [toast, setToast] = useState(null)   // {kind, text}
  const [usandoMock, setUsandoMock] = useState(false)

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
      const { data } = await api.get(`/api/ventas-instagram/publicaciones?${params}`)
      setPubs(data.publicaciones || [])
      setTotalPubs(data.total || 0)
    } finally { setCargando(false) }
  }

  useEffect(() => { cargarCuentas() }, [])
  useEffect(() => { cargarPubs() }, [filtroCuenta, filtroOper])

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

  const correr = async (cuentaId) => {
    setCorriendo(true)
    try {
      const url = cuentaId
        ? `/api/ventas-instagram/cuentas/${cuentaId}/scrapear`
        : '/api/ventas-instagram/scrapear'
      const { data } = await api.post(url)
      setUsandoMock(!!data.usando_mock)
      aviso('success', `Listo: ${data.nuevas} publicaciones nuevas de ${data.cuentas} cuenta(s).${data.usando_mock ? ' (modo demo)' : ''}`)
      cargarCuentas(); cargarPubs()
    } catch (e) {
      aviso('error', e?.response?.data?.detail || 'Error al correr el scraper.')
    } finally { setCorriendo(false) }
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
        <div className="flex items-center justify-between mb-3">
          <p className="font-semibold text-[14px] tracking-tight">Publicaciones <span className="text-muted font-normal">({totalPubs})</span></p>
        </div>

        {/* Filtros */}
        <div className="card p-3 mb-4 grid grid-cols-1 sm:grid-cols-3 gap-2 items-end">
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
            <label className="label">Buscar</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input className="input !pl-8" placeholder="texto o autor…"
                value={busqueda}
                onChange={e => setBusqueda(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && cargarPubs()} />
            </div>
          </div>
        </div>

        {cargando ? (
          <div className="card text-center py-20 text-muted text-[14px]">Cargando publicaciones…</div>
        ) : pubs.length === 0 ? (
          <div className="card text-center py-20">
            <Instagram size={34} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">No hay publicaciones todavía. Agregá cuentas y tocá «Correr todas».</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {pubs.map(p => (
              <div key={p.id} className="card overflow-hidden flex flex-col">
                {p.imagen_url && (
                  <div className="relative aspect-square bg-neutral-100 dark:bg-[#141414] overflow-hidden">
                    <img src={p.imagen_url} alt="" loading="lazy" className="w-full h-full object-cover"
                      onError={e => { e.currentTarget.style.display = 'none' }} />
                    {p.operacion && (
                      <span className="absolute top-2 left-2 chip-success capitalize text-[11px]">{p.operacion}</span>
                    )}
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
                  <div className="flex items-center gap-3 text-[11px] text-muted mt-auto pt-1">
                    <span className="flex items-center gap-1"><Heart size={11} /> {p.likes}</span>
                    <span className="flex items-center gap-1"><MessageCircle size={11} /> {p.comentarios}</span>
                    {p.url && (
                      <a href={p.url} target="_blank" rel="noopener noreferrer"
                        className="ml-auto flex items-center gap-1 hover:text-primary dark:hover:text-white transition">
                        <ExternalLink size={11} /> Ver post
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-2xl shadow-lift animate-fade-in text-[13px] text-white max-w-md
          ${toast.kind === 'success' ? 'bg-success' : 'bg-danger'}`}>
          {toast.text}
        </div>
      )}
    </Layout>
  )
}
