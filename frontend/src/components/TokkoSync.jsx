import { useEffect, useState } from 'react'
import { X, RefreshCw, Download, CheckCircle, AlertCircle, Building2, Key } from 'lucide-react'
import api from '../utils/api'

export default function TokkoSync({ onClose, onSynced }) {
  const [status, setStatus]     = useState(null)
  const [preview, setPreview]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [syncing, setSyncing]   = useState(false)
  const [result, setResult]     = useState(null)
  const [err, setErr]           = useState('')

  useEffect(() => {
    api.get('/api/tokko/status').then(r => setStatus(r.data)).catch(() => {})
  }, [])

  const cargarPreview = () => {
    setLoading(true); setErr(''); setPreview(null)
    api.get('/api/tokko/preview')
      .then(r => setPreview(r.data))
      .catch(e => setErr(e.response?.data?.detail || 'Error al conectar con Tokko.'))
      .finally(() => setLoading(false))
  }

  const sincronizar = () => {
    setSyncing(true); setErr('')
    api.post('/api/tokko/sync')
      .then(r => { setResult(r.data); onSynced?.() })
      .catch(e => setErr(e.response?.data?.detail || 'Error al sincronizar.'))
      .finally(() => setSyncing(false))
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4"
      onClick={onClose}>
      <div className="card w-full max-w-xl shadow-lift animate-scale-in flex flex-col max-h-[88vh]"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="px-6 py-5 border-b border-[#E5E5E5] dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-2xl mb-0.5">Sync Tokko Broker.</h2>
            <p className="text-[12px] text-[#737373] dark:text-[#7A7A7A]">
              Importar propiedades desde tu cuenta de Tokko
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

          {/* Estado de configuración */}
          {status !== null && (
            <div className={`flex items-center gap-3 p-4 rounded-2xl border
              ${status.configurado
                ? 'border-success/20 bg-success/5 dark:bg-success/10'
                : 'border-[#E5E5E5] dark:border-[#2A2A2A] bg-[#F9F9F9] dark:bg-[#141414]'
              }`}>
              {status.configurado
                ? <CheckCircle size={18} className="text-success shrink-0" />
                : <Key size={18} className="text-[#737373] dark:text-[#9A9A9A] shrink-0" />
              }
              <div className="text-[13px]">
                {status.configurado ? (
                  <span className="text-success font-medium">API Key configurada ✓</span>
                ) : (
                  <span className="text-[#0A0A0A] dark:text-[#E0E0E0]">
                    Configurá <code className="bg-[#E8E8E8] dark:bg-[#2A2A2A] px-1 py-0.5 rounded text-[11px]">TOKKO_API_KEY</code> en el archivo <code className="bg-[#E8E8E8] dark:bg-[#2A2A2A] px-1 py-0.5 rounded text-[11px]">backend/.env</code>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Instrucciones si no está configurado */}
          {status?.configurado === false && (
            <div className="p-4 rounded-2xl border border-[#E5E5E5] dark:border-[#2A2A2A] text-[12px] text-[#737373] dark:text-[#9A9A9A] space-y-2">
              <p className="font-semibold text-[#0A0A0A] dark:text-[#E0E0E0] text-[13px]">Cómo configurar:</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>Abrí el archivo <code className="bg-[#E8E8E8] dark:bg-[#2A2A2A] px-1 rounded">backend/.env</code></li>
                <li>Agregá la línea: <code className="bg-[#E8E8E8] dark:bg-[#2A2A2A] px-1 rounded">TOKKO_API_KEY=tu_api_key</code></li>
                <li>Reiniciá el backend</li>
              </ol>
              <p>Encontrás tu API Key en <strong>Tokko Broker → Configuración → API</strong>.</p>
            </div>
          )}

          {/* Preview de propiedades */}
          {preview && !result && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-[13px] font-semibold">
                  {preview.total} propiedades encontradas en Tokko
                </p>
                <div className="flex gap-2 text-[11px]">
                  <span className="chip-success">{preview.propiedades.filter(p => p.ya_importada).length} ya importadas</span>
                  <span className="chip-gray">{preview.propiedades.filter(p => !p.ya_importada).length} nuevas</span>
                </div>
              </div>
              <div className="space-y-2 max-h-52 overflow-y-auto">
                {preview.propiedades.map((p, i) => (
                  <div key={i} className={`flex items-center gap-3 p-3 rounded-xl border transition
                    ${p.ya_importada
                      ? 'border-[#E5E5E5] dark:border-[#2A2A2A] opacity-60'
                      : 'border-[#D4D4D4] dark:border-[#3A3A3A] bg-[#FAFAFA] dark:bg-[#1A1A1A]'
                    }`}>
                    <div className="w-7 h-7 rounded-xl bg-[#F0F0F0] dark:bg-[#2A2A2A] grid place-items-center shrink-0">
                      <Building2 size={13} className="text-[#737373]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium truncate">{p.direccion}</p>
                      <p className="text-[10px] text-[#737373] dark:text-[#7A7A7A] capitalize">
                        {p.tipo} · {p.ciudad} · {p.ambientes && `${p.ambientes} amb.`}
                        {p.precio_alquiler > 0 && ` · $${Number(p.precio_alquiler).toLocaleString('es-AR')}`}
                      </p>
                    </div>
                    {p.ya_importada && (
                      <span className="chip-gray text-[10px]">Importada</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resultado */}
          {result && (
            <div className="p-5 rounded-2xl border border-success/20 bg-success/5 dark:bg-success/10 text-center">
              <CheckCircle size={32} className="mx-auto text-success mb-3" />
              <p className="font-semibold text-[15px] mb-1">¡Sincronización exitosa!</p>
              <div className="flex justify-center gap-4 text-[13px] text-[#737373] dark:text-[#9A9A9A]">
                <span><strong className="text-success">{result.importadas}</strong> importadas</span>
                <span><strong className="text-[#0A0A0A] dark:text-white">{result.actualizadas}</strong> actualizadas</span>
              </div>
            </div>
          )}

          {err && (
            <div className="flex items-start gap-2 p-3 rounded-xl bg-danger/5 border border-danger/20 text-[12px] text-danger">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              {err}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[#E5E5E5] dark:border-[#2A2A2A] flex gap-3 shrink-0">
          {result ? (
            <button className="btn-primary flex-1" onClick={onClose}>Cerrar</button>
          ) : (
            <>
              <button className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
              {!preview ? (
                <button className="btn-primary flex-1" onClick={cargarPreview}
                  disabled={loading || !status?.configurado}>
                  <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                  {loading ? 'Cargando…' : 'Ver preview'}
                </button>
              ) : (
                <button className="btn-primary flex-1" onClick={sincronizar} disabled={syncing}>
                  <Download size={13} className={syncing ? 'animate-pulse' : ''} />
                  {syncing ? 'Importando…' : `Importar ${preview.propiedades.filter(p => !p.ya_importada).length} propiedades`}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
