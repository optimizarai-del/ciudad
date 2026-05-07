/**
 * Logo de CIUDAD — Negocios Inmobiliarios.
 * Usa la imagen oficial cargada en /public/logo-ciudad.jpg.
 * El JPG tiene fondo negro: las variantes 'light' (chica, en navbar/sidebar)
 * y 'mark' (sólo el isotipo) lo recortan en un cuadrado redondeado.
 *
 * Props:
 *   size:    'xs' | 'sm' | 'md' | 'lg' | 'xl'
 *   tagline: bool (muestra "Negocios Inmobiliarios" + #VIVIRMEJOR)
 *   variant: 'mark' (sólo logo cuadrado) | 'full' (logo + texto al lado)
 *   color:   'dark' | 'light'  (color del texto al lado)
 */
export default function Logo({
  size = 'md',
  tagline = false,
  variant = 'full',
  color = 'dark',
  className = '',
}) {
  const dims = {
    xs: { mark: 24, txt: 'text-[13px]', sub: 'text-[8px]',  slogan: 'text-[7px]'  },
    sm: { mark: 32, txt: 'text-base',   sub: 'text-[9px]',  slogan: 'text-[8px]'  },
    md: { mark: 40, txt: 'text-xl',     sub: 'text-[10px]', slogan: 'text-[9px]'  },
    lg: { mark: 64, txt: 'text-3xl',    sub: 'text-xs',     slogan: 'text-[10px]' },
    xl: { mark: 96, txt: 'text-5xl',    sub: 'text-sm',     slogan: 'text-[12px]' },
  }[size]

  const textColor = color === 'light' ? 'text-white' : 'text-primary'
  const subColor  = color === 'light' ? 'text-white/70' : 'text-muted'

  const Mark = (
    <img
      src="/logo-ciudad.jpg"
      alt="CIUDAD — Negocios Inmobiliarios"
      width={dims.mark}
      height={dims.mark}
      className="rounded-lg object-cover shrink-0"
      style={{ width: dims.mark, height: dims.mark }}
    />
  )

  if (variant === 'mark') return <span className={className}>{Mark}</span>

  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      {Mark}
      <div className="leading-none">
        <div className={`font-display font-bold tracking-tight ${textColor} ${dims.txt}`}>
          CIUDAD
        </div>
        {tagline && (
          <>
            <div className={`mt-1 font-medium tracking-[0.16em] uppercase ${subColor} ${dims.sub}`}>
              Negocios Inmobiliarios
            </div>
            <div
              className={`mt-1 font-bold tracking-[0.18em] ${dims.slogan}`}
              style={{ color: '#B8893A' }}
            >
              #VIVIRMEJOR
            </div>
          </>
        )}
      </div>
    </div>
  )
}
