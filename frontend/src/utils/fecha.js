// Parseo seguro de fechas para mostrar.
//
// Bug que resuelve: `new Date("2026-05-01")` interpreta el string como medianoche
// UTC; al mostrarlo en hora Argentina (UTC-3) se corre al día ANTERIOR
// (30/04/2026). Para fechas "solo día" (YYYY-MM-DD) hay que parsearlas en hora
// LOCAL. Las fechas con hora (ISO con 'T') se dejan como están.

export function toLocalDate(s) {
  if (!s) return null
  const str = String(s)
  // 'YYYY-MM-DD' → forzar medianoche local (evita el corrimiento de día).
  const iso = /^\d{4}-\d{2}-\d{2}$/.test(str) ? `${str}T00:00:00` : str
  const d = new Date(iso)
  return isNaN(d.getTime()) ? null : d
}

const FMT_DEFAULT = { day: '2-digit', month: 'short', year: 'numeric' }

// Formatea una fecha a es-AR sin corrimiento de día. `s` puede ser 'YYYY-MM-DD'
// o un ISO con hora. Devuelve `fallback` si no hay fecha válida.
export function fmtFecha(s, opts = FMT_DEFAULT, fallback = '—') {
  const d = toLocalDate(s)
  return d ? d.toLocaleDateString('es-AR', opts) : fallback
}
