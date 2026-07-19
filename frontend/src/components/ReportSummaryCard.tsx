import type { ReactNode } from 'react'
import type { ResearchReportResponse } from '@/types/api'
import { RecommendationBadge } from '@/components/RecommendationBadge'
import { formatDate } from '@/lib/utils'
import { ShieldAlert, Sparkles, TrendingUp } from 'lucide-react'

interface ReportSummaryCardProps {
  report: ResearchReportResponse
}

function excerpt(text: string | null | undefined, max = 280): string | null {
  if (!text?.trim()) return null
  const clean = text.trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max).trim()}…`
}

function bulletLines(text: string | null | undefined, maxItems = 4): string[] {
  if (!text) return []
  return text
    .split(/\n+/)
    .map((line) => line.replace(/^[-*•]\s*/, '').trim())
    .filter((line) => line.length > 20)
    .slice(0, maxItems)
}

export function ReportSummaryCard({ report }: ReportSummaryCardProps) {
  const rec = report.recommendation
  const companyName = report.financial_data?.profile?.company_name
  const upsideFromThesis = bulletLines(report.analysis, 3)
  const risks = rec?.risks?.length ? rec.risks : bulletLines(report.news_research_summary, 3)

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-2xl border-primary/20 bg-gradient-to-br from-primary/10 via-card/80 to-card/40 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Research complete</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight">{report.ticker}</h2>
            {companyName && <p className="text-muted-foreground">{companyName}</p>}
            <p className="mt-2 text-xs text-muted-foreground">Generated {formatDate(report.generated_at)}</p>
          </div>
          <RecommendationBadge rating={rec?.rating} confidence={rec?.confidence_score} />
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <Metric label="Time horizon" value={rec?.investment_horizon ?? 'Pending guardrails'} />
          <Metric
            label="Confidence"
            value={rec?.confidence_score != null ? `${rec.confidence_score}%` : '—'}
          />
          <Metric label="Target range" value={rec?.target_price_range ?? 'Not issued'} />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <InsightCard
          icon={<TrendingUp className="size-4 text-primary" />}
          title="Key upside drivers"
          items={
            upsideFromThesis.length > 0
              ? upsideFromThesis
              : rec?.reasoning
                ? [excerpt(rec.reasoning, 200)!]
                : ['Upside drivers will appear when the recommendation agent completes.']
          }
        />
        <InsightCard
          icon={<ShieldAlert className="size-4 text-amber-400" />}
          title="Key risks"
          items={
            risks.length > 0
              ? risks
              : ['Risk factors are extracted from the analyst thesis and news scan.']
          }
        />
        <InsightCard
          icon={<Sparkles className="size-4 text-primary" />}
          title="Valuation summary"
          content={
            excerpt(report.financial_data_summary, 360) ??
            'Valuation context is drawn from Yahoo Finance fundamentals for Indian listings.'
          }
        />
        <InsightCard
          icon={<Sparkles className="size-4 text-sky-400" />}
          title="Latest news impact"
          content={
            excerpt(report.news_research_summary, 360) ??
            'News impact summary appears after the news agent completes its scan.'
          }
        />
      </div>

      {report.analysis && (
        <div className="glass-card rounded-2xl p-6">
          <h3 className="mb-3 font-semibold">Final thesis</h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
            {report.analysis}
          </p>
        </div>
      )}

      {rec?.reasoning && (
        <div className="glass-card rounded-2xl border-primary/20 p-6">
          <h3 className="mb-3 font-semibold text-primary">Recommendation rationale</h3>
          <p className="text-sm leading-relaxed text-foreground">{rec.reasoning}</p>
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/30 px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  )
}

function InsightCard({
  icon,
  title,
  items,
  content,
}: {
  icon: ReactNode
  title: string
  items?: string[]
  content?: string
}) {
  return (
    <div className="glass-card rounded-2xl p-5">
      <div className="mb-3 flex items-center gap-2">
        {icon}
        <h3 className="font-semibold">{title}</h3>
      </div>
      {content ? (
        <p className="text-sm leading-relaxed text-muted-foreground">{content}</p>
      ) : (
        <ul className="space-y-2 text-sm text-muted-foreground">
          {items?.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
