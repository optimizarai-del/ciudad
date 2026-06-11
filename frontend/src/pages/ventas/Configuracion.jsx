import { useEffect, useState } from 'react'
import { Settings, Percent, MapPinned, Ruler, Plus, Trash2, Lock, Send, Store, CalendarClock, RefreshCw, Power } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const TIPOS = ['casa', 'departamento', 'lote', 'local', 'oficina', 'galpon', 'campo', 'otro']
const TABS = [
  { key: 'comisiones', label: 'Comisiones', icon: Percent },
  { key: 'barrios', label: 'Barrios', icon: MapPinned },
  { key: 'valorm2', label: 'Valor m²', icon: Ruler },
  { key: 'telegram', label: 'Telegram', icon: Send },
  { key: 'tokko', label: 'Tokko', icon: Store },
  { key: 'plantillas', label: 'Seguimiento', icon: CalendarClock },
]

export default function Configuracion() {
  const [tab, setTab] = useState('comisiones')
  const [me, setMe] = useState(null)
  useEffect(() => { api.get('/api/ventas-crm/me').then(r => setMe(r.data)) }, [])

  return (
    <Layout>
      <div className="max-w-4xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Módulo Ventas</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Configuración</h1>
          <p className="hero-sub">Comisiones, barrios de la ciudad y valores de referencia para tasaciones.</p>
        </header>

        {me && !me.es_admin && (
          <div className="card p-4 mb-4 flex items-center gap-3 text-[13px] text-muted">
            <Lock size={16} /> Solo el admin puede editar esta configuración. Estás en modo lectura.
          </div>
        )}

        <div className="flex gap-2 mb-6 border-b border-border">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-medium border-b-2 -mb-px transition ${
                tab === t.key ? 'border-[#B8893A] text-primary' : 'border-transparent text-muted hover:text-primary'
              }`}>
              <t.icon size={15} /> {t.label}
            </button>
          ))}
        </div>

        {tab === 'comisiones' && <Comisiones admin={me?.es_admin} />}
        {tab === 'barrios' && <Barrios admin={me?.es_admin} />}
        {tab === 'valorm2' && <ValorM2 admin={me?.es_admin} />}
        {tab === 'telegram' && <Telegram />}
        {tab === 'tokko' && <Tokko admin={me?.es_admin} />}
        {tab === 'plantillas' && <Plantillas admin={me?.es_admin} />}
      </div>
    </Layout>
  )
}

function Telegram() {
  const [estado, setEstado] = useState(null)
  const [link, setLink] = useState(null)
  const load = () => api.get('/api/ventas-crm/telegram/estado').then(r => setEstado(r.data))
  useEffect(() => { load() }, [])
  const generar = async () => {
    const r = await api.post('/api/ventas-crm/telegram/generar-token')
    setLink(r.data)
  }
  return (
    <div>
      <p className="text-[13px] text-muted mb-4">
        Vinculá tu Telegram para recibir las notificaciones (matches, tareas vencidas) por chat.
      </p>
      <div className="card p-5">
        <div className="flex items-center gap-3 mb-4">
          <span className={`w-2.5 h-2.5 rounded-full ${estado?.vinculado ? 'bg-emerald-500' : 'bg-gray-400'}`} />
          <p className="text-[14px] font-medium">{estado?.vinculado ? 'Telegram vinculado' : 'No vinculado'}</p>
        </div>
        {!estado?.bot_disponible && (
          <p className="text-[12px] text-amber-600 bg-amber-50 dark:bg-amber-900/20 rounded-xl px-3 py-2 mb-3">
            El bot todavía no tiene token configurado en el servidor (VENTAS_TELEGRAM_BOT_TOKEN). Podés generar el código igual; se activará cuando se conecte el bot.
          </p>
        )}
        {!estado?.vinculado && (
          <>
            <button className="btn-primary" onClick={generar}><Send size={14} /> Generar código de vinculación</button>
            {link && (
              <div className="mt-4 bg-neutral-50 dark:bg-[#141414] rounded-xl p-4">
                <p className="text-[12px] text-muted mb-1">Mandale esto al bot de Telegram (vence en 10 min):</p>
                <code className="text-[14px] font-mono text-[#B8893A]">{link.instruccion}</code>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function Tokko({ admin }) {
  const [cfg, setCfg] = useState(null)
  const [apiKey, setApiKey] = useState('')
  const [ciudades, setCiudades] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')

  const load = () => api.get('/api/ventas-crm/tokko-config').then(r => {
    setCfg(r.data); setCiudades((r.data.ciudades || []).join(', '))
  })
  useEffect(() => { load() }, [])

  const guardar = async (patch) => {
    const body = {
      ciudades: ciudades.split(',').map(s => s.trim()).filter(Boolean),
      ...patch,
    }
    if (apiKey) body.api_key = apiKey
    await api.put('/api/ventas-crm/tokko-config', body)
    setApiKey(''); load()
  }
  const sync = async () => {
    setSyncing(true); setMsg('')
    try {
      const r = await api.post('/api/ventas-crm/tokko-sync')
      setMsg(r.data.ok ? `Sync OK: ${r.data.nuevas} nuevas, ${r.data.actualizadas} actualizadas.` : r.data.motivo)
    } catch (e) { setMsg(e.response?.data?.detail || 'Error') } finally { setSyncing(false); load() }
  }

  if (!cfg) return null
  return (
    <div>
      <p className="text-[13px] text-muted mb-4">
        Integración con Tokko Broker. La segmentación por ciudades limita el sync a esas zonas (Mod #7).
      </p>
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${cfg.activo ? 'bg-emerald-500' : 'bg-gray-400'}`} />
            <span className="text-[14px] font-medium">{cfg.activo ? 'Activa' : 'Inactiva'}</span>
          </div>
          {admin && (
            <button className="btn-secondary text-[12px]" onClick={() => guardar({ activo: !cfg.activo })}>
              <Power size={13} /> {cfg.activo ? 'Desactivar' : 'Activar'}
            </button>
          )}
        </div>

        <div>
          <label className="label">API Key {cfg.tiene_api_key && <span className="text-emerald-600">(configurada)</span>}</label>
          <input className="input" type="password" placeholder={cfg.tiene_api_key ? '•••••• (dejá vacío para no cambiar)' : 'pegá la API key de Tokko'}
            value={apiKey} onChange={e => setApiKey(e.target.value)} disabled={!admin} />
        </div>
        <div>
          <label className="label">Ciudades a sincronizar (separadas por coma)</label>
          <input className="input" placeholder="Santa Rosa, General Pico" value={ciudades} onChange={e => setCiudades(e.target.value)} disabled={!admin} />
        </div>

        {admin && (
          <div className="flex gap-2">
            <button className="btn-primary" onClick={() => guardar({})}>Guardar</button>
            <button className="btn-secondary" onClick={sync} disabled={syncing}>
              <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} /> {syncing ? 'Sincronizando…' : 'Sincronizar ahora'}
            </button>
          </div>
        )}
        {msg && <p className="text-[12px] text-muted bg-neutral-50 dark:bg-[#141414] rounded-xl px-3 py-2">{msg}</p>}
        {cfg.ultima_sync && <p className="text-[11px] text-muted">Última sync: {new Date(cfg.ultima_sync).toLocaleString('es-AR')}</p>}
      </div>
    </div>
  )
}

function Plantillas({ admin }) {
  const [list, setList] = useState([])
  const [form, setForm] = useState({ nombre: '', offset_dias: '' })
  const load = () => api.get('/api/ventas-crm/plantillas').then(r => setList(r.data || []))
  useEffect(() => { load() }, [])
  const guardar = async e => {
    e.preventDefault()
    if (!form.nombre.trim() || !form.offset_dias) return
    await api.post('/api/ventas-crm/plantillas', { nombre: form.nombre, offset_dias: Number(form.offset_dias), activa: true })
    setForm({ nombre: '', offset_dias: '' }); load()
  }
  const toggle = async (p) => { await api.patch(`/api/ventas-crm/plantillas/${p.id}`, { nombre: p.nombre, offset_dias: p.offset_dias, activa: !p.activa }); load() }
  const borrar = async (p) => { await api.delete(`/api/ventas-crm/plantillas/${p.id}`); load() }
  return (
    <div>
      <p className="text-[13px] text-muted mb-4">
        Plantillas de seguimiento post-venta. Al cerrar una operación se crean tareas a estos días desde el cierre.
      </p>
      {admin && (
        <form onSubmit={guardar} className="card p-4 mb-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 items-end">
            <div className="sm:col-span-1"><label className="label">Nombre</label><input className="input" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} /></div>
            <div><label className="label">Días desde el cierre</label><input className="input" type="number" value={form.offset_dias} onChange={e => setForm({ ...form, offset_dias: e.target.value })} /></div>
            <button className="btn-primary"><Plus size={14} /> Agregar</button>
          </div>
        </form>
      )}
      <div className="space-y-2">
        {list.map(p => (
          <div key={p.id} className="card p-3 flex items-center gap-3">
            <span className={`w-2.5 h-2.5 rounded-full ${p.activa ? 'bg-emerald-500' : 'bg-gray-400'}`} />
            <div className="flex-1">
              <p className="text-[14px] font-medium">{p.nombre}</p>
              <p className="text-[11px] text-muted">{p.offset_dias} días desde el cierre</p>
            </div>
            {admin && <>
              <button onClick={() => toggle(p)} className="text-[12px] text-muted underline">{p.activa ? 'Desactivar' : 'Activar'}</button>
              <button onClick={() => borrar(p)} className="p-1 text-muted hover:text-danger"><Trash2 size={13} /></button>
            </>}
          </div>
        ))}
      </div>
    </div>
  )
}

function Comisiones({ admin }) {
  const [vendedores, setVendedores] = useState([])
  const [configs, setConfigs] = useState([])
  const [form, setForm] = useState({ vendedor_id: '', tipo: '', comision_pct: '' })

  const load = () => {
    api.get('/api/ventas-crm/vendedores').then(r => setVendedores(r.data || []))
    api.get('/api/ventas-crm/comision-config').then(r => setConfigs(r.data || []))
  }
  useEffect(() => { load() }, [])
  const vendNombre = id => vendedores.find(v => v.id === id)?.nombre || `#${id}`

  const guardar = async e => {
    e.preventDefault()
    if (!form.vendedor_id || !form.comision_pct) return
    await api.post('/api/ventas-crm/comision-config', {
      vendedor_id: Number(form.vendedor_id),
      tipo: form.tipo || null,
      comision_pct: Number(form.comision_pct),
    })
    setForm({ vendedor_id: '', tipo: '', comision_pct: '' }); load()
  }
  const borrar = async (c) => { await api.delete(`/api/ventas-crm/comision-config/${c.id}`); load() }

  return (
    <div>
      <p className="text-[13px] text-muted mb-4">
        Comisión por vendedor y por tipo de producto. Si no hay regla para un tipo,
        se usa la comisión por defecto del vendedor. La carga manual en una operación
        siempre tiene prioridad.
      </p>

      {/* Default por vendedor */}
      <div className="card p-4 mb-4">
        <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-3">Comisión por defecto</p>
        <div className="space-y-2">
          {vendedores.map(v => <VendedorDefault key={v.id} v={v} admin={admin} onSaved={load} />)}
        </div>
      </div>

      {admin && (
        <form onSubmit={guardar} className="card p-4 mb-4">
          <p className="text-[11px] uppercase tracking-wider text-muted font-semibold mb-3">Regla por tipo de producto</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
            <div><label className="label">Vendedor</label>
              <select className="input" value={form.vendedor_id} onChange={e => setForm({ ...form, vendedor_id: e.target.value })}>
                <option value="">—</option>{vendedores.map(v => <option key={v.id} value={v.id}>{v.nombre}</option>)}
              </select></div>
            <div><label className="label">Tipo</label>
              <select className="input" value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value })}>
                <option value="">Todos</option>{TIPOS.map(t => <option key={t}>{t}</option>)}
              </select></div>
            <div><label className="label">Comisión %</label>
              <input className="input" type="number" step="0.1" value={form.comision_pct} onChange={e => setForm({ ...form, comision_pct: e.target.value })} /></div>
            <button className="btn-primary"><Plus size={14} /> Agregar</button>
          </div>
        </form>
      )}

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border">
            <tr><th className="th">Vendedor</th><th className="th">Tipo</th><th className="th">Comisión</th><th className="th w-12" /></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {configs.length === 0 && <tr><td className="td text-muted text-[13px]" colSpan={4}>Sin reglas por tipo. Se usa el default de cada vendedor.</td></tr>}
            {configs.map(c => (
              <tr key={c.id}>
                <td className="td text-[13px]">{vendNombre(c.vendedor_id)}</td>
                <td className="td capitalize text-[13px]">{c.tipo || 'Todos'}</td>
                <td className="td text-[13px]">{c.comision_pct}%</td>
                <td className="td text-right">{admin && <button onClick={() => borrar(c)} className="p-1 text-muted hover:text-danger"><Trash2 size={13} /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function VendedorDefault({ v, admin, onSaved }) {
  const [pct, setPct] = useState(v.comision_default_pct ?? '')
  const save = async () => {
    await api.patch(`/api/ventas-crm/vendedores/${v.id}`,
      { comision_default_pct: pct === '' ? null : Number(pct) })
    onSaved()
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-[13px] flex-1">{v.nombre} {v.es_admin && <span className="chip-muted ml-1">admin</span>}</span>
      <input className="input w-24 text-right" type="number" step="0.1" value={pct} disabled={!admin}
        onChange={e => setPct(e.target.value)} />
      <span className="text-[13px] text-muted">%</span>
      {admin && <button onClick={save} className="btn-secondary text-[12px] py-1.5">Guardar</button>}
    </div>
  )
}

function Barrios({ admin }) {
  const [list, setList] = useState([])
  const [form, setForm] = useState({ nombre: '', ciudad: '', color: '#B8893A', poligono_geojson: '' })
  const load = () => api.get('/api/ventas-crm/barrios').then(r => setList(r.data || []))
  useEffect(() => { load() }, [])
  const guardar = async e => {
    e.preventDefault()
    if (!form.nombre.trim()) return
    await api.post('/api/ventas-crm/barrios', {
      nombre: form.nombre, ciudad: form.ciudad || null, color: form.color,
      poligono_geojson: form.poligono_geojson || null,
    })
    setForm({ nombre: '', ciudad: '', color: '#B8893A', poligono_geojson: '' }); load()
  }
  const borrar = async (b) => { if (!confirm('¿Eliminar barrio?')) return; await api.delete(`/api/ventas-crm/barrios/${b.id}`); load() }
  return (
    <div>
      <p className="text-[13px] text-muted mb-4">
        Barrios de la ciudad. El polígono GeoJSON (opcional) permite que al cargar una
        propiedad con dirección, el sistema detecte automáticamente a qué barrio pertenece.
      </p>
      {admin && (
        <form onSubmit={guardar} className="card p-4 mb-4 space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
            <div><label className="label">Nombre</label><input className="input" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} /></div>
            <div><label className="label">Ciudad</label><input className="input" value={form.ciudad} onChange={e => setForm({ ...form, ciudad: e.target.value })} /></div>
            <div><label className="label">Color</label><input className="input h-[42px] p-1" type="color" value={form.color} onChange={e => setForm({ ...form, color: e.target.value })} /></div>
            <button className="btn-primary"><Plus size={14} /> Agregar</button>
          </div>
          <div><label className="label">Polígono GeoJSON (opcional)</label>
            <textarea className="input resize-none font-mono text-[11px]" rows={2} placeholder='{"type":"Polygon","coordinates":[[[lng,lat],...]]}'
              value={form.poligono_geojson} onChange={e => setForm({ ...form, poligono_geojson: e.target.value })} /></div>
        </form>
      )}
      <div className="grid sm:grid-cols-2 gap-2">
        {list.length === 0 && <p className="text-muted text-[13px]">Sin barrios cargados.</p>}
        {list.map(b => (
          <div key={b.id} className="card p-3 flex items-center gap-3">
            <span className="w-4 h-4 rounded-full shrink-0" style={{ background: b.color }} />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium truncate">{b.nombre}</p>
              <p className="text-[11px] text-muted">{b.ciudad || '—'} · {b.poligono_geojson ? 'con polígono' : 'sin polígono'}</p>
            </div>
            {admin && <button onClick={() => borrar(b)} className="p-1 text-muted hover:text-danger"><Trash2 size={13} /></button>}
          </div>
        ))}
      </div>
    </div>
  )
}

function ValorM2({ admin }) {
  const [list, setList] = useState([])
  const [barrios, setBarrios] = useState([])
  const [form, setForm] = useState({ barrio_id: '', tipo: '', valor_m2_usd: '' })
  const load = () => {
    api.get('/api/ventas-crm/valor-m2').then(r => setList(r.data || []))
    api.get('/api/ventas-crm/barrios').then(r => setBarrios(r.data || []))
  }
  useEffect(() => { load() }, [])
  const barrioNombre = id => barrios.find(b => b.id === id)?.nombre || `#${id}`
  const guardar = async e => {
    e.preventDefault()
    if (!form.barrio_id || !form.valor_m2_usd) return
    await api.post('/api/ventas-crm/valor-m2', {
      barrio_id: Number(form.barrio_id), tipo: form.tipo || null, valor_m2_usd: Number(form.valor_m2_usd),
    })
    setForm({ barrio_id: '', tipo: '', valor_m2_usd: '' }); load()
  }
  const borrar = async (v) => { await api.delete(`/api/ventas-crm/valor-m2/${v.id}`); load() }
  return (
    <div>
      <p className="text-[13px] text-muted mb-4">
        Valor de referencia por m² para cada barrio y tipo. Se usa como respaldo en la
        tasación automática cuando no hay comparables suficientes en el catálogo.
      </p>
      {admin && (
        <form onSubmit={guardar} className="card p-4 mb-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
            <div><label className="label">Barrio</label>
              <select className="input" value={form.barrio_id} onChange={e => setForm({ ...form, barrio_id: e.target.value })}>
                <option value="">—</option>{barrios.map(b => <option key={b.id} value={b.id}>{b.nombre}</option>)}
              </select></div>
            <div><label className="label">Tipo</label>
              <select className="input" value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value })}>
                <option value="">Todos</option>{TIPOS.map(t => <option key={t}>{t}</option>)}
              </select></div>
            <div><label className="label">USD / m²</label><input className="input" type="number" value={form.valor_m2_usd} onChange={e => setForm({ ...form, valor_m2_usd: e.target.value })} /></div>
            <button className="btn-primary"><Plus size={14} /> Agregar</button>
          </div>
        </form>
      )}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border">
            <tr><th className="th">Barrio</th><th className="th">Tipo</th><th className="th">USD/m²</th><th className="th w-12" /></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {list.length === 0 && <tr><td className="td text-muted text-[13px]" colSpan={4}>Sin valores cargados.</td></tr>}
            {list.map(v => (
              <tr key={v.id}>
                <td className="td text-[13px]">{barrioNombre(v.barrio_id)}</td>
                <td className="td capitalize text-[13px]">{v.tipo || 'Todos'}</td>
                <td className="td text-[13px]">USD {v.valor_m2_usd.toLocaleString('es-AR')}</td>
                <td className="td text-right">{admin && <button onClick={() => borrar(v)} className="p-1 text-muted hover:text-danger"><Trash2 size={13} /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
