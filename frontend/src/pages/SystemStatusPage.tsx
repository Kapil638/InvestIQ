import { useCallback, useEffect, useState } from 'react'
import { Activity, RefreshCw } from 'lucide-react'
import { getDatabaseStatus, getHealth } from '@/lib/api'
import type { DatabaseStatusResponse, HealthResponse } from '@/types/api'
import { useKiteStatus } from '@/hooks/useKiteStatus'
import { useGrowwStatus } from '@/hooks/useGrowwStatus'
import { useTapetideStatus } from '@/hooks/useTapetideStatus'
import { useGoogleDriveStatus } from '@/hooks/useGoogleDriveStatus'
import { useAuthStatus } from '@/hooks/useAuthStatus'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Badge = 'live' | 'degraded' | 'disabled' | 'loading'

interface StatusCardProps {
  name: string
  loading: boolean
  badge: Badge
  message?: string | null
  detail?: string | null
}

const BADGE_STYLES: Record<Badge, string> = {
  live: 'bg-emerald-500/15 text-emerald-300',
  degraded: 'bg-amber-500/15 text-amber-300',
  disabled: 'bg-muted text-muted-foreground',
  loading: 'bg-muted text-muted-foreground',
}

const BADGE_LABELS: Record<Badge, string> = {
  live: 'Live',
  degraded: 'Degraded',
  disabled: 'Disabled',
  loading: 'Checking…',
}

function StatusCard({ name, loading, badge, message, detail }: StatusCardProps) {
  const shown = loading ? 'loading' : badge
  return (
    <div className="glass-card rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-foreground">{name}</p>
        <span
          className={cn(
            'rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
            BADGE_STYLES[shown],
          )}
        >
          {BADGE_LABELS[shown]}
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        {loading ? 'Checking…' : message ?? 'No status available.'}
      </p>
      {!loading && detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  )
}

export function SystemStatusPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [healthError, setHealthError] = useState<string | null>(null)

  const [dbStatus, setDbStatus] = useState<DatabaseStatusResponse | null>(null)
  const [dbLoading, setDbLoading] = useState(true)

  const { status: kiteStatus, loading: kiteLoading, refetch: refetchKite } = useKiteStatus()
  const { status: growwStatus, loading: growwLoading, refetch: refetchGroww } = useGrowwStatus()
  const { status: tapetideStatus, loading: tapetideLoading, refetch: refetchTapetide } = useTapetideStatus()
  const { status: driveStatus, loading: driveLoading, refetch: refetchDrive } = useGoogleDriveStatus()
  const { status: authStatus, loading: authLoading, refetch: refetchAuth } = useAuthStatus()

  const loadCoreStatus = useCallback(async () => {
    setHealthLoading(true)
    setDbLoading(true)
    setHealthError(null)

    try {
      const data = await getHealth()
      setHealth(data)
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : 'Backend unreachable')
      setHealth(null)
    } finally {
      setHealthLoading(false)
    }

    try {
      const data = await getDatabaseStatus()
      setDbStatus(data)
    } catch {
      setDbStatus({ connected: false, message: 'Could not reach the database status check.' })
    } finally {
      setDbLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCoreStatus()
  }, [loadCoreStatus])

  function refreshAll() {
    void loadCoreStatus()
    refetchKite()
    refetchGroww()
    refetchTapetide()
    refetchDrive()
    refetchAuth()
  }

  const anyLoading = healthLoading || dbLoading || kiteLoading || growwLoading || tapetideLoading || driveLoading

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Activity className="size-5 text-primary" />
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">System status</p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Service health</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Live connectivity for every integration InvestIQ depends on.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refreshAll} disabled={anyLoading}>
          <RefreshCw className={cn('size-4', anyLoading && 'animate-spin')} />
          Refresh all
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatusCard
          name="Backend API"
          loading={healthLoading}
          badge={healthError ? 'degraded' : 'live'}
          message={healthError ?? `${health?.app_name} v${health?.version} (${health?.environment})`}
          detail={health?.llm_provider ? `LLM: ${health.llm_provider} / ${health.llm_model ?? '—'}` : undefined}
        />
        <StatusCard
          name="Database (Supabase)"
          loading={dbLoading}
          badge={dbStatus?.connected ? 'live' : 'degraded'}
          message={dbStatus?.message}
          detail={dbStatus?.latency_ms != null ? `${dbStatus.latency_ms}ms` : undefined}
        />
        <StatusCard
          name="Kite Connect"
          loading={kiteLoading}
          badge={!kiteStatus?.enabled ? 'disabled' : kiteStatus.authenticated && kiteStatus.connected ? 'live' : 'degraded'}
          message={kiteStatus?.message}
        />
        <StatusCard
          name="Groww"
          loading={growwLoading}
          badge={!growwStatus?.enabled ? 'disabled' : growwStatus.connected ? 'live' : 'degraded'}
          message={growwStatus?.message}
        />
        <StatusCard
          name="Tapetide NSE/BSE MCP"
          loading={tapetideLoading}
          badge={!tapetideStatus?.enabled ? 'disabled' : tapetideStatus.connected ? 'live' : 'degraded'}
          message={tapetideStatus?.message}
        />
        <StatusCard
          name="Google Drive"
          loading={driveLoading}
          badge={!driveStatus?.enabled ? 'disabled' : driveStatus.connected ? 'live' : 'degraded'}
          message={driveStatus?.message}
        />
        <StatusCard
          name="Owner auth gate"
          loading={authLoading}
          badge={!authStatus?.owner_auth_configured ? 'disabled' : 'live'}
          message={
            authStatus?.owner_auth_configured
              ? authStatus.authenticated
                ? `Signed in${authStatus.email ? ` as ${authStatus.email}` : ''}.`
                : 'Configured, not signed in.'
              : 'Login gate is not configured - every route is open.'
          }
        />
      </div>
    </div>
  )
}
