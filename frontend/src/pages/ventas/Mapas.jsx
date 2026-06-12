import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MapPin, Layers, Building2, Loader2, Navigation, X, ExternalLink, RefreshCw } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const fmtUSD = n => n ? 'USD ' + n.toLocaleString('es-AR') : '—'

// Color por tipo de propiedad (mismo lenguaje cromático del resto del módulo).
const TIPO_COLOR = {
  casa: '#B8893A', departamento: '#3B82F6', lote: '#10B981',
  campo: '#84CC16', local: '#A855F7', galpon: '#64748B', otro: '#737373',
}
const colorDe = tipo => TIPO_COLOR[tipo] || '#737373'

// Pin SVG coloreado como divIcon (evita el bug de íconos rotos de Leaflet+bundler).
const pinIcon = (color, activo = false) => L.divIcon({
  className: 'ventas-pin',
  html: `<div style="
      width:${activo ? 30 : 24}px;height:${activo ? 30 : 24}px;
      transform:translate(-50%,-100%);
      filter:drop-shadow(0 2px 3px rgba(0,0,0,.45));
      transition:all .15s;">
      <svg viewBox="0 0 24 24" width="100%" height="100%">
        <path fill="${color}" stroke="#fff" stroke-width="1.5"
          d="M12 2C7.6 2 4 5.6 4 10c0 5.2 6.6 11.3 7.4 12 .3.3.9.3 1.2 0C13.4 21.3 20 15.2 20 10c0-4.4-3.6-8-8-8z"/>
        <circle cx="12" cy="10" r="3" fill="#fff"/>
      </svg></div>`,
  iconSize: [0, 0], iconAnchor: [0, 0],
})

const TILES = {
  mapa: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attr: '© OpenStreetMap', max: 19,
  },
  satelite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr: '© Esri World Imagery', max: 19,
  },
}

export default function Mapas() {
  const mapEl = useRef(null)
  const mapRef = useRef(null)
  const tileRef = useRef(null)
  const markersRef = useRef(new Map())     // id → L.marker
  const barriosLayerRef = useRef(null)

  const [data, setData] = useState({ propiedades: [], barrios: [], sin_geo: 0, centro: null })
  const [loading, setLoading] = useState(true)
  const [capa, setCapa] = useState('mapa')
  const [sel, setSel] = useState(null)        // propiedad seleccionada
  const [filtroTipo, setFiltroTipo] = useState('')
  const [geocoding, setGeocoding] = useState(false)
  const [aviso, setAviso] = useState('')

  const cargar = () => {
    setLoading(true)
    api.get('/api/ventas-crm/propiedades/mapa')
      .then(r => setData(r.data || { propiedades: [], barrios: [], sin_geo: 0 }))
      .catch(() => setData({ propiedades: [], barrios: [], sin_geo: 0 }))
      .finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [])

  // ── Inicializar el mapa una sola vez ──────────────────────────────
  useEffect(() => {
    if (mapRef.current || !mapEl.current) return
    const c = data.centro || { lat: -36.6203, lng: -64.2906, zoom: 13 }
    const map = L.map(mapEl.current, { zoomControl: true, attributionControl: true })
      .setView([c.lat, c.lng], c.zoom || 13)
    tileRef.current = L.tileLayer(TILES.mapa.url, { maxZoom: TILES.mapa.max, attribution: TILES.mapa.attr }).addTo(map)
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [data.centro])

  // ── Cambiar capa base (mapa / satélite) ───────────────────────────
  useEffect(() => {
    if (!mapRef.current || !tileRef.current) return
    tileRef.current.setUrl(TILES[capa].url)
  }, [capa])

  // ── Pintar polígonos de barrio ────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (barriosLayerRef.current) { map.removeLayer(barriosLayerRef.current); barriosLayerRef.current = null }
    const grupo = L.layerGroup()
    data.barrios.forEach(b => {
      if (!b.poligono) return
      try {
        L.geoJSON(b.poligono, {
          style: { color: b.color, weight: 2, fillColor: b.color, fillOpacity: 0.08 },
        }).bindTooltip(b.nombre, { sticky: true, className: 'ventas-barrio-tip' }).addTo(grupo)
      } catch { /* geojson inválido — ignorar */ }
    })
    grupo.addTo(map)
    barriosLayerRef.current = grupo
  }, [data.barrios])

  // ── Pintar / actualizar marcadores de propiedades ─────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    // Limpiar marcadores previos
    markersRef.current.forEach(m => map.removeLayer(m))
    markersRef.current.clear()

    const visibles = data.propiedades.filter(p => !filtroTipo || p.tipo === filtroTipo)
    visibles.forEach(p => {
      const m = L.marker([p.lat, p.lng], {
        icon: pinIcon(colorDe(p.tipo), sel?.id === p.id),
        draggable: true,
        title: p.titulo || p.direccion || `#${p.id}`,
      })
      m.on('click', () => setSel(p))
      m.on('dragend', async () => {
        const { lat, lng } = m.getLatLng()
        try {
          const r = await api.patch(`/api/ventas-crm/propiedades/${p.id}/ubicacion?lat=${lat}&lng=${lng}`)
          // Actualizar la propiedad en estado con la nueva ubicación + barrio
          setData(d => ({
            ...d,
            propiedades: d.propiedades.map(x => x.id === p.id
              ? { ...x, lat, lng, barrio_id: r.data.barrio_id } : x),
          }))
          setAviso(`«${p.titulo || p.direccion || '#' + p.id}» reubicada${r.data.barrio_id ? '' : ' (fuera de todo barrio)'}.`)
          setTimeout(() => setAviso(''), 3500)
        } catch {
          m.setLatLng([p.lat, p.lng])  // revertir si falló
          setAviso('No se pudo guardar la nueva ubicación.')
          setTimeout(() => setAviso(''), 3500)
        }
      })
      m.addTo(map)
      markersRef.current.set(p.id, m)
    })
  }, [data.propiedades, filtroTipo, sel])

  const irA = p => {
    setSel(p)
    mapRef.current?.flyTo([p.lat, p.lng], 16, { duration: 0.6 })
  }

  const geocodificar = async () => {
    setGeocoding(true)
    try {
      const r = await api.post('/api/ventas-crm/propiedades/geocodificar-faltantes?limite=15')
      setAviso(`Geocodificadas ${r.data.resueltas} · ${r.data.restantes} pendientes.`)
      cargar()
    } catch {
      setAviso('No se pudo geocodificar el lote.')
    } finally {
      setGeocoding(false)
      setTimeout(() => setAviso(''), 4000)
    }
  }

  const tiposPresentes = [...new Set(data.propiedades.map(p => p.tipo).filter(Boolean))]
  const visiblesCount = data.propiedades.filter(p => !filtroTipo || p.tipo === filtroTipo).length

  return (
    <Layout fullWidth>
      <div className="h-[calc(100vh-3rem)] flex flex-col animate-fade-in">
        {/* Header */}
        <header className="px-4 sm:px-6 pt-4 pb-3 shrink-0">
          <div className="hero-eyebrow mb-1">Mapa de inventario</div>
          <div className="flex items-end justify-between gap-3 flex-wrap">
            <div>
              <h1 className="hero-title text-2xl sm:text-3xl">Mapas</h1>
              <p className="text-[13px] text-muted mt-0.5">
                {visiblesCount} propiedades en mapa · {data.barrios.length} barrios
                {data.sin_geo > 0 && ` · ${data.sin_geo} sin ubicar`}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Filtro por tipo */}
              <select className="input !py-2 !w-auto text-[13px]" value={filtroTipo}
                onChange={e => setFiltroTipo(e.target.value)}>
                <option value="">Todos los tipos</option>
                {tiposPresentes.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              {/* Toggle capa */}
              <div className="inline-flex rounded-xl border border-border overflow-hidden">
                {['mapa', 'satelite'].map(c => (
                  <button key={c} onClick={() => setCapa(c)}
                    className={`px-3 py-2 text-[12px] font-medium capitalize transition ${
                      capa === c ? 'bg-[#B8893A] text-white' : 'text-muted hover:bg-black/5 dark:hover:bg-white/5'
                    }`}>
                    {c === 'mapa' ? 'Mapa' : 'Satélite'}
                  </button>
                ))}
              </div>
              {data.sin_geo > 0 && (
                <button onClick={geocodificar} disabled={geocoding} className="btn-secondary !py-2 text-[12px]">
                  {geocoding ? <Loader2 size={13} className="animate-spin" /> : <Navigation size={13} />}
                  Ubicar {Math.min(15, data.sin_geo)} pendientes
                </button>
              )}
              <button onClick={cargar} className="btn-ghost !p-2" title="Recargar"><RefreshCw size={15} /></button>
            </div>
          </div>
        </header>

        {aviso && (
          <div className="mx-4 sm:mx-6 mb-2 px-4 py-2 rounded-xl bg-[#B8893A]/10 border border-[#B8893A]/30 text-[13px] text-[#B8893A] shrink-0">
            {aviso}
          </div>
        )}

        {/* Mapa + panel */}
        <div className="flex-1 min-h-0 px-4 sm:px-6 pb-4">
          <div className="h-full grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4">

            {/* MAPA */}
            <div className="relative rounded-3xl overflow-hidden border border-border min-h-[360px]">
              <div ref={mapEl} className="absolute inset-0 z-0" />
              {loading && (
                <div className="absolute inset-0 grid place-items-center bg-white/60 dark:bg-black/60 z-[500]">
                  <Loader2 size={28} className="animate-spin text-[#B8893A]" />
                </div>
              )}
              {!loading && data.propiedades.length === 0 && (
                <div className="absolute inset-0 grid place-items-center pointer-events-none z-[400]">
                  <div className="text-center bg-white/90 dark:bg-black/80 rounded-2xl px-6 py-5 pointer-events-auto">
                    <MapPin size={32} className="mx-auto text-muted/40 mb-2" />
                    <p className="text-[13px] text-muted max-w-[220px]">
                      Ninguna propiedad tiene coordenadas todavía.
                      {data.sin_geo > 0 && ' Usá «Ubicar pendientes» para geocodificarlas.'}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* PANEL LATERAL */}
            <div className="card p-0 overflow-hidden flex flex-col min-h-[200px]">
              {sel ? (
                <FichaPropiedad p={sel} barrios={data.barrios} onClose={() => setSel(null)} />
              ) : (
                <>
                  <div className="px-4 py-3 border-b border-border flex items-center gap-2 shrink-0">
                    <Building2 size={15} className="text-[#B8893A]" />
                    <p className="text-[12px] uppercase tracking-wider font-semibold text-muted">
                      Propiedades en mapa
                    </p>
                  </div>
                  <div className="flex-1 overflow-y-auto divide-y divide-border">
                    {data.propiedades.filter(p => !filtroTipo || p.tipo === filtroTipo).map(p => (
                      <button key={p.id} onClick={() => irA(p)}
                        className="w-full text-left px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition flex items-start gap-2.5">
                        <span className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0" style={{ background: colorDe(p.tipo) }} />
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium truncate">{p.titulo || p.direccion || `#${p.id}`}</p>
                          <p className="text-[11px] text-muted capitalize">{p.tipo} · {p.ciudad || 's/ciudad'}</p>
                        </div>
                        <span className="text-[11px] text-muted shrink-0">{fmtUSD(p.precio_usd)}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

          </div>
        </div>
      </div>
    </Layout>
  )
}

function FichaPropiedad({ p, barrios, onClose }) {
  const barrio = barrios.find(b => b.id === p.barrio_id)
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
        <span className="chip-muted capitalize" style={{ color: colorDe(p.tipo) }}>{p.tipo}</span>
        <button onClick={onClose} className="btn-ghost !p-1.5"><X size={15} /></button>
      </div>
      <div className="p-4 overflow-y-auto flex-1">
        <h3 className="text-lg font-bold leading-tight">{p.titulo || p.direccion || `Propiedad #${p.id}`}</h3>
        {p.direccion && <p className="text-[12px] text-muted mt-0.5 flex items-center gap-1"><MapPin size={11} />{p.direccion}</p>}
        <p className="stat-value text-2xl mt-3">{fmtUSD(p.precio_usd)}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[13px] text-muted">
          {p.superficie_m2 && <span>{p.superficie_m2} m²</span>}
          {p.dormitorios != null && <span>{p.dormitorios} dorm</span>}
          {p.banos != null && <span>{p.banos} baños</span>}
        </div>
        <div className="mt-4 space-y-1.5 text-[12px]">
          <Row k="Ciudad" v={p.ciudad || '—'} />
          <Row k="Barrio" v={barrio?.nombre || 'Sin barrio asignado'} />
          <Row k="Origen" v={p.fuente || 'propia'} />
          <Row k="Coordenadas" v={`${p.lat?.toFixed(5)}, ${p.lng?.toFixed(5)}`} />
        </div>
        {p.link_externo && (
          <a href={p.link_externo} target="_blank" rel="noreferrer"
            className="btn-secondary w-full mt-4 text-[13px]">
            <ExternalLink size={13} /> Ver publicación
          </a>
        )}
        <p className="text-[11px] text-muted mt-4 flex items-center gap-1.5">
          <Layers size={12} /> Arrastrá el pin en el mapa para corregir su ubicación; el barrio se reasigna solo.
        </p>
      </div>
    </div>
  )
}

const Row = ({ k, v }) => (
  <div className="flex items-center justify-between gap-3">
    <span className="text-muted">{k}</span>
    <span className="font-medium text-right capitalize truncate">{v}</span>
  </div>
)
