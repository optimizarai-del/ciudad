import { useEffect, useState } from 'react'
import { FlaskConical, Mail, Send, CheckCircle2, XCircle, Loader2, ShieldCheck } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import { useAuth } from '../context/AuthContext'
import api from '../utils/api'

/**
 * Sección PRUEBAS (solo super admin). Banco de pruebas para verificar
 * funciones de la plataforma sin tocar producción (no procesa cobros ni
 * modifica datos). Primer item: "Disparo de emails".
 */
export default function Pruebas() {
  return (
    <Layout>
      <div className="max-w-4xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow flex items-center gap-1.5">
            <ShieldCheck size={13} /> Solo super admin
          </div>
          <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2 flex items-center gap-2">
            <FlaskConical className="text-[#B8893A]" size={30} /> Pruebas
          </h1>
          <p className="hero-sub">
            Probá herramientas y funciones de la plataforma de forma directa. Nada
            de lo que hagas acá procesa cobros ni modifica datos de producción.
          </p>
        </header>

        <DisparoEmails />
      </div>
    </Layout>
  )
}

function DisparoEmails() {
  const { user } = useAuth()
  const [estado, setEstado] = useState(null)
  const [destinatario, setDestinatario] = useState('')
  const [copia, setCopia] = useState('')
  const [conPdf, setConPdf] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [res, setRes] = useState(null)   // {ok, mensaje}

  useEffect(() => {
    api.get('/api/pruebas/email/estado').then(r => setEstado(r.data)).catch(() => setEstado(null))
    if (user?.email) setDestinatario(user.email)
  }, [user])

  const disparar = async () => {
    setEnviando(true); setRes(null)
    try {
      const { data } = await api.post('/api/pruebas/email/disparar', {
        destinatario: destinatario.trim(),
        copia: copia.trim() || null,
        con_pdf: conPdf,
      })
      setRes(data)
    } catch (e) {
      setRes({ ok: false, mensaje: e?.response?.data?.detail || 'Error al disparar el email.' })
    } finally { setEnviando(false) }
  }

  const ok = estado?.configurado
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-1">
        <Mail size={18} className="text-[#B8893A]" />
        <h2 className="text-[16px] font-semibold tracking-tight">Disparo de emails</h2>
      </div>
      <p className="text-[12px] text-muted mb-4">
        Manda un email de prueba con el mismo servicio que usan los comprobantes,
        para confirmar que el SMTP de producción quedó bien configurado.
      </p>

      {/* Estado de la config SMTP */}
      <div className={`rounded-xl px-3 py-2.5 mb-4 text-[12px] flex items-start gap-2 border ${
        ok ? 'bg-emerald-500/5 border-emerald-500/30 text-emerald-700 dark:text-emerald-400'
           : 'bg-danger/5 border-danger/30 text-danger'}`}>
        {ok ? <CheckCircle2 size={15} className="mt-0.5 shrink-0" /> : <XCircle size={15} className="mt-0.5 shrink-0" />}
        {estado == null ? (
          <span>Consultando configuración…</span>
        ) : ok ? (
          <span>
            SMTP configurado — <b>{estado.host}:{estado.port}</b>
            {estado.user ? <> · usuario <b>{estado.user}</b></> : null}
            {estado.from ? <> · remitente <b>{estado.from}</b></> : null}
          </span>
        ) : (
          <span>SMTP no configurado en este entorno (faltan SMTP_HOST / SMTP_USER). Cargá las variables en EasyPanel y redeploy.</span>
        )}
      </div>

      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="label">Enviar a</label>
          <input className="input !py-2 text-[13px]" type="email" placeholder="correo@ejemplo.com"
            value={destinatario} onChange={e => setDestinatario(e.target.value)} />
        </div>
        <div>
          <label className="label">Copia (opcional)</label>
          <input className="input !py-2 text-[13px]" type="email" placeholder="otra@ejemplo.com"
            value={copia} onChange={e => setCopia(e.target.value)} />
        </div>
      </div>

      <label className="flex items-center gap-2 text-[13px] mb-4 cursor-pointer w-fit">
        <input type="checkbox" checked={conPdf} onChange={e => setConPdf(e.target.checked)} />
        Adjuntar un PDF de ejemplo (como en un comprobante real)
      </label>

      <button className="btn-primary" disabled={enviando || !destinatario.trim()} onClick={disparar}>
        {enviando ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
        {enviando ? 'Enviando…' : 'Disparar email de prueba'}
      </button>

      {res && (
        <div className={`mt-4 rounded-xl px-4 py-3 text-[13px] flex items-start gap-2 border ${
          res.ok ? 'bg-emerald-500/5 border-emerald-500/30 text-emerald-700 dark:text-emerald-400'
                 : 'bg-danger/5 border-danger/30 text-danger'}`}>
          {res.ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
          <div>
            <p className="font-medium">{res.ok ? '¡Email enviado!' : 'No se pudo enviar'}</p>
            <p className="text-[12px] opacity-80 mt-0.5">
              {res.ok
                ? `Revisá la bandeja de ${res.destinatario}${res.con_pdf ? ' (con PDF adjunto)' : ''}.`
                : res.mensaje}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
