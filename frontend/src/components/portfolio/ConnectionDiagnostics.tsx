import { cn } from '@/lib/utils'

export interface DiagnosticRowData {
  label: string
  value: string
}

interface ConnectionDiagnosticsProps {
  title: string
  loadingLabel: string
  loading?: boolean
  hasData: boolean
  rows: DiagnosticRowData[]
  message?: string | null
  className?: string
}

function DiagnosticRow({ label, value }: DiagnosticRowData) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  )
}

export function yesNo(value: boolean | undefined) {
  if (value === undefined) return '—'
  return value ? 'Yes' : 'No'
}

// Shared shell for the Kite/Groww (and any future broker's) connection status
// card - each broker only differs in which rows it shows and its message,
// not in the card structure itself.
export function ConnectionDiagnostics({
  title,
  loadingLabel,
  loading = false,
  hasData,
  rows,
  message,
  className,
}: ConnectionDiagnosticsProps) {
  return (
    <div className={cn('glass-card rounded-2xl p-5', className)}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-primary">{title}</p>
      {loading && !hasData ? (
        <p className="text-sm text-muted-foreground">{loadingLabel}</p>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <DiagnosticRow key={row.label} {...row} />
          ))}
          <div className="border-t border-border/60 pt-3">
            <p className="text-xs text-muted-foreground">Last status message</p>
            <p className="mt-1 text-sm leading-relaxed text-foreground">
              {message ?? 'No status available.'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
