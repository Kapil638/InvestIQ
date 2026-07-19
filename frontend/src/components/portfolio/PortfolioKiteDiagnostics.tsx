import type { KiteStatusResponse } from '@/types/api'
import { cn } from '@/lib/utils'

interface PortfolioKiteDiagnosticsProps {
  status: KiteStatusResponse | null
  loading?: boolean
  className?: string
}

function DiagnosticRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  )
}

function yesNo(value: boolean | undefined) {
  if (value === undefined) return '—'
  return value ? 'Yes' : 'No'
}

export function PortfolioKiteDiagnostics({
  status,
  loading = false,
  className,
}: PortfolioKiteDiagnosticsProps) {
  return (
    <div className={cn('glass-card rounded-2xl p-5', className)}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-primary">
        Connection diagnostics
      </p>
      {loading && !status ? (
        <p className="text-sm text-muted-foreground">Loading Kite status…</p>
      ) : (
        <div className="space-y-2">
          <DiagnosticRow label="Kite enabled" value={yesNo(status?.enabled)} />
          <DiagnosticRow label="Authenticated" value={yesNo(status?.authenticated)} />
          <DiagnosticRow label="Connected" value={yesNo(status?.connected)} />
          <DiagnosticRow label="Broker" value={status?.broker ?? '—'} />
          <DiagnosticRow label="User ID" value={status?.user_id ?? '—'} />
          <div className="border-t border-border/60 pt-3">
            <p className="text-xs text-muted-foreground">Last status message</p>
            <p className="mt-1 text-sm leading-relaxed text-foreground">
              {status?.message ?? 'No status available.'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
