import { memo, useMemo } from 'react'
import type { ResearchReportResponse } from '@/types/api'
import { InvestmentCommittee } from '@/components/research/InvestmentCommittee'
import { CommitteeRecommendationBadge } from '@/components/research/RecommendationBadge'
import { GuardrailPanel } from '@/components/GuardrailPanel'
import { formatDate } from '@/lib/utils'
import { buildReportSections } from './reportSections'
import { cn } from '@/lib/utils'

interface ProfessionalReportProps {
  report: ResearchReportResponse
  className?: string
}

function ProfessionalReportInner({ report, className }: ProfessionalReportProps) {
  const allSections = useMemo(() => buildReportSections(report), [report])
  const sections = useMemo(
    () => allSections.filter((section) => !['recommendation', 'confidence', 'sources'].includes(section.id)),
    [allSections],
  )
  const executive = useMemo(() => allSections.find((s) => s.id === 'executive'), [allSections])
  const companyName = report.financial_data?.profile?.company_name
  const committee = report.investment_committee
  const verdict = committee?.verdict

  return (
    <div className={cn('space-y-8', className)}>
      <div className="glass-card rounded-2xl border-primary/20 bg-gradient-to-br from-primary/10 via-card/80 to-card/40 p-6 sm:p-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
              Institutional research report
            </p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight">{report.ticker}</h2>
            {companyName && <p className="text-muted-foreground">{companyName}</p>}
            <p className="mt-2 text-xs text-muted-foreground">
              Generated {formatDate(report.generated_at)}
              {report.model_used && (
                <span className="ml-2 text-muted-foreground/80">· {report.model_used}</span>
              )}
              {report.id && (
                <span className="ml-2 font-mono text-primary/80">#{report.id.slice(0, 8)}</span>
              )}
            </p>
          </div>
          {verdict ? (
            <div className="flex flex-col items-start gap-2 lg:items-end">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Committee verdict</p>
              <CommitteeRecommendationBadge recommendation={verdict.final_recommendation} />
              <p className="text-sm text-muted-foreground">
                {(report.confidence_score ?? verdict.overall_confidence)}% confidence
                {report.scoring_version && (
                  <span className="ml-1 text-xs">({report.scoring_version} scoring)</span>
                )}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {executive && (
        <section className="glass-card rounded-2xl border-primary/20 p-5 lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">
            {executive.title}
          </h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
            {executive.content}
          </p>
        </section>
      )}

      {committee && <InvestmentCommittee committee={committee} />}

      <div className="grid gap-4 lg:grid-cols-2">
        {sections
          .filter((section) => section.id !== 'executive')
          .map((section) => (
            <section
              key={section.id}
              className={cn(
                'glass-card rounded-2xl p-5',
                section.id === 'risks' || section.id === 'horizon' ? 'lg:col-span-2 border-primary/10' : '',
              )}
            >
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">
                {section.title}
              </h3>
              {section.items ? (
                <ul className="space-y-2 text-sm leading-relaxed text-muted-foreground">
                  {section.items.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                  {section.content}
                </p>
              )}
            </section>
          ))}
      </div>

      {(report.analysis_output?.scores_estimated || report.risk_output?.scores_estimated) && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
          Scores estimated — model output could not be parsed
        </p>
      )}

      {report.score_breakdown && (
        <section className="glass-card rounded-2xl border-primary/20 p-5">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">
            Score breakdown
          </h3>
          <p className="mb-4 text-xs text-muted-foreground">
            Deterministic committee scoring
            {report.scoring_version ? ` (${report.scoring_version})` : ''}
            {report.data_snapshot_hash && (
              <span className="ml-2 font-mono">hash {report.data_snapshot_hash.slice(0, 12)}…</span>
            )}
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(
              [
                ['Financial quality', report.score_breakdown.financial_quality_score],
                ['Valuation', report.score_breakdown.valuation_score],
                ['Growth', report.score_breakdown.growth_score],
                ['Risk', report.score_breakdown.risk_score],
                ['News', report.score_breakdown.news_score],
                ['Data quality', report.score_breakdown.data_quality_score],
              ] as const
            ).map(([label, value]) => (
              <div
                key={label}
                className="rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-sm"
              >
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="font-semibold tabular-nums">{value}%</p>
              </div>
            ))}
          </div>
          {report.confidence_change_reason && (
            <p className="mt-4 text-xs text-amber-300/90">{report.confidence_change_reason}</p>
          )}
          {report.regenerated_from_same_data && (
            <p className="mt-2 text-xs text-muted-foreground">
              Regenerated using unchanged market data (stable scoring).
            </p>
          )}
        </section>
      )}

      {report.guardrails && (
        <GuardrailPanel guardrails={report.guardrails} title="Analysis guardrails" />
      )}
      {report.risk_guardrails && (
        <GuardrailPanel guardrails={report.risk_guardrails} title="Risk guardrails" />
      )}
      {report.recommendation_guardrails && (
        <GuardrailPanel
          guardrails={report.recommendation_guardrails}
          title="Recommendation guardrails"
        />
      )}
    </div>
  )
}

export const ProfessionalReport = memo(ProfessionalReportInner)
