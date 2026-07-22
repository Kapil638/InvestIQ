import { TrendingDown, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TickerItem {
  symbol: string
  price: string
  change: string
  up: boolean
}

// Illustrative values for the login page's decorative ticker banner - not a
// live feed. Wiring this to real prices would need a new public (unguarded)
// backend endpoint, since every other market-data route sits behind the
// owner-auth gate and this banner renders pre-login.
const TICKER_ITEMS: TickerItem[] = [
  { symbol: 'SENSEX', price: '82,431.20', change: '+1.24%', up: true },
  { symbol: 'NIFTY 50', price: '25,010.40', change: '+1.08%', up: true },
  { symbol: 'RELIANCE', price: '2,945.60', change: '+0.82%', up: true },
  { symbol: 'TCS', price: '4,120.15', change: '-0.34%', up: false },
  { symbol: 'HDFC BANK', price: '1,678.90', change: '+0.51%', up: true },
  { symbol: 'INFY', price: '1,892.45', change: '+0.63%', up: true },
  { symbol: 'ICICI BANK', price: '1,284.30', change: '+0.28%', up: true },
  { symbol: 'BHARTI AIRTEL', price: '1,602.75', change: '-0.12%', up: false },
  { symbol: 'ITC', price: '468.20', change: '+0.45%', up: true },
  { symbol: 'BAJAJ FINANCE', price: '7,214.85', change: '-0.58%', up: false },
]

function TickerRow({ ariaHidden }: { ariaHidden?: boolean }) {
  return (
    <div className="flex shrink-0 items-center gap-8 px-4" aria-hidden={ariaHidden}>
      {TICKER_ITEMS.map((item, i) => (
        <div key={`${item.symbol}-${i}`} className="flex items-center gap-2 whitespace-nowrap">
          <span className="font-mono text-xs font-semibold tracking-wide text-foreground/90">
            {item.symbol}
          </span>
          <span className="font-mono text-xs text-muted-foreground">{item.price}</span>
          <span
            className={cn(
              'flex items-center gap-0.5 font-mono text-xs font-medium',
              item.up ? 'text-primary' : 'text-destructive',
            )}
          >
            {item.up ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
            {item.change}
          </span>
        </div>
      ))}
    </div>
  )
}

export function MarketTicker() {
  return (
    <div className="relative z-10 flex h-9 shrink-0 items-center overflow-hidden border-b border-border/60 bg-black/40 backdrop-blur-sm">
      <div className="flex shrink-0 items-center gap-1.5 border-r border-border/60 bg-black/30 px-3 py-1.5">
        <span className="relative flex size-1.5">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
        </span>
        <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-primary">
          Market Open
        </span>
      </div>
      <div className="market-ticker-track flex">
        <TickerRow />
        <TickerRow ariaHidden />
      </div>
    </div>
  )
}
