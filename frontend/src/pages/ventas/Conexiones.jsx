import { useEffect, useState } from 'react'
import { Plug, Globe, Check, X, AlertTriangle, Loader2, Trash2, ShieldCheck } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ORO = '#B8893A'

export default function Conexiones() {
  const [estado, setEstado] = useState(null)
  const [webUser, setWebUser] = useState('')
  const [webPass, setWebPass] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [probando, setProbando] = useState(false)
  const [msg, setMsg] = useState(null)   // { ok, texto }
  const [err, setErr] = useState('')

  const cargar = async () => {
    try {
      const { data } = await api.get('/api/ventas-crm/conexiones/tokko')
      setEstado(data)
      setWebUser(data.web_user || '')
    } catch (e) {
      setErr(e?.response?.status === 403
        ? 'Solo un admin puede ver las conexiones.'
        : 'No se pudo cargar el estado de las conexiones.')
    }
  }
  useEffect(() => { cargar() }, [])

  const guardar = async () => {
    if (!webUser.trim()) { setMsg({ ok: false, texto: 'El usuario de Tokko es obligatorio.' }); return }
    setGuardando(true); setMsg(null)
    try {
      const body = { web_user: webUser.trim() }
      if (webPass) body.web_pass = webPass   // vacío = conservar la guardada
      const { data } = await api.put('/api/ventas-crm/conexiones/tokko', body)
      setEstado(data); setWebPass('')
      setMsg({ ok: true, texto: 'Credenciales guardadas. Probá la conexión para verificarlas.' })
    } catch (e) {
      setMsg({ ok: false, texto: e?.response?.data?.detail || 'No se pudo guardar.' })
    } finally { setGuardando(false) }
  }

  const probar = async () => {
    setProbando(true); setMsg(null)
    try {
      const { data } = await api.post('/api/ventas-crm/conexiones/tokko/probar')
      setEstado(data)
      setMsg({ ok: data.ok, texto: data.msg })
    } catch (e) {
      setMsg({ ok: false, texto: e?.response?.data?.detail || 'No se pudo probar la conexión.' })
    } finally { setProbando(false) }
  }

  const borrar = async () => {
    if (!window.confirm('¿Borrar las credenciales de Tokko de este negocio?')) return
    setMsg(null)
    try {
      const { data } = await api.delete('/api/ventas-crm/conexiones/tokko')
      setEstado(data); setWebUser(''); setWebPass('')
      setMsg({ ok: true, texto: 'Credenciales borradas.' })
    } catch (e) {
      setMsg({ ok: false, texto: e?.response?.data?.detail || 'No se pudo borrar.' })
    }
  }

  if (err) return <Layout><div className="max-w-3xl mx-auto py-20 text-center text-muted">{err}</div></Layout>
  if (!estado) return <Layout><div className="max-w-3xl mx-auto py-20 text-center text-muted">Cargando…</div></Layout>

  const conectado = estado.configurado
  const probOk = estado.ultima_prueba_ok

  return (
    <Layout>
      <div className="max-w-3xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Integraciones</div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2 flex items-center gap-2">
            <Plug style={{ color: ORO }} size={28} /> Conexiones
          </h1>
          <p className="hero-sub">Conectá los servicios externos de tu negocio. Cada negocio usa sus propias credenciales.</p>
        </header>

        {/* Tarjeta Tokko */}
        <div className="card p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: `${ORO}1A` }}>
                <Globe style={{ color: ORO }} size={20} />
              </div>
              <div>
                <p className="font-semibold text-[15px]">Red Tokko</p>
                <p className="text-[12px] text-muted">Traé propiedades de la red de colegas por zona.</p>
              </div>
            </div>
            <EstadoChip conectado={conectado} probOk={probOk} />
          </div>

          <p className="text-[12px] text-muted mb-4 leading-relaxed">
            Ingresá el <b>usuario y contraseña del panel web de Tokko</b> (los mismos con los que entrás a
            tokkobroker.com). La contraseña se guarda <b>cifrada</b> y no se muestra. No es la API key.
          </p>

          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Usuario de Tokko</label>
              <input className="input !py-2 text-[13px]" autoComplete="off"
                placeholder="usuario@tuinmobiliaria.com"
                value={webUser} onChange={e => setWebUser(e.target.value)} />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <input className="input !py-2 text-[13px]" type="password" autoComplete="new-password"
                placeholder={conectado ? '•••••••• (sin cambios)' : 'Tu contraseña de Tokko'}
                value={webPass} onChange={e => setWebPass(e.target.value)} />
            </div>
          </div>

          {msg && (
            <div className={`mt-4 px-4 py-2.5 rounded-xl text-[13px] flex items-start gap-2 ${
              msg.ok ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                     : 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20'}`}>
              {msg.ok ? <Check size={15} className="mt-0.5 shrink-0" /> : <AlertTriangle size={15} className="mt-0.5 shrink-0" />}
              <span>{msg.texto}</span>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 mt-5">
            <button className="btn-primary" onClick={guardar} disabled={guardando}>
              {guardando ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Guardar
            </button>
            <button className="btn-secondary" onClick={probar} disabled={probando || !conectado}>
              {probando ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />} Probar conexión
            </button>
            {conectado && estado.fuente === 'plataforma' && (
              <button className="btn-ghost text-red-500 ml-auto" onClick={borrar} title="Borrar credenciales">
                <Trash2 size={15} /> Borrar
              </button>
            )}
          </div>

          {(estado.ultima_prueba_at || estado.fuente === 'env') && (
            <div className="mt-4 pt-4 border-t border-border text-[12px] text-muted space-y-1">
              {estado.fuente === 'env' && (
                <p>Actualmente se usan credenciales del servidor (variables de entorno). Cargá las tuyas acá para gestionarlas desde la plataforma.</p>
              )}
              {estado.ultima_prueba_at && (
                <p className="flex items-center gap-1.5">
                  {probOk ? <Check size={13} className="text-emerald-500" /> : <X size={13} className="text-red-500" />}
                  Última prueba: {new Date(estado.ultima_prueba_at).toLocaleString('es-AR')} — {estado.ultima_prueba_msg}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}

function EstadoChip({ conectado, probOk }) {
  if (conectado && probOk) return <span className="chip-success text-[11px] flex items-center gap-1"><Check size={11} /> Conectado</span>
  if (conectado) return <span className="chip-muted text-[11px] flex items-center gap-1" style={{ color: ORO }}>Configurado — sin probar</span>
  return <span className="chip-muted text-[11px] flex items-center gap-1"><X size={11} /> Sin conectar</span>
}
