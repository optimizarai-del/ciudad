import { useEffect, useState, useMemo } from 'react'
import {
  History, Undo2, RefreshCw, Filter, X, AlertCircle,
  CheckCircle2, User, Clock, ChevronLeft, ChevronRight,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'

/**
 * Historial de acciones de la plataforma (Alquileres).
 *
 * Cada fila representa una acción significativa (crear/editar/eliminar pago,
 * marcar cobrado, registrar pago, crear/editar contrato, etc.). Si la acción
 * es revertible y todavía no fue revertida, aparece el botón "Revertir".
 *
 * Reglas de UI:
 *   - Si `revertible = false`  → no aparece el botón (acción no admite undo).
 *   - Si `revertida = true`    → la fila se ve apagada + chip "Revertida".
 *   - Click en "Revertir" abre un modal que pide motivo (opcional) y confirma.
 */

const ENTIDAD_LABEL = {
  pagos: 'Pago',
  contratos: 'Contrato',
  ajustes_contrato: 'Ajuste',
  propiedades: 'Propiedad',
  clientes: 'Cliente',
  refacciones: 'Refacción',
}

const ACCION_LABEL = {
  create: 'Creó',
  update: 'Editó',
  delete: 'Eliminó',
  cobrar: 'Marcó como cobrado',
  registrar_pago: 'Registró pago',
  aplicar_ajuste: 'Aplicó ajuste',
}

const ACCION_CHIP = {
  create: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  update: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  delete: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  cobrar: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  registrar_pago: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  aplicar_ajuste: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
}

const PAGE_SIZE = 25

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export default function HistorialAcciones() {
  const [items, setItems]       = useState([])
  const [total, setTotal]       = useState(0)
  const [offset, setOffset]     = useState(0)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  // Filtros
  const [fEntidad, setFEntidad]               = useState('')
  const [fSoloRevertibles, setFSoloRevertibles] = useState(false)
  const [fIncluirRevertidas, setFIncluirRevertidas] = useState(true)

  // Modal de reversión
  const [revertModal, setRevertModal] = useState(null)  // { row } | null
  const [revertMotivo, setRevertMotivo] = useState('')
  const [reverting, setReverting]       = useState(false)
  const [revertError, setRevertError]   = useState(null)

  // Modal de detalle (snapshots)
  const [detalleModal, setDetalleModal] = useState(null)

  const cargar = () => {
    setLoading(true)
    setError(null)
    const params = { limit: PAGE_SIZE, offset }
    if (fEntidad) params.entidad = fEntidad
    if (fSoloRevertibles) params.solo_revertibles = true
    if (!fIncluirRevertidas) params.incluir_revertidas = false

    api.get('/api/historial', { params })
      .then(r => {
        setItems(r.data.items || [])
        setTotal(r.data.total || 0)
      })
      .catch(e => setError(e?.response?.data?.detail || 'No se pudo cargar el historial'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { cargar() }, [offset, fEntidad, fSoloRevertibles, fIncluirRevertidas])

  // Cuando cambian los filtros, volvemos a página 1
  useEffect(() => { setOffset(0) }, [fEntidad, fSoloRevertibles, fIncluirRevertidas])

  const abrirRevertir = (row) => {
    setRevertModal({ row })
    setRevertMotivo('')
    setRevertError(null)
  }

  const confirmarRevertir = async () => {
    if (!revertModal) return
    setReverting(true)
    setRevertError(null)
    try {
      await api.post(`/api/historial/${revertModal.row.id}/revertir`, {
        motivo: revertMotivo || null,
      })
      setRevertModal(null)
      cargar()
    } catch (e) {
      setRevertError(e?.response?.data?.detail || 'No se pudo revertir la acción')
    } finally {
      setReverting(false)
    }
  }

  const abrirDetalle = async (row) => {
    try {
      const r = await api.get(`/api/historial/${row.id}`)
      setDetalleModal(r.data)
    } catch (e) {
      alert(e?.response?.data?.detail || 'No se pudo cargar el detalle')
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const paginaActual = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <Layout>
      <div className="p-4 lg:p-6 max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-black dark:bg-white text-white dark:text-black flex items-center justify-center">
              <History size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold">Historial de acciones</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Registro de todo lo que pasa en la plataforma. Podés revertir acciones críticas.
              </p>
            </div>
          </div>
          <button
            className="px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-800 text-sm flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-900"
            onClick={cargar}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refrescar
          </button>
        </div>

        {/* Filtros */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <Filter size={14} />
            Filtros:
          </div>
          <select
            className="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#0A0A0A] text-sm"
            value={fEntidad}
            onChange={e => setFEntidad(e.target.value)}
          >
            <option value="">Todas las entidades</option>
            <option value="pagos">Pagos / Cobros</option>
            <option value="contratos">Contratos</option>
            <option value="ajustes_contrato">Ajustes</option>
            <option value="refacciones">Refacciones</option>
          </select>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={fSoloRevertibles}
              onChange={e => setFSoloRevertibles(e.target.checked)}
            />
            Solo revertibles
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={fIncluirRevertidas}
              onChange={e => setFIncluirRevertidas(e.target.checked)}
            />
            Incluir ya revertidas
          </label>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-900/20 text-sm flex items-center gap-2 text-rose-700 dark:text-rose-300">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* Tabla */}
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white dark:bg-[#0A0A0A]">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900/50 text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2 font-semibold">Fecha</th>
                <th className="px-3 py-2 font-semibold">Usuario</th>
                <th className="px-3 py-2 font-semibold">Acción</th>
                <th className="px-3 py-2 font-semibold">Entidad</th>
                <th className="px-3 py-2 font-semibold">Descripción</th>
                <th className="px-3 py-2 font-semibold text-right">Estado</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {loading && items.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-gray-400">Cargando…</td></tr>
              )}
              {!loading && items.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-gray-400">
                  No hay acciones registradas con estos filtros.
                </td></tr>
              )}
              {items.map(row => {
                const accionLabel = ACCION_LABEL[row.accion] || row.accion
                const chip = ACCION_CHIP[row.accion] || 'bg-gray-100 text-gray-700'
                const entidadLabel = ENTIDAD_LABEL[row.entidad] || row.entidad
                return (
                  <tr
                    key={row.id}
                    className={`border-t border-gray-100 dark:border-gray-900 ${row.revertida ? 'opacity-50' : ''}`}
                  >
                    <td className="px-3 py-2 whitespace-nowrap text-gray-600 dark:text-gray-400">
                      <div className="flex items-center gap-1.5">
                        <Clock size={12} />
                        {formatDate(row.created_at)}
                      </div>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <User size={12} className="text-gray-400" />
                        {row.user_nombre || `#${row.user_id ?? '-'}`}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${chip}`}>
                        {accionLabel}
                      </span>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-500 dark:text-gray-400">
                      {entidadLabel}
                      {row.entidad_id ? <span className="ml-1 text-gray-400">#{row.entidad_id}</span> : null}
                    </td>
                    <td
                      className="px-3 py-2 cursor-pointer hover:underline"
                      onClick={() => abrirDetalle(row)}
                      title="Ver detalle"
                    >
                      {row.descripcion}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      {row.revertida ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">
                          <CheckCircle2 size={11} /> Revertida
                        </span>
                      ) : row.revertible ? (
                        <span className="text-xs text-gray-400">—</span>
                      ) : (
                        <span className="text-xs text-gray-400">No revertible</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {!row.revertida && row.revertible && (
                        <button
                          onClick={() => abrirRevertir(row)}
                          className="px-2.5 py-1 rounded-lg text-xs font-medium bg-black dark:bg-white text-white dark:text-black flex items-center gap-1 ml-auto hover:opacity-80"
                        >
                          <Undo2 size={12} /> Revertir
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        {total > PAGE_SIZE && (
          <div className="mt-3 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
            <span>{total} acciones en total</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-800 disabled:opacity-40 flex items-center gap-1"
              >
                <ChevronLeft size={14} /> Anterior
              </button>
              <span>Página {paginaActual} de {totalPaginas}</span>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
                className="px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-800 disabled:opacity-40 flex items-center gap-1"
              >
                Siguiente <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modal de reversión */}
      {revertModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => !reverting && setRevertModal(null)}>
          <div className="bg-white dark:bg-[#0A0A0A] rounded-2xl p-5 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Undo2 size={18} />
                <h2 className="font-bold">Revertir acción</h2>
              </div>
              <button onClick={() => !reverting && setRevertModal(null)}>
                <X size={18} />
              </button>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              Vas a deshacer:
            </p>
            <div className="mb-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 text-sm">
              <div className="text-xs text-gray-500 mb-1">
                {formatDate(revertModal.row.created_at)} · {revertModal.row.user_nombre || `#${revertModal.row.user_id}`}
              </div>
              <div className="font-medium">{revertModal.row.descripcion}</div>
            </div>
            <label className="block text-xs text-gray-500 mb-1">Motivo (opcional)</label>
            <input
              type="text"
              value={revertMotivo}
              onChange={e => setRevertMotivo(e.target.value)}
              placeholder="Ej: error al cargar"
              className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#0A0A0A] text-sm mb-3"
              disabled={reverting}
            />
            {revertError && (
              <div className="mb-3 p-2 rounded-lg bg-rose-50 dark:bg-rose-900/20 text-sm text-rose-700 dark:text-rose-300 flex items-center gap-2">
                <AlertCircle size={14} /> {revertError}
              </div>
            )}
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setRevertModal(null)}
                disabled={reverting}
                className="px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-800 text-sm"
              >
                Cancelar
              </button>
              <button
                onClick={confirmarRevertir}
                disabled={reverting}
                className="px-3 py-2 rounded-xl bg-black dark:bg-white text-white dark:text-black text-sm font-medium flex items-center gap-1.5 disabled:opacity-50"
              >
                <Undo2 size={14} /> {reverting ? 'Revirtiendo…' : 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de detalle (snapshots) */}
      {detalleModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setDetalleModal(null)}>
          <div className="bg-white dark:bg-[#0A0A0A] rounded-2xl p-5 w-full max-w-3xl max-h-[85vh] overflow-y-auto shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold">Detalle de la acción</h2>
              <button onClick={() => setDetalleModal(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="text-sm space-y-2">
              <div><b>{detalleModal.descripcion}</b></div>
              <div className="text-xs text-gray-500">
                {formatDate(detalleModal.created_at)} · {detalleModal.user_nombre} · {ENTIDAD_LABEL[detalleModal.entidad] || detalleModal.entidad}
                {detalleModal.entidad_id ? ` #${detalleModal.entidad_id}` : ''}
              </div>
              <div className="grid md:grid-cols-2 gap-3 mt-3">
                <div>
                  <div className="text-xs font-bold text-gray-500 mb-1">Antes</div>
                  <pre className="text-[10px] bg-gray-50 dark:bg-gray-900 p-2 rounded-lg overflow-auto max-h-80">
                    {detalleModal.snapshot_antes ? JSON.stringify(detalleModal.snapshot_antes, null, 2) : '— (no aplica)'}
                  </pre>
                </div>
                <div>
                  <div className="text-xs font-bold text-gray-500 mb-1">Después</div>
                  <pre className="text-[10px] bg-gray-50 dark:bg-gray-900 p-2 rounded-lg overflow-auto max-h-80">
                    {detalleModal.snapshot_despues ? JSON.stringify(detalleModal.snapshot_despues, null, 2) : '— (eliminado)'}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
