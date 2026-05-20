import { useEffect, useRef, useState } from 'react'
import { X, Upload, Trash2, Star, FileText, Image as ImageIcon, File, Download, Eye } from 'lucide-react'
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
  const [lightbox, setLightbox] = useState(null)  // adjunto a mostrar full-size
  const fileRef = useRef(null)

  const cargar = () => {
    setLoading(true)
    // incluir_url=true: el backend nos devuelve la URL firmada de Supabase
    // Storage (1h de validez) embebida en cada adjunto. Así <img src> y el
    // botón Ver pueden apuntar directo sin pasar por el backend con auth.
    api.get(`/api/propiedades/${propiedad.id}/adjuntos?incluir_url=true`)
      .then(r => setList(r.data || []))
      .finally(() => setLoading(false))
  }
  useEffect(() => { cargar() }, [propiedad.id])

  const [progreso, setProgreso] = useState(null)  // { hechos, total }

  const subir = async (filesList) => {
    const files = Array.from(filesList || [])
    if (!files.length) return
    setUploading(true); setErr('')
    setProgreso({ hechos: 0, total: files.length })

    const errores = []
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      try {
        const fd = new FormData()
        fd.append('archivo', file)
        fd.append('tipo', tipo)
        if (descripcion) fd.append('descripcion', descripcion)
        // Solo el primer archivo del batch puede ser principal (sino se pisan)
        fd.append('es_principal', (esPrincipal && i === 0) ? 'true' : 'false')
        await api.post(`/api/propiedades/${propiedad.id}/adjuntos`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } catch (e) {
        errores.push(`${file.name}: ${e.response?.data?.detail || 'falló'}`)
      }
      setProgreso({ hechos: i + 1, total: files.length })
    }

    setDescripcion(''); setPrincipal(false)
    if (fileRef.current) fileRef.current.value = ''
    if (errores.length) {
      setErr(`${errores.length} archivo(s) fallaron: ${errores.slice(0, 3).join(' | ')}`)
    }
    cargar()
    setUploading(false)
    setTimeout(() => setProgreso(null), 1500)
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

  // URL directa que viene del backend (signed URL de Storage o data: URI legacy).
  // No requiere Authorization header, va directo del browser a Supabase.
  const url = (a) => a.url || `${api.defaults.baseURL}/api/propiedades/${propiedad.id}/adjuntos/${a.id}`
  const isImg = (a) => (a.mime || '').startsWith('image/')
  const tamano = (b) => !b ? '' : b > 1024 * 1024
    ? `${(b / 1024 / 1024).toLocaleString('es-AR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} MB`
    : `${Math.round(b / 1024).toLocaleString('es-AR')} KB`

  const descargar = async (a) => {
    // Forzar download (no preview) — fetch + blob + a.download
    try {
      const u = url(a)
      const r = await fetch(u)
      const blob = await r.blob()
      const obj = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = obj
      link.download = a.nombre_archivo || `adjunto-${a.id}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(obj), 1000)
    } catch (e) {
      window.open(url(a), '_blank')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card w-full max-w-3xl shadow-lift animate-scale-in flex flex-col max-h-[90vh] my-6"
        onClick={e => e.stopPropagation()}>

        <div className="px-6 py-5 border-b border-border dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-xl sm:text-2xl mb-0.5">Adjuntos.</h2>
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
              multiple
              onChange={e => subir(e.target.files)}
              accept="image/*,application/pdf"
              className="hidden"
            />
            <button className="btn-primary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              <Upload size={13} />
              {uploading
                ? (progreso ? `Subiendo ${progreso.hechos}/${progreso.total}…` : 'Subiendo…')
                : 'Subir archivos'}
            </button>
          </div>
          <p className="text-[11px] text-muted dark:text-gray-500 mt-2">
            Podés seleccionar varios archivos a la vez (Ctrl/⌘ + click).
          </p>
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
                  <div
                    className="aspect-video bg-neutral-100 dark:bg-[#1E1E1E] rounded-xl overflow-hidden mb-2 grid place-items-center cursor-pointer relative group"
                    onClick={() => isImg(a) ? setLightbox(a) : window.open(url(a), '_blank')}
                  >
                    {isImg(a) && a.url ? (
                      <>
                        <img
                          src={a.url}
                          alt={a.nombre_archivo}
                          loading="lazy"
                          className="object-cover w-full h-full transition-transform group-hover:scale-105"
                          onError={e => { e.currentTarget.style.display = 'none' }}
                        />
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition flex items-center justify-center">
                          <Eye size={20} className="text-white opacity-0 group-hover:opacity-100 transition" />
                        </div>
                      </>
                    ) : isImg(a) ? (
                      <ImageIcon size={36} className="text-muted dark:text-gray-600" />
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
                    <button
                      className="btn-secondary text-[11px] py-1 px-2 flex-1 text-center inline-flex items-center justify-center gap-1"
                      onClick={() => isImg(a) ? setLightbox(a) : window.open(url(a), '_blank')}
                      title="Ver en grande"
                    >
                      <Eye size={11} /> Ver
                    </button>
                    <button
                      className="btn-ghost p-1.5"
                      title="Descargar"
                      onClick={() => descargar(a)}
                    >
                      <Download size={11} />
                    </button>
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

      {lightbox && (
        <div
          className="fixed inset-0 z-[60] bg-black/90 grid place-items-center p-6 animate-fade-in"
          onClick={() => setLightbox(null)}
        >
          <button
            className="absolute top-4 right-4 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition"
            onClick={() => setLightbox(null)}
          >
            <X size={20} />
          </button>
          <button
            className="absolute top-4 left-4 px-3 py-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white text-[12px] transition inline-flex items-center gap-1.5"
            onClick={e => { e.stopPropagation(); descargar(lightbox) }}
          >
            <Download size={13} /> Descargar
          </button>
          <img
            src={lightbox.url}
            alt={lightbox.nombre_archivo}
            className="max-w-full max-h-full object-contain"
            onClick={e => e.stopPropagation()}
          />
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full bg-white/10 text-white text-[12px]">
            {lightbox.nombre_archivo} · {tamano(lightbox.tamano_bytes)}
          </div>
        </div>
      )}
    </div>
  )
}
