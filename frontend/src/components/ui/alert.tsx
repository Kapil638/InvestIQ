import { AlertCircle, CheckCircle2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AlertProps {
  variant?: 'default' | 'destructive' | 'success'
  title?: string
  children: React.ReactNode
  className?: string
}

export function Alert({ variant = 'default', title, children, className }: AlertProps) {
  const Icon = variant === 'destructive' ? AlertCircle : variant === 'success' ? CheckCircle2 : Info

  return (
    <div
      className={cn(
        'flex gap-3 rounded-lg border p-4 text-sm',
        variant === 'destructive' && 'border-destructive/40 bg-destructive/10 text-red-200',
        variant === 'success' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
        variant === 'default' && 'border-border bg-muted/40 text-foreground',
        className,
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div>
        {title && <p className="mb-1 font-medium">{title}</p>}
        <div className="text-muted-foreground">{children}</div>
      </div>
    </div>
  )
}
