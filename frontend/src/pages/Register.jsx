import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Logo from '../components/Logo'
import api from '../utils/api'

export default function Register() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({ nombre: '', email: '', telefono: '', password: '', confirm: '' })
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const set = k => e => setForm({ ...form, [k]: e.target.value })

  const handle = async e => {
    e.preventDefault()
    if (form.password !== form.confirm) { setErr('Las contraseñas no coinciden.'); return }
    setLoading(true); setErr('')
    try {
      await api.post('/auth/register', {
        nombre: form.nombre, email: form.email,
        telefono: form.telefono, password: form.password,
      })
      await login(form.email, form.password)
      nav('/dashboard')
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error al registrar.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#F7F7F7] dark:bg-[#0A0A0A] flex items-center justify-center p-6 transition-colors duration-300">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-10 text-center">
          <Logo size="md" className="justify-center" />
          <p className="text-[#737373] dark:text-[#9A9A9A] text-[13px] mt-2">Creá tu cuenta</p>
        </div>

        <div className="card p-8 shadow-card">
          <h2 className="hero-title text-3xl mb-7">Registro.</h2>

          <form onSubmit={handle} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Nombre</label>
                <input className="input" placeholder="María" value={form.nombre} onChange={set('nombre')} required />
              </div>
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" placeholder="maria@mail.com" value={form.email} onChange={set('email')} required />
              </div>
            </div>
            <div>
              <label className="label">Teléfono (opcional)</label>
              <input className="input" placeholder="+54 9 11 ..." value={form.telefono} onChange={set('telefono')} />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <input className="input" type="password" value={form.password} onChange={set('password')} required />
            </div>
            <div>
              <label className="label">Confirmar contraseña</label>
              <input className="input" type="password" value={form.confirm} onChange={set('confirm')} required />
            </div>

            {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2.5 rounded-xl">{err}</p>}

            <button className="btn-primary btn-lg w-full mt-1" disabled={loading}>
              {loading ? 'Creando cuenta…' : 'Crear cuenta'}
            </button>
          </form>
        </div>

        <p className="text-[13px] text-muted text-center mt-6">
          ¿Ya tenés cuenta?{' '}
          <Link to="/login" className="text-[#0A0A0A] dark:text-white font-medium hover:underline">Iniciar sesión</Link>
        </p>
      </div>
    </div>
  )
}
