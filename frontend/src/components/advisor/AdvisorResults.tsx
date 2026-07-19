import { BarChart3, ShieldAlert, Sparkles } from 'lucide-react'
import type { IndianCompany } from '@/data/indianCompanies'
import type { StockRecommendation } from '@/types/api'
import { AdvisorStockCard } from '@/components/advisor/AdvisorStockCard'
import { cn } from '@/lib/utils'

interface AdvisorResultsProps {
  recommendations: StockRecommendation[]
  onOpenOverview: (company: IndianCompany) => void
  onRunResearch: (company: IndianCompany) => void
  className?: string
}

export function AdvisorResults({
  recommendations,
  onOpenOverview,
  onRunResearch,
  className,
}: AdvisorResultsProps) {
  if (recommendations.length === 0) {
    return (
      <div className={cn('glass-card rounded-2xl p-8 text-center text-muted-foreground', className)}>
        No stock suggestions were returned. Try refining your prompt with capital, horizon, and risk level.
      </div>
    )
  }

  return (
    <section className={cn('space-y-4', className)}>
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-violet-300" />
        <h3 className="text-lg font-semibold tracking-tight">Top {recommendations.length} suggestions</h3>
      </div>

      <div className="grid gap-4">
        {recommendations.map((rec) => (
          <AdvisorStockCard
            key={`${rec.rank}-${rec.symbol}`}
            recommendation={rec}
            onOpenOverview={onOpenOverview}
            onRunResearch={onRunResearch}
          />
        ))}
      </div>
    </section>
  )
}

interface PortfolioMixSectionProps {
  largeCapPercent: number
  midCapPercent: number
  smallCapPercent: number
  sectorExposure: { sector: string; percent: number }[]
  riskSummary: string
  timeHorizonSuitability: string
  className?: string
}

export function AdvisorPortfolioMix({
  largeCapPercent,
  midCapPercent,
  smallCapPercent,
  sectorExposure,
  riskSummary,
  timeHorizonSuitability,
  className,
}: PortfolioMixSectionProps) {
  return (
    <section className={cn('glass-card rounded-2xl border border-border/60 p-5 sm:p-6', className)}>
      <div className="flex items-center gap-2">
        <BarChart3 className="size-4 text-primary" />
        <h3 className="text-sm font-semibold uppercase tracking-wider text-primary">Portfolio mix</h3>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <MixStat label="Large cap" value={`${largeCapPercent}%`} />
        <MixStat label="Mid cap" value={`${midCapPercent}%`} />
        <MixStat label="Small cap" value={`${smallCapPercent}%`} />
      </div>

      {sectorExposure.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Sector exposure
          </p>
          <div className="mt-2 space-y-2">
            {sectorExposure.map((item) => (
              <div key={item.sector} className="flex items-center justify-between text-sm">
                <span>{item.sector}</span>
                <span className="font-medium tabular-nums text-primary">{item.percent}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border/50 bg-background/30 p-4">
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldAlert className="size-3.5" />
            Risk level
          </p>
          <p className="mt-1 text-sm">{riskSummary}</p>
        </div>
        <div className="rounded-xl border border-border/50 bg-background/30 p-4">
          <p className="text-xs text-muted-foreground">Time horizon suitability</p>
          <p className="mt-1 text-sm">{timeHorizonSuitability}</p>
        </div>
      </div>
    </section>
  )
}

function MixStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-background/30 px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}
