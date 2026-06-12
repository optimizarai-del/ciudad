import { useEffect, useState } from 'react'
import { Sparkles, Building2, Check, X, ChevronLeft, ChevronRight, Layers, Users } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const fmtUSD = n => n ? 'USD ' + n.toLocaleString('es-AR') : '—'
const scoreColor = s => s >= 80 ? 'bg-emerald-500' : s >= 65 ? 'bg-amber-500' : 'bg-sky-500'
const scoreText = s => s >= 80 ? 'text-emerald-600' : s >= 65 ? 'text-amber-600' : 'text-sky-600'

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
          <div className="flex items-end justify-between gap-3 flex-wrap">
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
          <>
            {/* Detalle: propiedad seleccionada (izq) + clientes que matchean (der) */}
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-4">

              {/* IZQUIERDA — propiedad */}
              <div className="card p-5 sm:p-6 min-w-0">
                <div className="flex items-center justify-between mb-4">
                  <button onClick={() => setSel(s => Math.max(0, s - 1))} disabled={sel === 0}
                    className="btn-ghost p-2 disabled:opacity-30"><ChevronLeft size={18} /></button>
                  <span className="text-[12px] text-muted">{sel + 1} de {grupos.length}</span>
                  <button onClick={() => setSel(s => Math.min(grupos.length - 1, s + 1))} disabled={sel === grupos.length - 1}
                    className="btn-ghost p-2 disabled:opacity-30"><ChevronRight size={18} /></button>
                </div>

                {actual && (
                  <>
                    <div className="rounded-2xl bg-neutral-100 dark:bg-[#141414] aspect-[16/9] grid place-items-center mb-4">
                      <Building2 size={48} className="text-muted/30" />
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="text-xl font-bold truncate">{actual.propiedad.titulo || actual.propiedad.direccion || `Propiedad #${actual.propiedad.id}`}</h2>
                        <p className="text-[13px] text-muted capitalize">{actual.propiedad.tipo} · {actual.propiedad.ciudad || 's/ciudad'}</p>
                      </div>
                      {actual.propiedad.fuente && actual.propiedad.fuente !== 'propia' && (
                        <span className="chip-muted capitalize shrink-0">{actual.propiedad.fuente}</span>
                      )}
                    </div>
                    <p className="stat-value text-2xl mt-2">{fmtUSD(actual.propiedad.precio_usd)}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[13px] text-muted">
                      {actual.propiedad.superficie_m2 && <span>{actual.propiedad.superficie_m2} m²</span>}
                      {actual.propiedad.dormitorios && <span>{actual.propiedad.dormitorios} dorm</span>}
                      {actual.propiedad.banos && <span>{actual.propiedad.banos} baños</span>}
                    </div>
                  </>
                )}
              </div>

              {/* DERECHA — clientes que matchean */}
              <div className="card p-4 min-w-0">
                <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-3 flex items-center gap-1.5">
                  <Users size={13} /> Clientes que matchean ({actual?.matches.length || 0})
                </p>
                <div className="space-y-2">
                  {actual?.matches.map(m => (
                    <div key={m.match_id} className="rounded-xl border border-border p-3 hover:border-[#B8893A]/40 transition">
                      <div className="flex items-start gap-2.5">
                        <div className={`w-10 h-10 rounded-lg ${scoreColor(m.score)} text-white grid place-items-center text-[14px] font-bold shrink-0`}>
                          {m.score}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-[13px] truncate">{m.cliente_nombre}</p>
                          <p className="text-[11px] text-muted">pedido #{m.pedido_id} · {m.estado}</p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button onClick={() => accion(m.match_id, 'mostrado')} title="Marcar mostrado"
                            className="p-1.5 rounded-lg text-muted hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20"><Check size={15} /></button>
                          <button onClick={() => accion(m.match_id, 'descartado')} title="Descartar"
                            className="p-1.5 rounded-lg text-muted hover:text-danger hover:bg-danger/10"><X size={15} /></button>
                        </div>
                      </div>
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

            {/* Selector — grilla de propiedades (cuadradas) */}
            <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mt-8 mb-3">
              Todas las propiedades con match
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {grupos.map((g, i) => (
                <button key={g.propiedad.id} onClick={() => setSel(i)}
                  className={`text-left rounded-2xl border p-3 transition ${
                    i === sel ? 'border-[#B8893A] bg-[#B8893A]/10 ring-2 ring-[#B8893A]/20'
                              : 'border-border bg-white dark:bg-[#141414] hover:border-[#B8893A]/40'
                  }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={`w-6 h-6 rounded-md ${scoreColor(g.max_score)} text-white grid place-items-center text-[11px] font-bold`}>
                      {g.max_score}
                    </span>
                    <span className="text-[11px] text-muted flex items-center gap-0.5"><Users size={10} />{g.matches.length}</span>
                  </div>
                  <p className="text-[12px] font-medium leading-tight line-clamp-2">{g.propiedad.titulo || g.propiedad.direccion || `#${g.propiedad.id}`}</p>
                  <p className="text-[11px] text-muted mt-0.5">{fmtUSD(g.propiedad.precio_usd)}</p>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
