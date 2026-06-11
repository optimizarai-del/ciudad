import { useEffect, useState } from 'react'
import { Plus, X, CheckCircle2 } from 'lucide-react'
import Layout from '../../components/Layout/Layout'
import api from '../../utils/api'

const ESTADOS = ['abierta', 'sena', 'cerrada', 'caida']
const fmtUSD = n => n ? 'USD ' + n.toLocaleString('es-AR') : '—'
const num = v => v === '' || v == null ? null : Number(v)

export default function Operaciones() {
  const [list, setList] = useState([])
  const [clientes, setClientes] = useState([])
  const [props, setProps] = useState([])
  const [open, setOpen] = useState(false)

  const load = () => {
    api.get('/api/ventas-crm/operaciones').then(r => setList(r.data || []))
    api.get('/api/ventas-crm/clientes').then(r => setClientes(r.data || []))
    api.get('/api/ventas-crm/propiedades').then(r => setProps(r.data || []))
  }
  useEffect(() => { load() }, [])
  const cli = id => clientes.find(c => c.id === id)?.nombre || '—'

  return (
    <Layout>
      <div className="max-w-5xl mx-auto animate-fade-in">
        <header className="mb-6">
          <div className="hero-eyebrow">Operaciones cerradas</div>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h1 className="hero-title text-3xl sm:text-4xl md:text-5xl mb-2">Operaciones</h1>
              <p className="hero-sub">Cierres con cálculo automático de comisión.</p>
            </div>
            <button className="btn-primary" onClick={() => setOpen(true)}><Plus size={14} /> Nueva operación</button>
          </div>
        </header>

        {list.length === 0 ? (
          <div className="card text-center py-20"><CheckCircle2 size={36} className="mx-auto text-muted/30 mb-3" /><p className="text-muted text-[14px]">Sin operaciones todavía.</p></div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead className="bg-neutral-50 dark:bg-[#141414] border-b border-border">
                <tr><th className="th">Cliente</th><th className="th text-center">Estado</th><th className="th">Monto</th><th className="th">Comisión</th><th className="th">Fecha</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {list.map(o => (
                  <tr key={o.id} className="hover:bg-neutral-50 dark:hover:bg-[#1A1A1A]">
                    <td className="td font-medium text-[13px]">{cli(o.cliente_id)}</td>
                    <td className="td text-center"><span className="chip-muted capitalize">{o.estado}</span></td>
                    <td className="td text-[13px]">{fmtUSD(o.monto_cierre_usd)}</td>
                    <td className="td text-[13px]">{fmtUSD(o.comision_monto_usd)} <span className="text-[11px] text-muted">({o.comision_pct}%{o.comision_manual ? ' manual' : ''})</span></td>
                    <td className="td text-[12px] text-muted">{o.fecha_cierre || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {open && <OpModal clientes={clientes} props={props} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load() }} />}
    </Layout>
  )
}

function OpModal({ clientes, props, onClose, onSaved }) {
  const [form, setForm] = useState({ cliente_id: '', propiedad_id: '', estado: 'cerrada', monto_cierre_usd: '', fecha_cierre: '', comision_pct: '', comision_monto_usd: '', notas: '' })
  const [manual, setManual] = useState(false)
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(false)
  const set = k => e => setForm({ ...form, [k]: e.target.value })
  const submit = async e => {
    e.preventDefault(); setErr('')
    if (!form.cliente_id) { setErr('Elegí un cliente.'); return }
    if (!form.monto_cierre_usd) { setErr('Ingresá el monto de cierre.'); return }
    setLoading(true)
    const payload = {
      cliente_id: num(form.cliente_id), propiedad_id: num(form.propiedad_id),
      estado: form.estado, monto_cierre_usd: num(form.monto_cierre_usd),
      fecha_cierre: form.fecha_cierre || null, notas: form.notas || null,
    }
    if (manual) { payload.comision_pct = num(form.comision_pct); payload.comision_monto_usd = num(form.comision_monto_usd) }
    try { await api.post('/api/ventas-crm/operaciones', payload); onSaved() }
    catch (e) { setErr(e.response?.data?.detail || 'Error.') } finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 grid place-items-center p-4 overflow-auto" onClick={onClose}>
      <div className="card p-6 sm:p-8 w-full max-w-lg shadow-lift animate-scale-in my-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6"><h2 className="hero-title text-xl sm:text-2xl">Nueva operación</h2><button onClick={onClose} className="btn-ghost p-2"><X size={16} /></button></div>
        <form onSubmit={submit} className="space-y-4">
          <div><label className="label">Cliente</label><select className="input" value={form.cliente_id} onChange={set('cliente_id')}><option value="">— elegir —</option>{clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select></div>
          <div><label className="label">Propiedad</label><select className="input" value={form.propiedad_id} onChange={set('propiedad_id')}><option value="">— elegir —</option>{props.map(p => <option key={p.id} value={p.id}>{p.titulo || p.direccion || `#${p.id}`}</option>)}</select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Estado</label><select className="input" value={form.estado} onChange={set('estado')}>{ESTADOS.map(s => <option key={s}>{s}</option>)}</select></div>
            <div><label className="label">Monto cierre USD</label><input className="input" type="number" value={form.monto_cierre_usd} onChange={set('monto_cierre_usd')} /></div>
          </div>
          <div><label className="label">Fecha de cierre</label><input className="input" type="date" value={form.fecha_cierre} onChange={set('fecha_cierre')} /></div>
          <label className="flex items-center gap-2 text-[13px] text-muted">
            <input type="checkbox" checked={manual} onChange={e => setManual(e.target.checked)} /> Cargar comisión manualmente
          </label>
          {manual ? (
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Comisión %</label><input className="input" type="number" step="0.1" value={form.comision_pct} onChange={set('comision_pct')} /></div>
              <div><label className="label">Monto comisión USD</label><input className="input" type="number" value={form.comision_monto_usd} onChange={set('comision_monto_usd')} /></div>
            </div>
          ) : <p className="text-[12px] text-muted bg-neutral-50 dark:bg-[#141414] rounded-xl px-3 py-2">La comisión se calcula automáticamente según la config del vendedor y el tipo de propiedad.</p>}
          <div><label className="label">Notas</label><textarea className="input resize-none" rows={2} value={form.notas} onChange={set('notas')} /></div>
          {err && <p className="text-[13px] text-danger bg-danger/5 px-4 py-2 rounded-xl">{err}</p>}
          <div className="flex gap-3 pt-1"><button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancelar</button><button className="btn-primary flex-1" disabled={loading}>{loading ? 'Guardando…' : 'Crear'}</button></div>
        </form>
      </div>
    </div>
  )
}
