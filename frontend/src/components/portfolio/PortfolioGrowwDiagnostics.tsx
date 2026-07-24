import type { GrowwStatusResponse } from '@/types/api'
import { cn } from '@/lib/utils'

interface PortfolioGrowwDiagnosticsProps {
  status: GrowwStatusResponse | null
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

// No "Connect" button, unlike Kite's diagnostics card - Groww has no browser
// OAuth step. Connectivity is purely a function of GROWW_ENABLED and
// GROWW_API_KEY/SECRET being valid server-side, so this is read-only status.
export function PortfolioGrowwDiagnostics({
  status,
  loading = false,
  className,
}: PortfolioGrowwDiagnosticsProps) {
  return (
    <div className={cn('glass-card rounded-2xl p-5', className)}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-primary">
        Groww connection diagnostics
      </p>
      {loading && !status ? (
        <p className="text-sm text-muted-foreground">Loading Groww status…</p>
      ) : (
        <div className="space-y-2">
          <DiagnosticRow label="Groww enabled" value={yesNo(status?.enabled)} />
          <DiagnosticRow label="Credentials configured" value={yesNo(status?.credentials_configured)} />
          <DiagnosticRow label="Connected" value={yesNo(status?.connected)} />
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
