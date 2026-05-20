import { useEffect, useState } from 'react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import {
  HardDrive, Download, Clock, Database, Package,
  CheckCircle, AlertCircle, Loader2, Info,
} from 'lucide-react'

// ─── Formateo de números estilo Argentina (300.000,54) ───────────────────────
const fmtNum = (n, decimals = 0) =>
  new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n ?? 0)

const fmtBytes = (bytes) => {
  if (!bytes) return '—'
  if (bytes < 1024)       return `${fmtNum(bytes)} B`
  if (bytes < 1024 ** 2)  return `${fmtNum(bytes / 1024, 2)} KB`
  if (bytes < 1024 ** 3)  return `${fmtNum(bytes / 1024 ** 2, 2)} MB`
  return `${fmtNum(bytes / 1024 ** 3, 2)} GB`
}

const fmtFecha = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-AR', {
    day:    '2-digit',
    month:  '2-digit',
    year:   'numeric',
    hour:   '2-digit',
    minute: '2-digit',
  })
}

// Total de filas exportadas sumando todas las tablas
const totalFilas = (tablas = {}) =>
  Object.values(tablas).reduce((s, n) => s + (Number(n) || 0), 0)


export default function VersionesLocal() {
  const [versiones, setVersiones]   = useState([])
  const [loading, setLoading]       = useState(true)
  const [generando, setGenerando]   = useState(false)
  const [error, setError]           = useState('')
  const [exito, setExito]           = useState('')

  const cargar = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/versiones')
      setVersiones(r.data)
    } catch {
      setError('No se pudo cargar el historial de versiones.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { cargar() }, [])

  const descargar = async () => {
    if (generando) return
    setGenerando(true)
    setError('')
    setExito('')
    try {
      // Pedir el ZIP — puede tardar un minuto mientras exporta la DB y empaqueta
      const r = await api.post('/api/versiones/crear', {}, { responseType: 'blob', timeout: 300_000 })

      // Extraer nombre del archivo del header Content-Disposition
      const cd     = r.headers['content-disposition'] || ''
      const match  = cd.match(/filename="?([^";\n]+)"?/)
      const nombre = match ? match[1] : `ciudad-v${Date.now()}.zip`

      // Trigger descarga en el navegador
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/zip' }))
      const a   = document.createElement('a')
      a.href     = url
      a.download = nombre
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 2000)

      setExito(`Versión "${nombre}" descargada correctamente.`)
      cargar()   // refrescar historial
    } catch (e) {
      setError(
        e.response?.data?.detail
          || 'Error generando la versión. Revisá los logs del servidor.'
      )
    } finally {
      setGenerando(false)
    }
  }

  const tablasOrdenadas = (tablas = {}) =>
    Object.entries(tablas)
      .filter(([, n]) => n > 0)
      .sort(([, a], [, b]) => b - a)

  return (
    <Layout>
      <div className="p-6 space-y-6 max-w-4xl mx-auto">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs font-semibold tracking-widest text-gray-400 dark:text-gray-500 uppercase mb-1">
              Herramientas
            </p>
            <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">
              Versiones local
            </h1>
            <p className="text-sm text-muted max-w-xl">
              Descargá un ZIP con todo el sistema listo para correr sin internet.
              Incluye el código fuente y una copia fija de la base de datos.
            </p>
          </div>

          <button
            onClick={descargar}
            disabled={generando}
            className="btn-primary gap-2 shrink-0 min-w-[200px] justify-center"
          >
            {generando
              ? <><Loader2 size={15} className="animate-spin" /> Generando…</>
              : <><Download size={15} /> Descargar versión</>
            }
          </button>
        </div>

        {/* Mensajes */}
        {error && (
          <div className="flex items-start gap-3 p-4 rounded-2xl bg-danger/5 border border-danger/20 text-danger text-sm">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            {error}
          </div>
        )}
        {exito && (
          <div className="flex items-start gap-3 p-4 rounded-2xl bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 text-sm">
            <CheckCircle size={16} className="shrink-0 mt-0.5" />
            {exito}
          </div>
        )}

        {/* Spinner de generación */}
        {generando && (
          <div className="card p-6 flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-[#0A0A0A] dark:bg-white grid place-items-center shrink-0">
              <Package size={22} className="text-white dark:text-[#0A0A0A] animate-pulse" />
            </div>
            <div>
              <p className="font-semibold text-sm">Generando snapshot…</p>
              <p className="text-xs text-muted mt-0.5">
                Exportando la base de datos y empaquetando el código.
                Puede tardar hasta un minuto dependiendo del volumen de datos.
              </p>
            </div>
          </div>
        )}

        {/* Cómo funciona */}
        <div className="card p-5 bg-[#FAF8F3] dark:bg-[#141410] border-[#E8E0CC] dark:border-[#2A2518]">
          <div className="flex items-center gap-2 mb-3">
            <Info size={14} className="text-[#B8893A]" />
            <p className="text-[12px] font-semibold uppercase tracking-widest text-[#B8893A]">
              Cómo funciona
            </p>
          </div>
          <div className="grid sm:grid-cols-3 gap-4 text-[12px] text-muted">
            <Step n="1" title="Descargá el ZIP">
              Hacé clic en "Descargar versión". Se genera un ZIP con todo lo necesario.
            </Step>
            <Step n="2" title="Extraé la carpeta">
              Descomprimí el ZIP en cualquier carpeta de tu computadora.
            </Step>
            <Step n="3" title="Doble clic y listo">
              Ejecutá <code className="bg-black/10 dark:bg-white/10 px-1 rounded">INICIAR.bat</code> (Windows)
              o <code className="bg-black/10 dark:bg-white/10 px-1 rounded">iniciar.sh</code> (Mac/Linux).
              El sistema arranca y abre el navegador automáticamente.
            </Step>
          </div>
          <p className="text-[11px] text-muted mt-4 border-t border-[#E8E0CC] dark:border-[#2A2518] pt-3">
            <strong>Requisitos:</strong> Python 3.10+ y Node.js 18+ instalados en la computadora.
            Sin Node.js el sistema funciona sólo a nivel API (sin interfaz visual).
            La base de datos es una copia fija del momento de la descarga — los cambios locales
            no se sincronizan con la nube.
          </p>
        </div>

        {/* Historial */}
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted mb-3">
            Historial de descargas
          </h2>

          {loading ? (
            <div className="card p-8 text-center text-sm text-muted">Cargando…</div>
          ) : versiones.length === 0 ? (
            <div className="card p-10 text-center">
              <HardDrive size={28} className="text-muted mx-auto mb-3" />
              <p className="text-sm text-muted">
                Todavía no generaste ninguna versión local.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {versiones.map((v, idx) => (
                <VersionCard
                  key={v.id}
                  version={v}
                  esUltima={idx === 0}
                  tablasOrdenadas={tablasOrdenadas}
                />
              ))}
            </div>
          )}
        </div>

      </div>
    </Layout>
  )
}


function Step({ n, title, children }) {
  return (
    <div className="flex gap-2.5">
      <span className="w-5 h-5 rounded-full bg-[#B8893A]/20 text-[#B8893A] text-[10px] font-bold grid place-items-center shrink-0 mt-0.5">
        {n}
      </span>
      <div>
        <p className="font-semibold text-[12px] text-primary dark:text-white mb-0.5">{title}</p>
        <p>{children}</p>
      </div>
    </div>
  )
}


function VersionCard({ version: v, esUltima, tablasOrdenadas }) {
  const [expandida, setExpandida] = useState(false)
  const tablas = tablasOrdenadas(v.tablas)
  const filas  = totalFilas(v.tablas)

  return (
    <div className={`card p-4 transition-all ${esUltima ? 'ring-1 ring-[#0A0A0A]/10 dark:ring-white/10' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {/* Ícono */}
          <div className="w-10 h-10 rounded-xl bg-[#F0F0F0] dark:bg-[#1E1E1E] grid place-items-center shrink-0">
            <HardDrive size={16} className="text-muted" />
          </div>

          {/* Info principal */}
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-[13px] font-semibold truncate font-mono">
                {v.nombre}.zip
              </p>
              {esUltima && (
                <span className="chip-dark text-[10px]">Última</span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-0.5 flex-wrap">
              <span className="flex items-center gap-1 text-[11px] text-muted">
                <Clock size={10} />
                {fmtFecha(v.created_at)}
              </span>
              <span className="flex items-center gap-1 text-[11px] text-muted">
                <Package size={10} />
                {fmtBytes(v.size_bytes)}
              </span>
              <span className="flex items-center gap-1 text-[11px] text-muted">
                <Database size={10} />
                {fmtNum(filas)} filas exportadas
              </span>
            </div>
          </div>
        </div>

        {/* Expandir tablas */}
        {tablas.length > 0 && (
          <button
            onClick={() => setExpandida(x => !x)}
            className="btn-ghost text-[11px] shrink-0"
          >
            {expandida ? 'Ocultar' : 'Ver tablas'}
          </button>
        )}
      </div>

      {/* Detalle de tablas exportadas */}
      {expandida && tablas.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[#E5E5E5] dark:border-[#2A2A2A]">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted mb-2">
            Tablas incluidas
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1.5">
            {tablas.map(([tabla, n]) => (
              <div key={tabla}
                className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-[#F5F5F5] dark:bg-[#1A1A1A] text-[11px]">
                <span className="text-muted truncate mr-2">{tabla}</span>
                <span className="font-semibold tabular-nums shrink-0">{fmtNum(n)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
