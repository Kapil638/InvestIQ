import { cn } from '@/lib/utils'

interface SourceBadgesProps {
  sources: string[]
  className?: string
}

export function SourceBadges({ sources, className }: SourceBadgesProps) {
  if (!sources.length) return null

  return (
    <div className={cn('flex flex-wrap gap-1.5', className)}>
      {sources.map((source) => (
        <span
          key={source}
          className="rounded-md border border-border/60 bg-background/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
        >
          {source}
        </span>
      ))}
    </div>
  )
}
