import { useState, useEffect } from 'react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { Building2, Search } from 'lucide-react'

const TIPO_LABELS = { departamento:'Depto', casa:'Casa', local:'Local', campo:'Campo' }
const ESTADO_COLORS = {
  disponible: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  reservada:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  inactiva:   'bg-gray-100 text-gray-500 dark:bg-gray-800',
  ocupada:    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
}

export default function PropiedadesVenta() {
  const [props, setProps] = useState([])
  const [busqueda, setBusqueda] = useState('')

  useEffect(() => {
    api.get('/api/ventas/propiedades').then(r => setProps(r.data)).catch(console.error)
  }, [])

  const filtradas = props.filter(p =>
    !busqueda || p.direccion?.toLowerCase().includes(busqueda.toLowerCase()) ||
    p.ciudad?.toLowerCase().includes(busqueda.toLowerCase())
  )

  return (
    <Layout>
      <div className="p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-1">Ventas</p>
            <h1 className="text-3xl font-black">Propiedades en Venta</h1>
          </div>
          <p className="text-sm text-gray-400">{filtradas.length} propiedades</p>
        </div>

        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            placeholder="Buscar por dirección o ciudad..."
            className="input pl-9 w-full max-w-sm"
          />
        </div>

        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-800">
                <th className="th text-left">Propiedad</th>
                <th className="th text-left">Tipo</th>
                <th className="th text-right">Precio USD</th>
                <th className="th text-center">Superficie</th>
                <th className="th text-center">Estado</th>
                <th className="th text-center">Tokko</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map(p => (
                <tr key={p.id} className="border-b border-gray-50 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50">
                  <td className="td">
                    <p className="font-medium text-sm">{p.direccion}</p>
                    <p className="text-xs text-gray-400">{p.ciudad}</p>
                  </td>
                  <td className="td">
                    <span className="text-sm">{TIPO_LABELS[p.tipo] || p.tipo}</span>
                    {p.ambientes && <span className="text-xs text-gray-400 ml-1">· {p.ambientes} amb.</span>}
                  </td>
                  <td className="td text-right">
                    <p className="font-semibold text-sm">
                      {p.precio_venta ? `USD ${Number(p.precio_venta).toLocaleString()}` : 'Consultar'}
                    </p>
                  </td>
                  <td className="td text-center text-sm text-gray-500">
                    {p.superficie_m2 ? `${p.superficie_m2}m²` : '—'}
                  </td>
                  <td className="td text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ESTADO_COLORS[p.estado] || ''}`}>
                      {p.estado}
                    </span>
                  </td>
                  <td className="td text-center">
                    {p.tokko_id
                      ? <span className="text-xs text-green-600 dark:text-green-400 font-medium">✓ Publicado</span>
                      : <span className="text-xs text-gray-400">—</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  )
}
