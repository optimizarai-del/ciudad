import { useEffect, useState } from 'react'
import { TrendingUp, DollarSign, FileText, Building2 } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

export default function Finanzas() {
  const [contratos, setContratos] = useState([])
  const [propiedades, setProp] = useState([])

  useEffect(() => {
    api.get('/api/contratos').then(r => setContratos(r.data))
    api.get('/api/propiedades').then(r => setProp(r.data))
  }, [])

  const vigentes = contratos.filter(c => c.estado === 'vigente')
  const totalAlquilerMensual = vigentes.reduce((s, c) => s + (c.monto_inicial || 0), 0)
  const totalDepositos = vigentes.reduce((s, c) => s + (c.deposito || 0), 0)
  const totalComisiones = vigentes.reduce((s, c) => s + (c.monto_inicial * (c.comision_porc || 0) / 100), 0)

  // Agrupar por tipo
  const porTipo = {}
  contratos.forEach(c => {
    porTipo[c.tipo] = (porTipo[c.tipo] || 0) + 1
  })

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">

        <header className="mb-12">
          <div className="hero-eyebrow">Resumen financiero</div>
          <h1 className="hero-title text-5xl md:text-6xl mb-3">Finanzas.</h1>
          <p className="hero-sub">Visión general de ingresos y contratos activos.</p>
        </header>

        {/* Big numbers */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          <BigCard label="Alquiler mensual" value={`$${totalAlquilerMensual.toLocaleString('es-AR')}`}
            sub={`${vigentes.length} contratos vigentes`} icon={DollarSign} />
          <BigCard label="Depósitos en garantía" value={`$${totalDepositos.toLocaleString('es-AR')}`}
            sub="acumulado" icon={Building2} />
          <BigCard label="Comisiones estimadas" value={`$${Math.round(totalComisiones).toLocaleString('es-AR')}`}
            sub="sobre contratos vigentes" icon={TrendingUp} />
        </section>

        {/* Tabla contratos vigentes */}
        <div className="card overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <h2 className="font-semibold text-[15px] tracking-tight">Contratos vigentes</h2>
            <span className="chip-dark">{vigentes.length}</span>
          </div>
          {vigentes.length === 0
            ? <div className="py-16 text-center text-muted text-[14px]">No hay contratos vigentes.</div>
            : (
              <table className="w-full">
                <thead className="bg-neutral-50 border-b border-border">
                  <tr>
                    <th className="th">Código</th>
                    <th className="th hidden md:table-cell">Tipo</th>
                    <th className="th">Monto</th>
                    <th className="th hidden lg:table-cell">Depósito</th>
                    <th className="th hidden lg:table-cell">Índice</th>
                    <th className="th hidden md:table-cell">Vence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {vigentes.map(c => (
                    <tr key={c.id} className="hover:bg-neutral-50 transition">
                      <td className="td font-medium">{c.codigo || `#${c.id}`}</td>
                      <td className="td hidden md:table-cell capitalize text-[12px] text-muted">
                        {c.tipo?.replace(/_/g, ' ')}
                      </td>
                      <td className="td font-semibold">${Number(c.monto_inicial).toLocaleString('es-AR')}</td>
                      <td className="td hidden lg:table-cell text-muted">${Number(c.deposito).toLocaleString('es-AR')}</td>
                      <td className="td hidden lg:table-cell">
                        <span className="chip-gray">{c.indice_ajuste?.toUpperCase()}/{c.periodicidad_meses}m</span>
                      </td>
                      <td className="td hidden md:table-cell text-[12px] text-muted">{c.fecha_fin || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          }
        </div>

        {/* Distribución por tipo */}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="card p-6">
            <h2 className="font-semibold text-[15px] tracking-tight mb-5">Contratos por tipo</h2>
            <div className="space-y-3">
              {Object.entries(porTipo).map(([tipo, n]) => (
                <div key={tipo} className="flex items-center justify-between">
                  <span className="text-[13px] capitalize">{tipo.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-3">
                    <div className="h-1.5 bg-neutral-100 rounded-full w-24">
                      <div className="h-1.5 bg-primary rounded-full"
                        style={{ width: `${(n / contratos.length) * 100}%` }} />
                    </div>
                    <span className="text-[13px] font-semibold w-6 text-right">{n}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-6">
            <h2 className="font-semibold text-[15px] tracking-tight mb-5">Propiedades disponibles</h2>
            <div className="space-y-3">
              {['departamento','casa','local','campo'].map(tipo => {
                const total = propiedades.filter(p => p.tipo === tipo).length
                const disp  = propiedades.filter(p => p.tipo === tipo && p.estado === 'disponible').length
                if (total === 0) return null
                return (
                  <div key={tipo} className="flex items-center justify-between">
                    <span className="text-[13px] capitalize">{tipo}</span>
                    <div className="flex items-center gap-3">
                      <div className="h-1.5 bg-neutral-100 rounded-full w-24">
                        <div className="h-1.5 bg-success rounded-full"
                          style={{ width: total > 0 ? `${(disp / total) * 100}%` : '0%' }} />
                      </div>
                      <span className="text-[13px] font-semibold w-10 text-right text-muted">{disp}/{total}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

      </div>
    </Layout>
  )
}

function BigCard({ label, value, sub, icon: Icon }) {
  return (
    <div className="card p-7">
      <div className="flex items-start justify-between mb-4">
        <div className="w-9 h-9 rounded-2xl bg-neutral-100 grid place-items-center">
          <Icon size={16} className="text-muted" />
        </div>
      </div>
      <div className="stat-label mb-1.5">{label}</div>
      <div className="hero-title text-3xl md:text-4xl">{value}</div>
      <div className="text-[12px] text-muted mt-1.5">{sub}</div>
    </div>
  )
}
