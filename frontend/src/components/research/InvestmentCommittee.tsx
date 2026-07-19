import { memo } from 'react'
import type { InvestmentCommittee as InvestmentCommitteeData } from '@/types/investmentCommittee'
import { AnalystCard } from '@/components/research/AnalystCard'
import { CommitteeVerdictCard } from '@/components/research/CommitteeVerdict'
import { SourceBadges } from '@/components/research/SourceBadges'
import { cn } from '@/lib/utils'

interface InvestmentCommitteeProps {
  committee: InvestmentCommitteeData
  className?: string
}

function InvestmentCommitteeInner({ committee, className }: InvestmentCommitteeProps) {
  return (
    <section className={cn('space-y-5', className)}>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          Investment committee
        </p>
        <h3 className="mt-1 text-xl font-semibold tracking-tight">
          Independent analyst evaluations
        </h3>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Five specialist analysts reviewed this stock independently before the committee
          synthesized a final institutional view.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {committee.analysts.map((analyst) => (
          <AnalystCard key={analyst.id} analyst={analyst} />
        ))}
      </div>

      <CommitteeVerdictCard verdict={committee.verdict} />

      {committee.sources_used.length > 0 && (
        <div className="glass-card rounded-2xl p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Sources used
          </p>
          <SourceBadges sources={committee.sources_used} />
        </div>
      )}
    </section>
  )
}

export const InvestmentCommittee = memo(InvestmentCommitteeInner)
