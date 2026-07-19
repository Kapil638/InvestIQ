import type { CommitteeVerdict } from '@/types/investmentCommittee'
import { CommitteeRecommendationBadge } from '@/components/research/RecommendationBadge'
import { ConfidenceGauge } from '@/components/research/ConfidenceGauge'
import { cn } from '@/lib/utils'

interface CommitteeVerdictProps {
  verdict: CommitteeVerdict
  className?: string
}

export function CommitteeVerdictCard({ verdict, className }: CommitteeVerdictProps) {
  return (
    <section
      className={cn(
        'glass-card rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/10 via-card/80 to-violet-950/20 p-6 sm:p-8',
        className,
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
        Committee verdict
      </p>
      <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Overall verdict</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <CommitteeRecommendationBadge
              recommendation={verdict.final_recommendation}
              className="text-sm px-3 py-1"
            />
            {verdict.investment_horizon && (
              <span className="text-sm text-muted-foreground">
                Horizon: {verdict.investment_horizon}
              </span>
            )}
          </div>
        </div>
        <div className="w-full max-w-xs">
          <ConfidenceGauge value={verdict.overall_confidence} />
        </div>
      </div>

      <p className="mt-5 text-sm leading-relaxed text-foreground">{verdict.conclusion}</p>
      <p className="mt-3 text-xs text-muted-foreground">{verdict.consensus_summary}</p>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Bull case</p>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            {verdict.bull_case.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-emerald-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-orange-300">Bear case</p>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            {verdict.bear_case.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-orange-400" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
