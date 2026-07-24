import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Briefcase, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { analyzePortfolio, getKiteHoldings, API_BASE } from '@/lib/api'
import type { PortfolioAnalyzeResponse, PortfolioHolding } from '@/types/api'
import type { IndianCompany } from '@/data/indianCompanies'
import { findCompanyByTicker } from '@/data/indianCompanies'
import { useKiteStatus } from '@/hooks/useKiteStatus'
import { useGrowwStatus } from '@/hooks/useGrowwStatus'
import { resolveGrowwBadge, resolveKiteBadge } from '@/lib/dataPlane'
import { PortfolioAnalysis } from '@/components/portfolio/PortfolioAnalysis'
import { HoldingsTable } from '@/components/portfolio/HoldingsTable'
import { PortfolioKiteDiagnostics } from '@/components/portfolio/PortfolioKiteDiagnostics'
import { PortfolioGrowwDiagnostics } from '@/components/portfolio/PortfolioGrowwDiagnostics'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert } from '@/components/ui/alert'
import { cn, formatINR, formatPercent } from '@/lib/utils'

function holdingToCompany(holding: PortfolioHolding): IndianCompany {
  const known = findCompanyByTicker(holding.symbol)
  if (known) return known
  return {
    name: holding.company_name || holding.symbol,
    ticker: holding.symbol,
    exchange: holding.exchange || 'NSE',
    sector: holding.sector || undefined,
  }
}

function SummaryCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="glass-card rounded-xl p-4">
      <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}

export function PortfolioPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { status, loading: statusLoading, refetch } = useKiteStatus()
  const badge = resolveKiteBadge(status)
  const { status: growwStatus, loading: growwStatusLoading, refetch: growwRefetch } = useGrowwStatus()
  const growwBadge = resolveGrowwBadge(growwStatus)

  const [holdings, setHoldings] = useState<PortfolioHolding[]>([])
  const [holdingsMessage, setHoldingsMessage] = useState<string | null>(null)
  const [authRequired, setAuthRequired] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [analyzeLoading, setAnalyzeLoading] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<PortfolioAnalyzeResponse | null>(null)

  const loadHoldings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getKiteHoldings()
      setHoldings(data.holdings)
      setAuthRequired(data.auth_required)
      setHoldingsMessage(data.message ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load holdings')
      setHoldings([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!statusLoading) void loadHoldings()
  }, [statusLoading, loadHoldings])

  useEffect(() => {
    const connected = searchParams.get('kite_connected')
    const errored = searchParams.get('kite_error')
    if (connected === '1' || errored === '1') {
      refetch()
      void loadHoldings()
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, refetch, loadHoldings, setSearchParams])

  const totals = useMemo(() => {
    const invested = holdings.reduce((sum, h) => sum + (h.invested_value ?? 0), 0)
    const current = holdings.reduce((sum, h) => sum + (h.current_value ?? 0), 0)
    const pnl = holdings.reduce((sum, h) => sum + (h.pnl ?? 0), 0)
    const pnlPercent = invested > 0 ? (pnl / invested) * 100 : null
    const top = [...holdings].sort(
      (a, b) => (b.current_value ?? 0) - (a.current_value ?? 0),
    )[0]
    const topAlloc =
      top && current > 0 ? ((top.current_value ?? 0) / current) * 100 : null
    return { invested, current, pnl, pnlPercent, top, topAlloc }
  }, [holdings])

  function handleAIResearch(holding: PortfolioHolding) {
    const company = holdingToCompany(holding)
    navigate('/', { state: { company, openAI: true } })
  }

  async function handleAnalyze() {
    if (holdings.length === 0) return
    setAnalyzeLoading(true)
    setAnalyzeError(null)
    try {
      const result = await analyzePortfolio(holdings)
      setAnalysis(result)
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Portfolio analysis failed')
    } finally {
      setAnalyzeLoading(false)
    }
  }

  const kiteDisabled = badge === 'soon'
  const kiteAuth = badge === 'auth' || authRequired
  const hasHoldings = holdings.length > 0
  // Only block the whole page behind "Connect Zerodha" when there's nothing
  // else to show - if Groww already has holdings, show those and nudge for
  // Kite inline instead of hiding a working view behind a blocking screen.
  const showConnectZerodhaScreen = kiteAuth && !kiteDisabled && !hasHoldings

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Briefcase className="size-5 text-primary" />
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Portfolio</p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Your holdings</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Read-only broker portfolio via Kite Connect and Groww — research your holdings with InvestIQ AI.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            growwRefetch()
            void loadHoldings()
          }}
          disabled={loading}
        >
          <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <PortfolioKiteDiagnostics status={status} loading={statusLoading} />
        <PortfolioGrowwDiagnostics status={growwStatus} loading={growwStatusLoading} />
      </div>

      <div className="glass-card rounded-2xl p-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">Kite connection</span>
          <span
            className={cn(
              'rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
              badge === 'live'
                ? 'bg-emerald-500/15 text-emerald-300'
                : badge === 'auth'
                  ? 'bg-amber-500/15 text-amber-300'
                  : 'bg-muted text-muted-foreground',
            )}
          >
            {badge === 'live' ? 'Live' : badge === 'auth' ? 'Auth required' : 'Disabled'}
          </span>
          {status && <span className="text-xs text-muted-foreground">{status.message}</span>}
          {status?.user_id && (
            <span className="text-xs text-muted-foreground">
              · {status.broker ?? 'Zerodha'} · {status.user_id}
            </span>
          )}
          <span className="mx-1 text-muted-foreground">·</span>
          <span className="text-sm font-medium">Groww connection</span>
          <span
            className={cn(
              'rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
              growwBadge === 'live'
                ? 'bg-emerald-500/15 text-emerald-300'
                : 'bg-muted text-muted-foreground',
            )}
          >
            {growwBadge === 'live' ? 'Live' : 'Disabled'}
          </span>
          {growwStatus && <span className="text-xs text-muted-foreground">{growwStatus.message}</span>}
        </div>
      </div>

      {kiteDisabled && !hasHoldings && (
        <Alert title="Kite Connect is not enabled">
          Enable Kite MCP on the backend to view your Zerodha portfolio.
        </Alert>
      )}

      {showConnectZerodhaScreen && (
        <div className="glass-card rounded-2xl p-8 text-center">
          <p className="text-lg font-medium">Connect Zerodha</p>
          <p className="mt-2 text-sm text-muted-foreground">
            {holdingsMessage || status?.message || 'Authorize InvestIQ to read your holdings and live market data.'}
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <a
              href={`${API_BASE}/kite/login`}
              className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Connect Zerodha
            </a>
            <Button variant="outline" onClick={() => { refetch(); void loadHoldings() }}>
              Check Kite Connection
            </Button>
          </div>
        </div>
      )}

      {kiteAuth && !kiteDisabled && hasHoldings && (
        <div className="glass-card flex flex-wrap items-center justify-between gap-3 rounded-2xl p-4 text-sm">
          <span className="text-muted-foreground">
            {holdingsMessage || status?.message || 'Connect Zerodha to also see those holdings here.'}
          </span>
          <a
            href={`${API_BASE}/kite/login`}
            className="inline-flex h-8 items-center justify-center rounded-lg border border-border px-3 text-xs font-medium hover:bg-muted"
          >
            Connect Zerodha
          </a>
        </div>
      )}

      {error && (
        <Alert variant="destructive" title="Could not load holdings">
          {error}
        </Alert>
      )}

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {!loading && hasHoldings && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <SummaryCard label="Current value" value={formatINR(totals.current)} />
            <SummaryCard label="Invested" value={formatINR(totals.invested)} />
            <SummaryCard
              label="Total P&L"
              value={formatINR(totals.pnl)}
              sub={totals.pnlPercent != null ? formatPercent(totals.pnlPercent) : undefined}
            />
            <SummaryCard
              label="P&L %"
              value={totals.pnlPercent != null ? formatPercent(totals.pnlPercent) : '—'}
            />
            <SummaryCard label="Holdings" value={String(holdings.length)} />
            <SummaryCard
              label="Top holding"
              value={totals.top?.symbol ?? '—'}
              sub={totals.topAlloc != null ? `${totals.topAlloc.toFixed(1)}% allocation` : undefined}
            />
          </div>

          <div className="flex justify-end">
            <Button onClick={() => void handleAnalyze()} disabled={analyzeLoading}>
              {analyzeLoading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Sparkles className="size-4" />
              )}
              Analyze My Portfolio
            </Button>
          </div>

          {analyzeError && (
            <Alert variant="destructive" title="Analysis failed">
              {analyzeError}
            </Alert>
          )}

          {analysis && <PortfolioAnalysis analysis={analysis} />}

          <HoldingsTable holdings={holdings} onAIResearch={handleAIResearch} />
        </>
      )}

      {!loading && !kiteDisabled && !kiteAuth && !hasHoldings && !error && (
        <div className="glass-card rounded-2xl p-8 text-center text-muted-foreground">
          No holdings found in your connected broker accounts.
        </div>
      )}
    </div>
  )
}
