import { memo, useEffect, useState } from 'react'
import { Sparkles, TrendingDown, TrendingUp } from 'lucide-react'
import type { IndianCompany } from '@/data/indianCompanies'
import type { FinancialSummaryResponse, KiteQuoteResponse } from '@/types/api'
import { getKiteQuote } from '@/lib/api'
import { useKiteStatus } from '@/hooks/useKiteStatus'
import { formatINR, formatPercent, cn } from '@/lib/utils'
import { formatDataSourceLabel } from '@/lib/sourceLabels'
import { StockTabs, type StockTabId } from '@/components/StockTabs'
import { StockChartCard } from '@/components/StockChartCard'
import { ProsConsCard } from '@/components/ProsConsCard'
import { TrustLayer } from '@/components/TrustLayer'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert } from '@/components/ui/alert'

interface StockOverviewProps {
  company: IndianCompany
  financials: FinancialSummaryResponse | null
  loading: boolean
  error: string | null
  onOpenAI: () => void
}

function StockOverviewInner({ company, financials, loading, error, onOpenAI }: StockOverviewProps) {
  const [activeTab, setActiveTab] = useState<StockTabId>('overview')
  const { kiteLive } = useKiteStatus()
  const [liveQuote, setLiveQuote] = useState<KiteQuoteResponse | null>(null)

  const price = liveQuote?.last_price ?? financials?.current_price
  const priceSourceLabel = formatDataSourceLabel(
    liveQuote?.source ?? financials?.price_source ?? financials?.data_source,
  )
  const fundamentalsSourceLabel = formatDataSourceLabel(
    financials?.fundamentals_source ?? financials?.data_source ?? 'yahoo',
  )
  const currency = financials?.currency ?? liveQuote?.currency ?? 'INR'
  const changePercent = liveQuote?.change_percent

  useEffect(() => {
    if (!company.ticker || !kiteLive) {
      setLiveQuote(null)
      return
    }

    let cancelled = false
    void getKiteQuote(company.ticker)
      .then((quote) => {
        if (!cancelled) setLiveQuote(quote)
      })
      .catch(() => {
        if (!cancelled) setLiveQuote(null)
      })

    return () => {
      cancelled = true
    }
  }, [company.ticker, kiteLive])

  function handleTabChange(tab: StockTabId) {
    if (tab === 'ai') {
      onOpenAI()
      return
    }
    setActiveTab(tab)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-card rounded-2xl p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-md bg-primary/10 px-2 py-0.5 font-mono font-semibold text-primary">
                {company.ticker}
              </span>
              {company.exchange && <span>{company.exchange}</span>}
              {(financials?.sector || company.sector) && (
                <span>{financials?.sector || company.sector}</span>
              )}
            </div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              {financials?.company_name || company.name}
            </h1>
            {loading ? (
              <Skeleton className="h-8 w-40" />
            ) : (
              <>
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className="text-3xl font-semibold tabular-nums">
                    {price != null ? formatINR(price) : '—'}
                  </span>
                  <span className="text-sm text-muted-foreground">{currency}</span>
                  {changePercent != null && (
                    <span
                      className={cn(
                        'text-sm font-medium tabular-nums',
                        changePercent >= 0 ? 'text-primary' : 'text-amber-400',
                      )}
                    >
                      {changePercent >= 0 ? '+' : ''}
                      {changePercent.toFixed(2)}%
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Price via{' '}
                  <span className="rounded-md bg-primary/10 px-1.5 py-0.5 font-medium text-primary">
                    {priceSourceLabel}
                  </span>
                  {' · '}
                  Fundamentals via{' '}
                  <span className="rounded-md bg-violet-500/10 px-1.5 py-0.5 font-medium text-violet-200">
                    {fundamentalsSourceLabel}
                  </span>
                </p>
              </>
            )}
          </div>

          <Button size="lg" onClick={onOpenAI} className="shrink-0 gap-2 self-start">
            <Sparkles className="size-4" />
            AI Research
          </Button>
        </div>

        {loading ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Market cap" value={formatINR(financials?.market_cap, true)} />
            <Stat label="P/E ratio" value={financials?.pe_ratio?.toFixed(1) ?? '—'} />
            <Stat label="ROE" value={formatPercent(financials?.roe)} />
            <Stat
              label="Revenue growth"
              value={formatPercent(financials?.revenue_growth)}
              positive={(financials?.revenue_growth ?? 0) >= 0}
            />
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive" title="Could not load financial snapshot">
          {error}
        </Alert>
      )}

      <StockTabs activeTab={activeTab} onChange={handleTabChange} />

      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-2">
            <StockChartCard ticker={company.ticker} />
            <div className="glass-card rounded-2xl p-5">
              <h3 className="mb-4 font-semibold">Key snapshot</h3>
              <dl className="grid gap-3 sm:grid-cols-2">
                <SnapshotItem label="P/B ratio" value={financials?.pb_ratio?.toFixed(2) ?? '—'} />
                <SnapshotItem label="Debt / equity" value={financials?.debt_to_equity?.toFixed(2) ?? '—'} />
                <SnapshotItem label="Profit margin" value={formatPercent(financials?.profit_margin)} />
                <SnapshotItem label="Dividend yield" value={formatPercent(financials?.dividend_yield)} />
                <SnapshotItem label="Industry" value={financials?.industry || '—'} />
                <SnapshotItem label="Fundamentals" value={fundamentalsSourceLabel} />
                <SnapshotItem label="Live price" value={priceSourceLabel} />
                <SnapshotItem label="News (AI)" value="Tavily" />
              </dl>
            </div>
          </div>
          <ProsConsCard financials={financials} />
        </div>
      )}

      {activeTab === 'chart' && <StockChartCard ticker={company.ticker} />}

      {activeTab === 'financials' && (
        <TabPlaceholder
          title="Financial statements"
          description="Detailed income statement, balance sheet, and cash flow views are coming next."
        />
      )}

      {activeTab === 'pros-cons' && <ProsConsCard financials={financials} />}

      {activeTab === 'news' && (
        <TabPlaceholder
          title="News & sentiment"
          description="Live news from Tavily powers AI Q&A and the full research pipeline. A dedicated news feed is coming next."
        />
      )}

      <TrustLayer className="pt-2" />
    </div>
  )
}

export const StockOverview = memo(StockOverviewInner)

function Stat({
  label,
  value,
  positive,
}: {
  label: string
  value: string
  positive?: boolean
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/30 px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 flex items-center gap-1.5 text-sm font-medium tabular-nums">
        {positive === true && <TrendingUp className="size-3.5 text-primary" />}
        {positive === false && <TrendingDown className="size-3.5 text-amber-400" />}
        {value}
      </p>
    </div>
  )
}

function SnapshotItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{value}</dd>
    </div>
  )
}

function TabPlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <div className="glass-card rounded-2xl p-10 text-center">
      <h3 className="font-semibold">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
