import type { ResearchReportResponse } from '@/types/api'
import { formatINR, formatPercent } from '@/lib/utils'

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

  const financialHealthPoints = buildFinancialHealth(report)
  const valuationView = buildValuationView(report)

  const growthDrivers = report.analysis?.trim()
    ? splitBullets(report.analysis).slice(0, 5)
    : rec?.reasoning
      ? [rec.reasoning]
      : [NA]

  const keyRisks =
    rec?.risks && rec.risks.length > 0
      ? rec.risks
      : report.guardrails?.issues?.map((i) => i.message) ?? [NA]

  const newsImpactPoints = buildNewsImpact(report)

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
    { id: 'financial', title: 'Financial Health', content: '', items: financialHealthPoints },
    { id: 'valuation', title: 'Valuation View', content: valuationView },
    { id: 'growth', title: 'Growth Drivers', content: '', items: growthDrivers },
    { id: 'risks', title: 'Key Risks', content: '', items: keyRisks },
    { id: 'news', title: 'News Impact', content: '', items: newsImpactPoints },
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

// financial_data_summary / news_research_summary are raw JSON blobs built
// for LLM prompt context (see backend research_formatters.py) - never render
// them directly, or lines like `"ticker": "X",` leak into the UI. Build
// human-readable points from the structured fields instead.

function buildFinancialHealth(report: ResearchReportResponse): string[] {
  const fd = report.financial_data
  const ratios = fd?.ratios?.[0]
  const income = fd?.income_statements?.[0]
  const marketCap = fd?.profile?.market_cap

  const points: string[] = []
  if (marketCap != null) points.push(`Market cap: ${formatINR(marketCap, true)}`)
  if (ratios?.return_on_equity != null) points.push(`Return on equity: ${formatPercent(ratios.return_on_equity)}`)
  if (ratios?.net_profit_margin != null)
    points.push(`Net profit margin: ${formatPercent(ratios.net_profit_margin)}`)
  // Yahoo Finance's debtToEquity is already percentage-scale (e.g. 10.5 means
  // debt is 10.5% of equity), not a raw x-multiple, and not a 0-1 fraction -
  // format directly rather than via formatPercent's fraction-detection logic,
  // which would wrongly rescale a low (near debt-free) reading.
  if (ratios?.debt_to_equity != null) points.push(`Debt-to-equity: ${ratios.debt_to_equity.toFixed(1)}%`)
  if (ratios?.current_ratio != null) points.push(`Current ratio: ${ratios.current_ratio.toFixed(2)}`)
  if (income?.revenue != null) points.push(`Latest revenue: ${formatINR(income.revenue, true)}`)
  if (income?.net_income != null) points.push(`Latest net income: ${formatINR(income.net_income, true)}`)

  if (points.length > 0) return points.slice(0, 6)
  if (report.analysis) {
    const fallback = splitBullets(report.analysis).slice(0, 4)
    if (fallback.length > 0) return fallback
  }
  return [NA]
}

function buildValuationView(report: ResearchReportResponse): string {
  const rec = report.recommendation
  const ratios = report.financial_data?.ratios?.[0]
  const metrics = report.financial_data?.key_metrics?.[0]
  const pe = ratios?.price_to_earnings ?? metrics?.pe_ratio
  const pb = ratios?.price_to_book ?? metrics?.pb_ratio

  const lines: string[] = []
  if (rec?.target_price_range) lines.push(`Target price range: ${rec.target_price_range}`)
  if (pe != null) lines.push(`P/E ratio: ${pe.toFixed(2)}`)
  if (pb != null) lines.push(`P/B ratio: ${pb.toFixed(2)}`)

  return lines.length > 0 ? lines.join('\n') : NA
}

function buildNewsImpact(report: ResearchReportResponse): string[] {
  const news = report.news_data
  const points: string[] = []
  if (news?.sentiment_summary) points.push(news.sentiment_summary.trim())
  for (const group of [news?.latest_news, news?.earnings_and_filings, news?.sector_news]) {
    for (const article of group ?? []) {
      if (article.title) points.push(article.title)
      if (points.length >= 5) break
    }
    if (points.length >= 5) break
  }

  if (points.length > 0) return points
  if (report.analysis) {
    const fallback = splitBullets(report.analysis).slice(0, 3)
    if (fallback.length > 0) return fallback
  }
  return [NA]
}
