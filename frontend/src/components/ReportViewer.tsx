import type { ResearchReportResponse } from '@/types/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RecommendationBadge } from '@/components/RecommendationBadge'
import { GuardrailPanel } from '@/components/GuardrailPanel'
import { formatDate } from '@/lib/utils'

interface ReportViewerProps {
  report: ResearchReportResponse
}

function Section({ title, content }: { title: string; content?: string | null }) {
  if (!content) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{content}</p>
      </CardContent>
    </Card>
  )
}

export function ReportViewer({ report }: ReportViewerProps) {
  const companyName = report.financial_data?.profile?.company_name
  const rec = report.recommendation

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{report.ticker}</h1>
          {companyName && <p className="text-muted-foreground">{companyName}</p>}
          <p className="mt-1 text-xs text-muted-foreground">Generated {formatDate(report.generated_at)}</p>
        </div>
        <RecommendationBadge rating={rec?.rating} confidence={rec?.confidence_score} />
      </div>

      {rec && (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle>Investment Recommendation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="leading-relaxed text-foreground">{rec.reasoning}</p>
            {rec.risks.length > 0 && (
              <div>
                <p className="mb-2 font-medium">Key Risks</p>
                <ul className="list-inside list-disc space-y-1 text-muted-foreground">
                  {rec.risks.map((risk) => (
                    <li key={risk}>{risk}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-3">
              {rec.target_price_range && (
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Target Price</p>
                  <p className="font-medium">{rec.target_price_range}</p>
                </div>
              )}
              {rec.investment_horizon && (
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Horizon</p>
                  <p className="font-medium">{rec.investment_horizon}</p>
                </div>
              )}
              {rec.portfolio_allocation_suggestion && (
                <div>
                  <p className="text-xs uppercase text-muted-foreground">Allocation</p>
                  <p className="font-medium">{rec.portfolio_allocation_suggestion}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
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

      <Section title="Investment Thesis" content={report.analysis} />
      <Section title="Financial Data Summary" content={report.financial_data_summary} />
      <Section title="News Research Summary" content={report.news_research_summary} />
    </div>
  )
}
