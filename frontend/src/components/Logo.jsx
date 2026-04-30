export default function Logo({ size = 'md', tagline = false, color = 'dark', className = '' }) {
  const s = {
    xs: { txt: 'text-lg',  dot: 'w-1.5 h-1.5', tag: 'text-[8px]'  },
    sm: { txt: 'text-xl',  dot: 'w-2   h-2',   tag: 'text-[9px]'  },
    md: { txt: 'text-2xl', dot: 'w-2.5 h-2.5', tag: 'text-[10px]' },
    lg: { txt: 'text-5xl', dot: 'w-4   h-4',   tag: 'text-xs'     },
    xl: { txt: 'text-7xl', dot: 'w-6   h-6',   tag: 'text-sm'     },
  }[size]

  const textColor = color === 'light' ? 'text-white' : 'text-primary'
  const dotColor  = color === 'light' ? 'bg-white/60' : 'bg-primary/30'
  const tagColor  = color === 'light' ? 'text-white/50' : 'text-muted/60'

  return (
    <div className={`inline-flex flex-col leading-none ${className}`}>
      <div className={`flex items-end font-display font-bold tracking-[-0.04em] ${textColor} ${s.txt}`}>
        <span>CIUDAD</span>
        <span className={`${s.dot} ${dotColor} rounded-sm mb-[0.12em] ml-0.5`} aria-hidden />
      </div>
      {tagline && (
        <div className={`${s.tag} font-medium tracking-[0.18em] uppercase mt-1.5 ${tagColor}`}>
          Inmuebles · Contratos · Gestión
        </div>
      )}
    </div>
  )
}
