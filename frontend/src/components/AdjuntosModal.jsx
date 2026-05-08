import { useEffect, useRef, useState } from 'react'
import { X, Upload, Trash2, Star, FileText, Image as ImageIcon, File } from 'lucide-react'
import api from '../utils/api'

const TIPOS = ['foto', 'documento', 'plano', 'otro']

export default function AdjuntosModal({ propiedad, onClose }) {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [tipo, setTipo] = useState('foto')
  const [descripcion, setDescripcion] = useState('')
  const [esPrincipal, setPrincipal] = useState(false)
  const [err, setErr] = useState('')
  const fileRef = useRef(null)

  const cargar = () => {
    setLoading(true)
    api.get(`/api/propiedades/${propiedad.id}/adjuntos`)
      .then(r => setList(r.data || []))
      .finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [propiedad.id])

  const subir = async (file) => {
    if (!file) return
    setUploading(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('archivo', file)
      fd.append('tipo', tipo)
      if (descripcion) fd.append('descripcion', descripcion)
      fd.append('es_principal', esPrincipal ? 'true' : 'false')
      await api.post(`/api/propiedades/${propiedad.id}/adjuntos`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setDescripcion(''); setPrincipal(false)
      if (fileRef.current) fileRef.current.value = ''
      cargar()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al subir')
    } finally { setUploading(false) }
  }

  const eliminar = async (a) => {
    if (!confirm(`Eliminar "${a.nombre_archivo}"?`)) return
    await api.delete(`/api/propiedades/${propiedad.id}/adjuntos/${a.id}`)
    cargar()
  }

  const marcarPrincipal = async (a) => {
    await api.patch(`/api/propiedades/${propiedad.id}/adjuntos/${a.id}`, { es_principal: !a.es_principal })
    cargar()
  }

  const url = (a) => `${api.defaults.baseURL}/api/propiedades/${propiedad.id}/adjuntos/${a.id}`
  const isImg = (a) => (a.mime || '').startsWith('image/')
  const tamano = (b) => !b ? '' : b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card w-full max-w-3xl shadow-lift animate-scale-in flex flex-col max-h-[90vh] my-6"
        onClick={e => e.stopPropagation()}>

        <div className="px-6 py-5 border-b border-border dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-2xl mb-0.5">Adjuntos.</h2>
            <p className="text-[12px] text-muted dark:text-gray-500">{propiedad.direccion}</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        {/* Form upload */}
        <div className="px-6 py-4 border-b border-border dark:border-[#2A2A2A] shrink-0">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <div>
              <label className="label">Tipo</label>
              <select className="input" value={tipo} onChange={e => setTipo(e.target.value)}>
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="label">Descripción (opcional)</label>
              <input className="input" value={descripcion} onChange={e => setDescripcion(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <label className="text-[12px] text-muted dark:text-gray-500 flex items-center gap-2 select-none">
              <input type="checkbox" checked={esPrincipal} onChange={e => setPrincipal(e.target.checked)} />
              Marcar como principal
            </label>
            <input
              ref={fileRef}
              type="file"
              onChange={e => subir(e.target.files?.[0])}
              accept="image/*,application/pdf"
              className="hidden"
            />
            <button className="btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              <Upload size={13} />{uploading ? 'Subiendo…' : 'Subir archivo'}
            </button>
          </div>
          {err && <p className="text-[12px] text-danger mt-2">{err}</p>}
        </div>

        {/* Lista / galería */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="text-center text-sm text-muted dark:text-gray-500 py-10">Cargando…</div>
          ) : list.length === 0 ? (
            <div className="text-center py-12">
              <FileText size={32} className="mx-auto text-gray-300 dark:text-gray-700 mb-2" />
              <p className="text-sm text-muted dark:text-gray-500">Aún no hay archivos para esta propiedad.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {list.map(a => (
                <div key={a.id} className="card p-3 card-hover">
                  <div className="aspect-video bg-neutral-100 dark:bg-[#1E1E1E] rounded-xl overflow-hidden mb-2 grid place-items-center">
                    {isImg(a) ? (
                      <img src={url(a)} alt={a.nombre_archivo} className="object-cover w-full h-full" />
                    ) : (
                      <File size={36} className="text-muted dark:text-gray-600" />
                    )}
                  </div>
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <p className="text-[12px] font-medium truncate flex-1">{a.nombre_archivo}</p>
                    {a.es_principal && <Star size={11} className="text-[#B8893A] shrink-0 fill-[#B8893A]" />}
                  </div>
                  <p className="text-[10px] text-muted dark:text-gray-500 capitalize">{a.tipo} · {tamano(a.tamano_bytes)}</p>
                  {a.descripcion && <p className="text-[11px] text-muted dark:text-gray-500 truncate mt-1">{a.descripcion}</p>}
                  <div className="flex gap-1 mt-2">
                    <a className="btn-secondary text-[11px] py-1 px-2 flex-1 text-center" href={url(a)} target="_blank" rel="noreferrer">Ver</a>
                    <button className="btn-ghost p-1.5" title="Marcar principal" onClick={() => marcarPrincipal(a)}>
                      <Star size={11} className={a.es_principal ? 'text-[#B8893A] fill-[#B8893A]' : ''} />
                    </button>
                    <button className="btn-danger p-1.5" onClick={() => eliminar(a)}><Trash2 size={11} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
