/**
 * Barra de progreso del contrato.
 *
 * Colores:
 *   - Verde       → más de 2 meses para el vencimiento
 *   - Amarillo    → 2 meses o menos
 *   - Rojo        → 1 mes o menos (o ya vencido)
 *
 * Modos:
 *   - `compact` (default) → versión chica para esquina superior derecha de cards
 *   - `full`              → versión grande con %% y meses restantes
 */
export default function ProgresoContrato({ inicio, fin, estado, mode = 'compact', className = '' }) {
  if (!inicio || !fin || estado !== 'vigente') return null
  const ini = new Date(inicio), end = new Date(fin), now = new Date()
  if (isNaN(ini) || isNaN(end) || end <= ini) return null

  const total = end - ini
  const elapsed = Math.max(0, Math.min(total, now - ini))
  const pct = Math.round((elapsed / total) * 100)

  const msPorMes = 1000 * 60 * 60 * 24 * 30.44
  const mesesRestantes = (end - now) / msPorMes

  let color, bg, label, textColor
  if (mesesRestantes <= 0) {
    color = 'bg-red-500'; bg = 'bg-red-100 dark:bg-red-900/30'
    textColor = 'text-red-600 dark:text-red-400'
    label = 'Vencido'
  } else if (mesesRestantes <= 1) {
    color = 'bg-red-500'; bg = 'bg-red-100 dark:bg-red-900/30'
    textColor = 'text-red-600 dark:text-red-400'
    label = 'Último mes'
  } else if (mesesRestantes <= 2) {
    color = 'bg-amber-500'; bg = 'bg-amber-100 dark:bg-amber-900/30'
    textColor = 'text-amber-600 dark:text-amber-400'
    label = `${Math.ceil(mesesRestantes)} meses`
  } else {
    color = 'bg-emerald-500'; bg = 'bg-emerald-100 dark:bg-emerald-900/30'
    textColor = 'text-emerald-700 dark:text-emerald-400'
    label = `${Math.ceil(mesesRestantes)} meses`
  }

  if (mode === 'compact') {
    return (
      <div className={`flex flex-col items-end gap-0.5 ${className}`}
        title={`${pct}% transcurrido · ${label} restantes`}>
        <span className={`text-[9px] font-semibold uppercase tracking-wider ${textColor}`}>{label}</span>
        <div className={`h-1 w-16 rounded-full overflow-hidden ${bg}`}>
          <div className={`h-full ${color} transition-all`} style={{ width: `${Math.max(4, pct)}%` }} />
        </div>
      </div>
    )
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between text-[10px] mb-1">
        <span className="text-muted">{pct}% transcurrido</span>
        <span className={`font-medium ${textColor}`}>{label} restantes</span>
      </div>
      <div className={`h-1.5 rounded-full overflow-hidden ${bg}`}>
        <div className={`h-full ${color} transition-all`} style={{ width: `${Math.max(2, pct)}%` }} />
      </div>
    </div>
  )
}
