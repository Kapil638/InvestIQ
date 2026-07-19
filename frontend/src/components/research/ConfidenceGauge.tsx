import { cn } from '@/lib/utils'

interface ConfidenceGaugeProps {
  value: number
  className?: string
  size?: 'sm' | 'md'
}

export function ConfidenceGauge({ value, className, size = 'md' }: ConfidenceGaugeProps) {
  const clamped = Math.max(0, Math.min(100, value))
  const tone =
    clamped >= 70 ? 'bg-emerald-500' : clamped >= 45 ? 'bg-amber-500' : 'bg-orange-500'

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Confidence</span>
        <span className="font-semibold tabular-nums text-foreground">{clamped}%</span>
      </div>
      <div
        className={cn(
          'overflow-hidden rounded-full bg-muted/80',
          size === 'sm' ? 'h-1.5' : 'h-2',
        )}
      >
        <div
          className={cn('h-full rounded-full transition-all', tone)}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
