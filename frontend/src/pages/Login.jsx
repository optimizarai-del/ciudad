import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Logo from '../components/Logo'

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = async e => {
    e.preventDefault()
    setLoading(true); setErr('')
    try {
      await login(form.email, form.password)
      nav('/dashboard')
    } catch {
      setErr('Email o contraseña incorrectos.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.15fr_1fr] bg-bg">

      {/* ── Izquierda: hero ── */}
      <div className="hidden lg:flex flex-col justify-between p-14 xl:p-20 bg-primary relative overflow-hidden">
        {/* Texturas sutiles */}
        <div className="absolute inset-0 opacity-[0.03]"
          style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)', backgroundSize: '32px 32px' }} />

        <Logo size="md" color="light" />

        <div className="relative z-10 max-w-lg animate-slide-up">
          <div className="text-[11px] uppercase tracking-[0.22em] text-white/40 font-semibold mb-6">
            Inmuebles · Contratos · Gestión
          </div>
          <h1 className="hero-title text-6xl xl:text-7xl text-white mb-6">
            Tu cartera<br />
            <span className="text-white/40">inmobiliaria.</span>
          </h1>
          <p className="text-white/50 text-lg leading-relaxed font-light max-w-md">
            Gestioná alquileres, ventas, contratos y calculadoras de costos
            desde un solo lugar.
          </p>
        </div>

        <div className="text-white/20 text-[11px] tracking-[0.15em] uppercase">
          © CIUDAD. 2026
        </div>
      </div>

      {/* ── Derecha: form ── */}
      <div className="flex flex-col justify-center px-6 py-12 lg:px-16 xl:px-20 bg-white">
        <div className="w-full max-w-sm mx-auto animate-fade-in">

          <div className="lg:hidden mb-10">
            <Logo size="md" />
          </div>

          <h2 className="hero-title text-4xl text-primary mb-2">Iniciar sesión</h2>
          <p className="text-muted text-[15px] font-light mb-10">Bienvenido de vuelta.</p>

          <form onSubmit={handle} className="space-y-5">
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" placeholder="admin@ciudad.com"
                value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <input className="input" type="password" placeholder="••••••••"
                value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required />
            </div>

            {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2.5 rounded-xl">{err}</p>}

            <button className="btn-primary btn-lg w-full mt-2" disabled={loading}>
              {loading ? 'Ingresando…' : 'Continuar'}
            </button>
          </form>

          {/* Demo box */}
          <div className="mt-8 p-4 rounded-2xl bg-neutral-100 border border-border">
            <p className="text-[11px] uppercase tracking-[0.12em] text-muted font-semibold mb-2">Demo</p>
            <div className="space-y-1">
              <p className="text-[13px] text-primary font-mono">admin@ciudad.com</p>
              <p className="text-[13px] text-primary font-mono">ciudad1234</p>
            </div>
            <button
              onClick={() => setForm({ email: 'admin@ciudad.com', password: 'ciudad1234' })}
              className="btn-ghost mt-3 w-full text-[12px] py-1.5">
              Completar automáticamente
            </button>
          </div>

          <p className="text-[13px] text-muted text-center mt-8">
            ¿No tenés cuenta?{' '}
            <Link to="/register" className="text-primary font-medium hover:underline">Registrarse</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
