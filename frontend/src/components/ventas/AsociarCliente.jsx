import { useState, useEffect } from 'react'
import { UserPlus, X, Check } from 'lucide-react'
import api from '../../utils/api'

/**
 * Botón + modal para asociar una propiedad (de cualquier fuente: instagram,
 * web/scraping, red tokko o catálogo) a un cliente del CRM de Ventas.
 *
 * Props:
 *   propiedad: {
 *     fuente: 'instagram'|'web'|'tokko'|'catalogo',
 *     ref_externa, propiedad_id?, titulo, direccion, precio_texto,
 *     operacion?, imagen_url?, link_externo?
 *   }
 *   className: clases para el botón (opcional)
 *   label: texto del botón (opcional; si no, solo ícono)
 */
export default function AsociarCliente({ propiedad, className = '', label = '' }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [clientes, setClientes] = useState([])
  const [loading, setLoading] = useState(false)
  const [okMsg, setOkMsg] = useState('')
  const [errMsg, setErrMsg] = useState('')
  const [saving, setSaving] = useState(null)

  const cargar = async (query = '') => {
    setLoading(true)
    try {
      const { data } = await api.get(
        `/api/ventas-crm/clientes?limit=50${query ? `&q=${encodeURIComponent(query)}` : ''}`
      )
      setClientes(Array.isArray(data) ? data : [])
    } catch { setClientes([]) } finally { setLoading(false) }
  }

  useEffect(() => { if (open) { setQ(''); setOkMsg(''); setErrMsg(''); cargar('') } }, [open])

  const asociar = async (cli) => {
    setSaving(cli.id); setOkMsg(''); setErrMsg('')
    try {
      const { data } = await api.post('/api/ventas-crm/selecciones', { cliente_id: cli.id, ...propiedad })
      setOkMsg(data.ya_existia ? `Ya estaba asociada a ${cli.nombre}` : `Asociada a ${cli.nombre}`)
      setTimeout(() => { setOpen(false) }, 1600)
    } catch (e) {
      setErrMsg(e?.response?.data?.detail || 'Error al asociar')
    } finally { setSaving(null) }
  }

  return (
    <>
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(true) }}
        className={className || 'btn-ghost !p-1.5'}
        title="Asociar a un cliente"
      >
        <UserPlus size={14} />{label ? <span className="ml-1 text-[12px]">{label}</span> : null}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4"
          onClick={() => setOpen(false)}>
          <div className="card w-full max-w-md p-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <p className="font-semibold text-[15px]">Asociar a un cliente</p>
              <button onClick={() => setOpen(false)} className="btn-ghost !p-1"><X size={16} /></button>
            </div>

            {(propiedad?.titulo || propiedad?.direccion) && (
              <p className="text-[12px] text-muted mb-3 truncate">
                {propiedad.titulo || propiedad.direccion}
                {propiedad.precio_texto ? ` · ${propiedad.precio_texto}` : ''}
              </p>
            )}

            <input
              className="input !py-2 text-[13px] mb-2" placeholder="Buscar cliente por nombre, tel o email…"
              value={q} autoFocus
              onChange={e => { setQ(e.target.value); cargar(e.target.value) }}
            />

            {okMsg && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-[13px] text-emerald-400">
                <Check size={15} className="shrink-0" />{okMsg}
              </div>
            )}
            {errMsg && (
              <div className="mb-2 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-[13px] text-red-400">
                {errMsg}
              </div>
            )}

            <div className="max-h-72 overflow-y-auto divide-y divide-border">
              {loading ? (
                <p className="text-[13px] text-muted py-6 text-center">Cargando…</p>
              ) : clientes.length === 0 ? (
                <p className="text-[13px] text-muted py-6 text-center">
                  Sin clientes. Creá uno en la sección Clientes.
                </p>
              ) : clientes.map(c => (
                <button key={c.id} onClick={() => asociar(c)} disabled={saving === c.id}
                  className="w-full flex items-center justify-between py-2 px-1 hover:bg-[#B8893A]/5 text-left rounded-lg">
                  <span className="text-[13px]">
                    {c.nombre}{c.telefono ? <span className="text-muted"> · {c.telefono}</span> : ''}
                  </span>
                  {saving === c.id
                    ? <span className="text-[12px] text-muted">…</span>
                    : <Check size={14} className="text-muted" />}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
