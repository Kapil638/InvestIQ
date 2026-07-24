import { memo, useCallback } from 'react'
import type { PortfolioHolding } from '@/types/api'
import { cn, formatINR, formatPercent } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const BROKER_LABELS: Record<string, string> = {
  kite: 'Zerodha',
  groww: 'Groww',
}

function BrokerBadge({ priceSource }: { priceSource: string }) {
  const label = BROKER_LABELS[priceSource] ?? priceSource
  return (
    <span
      className={cn(
        'ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
        priceSource === 'groww'
          ? 'bg-emerald-500/10 text-emerald-500'
          : 'bg-primary/10 text-primary',
      )}
    >
      {label}
    </span>
  )
}

interface HoldingsTableProps {
  holdings: PortfolioHolding[]
  onAIResearch: (holding: PortfolioHolding) => void
}

function HoldingsTableInner({ holdings, onAIResearch }: HoldingsTableProps) {
  return (
    <div className="glass-card overflow-hidden rounded-2xl">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3">Company / Symbol</th>
              <th className="px-4 py-3">Qty</th>
              <th className="px-4 py-3">Avg</th>
              <th className="px-4 py-3">Current</th>
              <th className="px-4 py-3">Invested</th>
              <th className="px-4 py-3">Value</th>
              <th className="px-4 py-3">P&L</th>
              <th className="px-4 py-3">P&L %</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <HoldingRow
                key={`${h.price_source}-${h.exchange}-${h.symbol}`}
                holding={h}
                onAIResearch={onAIResearch}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const HoldingRow = memo(function HoldingRow({
  holding: h,
  onAIResearch,
}: {
  holding: PortfolioHolding
  onAIResearch: (holding: PortfolioHolding) => void
}) {
  const onClick = useCallback(() => onAIResearch(h), [h, onAIResearch])

  return (
    <tr className="border-b border-border/40">
      <td className="px-4 py-3">
        <p className="flex items-center font-medium">
          {h.company_name || h.symbol}
          <BrokerBadge priceSource={h.price_source} />
        </p>
        <p className="text-xs text-muted-foreground">
          {h.symbol}
          {h.exchange ? ` · ${h.exchange}` : ''}
        </p>
      </td>
      <td className="px-4 py-3">{h.quantity ?? '—'}</td>
      <td className="px-4 py-3">{h.average_price != null ? formatINR(h.average_price) : '—'}</td>
      <td className="px-4 py-3">{h.last_price != null ? formatINR(h.last_price) : '—'}</td>
      <td className="px-4 py-3">{h.invested_value != null ? formatINR(h.invested_value) : '—'}</td>
      <td className="px-4 py-3">{h.current_value != null ? formatINR(h.current_value) : '—'}</td>
      <td className="px-4 py-3">{h.pnl != null ? formatINR(h.pnl) : '—'}</td>
      <td className="px-4 py-3">{h.pnl_percent != null ? formatPercent(h.pnl_percent) : '—'}</td>
      <td className="px-4 py-3">
        <Button size="sm" variant="outline" onClick={onClick}>
          AI Research
        </Button>
      </td>
    </tr>
  )
})

export const HoldingsTable = memo(HoldingsTableInner)
