import { useEffect, useState } from 'react'
import { TrendingDown, TrendingUp } from 'lucide-react'
import { getNiftyTicker } from '@/lib/api'
import type { TickerItem } from '@/types/api'
import { cn } from '@/lib/utils'

// Matches the backend's 15-minute cache TTL for this endpoint (Tapetide's
// free tier shares one daily quota across the whole app - polling faster
// than the cache refreshes would just re-request the same cached response).
const REFRESH_INTERVAL_MS = 5 * 60_000

function formatPrice(price: number | null | undefined): string {
  if (price == null) return '—'
  return price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatChange(change: number | null | undefined): string {
  if (change == null) return ''
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}%`
}

function TickerRow({ items, ariaHidden }: { items: TickerItem[]; ariaHidden?: boolean }) {
  return (
    <div className="flex shrink-0 items-center gap-8 px-4" aria-hidden={ariaHidden}>
      {items.map((item, i) => {
        const up = (item.change_percent ?? 0) >= 0
        return (
          <div key={`${item.symbol}-${i}`} className="flex items-center gap-2 whitespace-nowrap">
            <span className="font-mono text-xs font-semibold tracking-wide text-foreground/90">
              {item.symbol}
            </span>
            <span className="font-mono text-xs text-muted-foreground">{formatPrice(item.price)}</span>
            {item.change_percent != null && (
              <span
                className={cn(
                  'flex items-center gap-0.5 font-mono text-xs font-medium',
                  up ? 'text-primary' : 'text-destructive',
                )}
              >
                {up ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
                {formatChange(item.change_percent)}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function MarketTicker() {
  const [items, setItems] = useState<TickerItem[]>([])
  const [marketOpen, setMarketOpen] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await getNiftyTicker()
        if (cancelled) return
        setItems(data.items)
        setMarketOpen(data.market_open)
        setFailed(false)
      } catch {
        if (!cancelled) setFailed(true)
      }
    }

    void load()
    const interval = setInterval(() => void load(), REFRESH_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  // Fail gracefully: no data (backend/Tapetide unreachable) means no banner,
  // rather than showing an empty or stale-looking bar.
  if (failed || items.length === 0) return null

  return (
    <div className="relative z-10 flex h-9 shrink-0 items-center overflow-hidden border-b border-border/60 bg-black/40 backdrop-blur-sm">
      <div className="flex shrink-0 items-center gap-1.5 border-r border-border/60 bg-black/30 px-3 py-1.5">
        {marketOpen ? (
          <>
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
            </span>
            <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-primary">
              Market Open
            </span>
          </>
        ) : (
          <>
            <span className="inline-flex size-1.5 rounded-full bg-warning" />
            <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-warning">
              Market Closed · Last Traded
            </span>
          </>
        )}
      </div>
      {/* Dedicated clipping lane for the scrolling track - its own box, not
          just the outer bar's, must bound the animation. transform:translateX
          slides the track's painted content without moving its layout box,
          so without this wrapper the sliding numbers visually bleed left
          underneath the badge (only the ancestor bar's overflow applied,
          which doesn't stop a sibling's transformed content from painting
          over another sibling). */}
      <div className="min-w-0 flex-1 overflow-hidden">
        <div className="market-ticker-track flex">
          <TickerRow items={items} />
          <TickerRow items={items} ariaHidden />
        </div>
      </div>
    </div>
  )
}
