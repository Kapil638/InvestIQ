export type CommitteeRecommendation = 'BUY' | 'HOLD' | 'SELL' | 'AVOID'

export type AnalystPersonaId =
  | 'fundamental'
  | 'news'
  | 'technical'
  | 'valuation'
  | 'risk'
  | string

export interface AnalystOpinion {
  id: AnalystPersonaId
  name: string
  title: string
  recommendation: CommitteeRecommendation
  confidence: number
  supporting_points: string[]
  sources: string[]
}

export interface CommitteeVerdict {
  final_recommendation: CommitteeRecommendation
  overall_confidence: number
  investment_horizon?: string | null
  bull_case: string[]
  bear_case: string[]
  conclusion: string
  consensus_summary: string
}

export interface InvestmentCommittee {
  analysts: AnalystOpinion[]
  verdict: CommitteeVerdict
  sources_used: string[]
}
