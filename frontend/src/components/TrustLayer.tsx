import { cn } from '@/lib/utils'
import { kiteBadgeLabel, resolveDataSources } from '@/lib/dataPlane'
import { useKiteStatus } from '@/hooks/useKiteStatus'
import { useTapetideStatus } from '@/hooks/useTapetideStatus'

export function TrustLayer({ className }: { className?: string }) {
  const { status: kiteStatus } = useKiteStatus()
  const { status: tapetideStatus } = useTapetideStatus()
  const sources = resolveDataSources(kiteStatus, tapetideStatus)

  const fundamentalsLive = Boolean(
    tapetideStatus?.enabled && tapetideStatus.connected && tapetideStatus.token_configured,
  )

  return (
    <section className={cn('space-y-4', className)}>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Data plane</p>
        <h3 className="mt-1 text-lg font-semibold">Grounded in verified sources</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Fundamentals from {fundamentalsLive ? 'Tapetide NSE/BSE MCP' : 'Yahoo Finance'} · live data
          from Tapetide NSE/BSE MCP or Kite · news from Tavily · memory in Supabase & ChromaDB.
        </p>
        {tapetideStatus && (
          <p className="mt-2 text-xs text-muted-foreground">
            Tapetide NSE/BSE MCP: {tapetideStatus.message}
          </p>
        )}
        {kiteStatus && (
          <p className="mt-1 text-xs text-muted-foreground">Kite: {kiteStatus.message}</p>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {sources.map((source) => (
          <div
            key={source.id}
            className="glass-card rounded-xl p-4 transition-colors hover:border-primary/30"
          >
            <div className="mb-3 flex items-start justify-between gap-2">
              <source.icon className="size-5 shrink-0 text-primary" />
              <span
                className={cn(
                  'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                  source.status === 'live'
                    ? 'bg-emerald-500/15 text-emerald-300'
                    : source.status === 'auth'
                      ? 'bg-amber-500/15 text-amber-300'
                      : 'bg-muted text-muted-foreground',
                )}
              >
                {kiteBadgeLabel(source.status)}
              </span>
            </div>
            <p className="text-sm font-medium">{source.title}</p>
            <p className="mt-0.5 text-xs font-medium text-primary/90">{source.provider}</p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{source.description}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
