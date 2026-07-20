import type { InvestmentCommittee } from '@/types/investmentCommittee'

export type RecommendationRating = 'Buy' | 'Hold' | 'Avoid' | 'Watchlist'

export interface InvestmentRecommendation {
  rating: RecommendationRating
  confidence_score: number
  reasoning: string
  risks: string[]
  target_price_range?: string | null
  investment_horizon?: string | null
  portfolio_allocation_suggestion?: string | null
}

export interface GuardrailIssue {
  code: string
  message: string
  severity: 'warning' | 'error'
}

export interface GuardrailResult {
  passed: boolean
  issues: GuardrailIssue[]
  retry_count: number
  blocked_reason?: string | null
}

export interface CompanyProfile {
  symbol: string
  company_name: string
  sector?: string | null
  industry?: string | null
  market_cap?: number | null
  price?: number | null
  description?: string | null
}

export interface FinancialResearchResponse {
  ticker: string
  profile: CompanyProfile
  data_sources?: string[]
}

export interface FinancialSummaryResponse {
  ticker: string
  company_name: string
  sector: string
  industry: string
  market_cap: number | null
  current_price: number | null
  currency: string
  pe_ratio: number | null
  pb_ratio: number | null
  roe: number | null
  debt_to_equity: number | null
  revenue_growth: number | null
  profit_margin: number | null
  dividend_yield: number | null
  data_source: string
  price_source?: string
  fundamentals_source?: string
  data_timestamp: string
}

export interface TapetideStatusResponse {
  enabled: boolean
  read_only: boolean
  connected: boolean
  message: string
  mcp_url?: string | null
  token_configured: boolean
  available_read_tools: string[]
}

/** @deprecated Use TapetideStatusResponse */
export type NseBseStatusResponse = TapetideStatusResponse

export interface AnalysisOutput {
  narrative: string
  scores: Record<string, number>
  scores_estimated?: boolean
}

export interface RiskOutput {
  narrative: string
  scores: Record<string, number>
  risks: string[]
  scores_estimated?: boolean
}

export interface ResearchReportResponse {
  id?: string | null
  ticker: string
  generated_at: string
  financial_data?: FinancialResearchResponse | null
  financial_data_summary?: string | null
  news_research_summary?: string | null
  analysis?: string | null
  analysis_output?: AnalysisOutput | null
  risk_output?: RiskOutput | null
  structured_risks?: {
    risks: string[]
    source: string
    risk_count: number
  } | null
  guardrails?: GuardrailResult | null
  risk_guardrails?: GuardrailResult | null
  recommendation_guardrails?: GuardrailResult | null
  recommendation?: InvestmentRecommendation | null
  investment_committee?: InvestmentCommittee | null
  pipeline_trace?: PipelineStageTrace[]
  confidence_score?: number | null
  score_breakdown?: ScoreBreakdown | null
  scoring_version?: string | null
  data_snapshot_hash?: string | null
  confidence_change_reason?: string | null
  regenerated_from_same_data?: boolean
  model_used?: string | null
}

export interface PipelineStageTrace {
  stage: string
  status: string
  started_at: string
  completed_at?: string | null
  duration_ms?: number | null
  detail?: string | null
}

export interface ScoreBreakdown {
  financial_quality_score: number
  valuation_score: number
  growth_score: number
  risk_score: number
  news_score: number
  data_quality_score: number
}

export interface ReportSummary {
  id: string
  ticker: string
  company_name?: string | null
  rating?: string | null
  confidence_score?: number | null
  guardrails_passed: boolean
  generated_at: string
  pdf_generated_at?: string | null
  google_drive_file_id?: string | null
  google_drive_url?: string | null
  google_drive_saved_at?: string | null
}

export interface ReportDriveSaveResponse {
  success: boolean
  drive_file_id: string
  drive_url: string
}

export interface ReportListResponse {
  items: ReportSummary[]
  total: number
  limit: number
  offset: number
}

export interface BulkDeleteReportsResponse {
  deleted: number
  not_found: string[]
}

export interface StoredReportResponse {
  id: string
  ticker: string
  company_name?: string | null
  rating?: string | null
  confidence_score?: number | null
  guardrails_passed: boolean
  generated_at: string
  report: ResearchReportResponse
  pdf_generated_at?: string | null
  google_drive_file_id?: string | null
  google_drive_url?: string | null
  google_drive_saved_at?: string | null
}

export interface ResearchAskResponse {
  ticker: string
  company_name: string
  question: string
  answer: string
  generated_at: string
  data_sources: string[]
}

export interface KiteStatusResponse {
  enabled: boolean
  read_only: boolean
  authenticated: boolean
  connected: boolean
  user_id?: string | null
  broker?: string | null
  message: string
  mcp_url?: string | null
  excluded_tools: string[]
  available_read_tools: string[]
}

export interface GoogleDriveStatusResponse {
  enabled: boolean
  oauth_configured: boolean
  authenticated: boolean
  connected: boolean
  user_email?: string | null
  message: string
}

export interface AuthStatusResponse {
  authenticated: boolean
  owner_auth_configured: boolean
  email?: string | null
  display_name?: string | null
  picture_url?: string | null
  has_passkey: boolean
}

export interface KiteQuoteResponse {
  symbol: string
  kite_symbol: string
  exchange?: string | null
  last_price: number | null
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  change: number | null
  change_percent: number | null
  currency: string
  source: string
  timestamp: string
}

export interface HistoricalCandle {
  timestamp: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
}

export type HistoryInterval = 'minute' | '5minute' | '15minute' | 'day' | 'week' | 'month'

export interface PortfolioHolding {
  symbol: string
  exchange?: string | null
  company_name?: string | null
  quantity?: number | null
  average_price?: number | null
  last_price?: number | null
  invested_value?: number | null
  current_value?: number | null
  pnl?: number | null
  pnl_percent?: number | null
  day_change?: number | null
  sector?: string | null
  price_source: string
}

export interface PortfolioHoldingsResponse {
  holdings: PortfolioHolding[]
  auth_required: boolean
  message?: string | null
  source?: string | null
  timestamp: string
}

export interface SectorExposureItem {
  sector: string
  allocation_percent: number
  holdings: string[]
}

export interface PortfolioAnalyzeResponse {
  summary: string
  concentration_risk: string
  strong_holdings: string[]
  weak_holdings: string[]
  sector_exposure: SectorExposureItem[]
  rebalance_suggestions: string[]
  three_year_view: string
  watchlist_actions: string[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ReportChatRequest {
  question: string
  history: ChatTurn[]
}

export interface ReportChatResponse {
  answer: string
  sources: string[]
  report_id: string
}

export interface CompanySearchResult {
  symbol: string
  exchange: string
  company_name: string
  sector?: string | null
  source: string
}

export interface CompanySearchResponse {
  results: CompanySearchResult[]
  source: string
  fallback?: boolean
}

export interface InvestorProfile {
  capital?: string | null
  time_horizon?: string | null
  risk_appetite?: string | null
  preferences: string[]
  avoidances: string[]
  market_cap_preference?: string | null
  dividend_growth_preference?: string | null
  investment_style?: string | null
}

export interface ProfileFieldDisplay {
  label: string
  value: string | null
  source: 'user' | 'assumed' | 'missing'
}

export interface AdvisorRetrievalSummary {
  raw_candidates_count: number
  validated_candidates_count: number
  providers_used: string[]
}

export interface CompanyResearchAction {
  symbol: string
  company_name?: string | null
  message: string
}

export interface StockRecommendation {
  rank: number
  symbol: string
  company_name: string
  sector: string
  match_score: number
  suggested_allocation_percent: number
  why_it_fits: string[]
  key_risks: string[]
  data_sources: string[]
  matched_themes?: string[]
  theme_match_score?: number
  theme_match_reason?: string
  key_evidence?: string[]
  financial_quality_score?: number | null
  valuation_score?: number | null
  risk_score?: number | null
  overall_match_score?: number
}

export interface AdvisorSectorExposure {
  sector: string
  percent: number
}

export interface PortfolioMix {
  large_cap_percent: number
  mid_cap_percent: number
  small_cap_percent: number
  sector_exposure: AdvisorSectorExposure[]
  risk_summary: string
  time_horizon_suitability: string
}

export interface AdvisorRecommendResponse {
  intent: string
  investor_profile: InvestorProfile
  profile_fields: ProfileFieldDisplay[]
  recommendations: StockRecommendation[]
  portfolio_mix: PortfolioMix
  disclaimer: string
  warning?: string | null
  assumptions_used?: string[]
  missing_inputs?: string[]
  warnings?: string[]
  retrieval_summary?: AdvisorRetrievalSummary
  clarification_message?: string | null
  company_research_action?: CompanyResearchAction | null
}
