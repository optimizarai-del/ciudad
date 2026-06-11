import { useEffect, useMemo, useState } from 'react'
import { Sparkles, Building2, Check, X, ChevronLeft, ChevronRight, Layers } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const fmtUSD = n => n ? 'USD ' + n.toLocaleString('es-AR') : '—'
const scoreColor = s => s >= 80 ? 'bg-emerald-500' : s >= 65 ? 'bg-amber-500' : 'bg-sky-500'

export default function Matches() {
  const [grupos, setGrupos] = useState([])
  const [sel, setSel] = useState(0)

  const load = () => api.get('/api/ventas-crm/matches').then(r => {
    const gs = r.data?.grupos || []
    setGrupos(gs)
    setSel(s => Math.min(s, Math.max(0, gs.length - 1)))
  }).catch(() => setGrupos([]))
  useEffect(() => { load() }, [])

  const actual = grupos[sel]

  const accion = async (matchId, estado) => {
    try {
      await api.patch(`/api/ventas-crm/matches/${matchId}?estado=${estado}`)
      load()
    } catch (e) { alert(e.response?.data?.detail || 'No se pudo actualizar el match.') }
  }

  return (
    <Layout>
      <div className="max-w-[1300px] mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Inteligencia comercial</div>
          <div className="flex items-end justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Matches</h1>
              <p className="hero-sub">Propiedades cruzadas con los pedidos activos de los clientes.</p>
            </div>
            <span className="chip-dark"><Layers size={12} className="inline mr-1" />{grupos.length} propiedades con match</span>
          </div>
        </header>

        {grupos.length === 0 ? (
          <div className="card text-center py-20">
            <Sparkles size={36} className="mx-auto text-muted/30 mb-3" />
            <p className="text-muted text-[14px]">Todavía no hay matches. Se generan automáticamente al cargar pedidos y propiedades.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
            {/* IZQUIERDA: propiedad grande + navegación */}
            <div className="card p-5 sm:p-6">
              <div className="flex items-center justify-between mb-4">
                <button onClick={() => setSel(s => Math.max(0, s - 1))} disabled={sel === 0}
                  className="btn-ghost p-2 disabled:opacity-30"><ChevronLeft size={18} /></button>
                <span className="text-[12px] text-muted">{sel + 1} de {grupos.length}</span>
                <button onClick={() => setSel(s => Math.min(grupos.length - 1, s + 1))} disabled={sel === grupos.length - 1}
                  className="btn-ghost p-2 disabled:opacity-30"><ChevronRight size={18} /></button>
              </div>

              {actual && (
                <>
                  <div className="rounded-2xl bg-neutral-100 dark:bg-[#141414] h-44 grid place-items-center mb-4">
                    <Building2 size={48} className="text-muted/30" />
                  </div>
                  <h2 className="text-xl font-bold">{actual.propiedad.titulo || actual.propiedad.direccion || `Propiedad #${actual.propiedad.id}`}</h2>
                  <p className="text-[13px] text-muted capitalize">{actual.propiedad.tipo} · {actual.propiedad.ciudad || 's/ciudad'}</p>
                  <p className="stat-value text-2xl mt-2">{fmtUSD(actual.propiedad.precio_usd)}</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[13px] text-muted">
                    {actual.propiedad.superficie_m2 && <span>{actual.propiedad.superficie_m2} m²</span>}
                    {actual.propiedad.dormitorios && <span>{actual.propiedad.dormitorios} dorm</span>}
                    {actual.propiedad.banos && <span>{actual.propiedad.banos} baños</span>}
                    {actual.propiedad.fuente && actual.propiedad.fuente !== 'propia' && (
                      <span className="chip-muted capitalize">{actual.propiedad.fuente}</span>
                    )}
                  </div>
                </>
              )}

              {/* Tira de propiedades (selector) */}
              <div className="flex gap-2 mt-5 overflow-x-auto pb-1">
                {grupos.map((g, i) => (
                  <button key={g.propiedad.id} onClick={() => setSel(i)}
                    className={`shrink-0 px-3 py-2 rounded-xl text-[12px] border transition ${
                      i === sel ? 'border-[#B8893A] bg-[#B8893A]/10 text-primary' : 'border-border text-muted hover:bg-neutral-50 dark:hover:bg-[#1A1A1A]'
                    }`}>
                    <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${scoreColor(g.max_score)}`} />
                    {(g.propiedad.titulo || g.propiedad.direccion || `#${g.propiedad.id}`).slice(0, 18)}
                    <span className="ml-1 text-muted/70">({g.matches.length})</span>
                  </button>
                ))}
              </div>
            </div>

            {/* DERECHA: clientes que matchean (lista chica) */}
            <div className="card p-4">
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-3">
                Clientes que matchean
              </p>
              <div className="space-y-2">
                {actual?.matches.map(m => (
                  <div key={m.match_id} className="rounded-xl border border-border p-3 hover:border-[#B8893A]/40 transition group">
                    <div className="flex items-start gap-2.5">
                      <div className={`w-9 h-9 rounded-lg ${scoreColor(m.score)} text-white grid place-items-center text-[13px] font-bold shrink-0`}>
                        {m.score}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-[13px] truncate">{m.cliente_nombre}</p>
                        <p className="text-[11px] text-muted">pedido #{m.pedido_id} · {m.estado}</p>
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => accion(m.match_id, 'mostrado')} title="Marcar mostrado"
                          className="p-1.5 rounded-lg text-muted hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20"><Check size={14} /></button>
                        <button onClick={() => accion(m.match_id, 'descartado')} title="Descartar"
                          className="p-1.5 rounded-lg text-muted hover:text-danger hover:bg-danger/10"><X size={14} /></button>
                      </div>
                    </div>
                    {/* Razones del match (hover) */}
                    {m.razones?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {m.razones.map((r, i) => (
                          <span key={i} className="text-[10px] bg-neutral-100 dark:bg-[#1E1E1E] rounded px-1.5 py-0.5 text-muted">
                            +{r.puntos} {r.motivo}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
