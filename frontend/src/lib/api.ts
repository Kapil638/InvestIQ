import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser'
import type {
  AuthStatusResponse,
  DatabaseStatusResponse,
  FinancialSummaryResponse,
  GrowwStatusResponse,
  HealthResponse,
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

// Exported for the handful of full-page redirect links (Kite/Google Drive
// OAuth "Connect" buttons) that need an absolute URL - a plain relative
// href works fine locally (Vite's dev proxy makes it same-origin) but
// silently 404s in production, where the frontend (Vercel) and backend
// (Render) are different domains and there's no proxy.
export const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

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

const NETWORK_RETRY_ATTEMPTS = 2
const NETWORK_RETRY_DELAY_MS = 1500

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

interface RequestOptions extends RequestInit {
  // Set false for expensive, long-running, non-idempotent-feeling calls (e.g.
  // the multi-minute full report generation) where silently re-triggering an
  // expensive LLM pipeline on a dropped connection would be the wrong default
  // - better to surface the error and let the user explicitly retry.
  retryOnNetworkError?: boolean
}

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const { retryOnNetworkError = true, ...fetchInit } = init ?? {}
  const attempts = retryOnNetworkError ? NETWORK_RETRY_ATTEMPTS : 1

  let response: Response | undefined
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      response = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...fetchInit.headers },
        credentials: 'include',
        ...fetchInit,
      })
      break
    } catch {
      if (attempt === attempts) {
        throw new Error(
          'Cannot reach the InvestIQ backend. Ensure the backend is running on port 8002 and refresh the page.',
        )
      }
      // A dropped connection here is often a brief server restart (e.g. a
      // free-tier instance recovering from an out-of-memory crash) rather
      // than a real outage - a short retry rides it out instead of failing
      // in front of the user for something that resolves itself in seconds.
      await sleep(NETWORK_RETRY_DELAY_MS)
    }
  }
  // The loop above always either assigns response or throws before falling through.
  const resolvedResponse = response!

  if (!resolvedResponse.ok) {
    let message = `Request failed (${resolvedResponse.status})`
    try {
      const body = (await resolvedResponse.json()) as ApiErrorBody
      message = formatApiError(body, resolvedResponse.status)
    } catch {
      // use default message
    }
    throw new Error(message)
  }

  if (resolvedResponse.status === 204) {
    return undefined as T
  }

  return resolvedResponse.json() as Promise<T>
}

export function getFinancialSummary(ticker: string): Promise<FinancialSummaryResponse> {
  return request<FinancialSummaryResponse>(`/financials/${ticker.toUpperCase()}`)
}

export function getKiteStatus(): Promise<KiteStatusResponse> {
  return request<KiteStatusResponse>('/kite/status')
}

export function getGrowwStatus(): Promise<GrowwStatusResponse> {
  return request<GrowwStatusResponse>('/groww/status')
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function getDatabaseStatus(): Promise<DatabaseStatusResponse> {
  return request<DatabaseStatusResponse>('/status/database')
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
    // A multi-minute multi-agent LLM pipeline - never silently re-trigger
    // this on a dropped connection, since a retry would burn LLM cost on an
    // already-possibly-partially-run generation with no guarantee of success.
    retryOnNetworkError: false,
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
  let response: Response | undefined
  for (let attempt = 1; attempt <= NETWORK_RETRY_ATTEMPTS; attempt++) {
    try {
      response = await fetch(`${API_BASE}/reports/${reportId}/pdf`, {
        method: 'POST',
        credentials: 'include',
      })
      break
    } catch {
      if (attempt === NETWORK_RETRY_ATTEMPTS) {
        throw new Error(
          'Cannot reach the InvestIQ backend. Ensure the backend is running on port 8002 and refresh the page.',
        )
      }
      await sleep(NETWORK_RETRY_DELAY_MS)
    }
  }
  const resolvedResponse = response!

  if (!resolvedResponse.ok) {
    let message = `PDF generation failed (${resolvedResponse.status})`
    try {
      const body = (await resolvedResponse.json()) as ApiErrorBody
      message = formatApiError(body, resolvedResponse.status)
    } catch {
      // use default message
    }
    throw new Error(message)
  }

  const blob = await resolvedResponse.blob()
  const filename =
    parseContentDispositionFilename(resolvedResponse.headers.get('Content-Disposition')) ??
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
