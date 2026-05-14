import { useEffect, useState } from 'react'
import { Search, RefreshCw, Image as ImageIcon, ExternalLink } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import TokkoSync from '../components/TokkoSync'
import AdjuntosModal from '../components/AdjuntosModal'
import api from '../utils/api'

const TIPO_LABELS = { departamento:'Depto', casa:'Casa', local:'Local', campo:'Campo/Terreno' }
const ESTADO_COLORS = {
  disponible: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  reservada:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  inactiva:   'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500',
  ocupada:    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
}

export default function PropiedadesVenta() {
  const [propsList, setProps] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [tokkoOpen, setTokkoOpen] = useState(false)
  const [adjPropiedad, setAdjPropiedad] = useState(null)
  const [thumbs, setThumbs] = useState({})  // {prop_id: url}

  const load = async () => {
    const r = await api.get('/api/ventas/propiedades')
    const data = r.data || []
    setProps(data)
    // Cargar thumbnails (foto principal) en paralelo, sin bloquear el render
    Promise.all(data.map(async p => {
      try {
        const a = await api.get(`/api/propiedades/${p.id}/adjuntos`)
        const principal = (a.data || []).find(x => x.es_principal) || (a.data || [])[0]
        if (principal) {
          return [p.id, `${api.defaults.baseURL}/api/propiedades/${p.id}/adjuntos/${principal.id}`]
        }
      } catch {}
      return null
    })).then(pairs => {
      const m = {}
      pairs.filter(Boolean).forEach(([k, v]) => { m[k] = v })
      setThumbs(m)
    })
  }
  useEffect(() => { load() }, [])

  const filtradas = propsList.filter(p =>
    !busqueda
    || (p.direccion || '').toLowerCase().includes(busqueda.toLowerCase())
    || (p.ciudad || '').toLowerCase().includes(busqueda.toLowerCase())
    || (p.tokko_id || '').toString().includes(busqueda)
  )

  const totalTokko = propsList.filter(p => p.tokko_id).length

  return (
    <Layout>
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 dark:text-gray-500 uppercase mb-1">Ventas</p>
            <h1 className="hero-title text-5xl md:text-6xl mb-3">Propiedades en Venta</h1>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
              {filtradas.length} propiedades · <span className="text-[#B8893A]">{totalTokko} sincronizadas con Tokko</span>
            </p>
          </div>
          <button className="btn-primary" onClick={() => setTokkoOpen(true)}>
            <RefreshCw size={14} /> Sync Tokko
          </button>
        </div>

        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            placeholder="Buscar por dirección, ciudad o ID Tokko..."
            className="input pl-9 w-full max-w-sm"
          />
        </div>

        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800">
                <th className="th text-left w-16">Foto</th>
                <th className="th text-left">Propiedad</th>
                <th className="th text-left">Tipo</th>
                <th className="th text-right">Precio</th>
                <th className="th text-center hidden md:table-cell">Sup.</th>
                <th className="th text-center hidden lg:table-cell">Estado</th>
                <th className="th text-center">Tokko</th>
                <th className="th text-center w-16">Fotos</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map(p => (
                <tr key={p.id} className="border-b border-gray-50 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-[#1A1A1A]">
                  <td className="td">
                    <div className="w-12 h-12 rounded-lg bg-neutral-100 dark:bg-[#1E1E1E] overflow-hidden grid place-items-center">
                      {thumbs[p.id]
                        ? <img src={thumbs[p.id]} alt="" className="object-cover w-full h-full" />
                        : <ImageIcon size={14} className="text-gray-400 dark:text-gray-600" />
                      }
                    </div>
                  </td>
                  <td className="td">
                    <p className="font-medium text-sm">{p.direccion}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">{p.ciudad}</p>
                  </td>
                  <td className="td">
                    <span className="text-sm">{TIPO_LABELS[p.tipo] || p.tipo}</span>
                    {p.ambientes ? <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">· {p.ambientes} amb.</span> : null}
                  </td>
                  <td className="td text-right">
                    <p className="font-semibold text-sm">
                      {p.precio_venta ? `USD ${Number(p.precio_venta).toLocaleString('es-AR')}` : 'Consultar'}
                    </p>
                  </td>
                  <td className="td text-center text-sm text-gray-500 dark:text-gray-500 hidden md:table-cell">
                    {p.superficie_m2 ? `${Math.round(p.superficie_m2)}m²` : '—'}
                  </td>
                  <td className="td text-center hidden lg:table-cell">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ESTADO_COLORS[p.estado] || ''}`}>
                      {p.estado}
                    </span>
                  </td>
                  <td className="td text-center">
                    {p.tokko_id ? (
                      <a href={`https://www.tokkobroker.com/propiedad/${p.tokko_id}`}
                         target="_blank" rel="noreferrer"
                         className="inline-flex items-center gap-1 text-xs text-[#B8893A] font-medium hover:underline">
                        TKO-{p.tokko_id} <ExternalLink size={9} />
                      </a>
                    ) : (
                      <span className="text-xs text-gray-400 dark:text-gray-500">—</span>
                    )}
                  </td>
                  <td className="td text-center">
                    <button onClick={() => setAdjPropiedad(p)}
                      className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-[#1E1E1E] text-muted dark:text-gray-500 transition"
                      title="Ver fotos">
                      <ImageIcon size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {tokkoOpen && (
        <TokkoSync onClose={() => setTokkoOpen(false)} onSynced={() => load()} />
      )}
      {adjPropiedad && (
        <AdjuntosModal propiedad={adjPropiedad} onClose={() => setAdjPropiedad(null)} />
      )}
    </Layout>
  )
}
