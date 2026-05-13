import { useEffect, useRef, useState } from 'react'
import { X, RefreshCw, Building2, ExternalLink, CheckCircle2, AlertCircle } from 'lucide-react'
import api from '../utils/api'


/**
 * Modal "Buscar tasa en Municipalidad de Santa Rosa".
 *
 * Flujo:
 *  1. Pide config al backend → sitekey reCAPTCHA del municipio.
 *  2. Carga script https://www.google.com/recaptcha/api.js (una sola vez).
 *  3. Renderiza el widget reCAPTCHA v2 (checkbox).
 *  4. Cuando el usuario lo resuelve, recibe un token.
 *  5. POST al backend con {captcha_token}. El backend reenvía a la muni,
 *     parsea cuotas, guarda en la DB y devuelve el detalle.
 *  6. Mostramos la tabla de cuotas y la tasa de referencia.
 */
export default function ModalTasaMSR({ propiedad, onClose, onActualizado }) {
  const [config, setConfig] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [resultado, setResultado] = useState(null)
  const widgetRef = useRef(null)
  const widgetId = useRef(null)

  // Config inicial
  useEffect(() => {
    api.get('/api/tasas-msr/config').then(r => setConfig(r.data))
      .catch(() => setConfig({ habilitado: false }))
  }, [])

  // Cargar reCAPTCHA script y renderizar widget
  useEffect(() => {
    if (!config?.habilitado || !config?.sitekey) return

    const renderWidget = () => {
      if (!window.grecaptcha || !widgetRef.current) return
      if (widgetId.current !== null) return  // ya renderizado
      try {
        widgetId.current = window.grecaptcha.render(widgetRef.current, {
          sitekey: config.sitekey,
          callback: t => setToken(t),
          'expired-callback': () => setToken(null),
          'error-callback':   () => setToken(null),
        })
      } catch (e) {
        console.error('reCAPTCHA render fail', e)
      }
    }

    // El script ya puede estar cargado de antes; si no, lo cargamos
    if (window.grecaptcha && window.grecaptcha.render) {
      renderWidget()
    } else {
      const exists = document.querySelector('script[src*="recaptcha/api.js"]')
      if (!exists) {
        const s = document.createElement('script')
        s.src = 'https://www.google.com/recaptcha/api.js?render=explicit'
        s.async = true; s.defer = true
        document.head.appendChild(s)
      }
      const i = setInterval(() => {
        if (window.grecaptcha && window.grecaptcha.render) {
          clearInterval(i)
          renderWidget()
        }
      }, 200)
      return () => clearInterval(i)
    }
  }, [config])

  const consultar = async () => {
    if (!token) { setErr('Marcá "No soy un robot" primero.'); return }
    setLoading(true); setErr(''); setResultado(null)
    try {
      const r = await api.post(`/api/propiedades/${propiedad.id}/consultar-tasa-msr`, {
        captcha_token: token,
      })
      setResultado(r.data)
      onActualizado?.(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al consultar la municipalidad')
      // Resetear captcha porque el token es de un solo uso
      if (window.grecaptcha && widgetId.current !== null) {
        window.grecaptcha.reset(widgetId.current)
      }
      setToken(null)
    } finally { setLoading(false) }
  }

  const fmt = (v) => v == null ? '—' : `$ ${Number(v).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card w-full max-w-2xl shadow-lift animate-scale-in flex flex-col max-h-[90vh] my-6"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="px-6 py-5 border-b border-border dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-2xl mb-0.5 flex items-center gap-2">
              <Building2 size={20} /> Tasa Municipal.
            </h2>
            <p className="text-[12px] text-muted dark:text-gray-500">
              {propiedad.direccion}
              {propiedad.numero_referencia && (
                <> · Padrón: <span className="font-mono">{propiedad.numero_referencia}</span></>
              )}
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

          {!propiedad.numero_referencia && (
            <div className="card p-4 border-l-4 !border-l-warn bg-warn/5 flex items-start gap-3">
              <AlertCircle size={18} className="text-warn shrink-0 mt-0.5" />
              <div>
                <p className="text-[13px] font-medium">Falta cargar el número de referencia.</p>
                <p className="text-[12px] text-muted dark:text-gray-500 mt-1">
                  Editá la propiedad y completá el campo "Nº de referencia municipal" (padrón) antes de consultar.
                </p>
              </div>
            </div>
          )}

          {config === null && (
            <p className="text-center text-muted text-[13px] py-6">Cargando configuración…</p>
          )}

          {config && !config.habilitado && (
            <div className="card p-4 border-l-4 !border-l-danger bg-danger/5">
              <p className="text-[13px] font-medium text-danger">Servicio no configurado.</p>
              <p className="text-[12px] text-muted mt-1">
                El admin debe setear la env var <code>MSR_RECAPTCHA_SITEKEY</code> con
                el sitekey público de reCAPTCHA del portal de la Municipalidad
                de Santa Rosa.
              </p>
              <a href="https://consultadeuda.santarosa.gob.ar/" target="_blank" rel="noreferrer"
                className="text-[12px] text-primary dark:text-white hover:underline mt-2 inline-flex items-center gap-1">
                Abrir portal de la municipalidad <ExternalLink size={11} />
              </a>
            </div>
          )}

          {config?.habilitado && propiedad.numero_referencia && !resultado && (
            <>
              <p className="text-[13px] text-muted dark:text-gray-400">
                Marcá la verificación y tocá <strong>Consultar</strong>. La consulta usa los datos
                del portal oficial <span className="font-mono text-[11px]">consultadeuda.santarosa.gob.ar</span> y
                el monto se guarda en la propiedad.
              </p>
              <div ref={widgetRef} className="flex justify-center" />
              <button
                className="btn-primary w-full"
                onClick={consultar}
                disabled={!token || loading}
              >
                <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                {loading ? 'Consultando…' : 'Consultar deuda actual'}
              </button>
            </>
          )}

          {err && (
            <div className="card p-3 bg-danger/5 border border-danger/20 flex items-start gap-2">
              <AlertCircle size={14} className="text-danger shrink-0 mt-0.5" />
              <p className="text-[12px] text-danger">{err}</p>
            </div>
          )}

          {resultado && (
            <div className="space-y-3">
              <div className="card p-4 border-l-4 !border-l-success bg-success/5 flex items-start gap-3">
                <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-[13px] font-medium">Consulta exitosa</p>
                  <p className="text-[12px] text-muted dark:text-gray-500 mt-0.5">
                    {resultado.cantidad} cuota(s) · total <strong>{fmt(resultado.total)}</strong>
                    {resultado.tasa_municipal > 0 && (
                      <> · tasa actual guardada: <strong>{fmt(resultado.tasa_municipal)}</strong></>
                    )}
                  </p>
                </div>
              </div>

              {resultado.cuotas?.length > 0 && (
                <div className="card overflow-hidden">
                  <div className="px-4 py-2.5 border-b border-border dark:border-[#2A2A2A] bg-neutral-50 dark:bg-[#141414]">
                    <p className="text-[11px] uppercase tracking-wider text-muted font-semibold">Detalle de cuotas</p>
                  </div>
                  <ul className="divide-y divide-border dark:divide-[#2A2A2A]">
                    {resultado.cuotas.slice(0, 20).map((c, i) => (
                      <li key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-[12px] font-medium">{c.periodo || c.concepto || `Cuota ${i + 1}`}</p>
                          <p className="text-[10px] text-muted dark:text-gray-500">
                            {c.vencimiento || ''} {c.estado ? `· ${c.estado}` : ''}
                          </p>
                        </div>
                        <p className="text-[13px] font-semibold tabular-nums">{fmt(c.importe)}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-3 border-t border-border dark:border-[#2A2A2A] flex justify-between items-center shrink-0">
          <a href="https://consultadeuda.santarosa.gob.ar/" target="_blank" rel="noreferrer"
            className="text-[11px] text-muted hover:text-primary dark:hover:text-white inline-flex items-center gap-1">
            Abrir portal MSR <ExternalLink size={10} />
          </a>
          <button className="btn-secondary text-[12px] py-1.5 px-4" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  )
}
