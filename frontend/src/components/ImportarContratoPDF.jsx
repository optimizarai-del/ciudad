import { useState } from 'react'
import {
  Upload, FileText, Sparkles, CheckCircle2, AlertCircle, X, Loader2,
} from 'lucide-react'
import api from '../utils/api'

/**
 * Modal de 3 pasos para importar un contrato desde PDF usando IA.
 *
 *   1. Upload: el usuario elige el PDF.
 *   2. Preview: la IA devuelve los datos extraídos en formularios editables.
 *      El usuario corrige cualquier cosa.
 *   3. Confirm: backend crea propietario, inquilino, propiedad y contrato
 *      (reutilizando registros existentes por DNI o dirección).
 *
 * onSaved(resumen) se invoca con el dict que devuelve /importar-pdf-confirmar.
 */
export default function ImportarContratoPDF({ onClose, onSaved }) {
  const [step, setStep] = useState('upload')   // 'upload' | 'preview' | 'done'
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [datos, setDatos] = useState(null)
  const [resumen, setResumen] = useState(null)

  const subir = async () => {
    if (!file) return
    setLoading(true); setErr('')
    const fd = new FormData()
    fd.append('archivo', file)
    try {
      const r = await api.post('/api/contratos/importar-pdf-preview', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      })
      setDatos(r.data.datos)
      setStep('preview')
    } catch (e) {
      setErr(e.response?.data?.detail || 'No se pudo procesar el PDF.')
    } finally { setLoading(false) }
  }

  const confirmar = async () => {
    setLoading(true); setErr('')
    try {
      const r = await api.post('/api/contratos/importar-pdf-confirmar', datos)
      setResumen(r.data)
      setStep('done')
      // Notificar al padre que recargue listas
      if (onSaved) onSaved(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'No se pudo importar.')
    } finally { setLoading(false) }
  }

  // Helpers para editar campos anidados del JSON extraído
  const setNested = (path, value) => {
    setDatos(prev => {
      const next = JSON.parse(JSON.stringify(prev))
      const parts = path.split('.')
      let cur = next
      for (let i = 0; i < parts.length - 1; i++) {
        cur[parts[i]] = cur[parts[i]] || {}
        cur = cur[parts[i]]
      }
      cur[parts[parts.length - 1]] = value === '' ? null : value
      return next
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card w-full max-w-3xl shadow-lift animate-scale-in flex flex-col max-h-[90vh] my-6"
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="px-6 py-5 border-b border-border dark:border-[#2A2A2A] flex items-start justify-between shrink-0">
          <div>
            <h2 className="hero-title text-xl sm:text-2xl mb-0.5 flex items-center gap-2">
              <Sparkles size={20} className="text-[#B8893A]" />
              Importar contrato desde PDF
            </h2>
            <p className="text-[12px] text-muted">
              La IA extrae propietario, inquilino, propiedad y datos del contrato.
            </p>
          </div>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        {/* Pasos visuales */}
        <div className="px-6 pt-4 pb-2 flex items-center gap-2 text-[11px] shrink-0">
          <Step n={1} label="Subir PDF" active={step === 'upload'} done={step !== 'upload'} />
          <div className="flex-1 h-px bg-border" />
          <Step n={2} label="Revisar datos" active={step === 'preview'} done={step === 'done'} />
          <div className="flex-1 h-px bg-border" />
          <Step n={3} label="Listo" active={step === 'done'} done={false} />
        </div>

        {/* Cuerpo */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {step === 'upload' && (
            <UploadStep file={file} setFile={setFile} loading={loading} err={err} onUpload={subir} />
          )}
          {step === 'preview' && datos && (
            <PreviewStep datos={datos} setNested={setNested} loading={loading} err={err} onConfirm={confirmar} />
          )}
          {step === 'done' && resumen && (
            <DoneStep resumen={resumen} onClose={onClose} />
          )}
        </div>
      </div>
    </div>
  )
}

function Step({ n, label, active, done }) {
  return (
    <div className={`flex items-center gap-1.5 ${active ? 'text-primary dark:text-white font-semibold' : done ? 'text-success' : 'text-muted'}`}>
      <span className={`w-5 h-5 rounded-full grid place-items-center text-[10px] font-bold
        ${active ? 'bg-[#B8893A] text-white' : done ? 'bg-success text-white' : 'bg-neutral-200 dark:bg-[#2A2A2A]'}`}>
        {done ? <CheckCircle2 size={12} /> : n}
      </span>
      {label}
    </div>
  )
}

function UploadStep({ file, setFile, loading, err, onUpload }) {
  return (
    <div className="space-y-4">
      <label className="block">
        <div className="border-2 border-dashed border-border dark:border-[#3A3A3A] rounded-2xl p-10 text-center hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition cursor-pointer">
          <Upload size={32} className="mx-auto text-muted mb-3" />
          {file ? (
            <>
              <p className="font-semibold text-[14px]">{file.name}</p>
              <p className="text-[11px] text-muted">
                {Math.round(file.size / 1024).toLocaleString('es-AR')} KB — click para cambiar
              </p>
            </>
          ) : (
            <>
              <p className="font-semibold text-[14px]">Elegir contrato en PDF</p>
              <p className="text-[11px] text-muted">Máximo 15 MB. Idealmente texto seleccionable.</p>
            </>
          )}
          <input type="file" accept="application/pdf,.pdf" className="hidden"
            onChange={e => setFile(e.target.files?.[0] || null)} />
        </div>
      </label>

      <div className="rounded-xl p-3 bg-[#B8893A]/5 border border-[#B8893A]/20 text-[12px] text-muted flex gap-2">
        <Sparkles size={13} className="text-[#B8893A] shrink-0 mt-0.5" />
        <div>
          La IA va a extraer automáticamente:
          <ul className="mt-1 space-y-0.5 list-disc list-inside opacity-90">
            <li>Datos del propietario (nombre, DNI, contacto)</li>
            <li>Datos del inquilino</li>
            <li>Dirección y características del inmueble</li>
            <li>Monto, depósito, fechas, índice y comisión</li>
          </ul>
          Después vas a poder revisar y editar todo antes de guardar.
        </div>
      </div>

      {err && (
        <div className="rounded-xl p-3 bg-danger/5 border border-danger/20 text-[12px] text-danger flex gap-2">
          <AlertCircle size={13} className="shrink-0 mt-0.5" />
          <p>{err}</p>
        </div>
      )}

      <button
        className="btn-primary w-full"
        onClick={onUpload}
        disabled={!file || loading}
      >
        {loading ? <><Loader2 size={14} className="animate-spin" /> Procesando…</> : <><Sparkles size={14} /> Procesar con IA</>}
      </button>
    </div>
  )
}

function Field({ label, value, onChange, type = 'text', placeholder = '' }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        type={type}
        className="input"
        value={value ?? ''}
        placeholder={placeholder}
        onChange={e => onChange(type === 'number' ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value)}
      />
    </div>
  )
}

function PreviewStep({ datos, setNested, loading, err, onConfirm }) {
  const TIPOS_CONTRATO = ['alquiler_vivienda','alquiler_comercial','boleto_compraventa','sena_alquiler']
  const ESTADOS = ['borrador','vigente','vencido','rescindido','reservado']
  const INDICES = ['ipc','icl','fijo','sin_ajuste']
  const TIPOS_PROP = ['departamento','casa','local','oficina','galpon','campo']

  return (
    <div className="space-y-5">
      <div className="rounded-xl p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-900 text-[12px] flex gap-2">
        <Sparkles size={13} className="text-blue-600 shrink-0 mt-0.5" />
        <p className="text-blue-700 dark:text-blue-300">
          Revisá lo que extrajo la IA y corregí lo que haga falta antes de confirmar. Si el propietario o el inquilino ya existen en tu base, los reutilizamos automáticamente por DNI.
        </p>
      </div>

      {/* Propietarios: lista — el contrato puede tener 1 o varios */}
      <PropietariosSection datos={datos} setNested={setNested} />


      {/* Inquilino */}
      <Seccion titulo="Inquilino / Comprador">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Nombre" value={datos.inquilino?.nombre} onChange={v => setNested('inquilino.nombre', v)} />
          <Field label="Apellido" value={datos.inquilino?.apellido} onChange={v => setNested('inquilino.apellido', v)} />
          <Field label="Razón social" value={datos.inquilino?.razon_social} onChange={v => setNested('inquilino.razon_social', v)} />
          <Field label="DNI / CUIT" value={datos.inquilino?.documento} onChange={v => setNested('inquilino.documento', v)} />
          <Field label="Email" value={datos.inquilino?.email} onChange={v => setNested('inquilino.email', v)} type="email" />
          <Field label="Teléfono" value={datos.inquilino?.telefono} onChange={v => setNested('inquilino.telefono', v)} />
        </div>
      </Seccion>

      {/* Propiedad */}
      <Seccion titulo="Propiedad">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="col-span-2">
            <Field label="Dirección *" value={datos.propiedad?.direccion} onChange={v => setNested('propiedad.direccion', v)} />
          </div>
          <Field label="Ciudad" value={datos.propiedad?.ciudad} onChange={v => setNested('propiedad.ciudad', v)} />
          <Field label="Provincia" value={datos.propiedad?.provincia} onChange={v => setNested('propiedad.provincia', v)} />
          <div>
            <label className="label">Tipo</label>
            <select className="input" value={datos.propiedad?.tipo || 'departamento'} onChange={e => setNested('propiedad.tipo', e.target.value)}>
              {TIPOS_PROP.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <Field label="Ambientes" type="number" value={datos.propiedad?.ambientes} onChange={v => setNested('propiedad.ambientes', v)} />
          <Field label="Superficie m²" type="number" value={datos.propiedad?.superficie_m2} onChange={v => setNested('propiedad.superficie_m2', v)} />
          <Field label="Alquiler $" type="number" value={datos.propiedad?.precio_alquiler} onChange={v => setNested('propiedad.precio_alquiler', v)} />
          <Field label="Expensas $" type="number" value={datos.propiedad?.expensas} onChange={v => setNested('propiedad.expensas', v)} />
          <Field label="Tasa municipal $" type="number" value={datos.propiedad?.tasa_municipal} onChange={v => setNested('propiedad.tasa_municipal', v)} />
        </div>
      </Seccion>

      {/* Contrato */}
      <Seccion titulo="Contrato">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Tipo</label>
            <select className="input" value={datos.tipo || 'alquiler_vivienda'} onChange={e => setNested('tipo', e.target.value)}>
              {TIPOS_CONTRATO.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Estado</label>
            <select className="input" value={datos.estado || 'vigente'} onChange={e => setNested('estado', e.target.value)}>
              {ESTADOS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <Field label="Fecha inicio" type="date" value={datos.fecha_inicio} onChange={v => setNested('fecha_inicio', v)} />
          <Field label="Fecha fin" type="date" value={datos.fecha_fin} onChange={v => setNested('fecha_fin', v)} />
          <Field label="Monto inicial $" type="number" value={datos.monto_inicial} onChange={v => setNested('monto_inicial', v)} />
          <Field label="Depósito $" type="number" value={datos.deposito} onChange={v => setNested('deposito', v)} />
          <div>
            <label className="label">Índice ajuste</label>
            <select className="input" value={datos.indice_ajuste || 'ipc'} onChange={e => setNested('indice_ajuste', e.target.value)}>
              {INDICES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <Field label="Periodicidad (meses)" type="number" value={datos.periodicidad_meses} onChange={v => setNested('periodicidad_meses', v)} />
          <Field label="% fijo (si aplica)" type="number" value={datos.porcentaje_fijo} onChange={v => setNested('porcentaje_fijo', v)} />
          <Field label="Comisión %" type="number" value={datos.comision_porc} onChange={v => setNested('comision_porc', v)} />
        </div>
        <div className="mt-3">
          <label className="label">Notas</label>
          <textarea
            className="input resize-none"
            rows={2}
            value={datos.notas ?? ''}
            onChange={e => setNested('notas', e.target.value)}
          />
        </div>
      </Seccion>

      {err && (
        <div className="rounded-xl p-3 bg-danger/5 border border-danger/20 text-[12px] text-danger flex gap-2">
          <AlertCircle size={13} className="shrink-0 mt-0.5" />
          <p>{err}</p>
        </div>
      )}

      <button className="btn-primary w-full" onClick={onConfirm} disabled={loading}>
        {loading ? <><Loader2 size={14} className="animate-spin" /> Creando…</> : <><CheckCircle2 size={14} /> Confirmar e importar</>}
      </button>
    </div>
  )
}

/**
 * Sección de propietarios extraídos del PDF. Acepta múltiples co-propietarios.
 * El array es `datos.propietarios` (formato nuevo). Mantiene compat con el
 * formato viejo donde había un solo objeto `datos.propietario`.
 */
function PropietariosSection({ datos, setNested }) {
  // Normalizar a array si vino como objeto único (compat)
  const lista = datos.propietarios || (datos.propietario ? [datos.propietario] : [])

  const updateAt = (idx, field, value) => {
    const copy = lista.map((p, i) => i === idx ? { ...p, [field]: value === '' ? null : value } : p)
    setNested('propietarios', copy)
  }
  const eliminar = (idx) => {
    setNested('propietarios', lista.filter((_, i) => i !== idx))
  }
  const agregar = () => {
    setNested('propietarios', [
      ...lista,
      { nombre: '', apellido: '', razon_social: null, documento: null,
        email: null, telefono: null, porcentaje: null },
    ])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold">
          Propietarios <span className="text-muted/70 font-normal lowercase tracking-normal">({lista.length})</span>
        </p>
        <button type="button" onClick={agregar}
          className="text-[11px] text-primary dark:text-white hover:underline font-medium">
          + Agregar propietario
        </button>
      </div>

      {lista.length === 0 && (
        <div className="rounded-2xl bg-warn/5 border border-warn/20 p-4 text-[12px] text-warn">
          La IA no detectó ningún propietario en el PDF. Agregá al menos uno antes de confirmar.
        </div>
      )}

      <div className="space-y-3">
        {lista.map((p, idx) => (
          <div key={idx} className="rounded-2xl bg-neutral-50 dark:bg-[#141414] border border-border dark:border-[#2A2A2A] p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[12px] font-semibold">
                Propietario #{idx + 1}
                {idx === 0 && <span className="ml-2 text-[10px] text-[#B8893A]">PRINCIPAL</span>}
              </p>
              {lista.length > 1 && (
                <button type="button" onClick={() => eliminar(idx)}
                  className="text-[11px] text-danger hover:underline">
                  Quitar
                </button>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label">Nombre</label>
                <input className="input" value={p.nombre || ''}
                  onChange={e => updateAt(idx, 'nombre', e.target.value)} />
              </div>
              <div>
                <label className="label">Apellido</label>
                <input className="input" value={p.apellido || ''}
                  onChange={e => updateAt(idx, 'apellido', e.target.value)} />
              </div>
              <div>
                <label className="label">Razón social</label>
                <input className="input" value={p.razon_social || ''}
                  onChange={e => updateAt(idx, 'razon_social', e.target.value)} />
              </div>
              <div>
                <label className="label">DNI / CUIT</label>
                <input className="input" value={p.documento || ''}
                  onChange={e => updateAt(idx, 'documento', e.target.value)} />
              </div>
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" value={p.email || ''}
                  onChange={e => updateAt(idx, 'email', e.target.value)} />
              </div>
              <div>
                <label className="label">Teléfono</label>
                <input className="input" value={p.telefono || ''}
                  onChange={e => updateAt(idx, 'telefono', e.target.value)} />
              </div>
              <div className="sm:col-span-2">
                <label className="label">% copropiedad (opcional)</label>
                <input className="input !max-w-[120px]" type="number" min="0" max="100" step="0.01"
                  placeholder="—"
                  value={p.porcentaje ?? ''}
                  onChange={e => updateAt(idx, 'porcentaje', e.target.value === '' ? null : Number(e.target.value))} />
                <p className="text-[10px] text-muted mt-1">
                  Dejalo vacío si todos cobran por igual (división equitativa en liquidaciones).
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


function Seccion({ titulo, children }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-2">{titulo}</p>
      <div className="rounded-2xl bg-neutral-50 dark:bg-[#141414] border border-border dark:border-[#2A2A2A] p-4">
        {children}
      </div>
    </div>
  )
}

function DoneStep({ resumen, onClose }) {
  const Row = ({ label, info }) => (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0 text-[13px]">
      <span className="text-muted">{label}</span>
      <span className={`font-medium ${info.reutilizado ? 'text-blue-600 dark:text-blue-400' : 'text-success'}`}>
        {info.reutilizado ? 'Reutilizado' : 'Creado'} · #{info.id}
      </span>
    </div>
  )
  return (
    <div className="text-center py-2">
      <div className="w-14 h-14 rounded-full bg-success/10 grid place-items-center mx-auto mb-3">
        <CheckCircle2 size={28} className="text-success" />
      </div>
      <h3 className="hero-title text-xl sm:text-2xl mb-1">Contrato importado</h3>
      <p className="text-[12px] text-muted mb-5">
        Código <span className="font-mono">{resumen.contrato?.codigo}</span>
      </p>

      <div className="text-left card p-4 mb-4">
        {(resumen.propietarios || []).map((p, i) => (
          <Row
            key={p.id || i}
            label={`Propietario${(resumen.propietarios?.length || 0) > 1 ? ` ${i + 1}` : ''}${p.porcentaje ? ` (${p.porcentaje}%)` : ''}`}
            info={p}
          />
        ))}
        {/* Compat con respuesta vieja */}
        {!resumen.propietarios && resumen.propietario && (
          <Row label="Propietario" info={resumen.propietario} />
        )}
        {resumen.inquilino?.id && <Row label="Inquilino" info={resumen.inquilino} />}
        <Row label="Propiedad" info={resumen.propiedad} />
      </div>

      <button className="btn-primary w-full" onClick={onClose}>
        Cerrar
      </button>
    </div>
  )
}
