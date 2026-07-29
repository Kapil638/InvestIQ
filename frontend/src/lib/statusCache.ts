import { getAuthStatus, getGoogleDriveStatus, getGrowwStatus, getKiteStatus, getTapetideStatus } from '@/lib/api'
import type {
  AuthStatusResponse,
  GoogleDriveStatusResponse,
  GrowwStatusResponse,
  KiteStatusResponse,
  TapetideStatusResponse,
} from '@/types/api'

const STATUS_TTL_MS = 60_000
// Shorter TTL for auth: a stale "authenticated" read has higher stakes than a
// stale Kite/Drive/Tapetide connection badge.
const AUTH_STATUS_TTL_MS = 10_000

type CacheEntry<T> = {
  data: T
  ts: number
}

function isFresh<T>(entry: CacheEntry<T> | null, ttlMs: number): entry is CacheEntry<T> {
  return entry !== null && Date.now() - entry.ts < ttlMs
}

// Every status source (Kite, Groww, Tapetide, Drive, Auth) needs the same
// shape: a TTL cache + in-flight-request dedup + a disabled fallback on
// failure. This factory holds that logic once instead of once per source.
function createStatusFetcher<T>(fetchFn: () => Promise<T>, disabledValue: T, ttlMs: number = STATUS_TTL_MS) {
  let entry: CacheEntry<T> | null = null
  let inFlight: Promise<T> | null = null

  async function fetchCached(force = false): Promise<T> {
    if (!force && isFresh(entry, ttlMs)) return entry.data
    if (!force && inFlight) return inFlight

    inFlight = fetchFn()
      .then((data) => {
        entry = { data, ts: Date.now() }
        return data
      })
      .catch(() => {
        entry = { data: disabledValue, ts: Date.now() }
        return disabledValue
      })
      .finally(() => {
        inFlight = null
      })

    return inFlight
  }

  function invalidate(): void {
    entry = null
  }

  return { fetchCached, invalidate }
}

const KITE_DISABLED: KiteStatusResponse = {
  enabled: false,
  read_only: true,
  authenticated: false,
  connected: false,
  message: 'Kite Connect is not enabled.',
  excluded_tools: [],
  available_read_tools: [],
}

const GROWW_DISABLED: GrowwStatusResponse = {
  enabled: false,
  read_only: true,
  credentials_configured: false,
  connected: false,
  message: 'Groww is not enabled.',
}

const TAPETIDE_DISABLED: TapetideStatusResponse = {
  enabled: false,
  read_only: true,
  connected: false,
  message: 'Tapetide NSE/BSE MCP is not enabled.',
  token_configured: false,
  available_read_tools: [],
}

const DRIVE_DISABLED: GoogleDriveStatusResponse = {
  enabled: false,
  oauth_configured: false,
  authenticated: false,
  connected: false,
  message: 'Google Drive is not enabled.',
}

const AUTH_DISABLED: AuthStatusResponse = {
  authenticated: false,
  owner_auth_configured: false,
  has_passkey: false,
}

const kite = createStatusFetcher(getKiteStatus, KITE_DISABLED)
const groww = createStatusFetcher(getGrowwStatus, GROWW_DISABLED)
const tapetide = createStatusFetcher(getTapetideStatus, TAPETIDE_DISABLED)
const drive = createStatusFetcher(getGoogleDriveStatus, DRIVE_DISABLED)
const auth = createStatusFetcher(getAuthStatus, AUTH_DISABLED, AUTH_STATUS_TTL_MS)

export const fetchKiteStatusCached = kite.fetchCached
export const fetchGrowwStatusCached = groww.fetchCached
export const fetchTapetideStatusCached = tapetide.fetchCached
export const fetchGoogleDriveStatusCached = drive.fetchCached
export const fetchAuthStatusCached = auth.fetchCached

export function invalidateStatusCache(): void {
  kite.invalidate()
  groww.invalidate()
  tapetide.invalidate()
  drive.invalidate()
  auth.invalidate()
}

export function invalidateAuthStatusCache(): void {
  auth.invalidate()
}
