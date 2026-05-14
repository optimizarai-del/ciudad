import { useEffect, useState } from 'react'
import { Users, Pencil, X, ShieldCheck, Plus, Trash2, Mail } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { useAuth } from '../context/AuthContext'

const ROLES = ['admin', 'gerencia', 'alquileres', 'ventas', 'agente_ia']

const ROL_CHIP = {
  admin:      'chip-dark',
  gerencia:   'chip-success',
  alquileres: 'chip-gray',
  ventas:     'chip-warn',
  agente_ia:  'chip-muted',
}

const ROL_LABEL = {
  admin:      'Administrador',
  gerencia:   'Gerencia',
  alquileres: 'Alquileres',
  ventas:     'Ventas',
  agente_ia:  'Agente IA',
}

export default function Equipo() {
  const { user: me } = useAuth()
  const [list, setList] = useState([])
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [toast, setToast] = useState(null)  // {kind:'success'|'error', text}

  const load = () => api.get('/api/users').then(r => setList(r.data)).catch(() => {})
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

  return (
    <Layout>
      <div className="max-w-4xl mx-auto animate-fade-in">

        <header className="mb-10">
          <div className="hero-eyebrow">Administración</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Equipo</h1>
              <p className="hero-sub">Usuarios del sistema y sus permisos.</p>
            </div>
            <button className="btn-primary" onClick={() => setCreating(true)}>
              <Plus size={14} /> Nuevo usuario
            </button>
          </div>
        </header>

        {/* Tabla */}
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-border dark:border-[#2A2A2A] flex items-center justify-between">
            <h2 className="font-semibold text-[15px] tracking-tight">Miembros activos</h2>
            <span className="chip-gray">{list.length} usuarios</span>
          </div>

          {list.length === 0 ? (
            <div className="py-20 text-center">
              <Users size={36} className="mx-auto text-muted/30 mb-4" />
              <p className="text-muted text-[14px] mb-4">No hay usuarios registrados aún.</p>
              <button className="btn-primary" onClick={() => setCreating(true)}>
                <Plus size={14} /> Crear primer usuario
              </button>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border dark:border-[#2A2A2A]">
                <tr>
                  <th className="th">Usuario</th>
                  <th className="th hidden md:table-cell">Email</th>
                  <th className="th">Rol</th>
                  <th className="th hidden md:table-cell">Estado</th>
                  <th className="th w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border dark:divide-[#2A2A2A]">
                {list.map(u => (
                  <tr key={u.id} className="hover:bg-neutral-50 dark:hover:bg-[#1A1A1A] transition">
                    <td className="td">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary text-white dark:bg-white dark:text-primary grid place-items-center text-[11px] font-semibold shrink-0">
                          {u.nombre?.[0]?.toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-[13px] flex items-center gap-1.5">
                            {u.nombre}
                            {u.id === me?.id && (
                              <span className="chip-muted text-[9px] py-0.5">Vos</span>
                            )}
                          </p>
                          {u.telefono && (
                            <p className="text-[11px] text-muted dark:text-gray-500">{u.telefono}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="td hidden md:table-cell text-[12px] text-muted dark:text-gray-500">{u.email}</td>
                    <td className="td">
                      <span className={ROL_CHIP[u.role] || 'chip-muted'}>
                        {ROL_LABEL[u.role] || u.role}
                      </span>
                    </td>
                    <td className="td hidden md:table-cell">
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-success' : 'bg-muted/40'}`} />
                        <span className="text-[12px] text-muted dark:text-gray-500">{u.is_active ? 'Activo' : 'Inactivo'}</span>
                      </div>
                    </td>
                    <td className="td">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setEditing(u)}
                          title="Editar rol"
                          className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-[#1E1E1E] text-muted hover:text-primary dark:hover:text-white transition"
                        >
                          <Pencil size={13} />
                        </button>
                        {u.id !== me?.id && (
                          <button
                            onClick={() => setConfirmDelete(u)}
                            title="Eliminar usuario"
                            className="p-1.5 rounded-lg hover:bg-danger/10 text-muted hover:text-danger transition"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Info roles */}
        <div className="card p-6 mt-6">
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
                  { label: 'Cobranza',        perms: [true,  true,  true,  false, false] },
                  { label: 'Liquidaciones',   perms: [true,  true,  true,  false, false] },
                  { label: 'Clientes',        perms: [true,  true,  true,  true,  false] },
                  { label: 'Calculadora',     perms: [true,  true,  true,  true,  true ] },
                  { label: 'Tokko (Ventas)',  perms: [true,  true,  false, true,  false] },
                  { label: 'Finanzas',        perms: [true,  true,  false, false, false] },
                  { label: 'Recordatorios',   perms: [true,  true,  true,  true,  true ] },
                  { label: 'Agente IA',       perms: [true,  true,  true,  true,  true ] },
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
          <h2 className="hero-title text-2xl">Nuevo usuario</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Nombre completo *</label>
            <input className="input" required autoFocus
              value={form.nombre} onChange={set('nombre')} placeholder="Juan Pérez" />
          </div>
          <div className="grid grid-cols-2 gap-3">
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
