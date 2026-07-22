import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser'
import type {
  AuthStatusResponse,
  FinancialSummaryResponse,
  HistoricalCandle,
  HistoryInterval,
  KiteQuoteResponse,
  KiteStatusResponse,
  TapetideStatusResponse,
  GoogleDriveStatusResponse,
  PortfolioAnalyzeResponse,
  PortfolioHolding,
  PortfolioHoldingsResponse,
  ReportChatResponse,
  ChatTurn,
  ReportListResponse,
  BulkDeleteReportsResponse,
  ReportDriveSaveResponse,
  ResearchAskResponse,
  ResearchReportResponse,
  StoredReportResponse,
  CompanySearchResponse,
  AdvisorRecommendResponse,
  TickerResponse,
} from '@/types/api'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string } | string>
  type?: string
  status?: number
}

function formatApiError(body: ApiErrorBody, httpStatus: number): string {
  const status = body.status ?? httpStatus
  let detail = ''

  if (typeof body.detail === 'string') {
    detail = body.detail
  } else if (Array.isArray(body.detail)) {
    detail = body.detail
      .map((item) => (typeof item === 'string' ? item : item.msg ?? JSON.stringify(item)))
      .join('; ')
  }

  const typeSuffix = body.type ? ` (${body.type})` : ''

  if (detail) {
    return `[${status}] ${detail}${typeSuffix}`
  }

  return `Request failed (${status})${typeSuffix}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      credentials: 'include',
      ...init,
    })
  } catch {
    throw new Error(
      'Cannot reach the InvestIQ backend. Ensure the backend is running on port 8002 and refresh the page.',
    )
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as ApiErrorBody
      message = formatApiError(body, response.status)
    } catch {
      // use default message
    }
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export function getFinancialSummary(ticker: string): Promise<FinancialSummaryResponse> {
  return request<FinancialSummaryResponse>(`/financials/${ticker.toUpperCase()}`)
}

export function getKiteStatus(): Promise<KiteStatusResponse> {
  return request<KiteStatusResponse>('/kite/status')
}

export function getTapetideStatus(): Promise<TapetideStatusResponse> {
  return request<TapetideStatusResponse>('/tapetide/status')
}

export function getNiftyTicker(): Promise<TickerResponse> {
  return request<TickerResponse>('/ticker/nifty-top10')
}

export function getGoogleDriveStatus(): Promise<GoogleDriveStatusResponse> {
  return request<GoogleDriveStatusResponse>('/google-drive/status')
}

export function getAuthStatus(): Promise<AuthStatusResponse> {
  return request<AuthStatusResponse>('/auth/me')
}

export function googleSignIn(idToken: string): Promise<AuthStatusResponse> {
  return request<AuthStatusResponse>('/auth/google/signin', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  })
}

export function logout(): Promise<{ success: boolean }> {
  return request<{ success: boolean }>('/auth/logout', { method: 'POST' })
}

export function getWebauthnRegistrationOptions(): Promise<PublicKeyCredentialCreationOptionsJSON> {
  return request<PublicKeyCredentialCreationOptionsJSON>('/auth/webauthn/register/options', {
    method: 'POST',
  })
}

export function verifyWebauthnRegistration(
  credential: RegistrationResponseJSON,
  deviceLabel?: string,
): Promise<{ success: boolean }> {
  return request<{ success: boolean }>('/auth/webauthn/register/verify', {
    method: 'POST',
    body: JSON.stringify({ credential, device_label: deviceLabel }),
  })
}

export function getWebauthnAuthenticationOptions(): Promise<PublicKeyCredentialRequestOptionsJSON> {
  return request<PublicKeyCredentialRequestOptionsJSON>('/auth/webauthn/authenticate/options', {
    method: 'POST',
  })
}

export function verifyWebauthnAuthentication(
  credential: AuthenticationResponseJSON,
): Promise<AuthStatusResponse> {
  return request<AuthStatusResponse>('/auth/webauthn/authenticate/verify', {
    method: 'POST',
    body: JSON.stringify({ credential }),
  })
}

export function searchCompaniesApi(
  query: string,
  init?: { signal?: AbortSignal },
): Promise<CompanySearchResponse> {
  const search = new URLSearchParams({ q: query.trim() })
  return request<CompanySearchResponse>(`/search/companies?${search.toString()}`, init)
}

export function getKiteQuote(symbol: string): Promise<KiteQuoteResponse> {
  return request<KiteQuoteResponse>(`/kite/quotes/${symbol.toUpperCase()}`)
}

export function getKiteHistory(
  symbol: string,
  params: { interval: HistoryInterval; from?: string; to?: string },
): Promise<HistoricalCandle[]> {
  const search = new URLSearchParams()
  search.set('interval', params.interval)
  if (params.from) search.set('from', params.from)
  if (params.to) search.set('to', params.to)
  return request<HistoricalCandle[]>(`/kite/history/${symbol.toUpperCase()}?${search.toString()}`)
}

export function getKiteHoldings(): Promise<PortfolioHoldingsResponse> {
  return request<PortfolioHoldingsResponse>('/kite/holdings')
}

export function analyzePortfolio(holdings: PortfolioHolding[]): Promise<PortfolioAnalyzeResponse> {
  return request<PortfolioAnalyzeResponse>('/portfolio/analyze', {
    method: 'POST',
    body: JSON.stringify({ holdings }),
  })
}

export function askResearchQuestion(
  ticker: string,
  question: string,
): Promise<ResearchAskResponse> {
  return request<ResearchAskResponse>(`/research/${ticker.toUpperCase()}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}

export function generateReport(ticker: string): Promise<ResearchReportResponse> {
  return request<ResearchReportResponse>(`/research/${ticker.toUpperCase()}/report`, {
    method: 'POST',
  })
}

export function listReports(params?: {
  ticker?: string
  limit?: number
  offset?: number
}): Promise<ReportListResponse> {
  const search = new URLSearchParams()
  if (params?.ticker) search.set('ticker', params.ticker)
  if (params?.limit) search.set('limit', String(params.limit))
  if (params?.offset) search.set('offset', String(params.offset))
  const query = search.toString()
  return request<ReportListResponse>(`/reports${query ? `?${query}` : ''}`)
}

export function getReport(reportId: string): Promise<StoredReportResponse> {
  return request<StoredReportResponse>(`/reports/${reportId}`)
}

export function deleteReport(reportId: string): Promise<void> {
  return request<void>(`/reports/${reportId}`, { method: 'DELETE' })
}

export function deleteReportsBulk(reportIds: string[]): Promise<BulkDeleteReportsResponse> {
  return request<BulkDeleteReportsResponse>('/reports/bulk-delete', {
    method: 'POST',
    body: JSON.stringify({ report_ids: reportIds }),
  })
}

export function chatAboutReport(
  reportId: string,
  question: string,
  history: ChatTurn[] = [],
): Promise<ReportChatResponse> {
  return request<ReportChatResponse>(`/reports/${reportId}/chat`, {
    method: 'POST',
    body: JSON.stringify({
      question,
      history: history.map(({ role, content }) => ({ role, content })),
    }),
  })
}

export function getAdvisorRecommendations(prompt: string): Promise<AdvisorRecommendResponse> {
  return request<AdvisorRecommendResponse>('/advisor/recommend', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

export function listReportsByTicker(
  ticker: string,
  params?: { limit?: number; offset?: number },
): Promise<ReportListResponse> {
  const search = new URLSearchParams()
  if (params?.limit) search.set('limit', String(params.limit))
  if (params?.offset) search.set('offset', String(params.offset))
  const query = search.toString()
  return request<ReportListResponse>(
    `/reports/ticker/${ticker.toUpperCase()}${query ? `?${query}` : ''}`,
  )
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) return null
  const match = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(header)
  const raw = match?.[1] ?? match?.[2]
  return raw ? decodeURIComponent(raw) : null
}

export async function downloadReportPdf(reportId: string): Promise<string> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/reports/${reportId}/pdf`, {
      method: 'POST',
      credentials: 'include',
    })
  } catch {
    throw new Error(
      'Cannot reach the InvestIQ backend. Ensure the backend is running on port 8002 and refresh the page.',
    )
  }

  if (!response.ok) {
    let message = `PDF generation failed (${response.status})`
    try {
      const body = (await response.json()) as ApiErrorBody
      message = formatApiError(body, response.status)
    } catch {
      // use default message
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  const filename =
    parseContentDispositionFilename(response.headers.get('Content-Disposition')) ??
    `InvestIQ_report_${reportId}.pdf`
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
  return filename
}

export function saveReportToGoogleDrive(reportId: string): Promise<ReportDriveSaveResponse> {
  return request<ReportDriveSaveResponse>(`/reports/${reportId}/drive`, {
    method: 'POST',
  })
}
