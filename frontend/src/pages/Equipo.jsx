import { useEffect, useState } from 'react'
import { Users, Pencil, X, ShieldCheck, UserCircle } from 'lucide-react'
import Layout from '../components/Layout/Layout'
import api from '../utils/api'
import { useAuth } from '../context/AuthContext'

const ROLES = ['admin', 'operador', 'finanzas', 'agente_ia']

const ROL_CHIP = {
  admin:     'chip-dark',
  operador:  'chip-gray',
  finanzas:  'chip-success',
  agente_ia: 'chip-muted',
}

const ROL_LABEL = {
  admin:     'Administrador',
  operador:  'Operador',
  finanzas:  'Finanzas',
  agente_ia: 'Agente IA',
}

export default function Equipo() {
  const { user: me } = useAuth()
  const [list, setList] = useState([])
  const [editing, setEditing] = useState(null)

  const load = () => api.get('/api/users').then(r => setList(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  return (
    <Layout>
      <div className="max-w-4xl mx-auto animate-fade-in">

        <header className="mb-10">
          <div className="hero-eyebrow">Administración</div>
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <h1 className="hero-title text-5xl md:text-6xl mb-3">Equipo.</h1>
              <p className="hero-sub">Usuarios del sistema y sus permisos.</p>
            </div>
          </div>
        </header>

        {/* Tabla */}
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <h2 className="font-semibold text-[15px] tracking-tight">Miembros activos</h2>
            <span className="chip-gray">{list.length} usuarios</span>
          </div>

          {list.length === 0 ? (
            <div className="py-20 text-center">
              <Users size={36} className="mx-auto text-muted/30 mb-4" />
              <p className="text-muted text-[14px]">No hay usuarios registrados aún.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-neutral-50 border-b border-border">
                <tr>
                  <th className="th">Usuario</th>
                  <th className="th hidden md:table-cell">Email</th>
                  <th className="th">Rol</th>
                  <th className="th hidden md:table-cell">Estado</th>
                  <th className="th w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.map(u => (
                  <tr key={u.id} className="hover:bg-neutral-50 transition">
                    <td className="td">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary text-white grid place-items-center text-[11px] font-semibold shrink-0">
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
                            <p className="text-[11px] text-muted">{u.telefono}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="td hidden md:table-cell text-[12px] text-muted">{u.email}</td>
                    <td className="td">
                      <span className={ROL_CHIP[u.role] || 'chip-muted'}>
                        {ROL_LABEL[u.role] || u.role}
                      </span>
                    </td>
                    <td className="td hidden md:table-cell">
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-success' : 'bg-muted/40'}`} />
                        <span className="text-[12px] text-muted">{u.is_active ? 'Activo' : 'Inactivo'}</span>
                      </div>
                    </td>
                    <td className="td">
                      <button
                        onClick={() => setEditing(u)}
                        className="p-1.5 rounded-lg hover:bg-neutral-100 text-muted hover:text-primary transition"
                      >
                        <Pencil size={13} />
                      </button>
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
            <ShieldCheck size={15} className="text-muted" />
            <p className="font-semibold text-[13px] tracking-tight">Matriz de permisos</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <th className="text-left text-muted font-medium py-2 pr-4">Recurso</th>
                  {ROLES.map(r => (
                    <th key={r} className="text-center text-muted font-medium py-2 px-3">
                      {ROL_LABEL[r]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  { label: 'Propiedades',   perms: [true, true, true, false] },
                  { label: 'Contratos',     perms: [true, true, true, false] },
                  { label: 'Clientes',      perms: [true, true, false, false] },
                  { label: 'Calculadora',   perms: [true, true, true, true] },
                  { label: 'Finanzas',      perms: [true, false, true, false] },
                  { label: 'Agente IA',     perms: [true, true, true, true] },
                  { label: 'Equipo',        perms: [true, false, false, false] },
                ].map(row => (
                  <tr key={row.label} className="hover:bg-neutral-50 transition">
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

      {editing && (
        <ModalEditRol
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}
    </Layout>
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
          <h2 className="hero-title text-xl">Editar rol.</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button>
        </div>

        <div className="flex items-center gap-3 mb-6 p-4 bg-neutral-50 rounded-2xl">
          <div className="w-10 h-10 rounded-full bg-primary text-white grid place-items-center font-semibold">
            {user.nombre?.[0]?.toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-[14px]">{user.nombre}</p>
            <p className="text-[12px] text-muted">{user.email}</p>
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
