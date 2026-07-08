import { useEffect, useState } from 'react'
import { Globe, Download, Check, MapPin, Building2, RefreshCw, ExternalLink, Search, Radar, X } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import { useRole } from '../../context/RoleContext'
import api from '../../utils/api'

const OPERACIONES = [['', 'Todas'], ['venta', 'Venta'], ['alquiler', 'Alquiler']]
const OPER_VIVO = [['venta', 'Venta'], ['alquiler', 'Alquiler']]

// Localidades de La Pampa — palabras clave exactas para resolver la zona en
// Tokko. El usuario elige de la lista (o escribe) y Tokko la desambigua.
const ZONAS_LAPAMPA = [
  'Santa Rosa', 'Toay', 'General Pico', 'General Acha', 'Eduardo Castex',
  'Realicó', 'Intendente Alvear', 'Victorica', 'Macachín', 'Catriló',
  'Quemú Quemú', 'Winifreda', 'Ingeniero Luiggi', 'Guatraché', '25 de Mayo',
  'Colonia Barón', 'Doblas', 'Anguil', 'Miguel Riglos', 'Lonquimay',
  'Uriburu', 'Rancul', 'Parera', 'Bernasconi', 'La Adela', 'Alpachiri',
  'Santa Isabel', 'Telén', 'Trenel', 'Alta Italia', 'Bernardo Larroudé',
  'Caleufú', 'Arata', 'Embajador Martini', 'Jacinto Arauz', 'Ataliva Roca',
  'Utracán', 'General Manuel J. Campos', 'Villa Mirasol', 'Metileo',
  'Monte Nievas', 'Speluzzi', 'Rolón', 'Naicó', 'La Reforma', 'Puelches',
  'Puelén', 'Casa de Piedra', 'Gobernador Duval', 'Colonia Santa María',
  'Algarrobo del Águila', 'La Humada', 'Chacharramendi', 'Cuchillo Có',
]

// Combobox con buscador: filtra la lista mientras escribís y permite texto libre.
function ComboZona({ value, onChange, onPick }) {
  const [open, setOpen] = useState(false)
  const q = (value || '').trim().toLowerCase()
  const ops = ZONAS_LAPAMPA.filter(z => z.toLowerCase().includes(q)).slice(0, 10)
  return (
    <div className="relative">
      <input className="input !py-2 text-[13px]" placeholder="Ej: Santa Rosa, General Pico…"
        value={value} autoComplete="off"
        onChange={e => { onChange(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={e => { if (e.key === 'Enter') { setOpen(false); onPick(value) } }} />
      {open && ops.length > 0 && (
        <div className="absolute z-30 left-0 right-0 mt-1 rounded-xl border border-border bg-white dark:bg-[#141414] shadow-xl max-h-56 overflow-y-auto">
          {ops.map(z => (
            <button key={z} type="button"
              onMouseDown={e => { e.preventDefault(); onChange(z); onPick(z); setOpen(false) }}
              className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#B8893A]/10 flex items-center gap-2">
              <MapPin size={12} className="text-[#B8893A] shrink-0" /><span>{z}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function RedTokko() {
  const { isAdmin, role } = useRole()
  const esAdmin = isAdmin || role === 'ventas_admin' || role === 'gerencia'

  const [filtros, setFiltros] = useState({ zona: '', operacion: 'venta', precio_min: '', precio_max: '', dorm_min: '' })
  const [props, setProps] = useState([])
  const [nota, setNota] = useState('')
  const [loading, setLoading] = useState(false)
  const [sel, setSel] = useState(new Set())
  const [importando, setImportando] = useState(false)
  const [msg, setMsg] = useState('')

  // Búsqueda EN VIVO por zona (con desambiguación)
  const [zonaQuery, setZonaQuery] = useState('')
  const [candidatos, setCandidatos] = useState([])
  const [zonaElegida, setZonaElegida] = useState(null)
  const [resolviendo, setResolviendo] = useState(false)
  const [vivo, setVivo] = useState({ operacion: 'venta', precio_min: '', precio_max: '' })
  const [trayendo, setTrayendo] = useState(false)

  const resolverZonas = async (qArg) => {
    const q = (typeof qArg === 'string' ? qArg : zonaQuery).trim()
    if (q.length < 2) return
    setResolviendo(true); setCandidatos([]); setZonaElegida(null); setMsg('')
    try {
      const { data } = await api.get(`/api/ventas-crm/red-tokko/zonas?q=${encodeURIComponent(q)}`)
      setCandidatos(data.zonas || [])
      if (data.tokko_conectado === false) {
        setMsg('Tokko no está conectado en este servidor. Un admin tiene que configurar las credenciales (TOKKO_USER / TOKKO_PASS) para traer de la red.')
      } else if (!data.zonas?.length) {
        setMsg('No se encontró esa zona en Tokko. Probá otro nombre.')
      }
    } catch (e) {
      setMsg(e?.response?.data?.detail || 'No se pudo consultar Tokko.')
    } finally { setResolviendo(false) }
  }

  const traerEnVivo = async () => {
    if (!zonaElegida) return
    setTrayendo(true); setMsg(''); setSel(new Set())
    try {
      const { data } = await api.post('/api/ventas-crm/red-tokko/buscar', {
        loc_id: zonaElegida.loc_id, loc_type: zonaElegida.loc_type,
        zona_nombre: zonaElegida.ruta,
        operacion: vivo.operacion,
        precio_min: vivo.precio_min || null, precio_max: vivo.precio_max || null,
        limit: 60,
      })
      setProps(data.propiedades || [])
      setNota('')
      setMsg(`✓ Traídas ${data.trajo} de ${data.total_red ?? '?'} en la zona · ${data.geocodificadas || 0} geolocalizadas`)
    } catch (e) {
      setMsg(e?.response?.data?.detail || 'No se pudo traer de la red en vivo.')
    } finally { setTrayendo(false) }
  }

  const setV = k => e => setVivo(s => ({ ...s, [k]: e.target.value }))

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
      const mt = data.matches_generados ? ` · ${data.matches_generados} match${data.matches_generados > 1 ? 'es' : ''} nuevo${data.matches_generados > 1 ? 's' : ''}` : ''
      setMsg(`✓ Importadas ${data.creadas} · ya existían ${data.saltadas_ya_existentes}${mt} · ya están en el mapa`)
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

        {/* Búsqueda EN VIVO por zona (admin) */}
        {esAdmin && (
          <div className="card p-4 mb-4 border-[#B8893A]/30">
            <div className="flex items-center gap-2 mb-2">
              <Radar size={16} className="text-[#B8893A]" />
              <p className="text-[13px] font-semibold">Traer de la red en vivo por zona</p>
            </div>
            <p className="text-[11px] text-muted mb-3">
              Escribí una zona y elegí la correcta. Tokko trae solo esa zona (no toda la red).
            </p>

            {/* Paso 1: resolver zona (combobox con buscador de localidades) */}
            <div className="flex gap-2 items-end mb-2">
              <div className="flex-1">
                <label className="label">Zona</label>
                <ComboZona value={zonaQuery} onChange={setZonaQuery} onPick={z => resolverZonas(z)} />
              </div>
              <button className="btn-secondary !py-2 text-[13px]" onClick={() => resolverZonas()} disabled={resolviendo || zonaQuery.trim().length < 2}>
                <Search size={13} className={resolviendo ? 'animate-pulse' : ''} /> Resolver
              </button>
            </div>

            {/* Candidatos para desambiguar */}
            {candidatos.length > 0 && !zonaElegida && (
              <div className="border border-border rounded-xl divide-y divide-border mb-2 max-h-52 overflow-y-auto">
                {candidatos.map(z => (
                  <button key={z.valor} onClick={() => { setZonaElegida(z); setCandidatos([]) }}
                    className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#B8893A]/10 flex items-center gap-2">
                    <MapPin size={12} className="text-[#B8893A] shrink-0" />
                    <span className="truncate">{z.ruta}</span>
                    <span className="chip-muted text-[10px] ml-auto shrink-0">{z.loc_type}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Zona elegida + filtros + traer */}
            {zonaElegida && (
              <div className="bg-[#B8893A]/5 border border-[#B8893A]/20 rounded-xl p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Check size={14} className="text-emerald-500" />
                  <span className="text-[13px] font-medium">{zonaElegida.ruta}</span>
                  <button className="ml-auto btn-ghost !p-1" title="Cambiar zona"
                    onClick={() => { setZonaElegida(null); setCandidatos([]) }}><X size={14} /></button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
                  <div>
                    <label className="label">Operación</label>
                    <select className="input !py-2 text-[13px]" value={vivo.operacion} onChange={setV('operacion')}>
                      {OPER_VIVO.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </div>
                  <div><label className="label">USD mín</label><input className="input !py-2 text-[13px]" type="number" value={vivo.precio_min} onChange={setV('precio_min')} /></div>
                  <div><label className="label">USD máx</label><input className="input !py-2 text-[13px]" type="number" value={vivo.precio_max} onChange={setV('precio_max')} /></div>
                  <button className="btn-primary !py-2 text-[13px]" onClick={traerEnVivo} disabled={trayendo}>
                    <Radar size={13} className={trayendo ? 'animate-pulse' : ''} /> {trayendo ? 'Trayendo…' : 'Traer de la red'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Filtros (sobre lo ya guardado) */}
        <div className="card p-3 mb-4 grid grid-cols-2 sm:grid-cols-6 gap-2 items-end">
          <div className="col-span-2 sm:col-span-1">
            <label className="label">Zona</label>
            <ComboZona value={filtros.zona}
              onChange={z => setFiltros(f => ({ ...f, zona: z }))}
              onPick={z => setFiltros(f => ({ ...f, zona: z }))} />
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
