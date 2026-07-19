import type { FinancialSummaryResponse } from '@/types/api'
import { toPercentValue } from '@/lib/utils'
import { MinusCircle, PlusCircle } from 'lucide-react'

export interface ProsConsResult {
  pros: string[]
  cons: string[]
  isFallback: boolean
}

const FALLBACK_PROS = [
  'Strong brand and market presence',
  'Established listed company',
  'Financial data available for analysis',
]

const FALLBACK_CONS = [
  'Valuation needs deeper analysis',
  'Recent news and quarterly performance should be reviewed',
  'Market conditions may impact near-term returns',
]

export function deriveProsCons(financials: FinancialSummaryResponse | null): ProsConsResult {
  if (!financials) {
    return { pros: FALLBACK_PROS, cons: FALLBACK_CONS, isFallback: true }
  }

  const pros: string[] = []
  const cons: string[] = []

  const roe = toPercentValue(financials.roe)
  const profitMargin = toPercentValue(financials.profit_margin)
  const revenueGrowth = toPercentValue(financials.revenue_growth)
  const dividendYield = toPercentValue(financials.dividend_yield)

  if (roe != null && roe >= 15) {
    pros.push(`Healthy return on equity at ${roe.toFixed(1)}%`)
  }
  if (profitMargin != null && profitMargin >= 12) {
    pros.push(`Solid profit margins around ${profitMargin.toFixed(1)}%`)
  }
  if (revenueGrowth != null && revenueGrowth > 8) {
    pros.push(`Revenue growth momentum at ${revenueGrowth.toFixed(1)}%`)
  }
  if (financials.debt_to_equity != null && financials.debt_to_equity < 1) {
    pros.push('Conservative leverage profile relative to equity base')
  }
  if (dividendYield != null && dividendYield >= 1) {
    pros.push(`Offers dividend yield near ${dividendYield.toFixed(1)}%`)
  }
  if (financials.market_cap != null && financials.market_cap >= 1e12) {
    pros.push('Large-cap liquidity and institutional coverage')
  }
  if (financials.sector) {
    pros.push(`Leading player in ${financials.sector}`)
  }

  if (financials.pe_ratio != null && financials.pe_ratio > 35) {
    cons.push(`Premium valuation — P/E near ${financials.pe_ratio.toFixed(1)}x`)
  }
  if (revenueGrowth != null && revenueGrowth < 0) {
    cons.push('Revenue growth under pressure in recent periods')
  }
  if (financials.debt_to_equity != null && financials.debt_to_equity > 2) {
    cons.push('Elevated debt-to-equity warrants balance-sheet review')
  }
  if (roe != null && roe < 8) {
    cons.push('Return on equity below typical quality thresholds')
  }
  if (profitMargin != null && profitMargin < 5) {
    cons.push('Thin profit margins may limit resilience in downturns')
  }

  const isFallback = pros.length === 0 && cons.length === 0
  return {
    pros: pros.length > 0 ? pros.slice(0, 5) : FALLBACK_PROS,
    cons: cons.length > 0 ? cons.slice(0, 5) : FALLBACK_CONS,
    isFallback,
  }
}

interface ProsConsCardProps {
  financials: FinancialSummaryResponse | null
  compact?: boolean
}

export function ProsConsCard({ financials, compact }: ProsConsCardProps) {
  const { pros, cons, isFallback } = deriveProsCons(financials)

  return (
    <div className={compact ? 'grid gap-4 sm:grid-cols-2' : 'grid gap-4 lg:grid-cols-2'}>
      <div className="glass-card rounded-2xl p-5">
        <div className="mb-3 flex items-center gap-2">
          <PlusCircle className="size-4 text-primary" />
          <h3 className="font-semibold">Pros</h3>
        </div>
        <ul className="space-y-2 text-sm text-muted-foreground">
          {pros.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="glass-card rounded-2xl p-5">
        <div className="mb-3 flex items-center gap-2">
          <MinusCircle className="size-4 text-amber-400" />
          <h3 className="font-semibold">Cons</h3>
        </div>
        <ul className="space-y-2 text-sm text-muted-foreground">
          {cons.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-amber-400/80" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
      {isFallback && (
        <p className="text-xs text-muted-foreground sm:col-span-2">
          Snapshot-based summary — run AI Research for deeper, news-aware analysis.
        </p>
      )}
    </div>
  )
}
