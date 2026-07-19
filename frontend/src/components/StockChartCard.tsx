import { useEffect, useState } from 'react'
import { LineChart } from 'lucide-react'
import { getKiteHistory } from '@/lib/api'
import type { HistoricalCandle } from '@/types/api'
import { CandlestickChart } from '@/components/chart/CandlestickChart'
import {
  CHART_TIMEFRAMES,
  resolveChartRange,
  type ChartTimeframe,
} from '@/components/chart/chartTimeframes'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface StockChartCardProps {
  ticker: string
}

export function StockChartCard({ ticker }: StockChartCardProps) {
  const [timeframe, setTimeframe] = useState<ChartTimeframe>('1Y')
  const [candles, setCandles] = useState<HistoricalCandle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const range = resolveChartRange(timeframe)

    async function loadHistory() {
      setLoading(true)
      setError(null)

      try {
        const data = await getKiteHistory(ticker, {
          interval: range.interval,
          from: range.from,
          to: range.to,
        })
        if (!cancelled) setCandles(data)
      } catch (err) {
        if (!cancelled) {
          setCandles([])
          setError(err instanceof Error ? err.message : 'Failed to load chart data')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadHistory()
    return () => {
      cancelled = true
    }
  }, [ticker, timeframe])

  const hasData = candles.length > 0

  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold">Price chart</h3>
          <p className="text-xs text-muted-foreground">{ticker} · NSE/BSE</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {CHART_TIMEFRAMES.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => setTimeframe(item.label)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                timeframe === item.label
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="relative h-72 overflow-hidden rounded-xl border border-border/60 bg-background/20 sm:h-80">
        {loading && (
          <div className="absolute inset-0 z-10 space-y-3 p-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-full w-full" />
          </div>
        )}

        {!loading && error && (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <LineChart className="size-8 text-muted-foreground/50" />
            <p className="text-sm font-medium text-foreground">Chart data unavailable</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
        )}

        {!loading && !error && !hasData && (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <LineChart className="size-8 text-muted-foreground/50" />
            <p className="text-sm font-medium text-foreground">No historical data</p>
            <p className="text-xs text-muted-foreground">
              Try a different timeframe or check back during market hours.
            </p>
          </div>
        )}

        {!loading && !error && hasData && (
          <CandlestickChart candles={candles} className="absolute inset-0" />
        )}
      </div>
    </div>
  )
}
