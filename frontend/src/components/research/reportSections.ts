import type { ResearchReportResponse } from '@/types/api'

const NA = 'Not available'

export interface ReportSection {
  id: string
  title: string
  content: string
  items?: string[]
}

export function buildReportSections(report: ResearchReportResponse): ReportSection[] {
  const rec = report.recommendation
  const profile = report.financial_data?.profile

  const executiveSummary =
    rec?.reasoning?.trim() ||
    (report.analysis ? report.analysis.split('\n').slice(0, 3).join(' ').trim() : '') ||
    NA

  const businessOverview =
    profile?.description?.trim() ||
    [profile?.sector, profile?.industry].filter(Boolean).join(' · ') ||
    NA

  const financialHealth = report.financial_data_summary?.trim() || NA
  const valuationView = rec?.target_price_range
    ? `Target price range: ${rec.target_price_range}`
    : report.financial_data_summary?.includes('P/E') ||
        report.financial_data_summary?.includes('valuation')
      ? report.financial_data_summary
      : NA

  const growthDrivers = report.analysis?.trim()
    ? splitBullets(report.analysis).slice(0, 5)
    : rec?.reasoning
      ? [rec.reasoning]
      : [NA]

  const keyRisks =
    rec?.risks && rec.risks.length > 0
      ? rec.risks
      : report.guardrails?.issues?.map((i) => i.message) ?? [NA]

  const newsImpact = report.news_research_summary?.trim() || NA

  const threeYearView = rec?.investment_horizon
    ? `${rec.investment_horizon}. ${rec.reasoning || ''}`.trim()
    : report.analysis?.toLowerCase().includes('year')
      ? report.analysis
      : NA

  const finalRecommendation = rec?.rating
    ? `${rec.rating} — ${rec.reasoning || 'See analysis section.'}`
    : report.guardrails?.passed === false
      ? 'No rating issued — guardrails did not pass validation.'
      : NA

  const confidence =
    report.confidence_score != null
      ? `${report.confidence_score}% (deterministic ${report.scoring_version ?? 'v1'})`
      : rec?.confidence_score != null
        ? `${rec.confidence_score}%`
        : NA

  const sources: string[] = []
  if (report.financial_data?.data_sources?.length) {
    sources.push(...report.financial_data.data_sources.map((s) => `Yahoo Finance (${s})`))
  } else if (report.financial_data_summary) {
    sources.push('Yahoo Finance')
  }
  if (report.news_research_summary) sources.push('Tavily news')
  if (report.guardrails) sources.push('InvestIQ guardrails')
  sources.push('OpenRouter LLM agents')
  if (sources.length === 0) sources.push(NA)

  return [
    { id: 'executive', title: 'Executive Summary', content: executiveSummary },
    { id: 'business', title: 'Business Overview', content: businessOverview },
    { id: 'financial', title: 'Financial Health', content: financialHealth },
    { id: 'valuation', title: 'Valuation View', content: valuationView },
    { id: 'growth', title: 'Growth Drivers', content: '', items: growthDrivers },
    { id: 'risks', title: 'Key Risks', content: '', items: keyRisks },
    { id: 'news', title: 'News Impact', content: newsImpact },
    { id: 'horizon', title: '3-Year Investment View', content: threeYearView },
    { id: 'recommendation', title: 'Final Recommendation', content: finalRecommendation },
    { id: 'confidence', title: 'Confidence Score', content: confidence },
    { id: 'sources', title: 'Sources / Data Used', content: '', items: sources },
  ]
}

function splitBullets(text: string): string[] {
  return text
    .split(/\n+/)
    .map((line) => line.replace(/^[-*•]\s*/, '').trim())
    .filter((line) => line.length > 20)
}
