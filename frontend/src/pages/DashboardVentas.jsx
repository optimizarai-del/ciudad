import { useState, useEffect } from 'react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { Building2, TrendingUp, DollarSign, CheckSquare } from 'lucide-react'

export default function DashboardVentas() {
  const [data, setData] = useState(null)

  useEffect(() => {
    api.get('/api/ventas/dashboard').then(r => setData(r.data)).catch(console.error)
  }, [])

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div>
          <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase mb-1">Ventas</p>
          <h1 className="text-3xl font-black">Dashboard Ventas</h1>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'En venta', value: data?.total_en_venta ?? '—', icon: Building2 },
            { label: 'Disponibles', value: data?.disponibles ?? '—', icon: TrendingUp, color: 'text-green-600 dark:text-green-400' },
            { label: 'Reservadas', value: data?.reservadas ?? '—', icon: CheckSquare, color: 'text-amber-600' },
            { label: 'Precio promedio', value: data?.precio_promedio_usd ? `USD ${Number(data.precio_promedio_usd).toLocaleString()}` : '—', icon: DollarSign },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card p-5">
              <div className="flex items-start justify-between mb-3">
                <p className="text-xs font-semibold tracking-widest uppercase text-gray-400">{label}</p>
                <Icon size={16} className="text-gray-300 dark:text-gray-700" />
              </div>
              <p className={`text-3xl font-black ${color || ''}`}>{value}</p>
            </div>
          ))}
        </div>

        {data?.propiedades_destacadas?.length > 0 && (
          <div className="card p-5">
            <p className="text-sm font-semibold mb-4">Propiedades disponibles</p>
            <div className="grid grid-cols-2 gap-3">
              {data.propiedades_destacadas.map(p => (
                <div key={p.id} className="p-4 rounded-xl border border-gray-100 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-sm">{p.direccion}</p>
                      <p className="text-xs text-gray-400 mt-0.5 capitalize">{p.tipo} · {p.ambientes} amb. · {p.superficie_m2}m²</p>
                    </div>
                    <p className="text-sm font-bold text-green-700 dark:text-green-400">
                      {p.precio_venta ? `USD ${Number(p.precio_venta).toLocaleString()}` : 'Consultar'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
