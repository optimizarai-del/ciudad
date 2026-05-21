/**
 * Barra de tiempo restante del contrato (cuenta regresiva).
 *
 * La barra MUESTRA EL TIEMPO QUE QUEDA: arranca llena al principio del
 * contrato y se va vaciando a medida que pasa el tiempo.
 *
 * Colores según porcentaje restante (proporcional a la duración total):
 *   - Verde       → > 50% del tiempo restante
 *   - Amarillo    → 20% – 50% del tiempo restante
 *   - Rojo        → < 20% del tiempo restante  (o ≤ 1 mes absoluto, o vencido)
 *
 * Modos:
 *   - `compact` (default) → versión chica para tablas / esquinas de cards
 *   - `full`              → versión grande con %% y meses restantes
 */
export default function ProgresoContrato({ inicio, fin, estado, mode = 'compact', className = '' }) {
  if (!inicio || !fin || estado !== 'vigente') return null
  const ini = new Date(inicio), end = new Date(fin), now = new Date()
  if (isNaN(ini) || isNaN(end) || end <= ini) return null

  const total = end - ini
  const elapsed = Math.max(0, Math.min(total, now - ini))
  const pctElapsed = Math.round((elapsed / total) * 100)
  const pctRestante = Math.max(0, 100 - pctElapsed)

  const msPorMes = 1000 * 60 * 60 * 24 * 30.44
  const mesesRestantes = (end - now) / msPorMes

  // Color por porcentaje restante (proporcional al total del contrato)
  // o por meses absolutos cuando faltan muy pocos (gana lo más restrictivo).
  let color, bg, label, textColor
  if (mesesRestantes <= 0) {
    color = 'bg-red-500'; bg = 'bg-red-100 dark:bg-red-900/30'
    textColor = 'text-red-600 dark:text-red-400'
    label = 'Vencido'
  } else if (pctRestante < 20 || mesesRestantes <= 1) {
    color = 'bg-red-500'; bg = 'bg-red-100 dark:bg-red-900/30'
    textColor = 'text-red-600 dark:text-red-400'
    label = mesesRestantes <= 1 ? 'Último mes' : `${Math.ceil(mesesRestantes)} meses`
  } else if (pctRestante < 50) {
    color = 'bg-amber-500'; bg = 'bg-amber-100 dark:bg-amber-900/30'
    textColor = 'text-amber-600 dark:text-amber-400'
    label = `${Math.ceil(mesesRestantes)} meses`
  } else {
    color = 'bg-[#27FF00]'; bg = 'bg-[#27FF00]/15 dark:bg-[#27FF00]/20'
    textColor = 'text-[#1F9F00] dark:text-[#27FF00]'
    label = `${Math.ceil(mesesRestantes)} meses`
  }

  if (mode === 'compact') {
    return (
      <div className={`flex flex-col items-end gap-0.5 ${className}`}
        title={`${pctRestante}% del contrato restante · ${label}`}>
        <span className={`text-[9px] font-semibold uppercase tracking-wider ${textColor}`}>{label}</span>
        <div className={`h-1 w-16 rounded-full overflow-hidden ${bg}`}>
          <div className={`h-full ${color} transition-all`} style={{ width: `${Math.max(4, pctRestante)}%` }} />
        </div>
      </div>
    )
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between text-[10px] mb-1">
        <span className="text-muted">{pctRestante}% restante</span>
        <span className={`font-medium ${textColor}`}>{label}</span>
      </div>
      <div className={`h-1.5 rounded-full overflow-hidden ${bg}`}>
        <div className={`h-full ${color} transition-all`} style={{ width: `${Math.max(2, pctRestante)}%` }} />
      </div>
    </div>
  )
}
