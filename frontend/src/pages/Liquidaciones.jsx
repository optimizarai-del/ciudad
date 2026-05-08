import { useEffect, useState } from 'react'
import {
  ChevronLeft, ChevronRight, Download, FileText, Send, AlertTriangle,
  CheckCircle, KeyRound, RefreshCw,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

const fmt$ = n => `$${(Number(n) || 0).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`
const prevMes = m => { const [y, mm] = m.split('-').map(Number); return mm === 1 ? `${y - 1}-12` : `${y}-${String(mm - 1).padStart(2, '0')}` }
const nextMes = m => { const [y, mm] = m.split('-').map(Number); return mm === 12 ? `${y + 1}-01` : `${y}-${String(mm + 1).padStart(2, '0')}` }
const mesLabel = m => { const [y, mm] = m.split('-').map(Number); return new Date(y, mm - 1, 1).toLocaleString('es-AR', { month: 'long', year: 'numeric' }) }

export default function Liquidaciones() {
  const hoy = new Date()
  const [mes, setMes] = useState(`${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [emitir, setEmitir]   = useState(null)   // resultado del POST
  const [emitiendo, setEm]    = useState(false)
  const [enviarEmail, setEnv] = useState(true)

  const cargar = () => {
    setLoading(true); setEmitir(null)
    api.get(`/api/liquidaciones/preview?mes=${mes}`)
      .then(r => setPreview(r.data))
      .finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [mes])

  const ejecutar = async () => {
    if (!confirm(`Emitir liquidaciones para ${preview.total_propietarios} propietario(s)?`)) return
    setEm(true)
    try {
      const r = await api.post('/api/liquidaciones/emitir', { periodo: mes, enviar_email: enviarEmail })
      setEmitir(r.data)
      cargar()
    } catch (e) {
      alert(e.response?.data?.detail || 'Error al emitir el lote')
    } finally { setEm(false) }
  }

  const descargar = async (id) => {
    try {
      const r = await api.get(`/api/comprobantes/${id}/pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
      const a = document.createElement('a'); a.href = url; a.download = `liquidacion-${id}.pdf`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { alert('No se pudo descargar el PDF') }
  }

  return (
    <Layout>
      <div className="p-6 space-y-5 max-w-6xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 dark:text-gray-500 uppercase mb-1">Alquileres</p>
            <h1 className="text-3xl font-black">Liquidaciones masivas</h1>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
              Genera un PDF consolidado por propietario con todos sus pagos cobrados del mes.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setMes(prevMes(mes))} className="btn-ghost p-2"><ChevronLeft size={16} /></button>
            <span className="text-sm font-semibold capitalize min-w-[160px] text-center">{mesLabel(mes)}</span>
            <button onClick={() => setMes(nextMes(mes))} className="btn-ghost p-2"><ChevronRight size={16} /></button>
          </div>
        </div>

        {/* Resumen del lote */}
        {preview && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPI label="Propietarios" value={preview.total_propietarios} icon={KeyRound} />
            <KPI label="Pagos cobrados" value={preview.total_pagos} />
            <KPI label="Cobrado total" value={fmt$(preview.monto_cobrado_total)} color="text-green-600 dark:text-green-400" />
            <KPI label="Neto a transferir" value={fmt$(preview.neto_total_propietarios)} color="text-[#B8893A]" />
          </div>
        )}

        {/* Preview detalle */}
        <div className="card overflow-hidden">
          <div className="px-6 py-4 flex items-center justify-between border-b border-border dark:border-[#2A2A2A] flex-wrap gap-3">
            <p className="font-semibold text-[14px]">Vista previa del lote</p>
            <div className="flex items-center gap-3">
              <label className="text-[12px] text-gray-500 dark:text-gray-400 flex items-center gap-2 select-none">
                <input type="checkbox" checked={enviarEmail} onChange={e => setEnv(e.target.checked)} />
                Enviar por email al emitir
              </label>
              <button className="btn-secondary text-[12px] py-1.5 px-3" onClick={cargar} disabled={loading}>
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Recargar
              </button>
              <button className="btn-primary" onClick={ejecutar}
                disabled={emitiendo || !preview || !preview.total_propietarios}>
                <Send size={13} className={emitiendo ? 'animate-pulse' : ''} />
                {emitiendo ? 'Emitiendo…' : 'Emitir lote'}
              </button>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-sm text-gray-400 dark:text-gray-500 text-center">Cargando…</div>
          ) : !preview || preview.total_propietarios === 0 ? (
            <div className="p-10 text-center">
              <FileText size={32} className="mx-auto text-gray-300 dark:text-gray-700 mb-2" />
              <p className="text-sm text-gray-400 dark:text-gray-500">
                No hay pagos cobrados para liquidar en {mes}. Registra cobranzas y volvé a esta pantalla.
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border dark:border-[#2A2A2A]">
                <tr>
                  <th className="th text-left">Propietario</th>
                  <th className="th text-right hidden md:table-cell">Propiedades</th>
                  <th className="th text-right">Cobrado</th>
                  <th className="th text-right">Comisión</th>
                  <th className="th text-right">Neto</th>
                  <th className="th text-center">Email</th>
                </tr>
              </thead>
              <tbody>
                {preview.propietarios.map(p => (
                  <tr key={p.propietario_id} className="border-b border-gray-100 dark:border-[#2A2A2A] hover:bg-gray-50 dark:hover:bg-[#1A1A1A]">
                    <td className="td">
                      <p className="font-medium text-sm">{p.nombre}</p>
                      <p className="text-[11px] text-gray-400 dark:text-gray-500">{p.documento || '—'}</p>
                    </td>
                    <td className="td text-right text-sm hidden md:table-cell">{p.items.length}</td>
                    <td className="td text-right font-semibold">{fmt$(p.totales.cobrado_total)}</td>
                    <td className="td text-right text-amber-600">−{fmt$(p.totales.comision)}</td>
                    <td className="td text-right font-semibold text-[#B8893A]">{fmt$(p.totales.neto)}</td>
                    <td className="td text-center text-[11px] text-gray-500 dark:text-gray-400">{p.email || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Resultado del lote */}
        {emitir && (
          <div className="card p-5 border-l-4 border-[#B8893A]">
            <div className="flex items-center gap-3 mb-3">
              <CheckCircle size={20} className="text-green-600 dark:text-green-400" />
              <div>
                <p className="font-semibold">Lote emitido — {emitir.periodo}</p>
                <p className="text-[12px] text-muted dark:text-gray-500">
                  {emitir.total_propietarios} propietario(s) · neto total {fmt$(emitir.neto_total_propietarios)}
                </p>
              </div>
            </div>
            {!emitir.smtp_configurado && (
              <p className="text-[11px] bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900 rounded-xl p-3 mb-3 flex items-start gap-2">
                <AlertTriangle size={12} className="text-amber-600 mt-0.5 shrink-0" />
                <span>SMTP no configurado: los PDFs quedaron guardados y se pueden descargar desde acá.</span>
              </p>
            )}
            <div className="space-y-2">
              {emitir.salidas.map(s => (
                <div key={s.comprobante_id} className="flex items-center gap-3 p-2.5 rounded-xl border border-border dark:border-[#2A2A2A]">
                  <FileText size={14} className="text-muted dark:text-gray-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium truncate">{s.propietario}</p>
                    <p className="text-[11px] text-muted dark:text-gray-500 truncate">
                      {s.email_destinatario || 'sin email'} ·{' '}
                      {s.enviado_email
                        ? <span className="text-green-600 dark:text-green-400">enviado ✓</span>
                        : <span className="text-amber-600">{s.error_envio}</span>}
                    </p>
                  </div>
                  <span className="text-[13px] font-semibold text-[#B8893A]">{fmt$(s.neto)}</span>
                  <button className="btn-secondary text-[11px] py-1 px-2.5" onClick={() => descargar(s.comprobante_id)}>
                    <Download size={11} /> PDF
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}

function KPI({ label, value, color = '', icon: Icon }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-2">
        <p className="text-[10px] uppercase tracking-widest text-gray-400 dark:text-gray-500 font-semibold">{label}</p>
        {Icon && <Icon size={14} className="text-gray-300 dark:text-gray-600" />}
      </div>
      <p className={`text-2xl font-black ${color}`}>{value}</p>
    </div>
  )
}
