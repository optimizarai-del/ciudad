import { useEffect, useState } from 'react'
import {
  Users, Pencil, X, ShieldCheck, Plus, Trash2, Mail,
  Building2, Star, Activity, CalendarClock, Clock,
} from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { useAuth } from '../context/AuthContext'

const ROLES = ['admin', 'gerencia', 'alquileres', 'ventas', 'agente_ia']

// Paleta muosteada por rol: el dorado de marca para admin y tonos 700
// desaturados para el resto — distinguibles sin romper la identidad monocroma.
const ROL = {
  admin:      { label: 'Administrador', strip: '#B8893A' },
  gerencia:   { label: 'Gerencia',      strip: '#0F766E' },
  alquileres: { label: 'Alquileres',    strip: '#525252' },
  ventas:     { label: 'Ventas',        strip: '#B45309' },
  agente_ia:  { label: 'Agente IA',     strip: '#6D28D9' },
}

const ROL_CHIP = {
  admin:      'chip-dark',
  gerencia:   'chip-success',
  alquileres: 'chip-gray',
  ventas:     'chip-warn',
  agente_ia:  'chip-muted',
}

const ROL_LABEL = Object.fromEntries(
  Object.entries(ROL).map(([k, v]) => [k, v.label])
)

// "hace X" a partir de un ISO naive-UTC del backend (le forzamos Z).
function timeAgo(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  const diff = Math.floor((Date.now() - d) / 1000)
  if (diff < 60) return 'ahora'
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
  if (diff < 2592000) return `hace ${Math.floor(diff / 86400)}d`
  const meses = Math.floor(diff / 2592000)
  return `hace ${meses} mes${meses > 1 ? 'es' : ''}`
}

/* Tarjeta "paperclip": franja de color arriba, avatar centrado y, al pasar el
   mouse, un overlay que sube con el resumen de actividad de la persona. */
function PersonCard({ u, me, onEdit, onDelete }) {
  const r = ROL[u.role] || ROL.admin
  const act = u.actividad || { total: 0, mes: 0, ultima: null }
  const inicial = (u.nombre || u.email || '?').slice(0, 1).toUpperCase()

  return (
    <div className="group relative">
      <div className="card overflow-hidden transition-all duration-200 group-hover:-translate-y-1 group-hover:shadow-lift">
        <div className="h-1.5" style={{ background: r.strip }} />

        <div className="p-4 pb-6 flex flex-col items-center text-center gap-2">
          <div
            className="w-12 h-12 rounded-2xl grid place-items-center text-[16px] font-display font-semibold ring-1"
            style={{
              background: `${r.strip}22`,
              color: r.strip,
              borderColor: `${r.strip}55`,
            }}
          >
            {inicial}
          </div>

          <div className="min-w-0 w-full">
            <div className="text-[14px] font-medium truncate flex items-center justify-center gap-1.5">
              {u.nombre}
              {u.es_yo && (
                <Star size={11} className="text-[#B8893A] shrink-0" title="Sos vos" />
              )}
            </div>
            <div className="mt-1.5 flex items-center justify-center gap-2">
              <span className={ROL_CHIP[u.role] || 'chip-muted'}>{r.label}</span>
              <span className="inline-flex items-center gap-1 text-[10px] text-muted dark:text-gray-500">
                <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-success' : 'bg-muted/40'}`} />
                {u.is_active ? 'Activo' : 'Inactivo'}
              </span>
            </div>
          </div>
        </div>

        {/* overlay de actividad (sube al hover) */}
        <div className="absolute inset-x-0 bottom-0 translate-y-full group-hover:translate-y-0 transition-transform duration-200
                        bg-white/95 dark:bg-[#171717]/95 backdrop-blur-sm border-t border-border dark:border-[#2A2A2A]
                        px-3 py-2.5 grid grid-cols-3 gap-1">
          <Kpi icon={Activity}      value={act.total}          label="acciones" />
          <Kpi icon={CalendarClock} value={act.mes}            label="30 días" />
          <Kpi icon={Clock}         value={timeAgo(act.ultima)} label="última" small />
        </div>
      </div>

      {/* acciones de admin (arriba a la derecha, aparecen al hover) */}
      <div className="absolute top-2.5 right-2.5 flex gap-1 opacity-0 group-hover:opacity-100 transition">
        <button
          onClick={() => onEdit(u)}
          title="Editar rol"
          className="p-1.5 rounded-lg bg-white/90 dark:bg-[#1E1E1E]/90 backdrop-blur border border-border dark:border-[#2A2A2A]
                     text-muted hover:text-primary dark:hover:text-white transition"
        >
          <Pencil size={12} />
        </button>
        {!u.es_yo && (
          <button
            onClick={() => onDelete(u)}
            title="Eliminar usuario"
            className="p-1.5 rounded-lg bg-white/90 dark:bg-[#1E1E1E]/90 backdrop-blur border border-border dark:border-[#2A2A2A]
                       text-muted hover:text-danger transition"
          >
            <Trash2 size={12} />
          </button>
        )}
      </div>
    </div>
  )
}

function Kpi({ icon: Icon, value, label, small }) {
  return (
    <div className="text-center leading-tight">
      <div className={`font-display font-semibold text-primary dark:text-white ${small ? 'text-[11px]' : 'text-[15px]'}`}>
        {value}
      </div>
      <div className="text-[9px] text-muted dark:text-gray-500 uppercase tracking-wide flex items-center justify-center gap-0.5">
        <Icon size={9} /> {label}
      </div>
    </div>
  )
}

function Column({ rol, miembros, me, onEdit, onDelete }) {
  const r = ROL[rol] || ROL.admin
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 justify-center">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: r.strip }} />
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted dark:text-gray-500">
          {r.label}
        </span>
        <span className="text-[11px] text-muted dark:text-gray-600">{miembros.length}</span>
      </div>
      <div className="flex flex-col gap-3">
        {miembros.map(u => (
          <PersonCard key={u.id} u={u} me={me} onEdit={onEdit} onDelete={onDelete} />
        ))}
      </div>
    </div>
  )
}

export default function Equipo() {
  const { user: me } = useAuth()
  const [list, setList] = useState([])
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [toast, setToast] = useState(null)  // {kind:'success'|'error', text}

  const load = () => api.get('/api/users/equipo').then(r => setList(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  // Auto-cierre del toast a los 5s
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  const deleteUser = async u => {
    try {
      await api.delete(`/api/users/${u.id}`)
      setToast({ kind: 'success', text: `Usuario ${u.nombre} eliminado.` })
      load()
    } catch (e) {
      setToast({
        kind: 'error',
        text: e.response?.data?.detail || 'Error al eliminar.',
      })
    } finally {
      setConfirmDelete(null)
    }
  }

  // Agrupa por rol respetando el orden de ROLES; solo columnas con gente.
  const grupos = ROLES
    .map(rol => ({ rol, miembros: list.filter(u => u.role === rol) }))
    .filter(g => g.miembros.length > 0)

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">

        <header className="mb-10">
          <div className="hero-eyebrow">Administración</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl mb-3">Equipo</h1>
              <p className="hero-sub">
                Organigrama del equipo. Pasá el mouse por una persona para ver su actividad.
              </p>
            </div>
            <button className="btn-primary" onClick={() => setCreating(true)}>
              <Plus size={14} /> Nuevo usuario
            </button>
          </div>
        </header>

        {list.length === 0 ? (
          <div className="card py-20 text-center">
            <Users size={36} className="mx-auto text-muted/30 mb-4" />
            <p className="text-muted text-[14px] mb-4">No hay usuarios registrados aún.</p>
            <button className="btn-primary" onClick={() => setCreating(true)}>
              <Plus size={14} /> Crear primer usuario
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-6">
            {/* Nodo raíz: el workspace */}
            <div className="card px-6 py-4 flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl grid place-items-center ring-1"
                style={{ background: '#B8893A22', color: '#B8893A', borderColor: '#B8893A55' }}
              >
                <Building2 size={19} />
              </div>
              <div>
                <div className="font-display font-semibold text-[16px] tracking-tight">CIUDAD</div>
                <div className="text-[12px] text-muted dark:text-gray-500">
                  Workspace · {list.length} {list.length === 1 ? 'persona' : 'personas'}
                </div>
              </div>
            </div>

            <div className="w-px h-5 bg-border dark:bg-[#2A2A2A]" />

            {/* Columnas por rol */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-5 w-full items-start">
              {grupos.map(g => (
                <Column
                  key={g.rol}
                  rol={g.rol}
                  miembros={g.miembros}
                  me={me}
                  onEdit={setEditing}
                  onDelete={setConfirmDelete}
                />
              ))}
            </div>
          </div>
        )}

        {/* Matriz de permisos */}
        <div className="card p-6 mt-10">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck size={15} className="text-muted dark:text-gray-500" />
            <p className="font-semibold text-[13px] tracking-tight">Matriz de permisos</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <th className="text-left text-muted dark:text-gray-500 font-medium py-2 pr-4">Recurso</th>
                  {ROLES.map(r => (
                    <th key={r} className="text-center text-muted dark:text-gray-500 font-medium py-2 px-3">
                      {ROL_LABEL[r]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border dark:divide-[#2A2A2A]">
                {[
                  // [admin, gerencia, alquileres, ventas, agente_ia]
                  { label: 'Propiedades',     perms: [true,  true,  true,  true,  false] },
                  { label: 'Contratos',       perms: [true,  true,  true,  false, false] },
                  { label: 'Cobros',          perms: [true,  true,  true,  false, false] },
                  { label: 'Liquidaciones',   perms: [true,  true,  true,  false, false] },
                  { label: 'Clientes',        perms: [true,  true,  true,  true,  false] },
                  { label: 'Calculadora',     perms: [true,  true,  true,  true,  true ] },
                  { label: 'Tokko (Ventas)',  perms: [true,  true,  false, true,  false] },
                  { label: 'Finanzas',        perms: [true,  true,  false, false, false] },
                  { label: 'Recordatorios',   perms: [true,  true,  true,  true,  true ] },
                  { label: 'Asistente IA',    perms: [true,  true,  true,  true,  true ] },
                  { label: 'Equipo',          perms: [true,  false, false, false, false] },
                ].map(row => (
                  <tr key={row.label} className="hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition">
                    <td className="py-2.5 pr-4 font-medium">{row.label}</td>
                    {row.perms.map((ok, i) => (
                      <td key={i} className="text-center py-2.5 px-3">
                        {ok
                          ? <span className="text-success font-bold">✓</span>
                          : <span className="text-muted/30">—</span>
                        }
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      {creating && (
        <ModalNuevoUsuario
          onClose={() => setCreating(false)}
          onSaved={(info) => {
            setCreating(false)
            load()
            // info = {user, email_enviado, email_motivo}
            if (info?.email_enviado) {
              setToast({ kind: 'success', text: `Usuario creado. Email enviado a ${info.user.email}.` })
            } else {
              setToast({
                kind: 'error',
                text: `Usuario creado pero email NO enviado: ${info?.email_motivo || 'sin SMTP'}`,
              })
            }
          }}
        />
      )}

      {editing && (
        <ModalEditRol
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}

      {confirmDelete && (
        <ModalConfirmDelete
          user={confirmDelete}
          onClose={() => setConfirmDelete(null)}
          onConfirm={() => deleteUser(confirmDelete)}
        />
      )}

      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 px-5 py-3 rounded-2xl shadow-lift animate-fade-in flex items-center gap-2 max-w-md
          ${toast.kind === 'success'
            ? 'bg-success text-white'
            : 'bg-danger text-white'}`}
        >
          {toast.kind === 'success' ? <Mail size={14} /> : <X size={14} />}
          <span className="text-[13px]">{toast.text}</span>
        </div>
      )}
    </Layout>
  )
}


function ModalNuevoUsuario({ onClose, onSaved }) {
  const [form, setForm] = useState({
    nombre: '', email: '', telefono: '', password: '', role: 'alquileres',
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const submit = async e => {
    e.preventDefault()
    if (form.password.length < 6) {
      setErr('La contraseña debe tener al menos 6 caracteres.')
      return
    }
    setLoading(true); setErr('')
    try {
      // POST /api/users (admin only) — crea el usuario y dispara welcome email
      // si SMTP está configurado. Devuelve {user, email_enviado, email_motivo}.
      const r = await api.post('/api/users/', {
        nombre: form.nombre.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        telefono: form.telefono || null,
        role: form.role,
        enviar_email: true,
      })
      onSaved(r.data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al crear el usuario.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-md shadow-lift animate-scale-in my-6"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-xl sm:text-2xl">Nuevo usuario</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Nombre completo *</label>
            <input className="input" required autoFocus
              value={form.nombre} onChange={set('nombre')} placeholder="Juan Pérez" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Email *</label>
              <input className="input" type="email" required
                value={form.email} onChange={set('email')} placeholder="juan@ciudad.com" />
            </div>
            <div>
              <label className="label">Teléfono</label>
              <input className="input"
                value={form.telefono} onChange={set('telefono')} placeholder="+54 ..." />
            </div>
          </div>
          <div>
            <label className="label">Contraseña inicial * (mín. 6)</label>
            <input className="input" type="password" required minLength={6}
              value={form.password} onChange={set('password')} />
          </div>
          <div>
            <label className="label">Rol del sistema</label>
            <select className="input" value={form.role} onChange={set('role')}>
              {ROLES.map(r => (
                <option key={r} value={r}>{ROL_LABEL[r]}</option>
              ))}
            </select>
            <p className="text-[11px] text-muted dark:text-gray-500 mt-1.5">
              El rol determina qué áreas del sistema puede operar y qué tools puede invocar
              desde el agente de Telegram.
            </p>
          </div>

          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}

          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Creando…' : 'Crear usuario'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


function ModalEditRol({ user, onClose, onSaved }) {
  const [role, setRole] = useState(user.role)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const submit = async e => {
    e.preventDefault()
    setLoading(true); setErr('')
    try {
      await api.patch(`/api/users/${user.id}`, { role })
      onSaved()
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al guardar.')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-sm shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="hero-title text-xl">Editar rol</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <div className="flex items-center gap-3 mb-6 p-4 bg-neutral-50 dark:bg-[#1A1A1A] rounded-2xl">
          <div className="w-10 h-10 rounded-full bg-primary text-white dark:bg-white dark:text-primary grid place-items-center font-semibold">
            {user.nombre?.[0]?.toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-[14px]">{user.nombre}</p>
            <p className="text-[12px] text-muted dark:text-gray-500">{user.email}</p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Rol del sistema</label>
            <select className="input" value={role} onChange={e => setRole(e.target.value)}>
              {ROLES.map(r => (
                <option key={r} value={r}>{ROL_LABEL[r]}</option>
              ))}
            </select>
          </div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button>
            <button className="btn-primary flex-1" disabled={loading}>
              {loading ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


function ModalConfirmDelete({ user, onClose, onConfirm }) {
  const [loading, setLoading] = useState(false)
  const handle = async () => {
    setLoading(true)
    await onConfirm()
    setLoading(false)
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4"
      onClick={onClose}>
      <div className="card p-8 w-full max-w-sm shadow-lift animate-scale-in"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-danger/10 text-danger grid place-items-center">
            <Trash2 size={18} />
          </div>
          <h2 className="hero-title text-xl">Eliminar usuario</h2>
        </div>

        <p className="text-[13px] text-muted dark:text-gray-400 mb-2">
          Vas a eliminar permanentemente a:
        </p>
        <div className="bg-neutral-50 dark:bg-[#1A1A1A] rounded-2xl p-4 mb-6">
          <p className="font-semibold text-[14px]">{user.nombre}</p>
          <p className="text-[12px] text-muted dark:text-gray-500">{user.email}</p>
        </div>
        <p className="text-[12px] text-muted dark:text-gray-500 mb-6">
          Esta acción no se puede deshacer. El usuario perderá acceso al panel inmediatamente.
        </p>

        <div className="flex gap-3">
          <button type="button" className="btn-secondary flex-1" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button
            className="flex-1 px-4 py-2.5 rounded-full bg-danger text-white text-[13px] font-medium hover:bg-danger/90 transition disabled:opacity-50"
            onClick={handle}
            disabled={loading}
          >
            {loading ? "Eliminando…" : "Sí, eliminar"}
          </button>
        </div>
      </div>
    </div>
  )
}
