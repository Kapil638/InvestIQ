import { useState } from 'react'
import {
  BarChart3,
  Calculator,
  ChevronDown,
  Newspaper,
  ShieldAlert,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'
import type { AnalystOpinion, AnalystPersonaId } from '@/types/investmentCommittee'
import { CommitteeRecommendationBadge } from '@/components/research/RecommendationBadge'
import { ConfidenceGauge } from '@/components/research/ConfidenceGauge'
import { SourceBadges } from '@/components/research/SourceBadges'
import { cn } from '@/lib/utils'

const ICONS: Record<string, LucideIcon> = {
  fundamental: BarChart3,
  news: Newspaper,
  technical: TrendingUp,
  valuation: Calculator,
  risk: ShieldAlert,
}

interface AnalystCardProps {
  analyst: AnalystOpinion
  defaultOpen?: boolean
  className?: string
}

export function AnalystCard({ analyst, defaultOpen = false, className }: AnalystCardProps) {
  const [open, setOpen] = useState(defaultOpen)
  const Icon = ICONS[analyst.id as AnalystPersonaId] ?? BarChart3

  return (
    <article
      className={cn(
        'glass-card rounded-2xl border border-violet-500/15 bg-card/50 transition-colors',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-4 p-5 text-left"
      >
        <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-violet-500/15 text-violet-300">
          <Icon className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-semibold text-foreground">{analyst.name}</h4>
            <CommitteeRecommendationBadge recommendation={analyst.recommendation} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{analyst.title}</p>
          <div className="mt-3 max-w-xs">
            <ConfidenceGauge value={analyst.confidence} size="sm" />
          </div>
        </div>
        <ChevronDown
          className={cn(
            'mt-1 size-5 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div className="border-t border-border/50 px-5 pb-5 pt-4">
          <ul className="space-y-2.5">
            {analyst.supporting_points.map((point) => (
              <li key={point} className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-violet-400" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
          <SourceBadges sources={analyst.sources} className="mt-4" />
        </div>
      )}
    </article>
  )
}
