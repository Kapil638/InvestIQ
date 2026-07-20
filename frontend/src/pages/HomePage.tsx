import { useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import {
  askResearchQuestion,
  generateReport,
  getAdvisorRecommendations,
  getFinancialSummary,
} from '@/lib/api'
import type {
  AdvisorRecommendResponse,
  FinancialSummaryResponse,
  ResearchAskResponse,
  ResearchReportResponse,
} from '@/types/api'
import type { IndianCompany } from '@/data/indianCompanies'
import { CompanySearch } from '@/components/CompanySearch'
import { StockOverview } from '@/components/StockOverview'
import { AIAssistantModal } from '@/components/AIAssistantModal'
import { TrustLayer } from '@/components/TrustLayer'
import { AdvisorPromptCard } from '@/components/advisor/AdvisorPromptCard'
import { AdvisorProfileSummary } from '@/components/advisor/AdvisorProfileSummary'
import { AdvisorResults, AdvisorPortfolioMix } from '@/components/advisor/AdvisorResults'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { PasskeyEnrollBanner } from '@/components/auth/PasskeyEnrollBanner'

export function HomePage() {
  const location = useLocation()
  const [selectedCompany, setSelectedCompany] = useState<IndianCompany | null>(null)
  const [financials, setFinancials] = useState<FinancialSummaryResponse | null>(null)
  const [financialsLoading, setFinancialsLoading] = useState(false)
  const [financialsError, setFinancialsError] = useState<string | null>(null)

  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [askLoading, setAskLoading] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)
  const [askAnswer, setAskAnswer] = useState<ResearchAskResponse | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [report, setReport] = useState<ResearchReportResponse | null>(null)

  const [advisorLoading, setAdvisorLoading] = useState(false)
  const [advisorError, setAdvisorError] = useState<string | null>(null)
  const [advisorResult, setAdvisorResult] = useState<AdvisorRecommendResponse | null>(null)

  useEffect(() => {
    const state = location.state as { company?: IndianCompany; openAI?: boolean } | null
    if (state?.company) {
      setSelectedCompany(state.company)
      if (state.openAI) {
        setAiModalOpen(true)
        setAskAnswer(null)
        setAskError(null)
        setReport(null)
        setReportError(null)
      }
      window.history.replaceState({}, document.title)
    }
  }, [location.state])

  useEffect(() => {
    if (!selectedCompany) {
      setFinancials(null)
      setFinancialsError(null)
      return
    }

    let cancelled = false
    const company = selectedCompany

    async function loadFinancials() {
      setFinancialsLoading(true)
      setFinancialsError(null)
      setFinancials(null)
      setReport(null)
      setReportError(null)
      setAskAnswer(null)
      setAskError(null)

      try {
        const data = await getFinancialSummary(company.ticker)
        if (!cancelled) setFinancials(data)
      } catch (err) {
        if (!cancelled) {
          setFinancialsError(err instanceof Error ? err.message : 'Failed to load financial data')
        }
      } finally {
        if (!cancelled) setFinancialsLoading(false)
      }
    }

    void loadFinancials()
    return () => {
      cancelled = true
    }
  }, [selectedCompany])

  const handleCompanySelect = useCallback((company: IndianCompany) => {
    setSelectedCompany(company)
    setAiModalOpen(false)
    setAskAnswer(null)
    setAskError(null)
    setReport(null)
    setReportError(null)
  }, [])

  const handleOpenAI = useCallback(() => {
    setAskAnswer(null)
    setAskError(null)
    setReport(null)
    setReportError(null)
    setAiModalOpen(true)
  }, [])

  const handleAskQuestion = useCallback(
    async (question: string) => {
      if (!selectedCompany) return

      setAskLoading(true)
      setAskError(null)
      setAskAnswer(null)
      setReport(null)
      setReportError(null)

      try {
        const result = await askResearchQuestion(selectedCompany.ticker, question)
        setAskAnswer(result)
      } catch (err) {
        setAskError(err instanceof Error ? err.message : 'Failed to get answer')
      } finally {
        setAskLoading(false)
      }
    },
    [selectedCompany],
  )

  const handleGenerateReport = useCallback(async () => {
    if (!selectedCompany) return

    setReportLoading(true)
    setReportError(null)
    setReport(null)
    setAskAnswer(null)
    setAskError(null)

    try {
      const result = await generateReport(selectedCompany.ticker)
      setReport(result)
    } catch (err) {
      setReportError(err instanceof Error ? err.message : 'Failed to generate report')
    } finally {
      setReportLoading(false)
    }
  }, [selectedCompany])

  const handleAdvisorSubmit = useCallback(async (prompt: string) => {
    setAdvisorLoading(true)
    setAdvisorError(null)
    setAdvisorResult(null)

    try {
      const result = await getAdvisorRecommendations(prompt)
      setAdvisorResult(result)
    } catch (err) {
      setAdvisorError(err instanceof Error ? err.message : 'Advisor request failed')
    } finally {
      setAdvisorLoading(false)
    }
  }, [])

  const handleAdvisorOpenOverview = useCallback((company: IndianCompany) => {
    setSelectedCompany(company)
    setAiModalOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const handleAdvisorRunResearch = useCallback((company: IndianCompany) => {
    setSelectedCompany(company)
    setAskAnswer(null)
    setAskError(null)
    setReport(null)
    setReportError(null)
    setAiModalOpen(true)
  }, [])

  return (
    <div className="space-y-8">
      <PasskeyEnrollBanner />
      <section className="hero-glow relative rounded-3xl border border-border/60 p-6 sm:p-8">
        <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
          <div className="absolute -right-16 -top-16 size-48 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute -bottom-10 left-10 size-36 rounded-full bg-violet-500/10 blur-3xl" />
        </div>
        <div className="relative max-w-3xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-primary">
            Indian equity research
          </p>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Research a company or describe your investment goals
          </h1>
          <p className="mt-2 text-sm text-muted-foreground sm:text-base">
            Search a specific stock, or ask the AI advisor for curated Indian equity ideas worth
            researching further.
          </p>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-3xl border border-border/60 p-6 sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Find a company</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight">Search by name or ticker</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Explore fundamentals, charts, and launch full AI research for any listed Indian stock.
          </p>
          <div className="relative z-10 mt-5">
            <CompanySearch
              onSelect={handleCompanySelect}
              selectedCompany={selectedCompany}
              placeholder="Search Infosys, Reliance, HDFC Bank…"
              autoFocus={!selectedCompany && !advisorLoading}
            />
          </div>
        </div>

        <AdvisorPromptCard onSubmit={(prompt) => void handleAdvisorSubmit(prompt)} loading={advisorLoading} />
      </div>

      {advisorError && (
        <Alert variant="destructive" title="Advisor request failed">
          {advisorError}
        </Alert>
      )}

      {advisorResult && (
        <div className="space-y-6">
          {(advisorResult.warning || advisorResult.clarification_message) && (
            <Alert variant="default" title="Advisor note">
              <span className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                {advisorResult.clarification_message || advisorResult.warning}
              </span>
            </Alert>
          )}

          <AdvisorProfileSummary
            intent={advisorResult.intent}
            profileFields={advisorResult.profile_fields}
            assumptionsUsed={advisorResult.assumptions_used}
            missingInputs={advisorResult.missing_inputs}
            profile={advisorResult.investor_profile}
          />

          {advisorResult.company_research_action && (
            <div className="glass-card rounded-2xl border border-violet-500/30 p-5">
              <p className="text-sm text-muted-foreground">
                {advisorResult.company_research_action.message}
              </p>
              <Button
                className="mt-3"
                size="sm"
                onClick={() =>
                  handleAdvisorOpenOverview({
                    name: advisorResult.company_research_action!.company_name || advisorResult.company_research_action!.symbol,
                    ticker: advisorResult.company_research_action!.symbol,
                    exchange: 'NSE',
                  })
                }
              >
                Open Stock Overview
              </Button>
            </div>
          )}

          <AdvisorResults
            recommendations={advisorResult.recommendations}
            onOpenOverview={handleAdvisorOpenOverview}
            onRunResearch={handleAdvisorRunResearch}
          />

          <AdvisorPortfolioMix
            largeCapPercent={advisorResult.portfolio_mix.large_cap_percent}
            midCapPercent={advisorResult.portfolio_mix.mid_cap_percent}
            smallCapPercent={advisorResult.portfolio_mix.small_cap_percent}
            sectorExposure={advisorResult.portfolio_mix.sector_exposure}
            riskSummary={advisorResult.portfolio_mix.risk_summary}
            timeHorizonSuitability={advisorResult.portfolio_mix.time_horizon_suitability}
          />

          <p className="text-center text-xs text-muted-foreground">{advisorResult.disclaimer}</p>
        </div>
      )}

      {selectedCompany && (
        <StockOverview
          company={selectedCompany}
          financials={financials}
          loading={financialsLoading}
          error={financialsError}
          onOpenAI={handleOpenAI}
        />
      )}

      {!selectedCompany && !advisorResult && <TrustLayer />}

      {selectedCompany && (
        <AIAssistantModal
          open={aiModalOpen}
          company={selectedCompany}
          askLoading={askLoading}
          askError={askError}
          askAnswer={askAnswer}
          reportLoading={reportLoading}
          reportError={reportError}
          report={report}
          onClose={() => setAiModalOpen(false)}
          onAskQuestion={(question) => void handleAskQuestion(question)}
          onGenerateReport={() => void handleGenerateReport()}
        />
      )}
    </div>
  )
}
