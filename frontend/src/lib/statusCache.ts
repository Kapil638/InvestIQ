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

let kiteEntry: CacheEntry<KiteStatusResponse> | null = null
let growwEntry: CacheEntry<GrowwStatusResponse> | null = null
let tapetideEntry: CacheEntry<TapetideStatusResponse> | null = null
let driveEntry: CacheEntry<GoogleDriveStatusResponse> | null = null
let authEntry: CacheEntry<AuthStatusResponse> | null = null
let kiteInFlight: Promise<KiteStatusResponse> | null = null
let growwInFlight: Promise<GrowwStatusResponse> | null = null
let tapetideInFlight: Promise<TapetideStatusResponse> | null = null
let driveInFlight: Promise<GoogleDriveStatusResponse> | null = null
let authInFlight: Promise<AuthStatusResponse> | null = null

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

function isFresh<T>(entry: CacheEntry<T> | null, ttlMs: number = STATUS_TTL_MS): entry is CacheEntry<T> {
  return entry !== null && Date.now() - entry.ts < ttlMs
}

export function invalidateStatusCache(): void {
  kiteEntry = null
  growwEntry = null
  tapetideEntry = null
  driveEntry = null
  authEntry = null
}

export function invalidateAuthStatusCache(): void {
  authEntry = null
}

export async function fetchKiteStatusCached(force = false): Promise<KiteStatusResponse> {
  if (!force && isFresh(kiteEntry)) return kiteEntry.data
  if (!force && kiteInFlight) return kiteInFlight

  kiteInFlight = getKiteStatus()
    .then((data) => {
      kiteEntry = { data, ts: Date.now() }
      return data
    })
    .catch(() => {
      kiteEntry = { data: KITE_DISABLED, ts: Date.now() }
      return KITE_DISABLED
    })
    .finally(() => {
      kiteInFlight = null
    })

  return kiteInFlight
}

export async function fetchGrowwStatusCached(force = false): Promise<GrowwStatusResponse> {
  if (!force && isFresh(growwEntry)) return growwEntry.data
  if (!force && growwInFlight) return growwInFlight

  growwInFlight = getGrowwStatus()
    .then((data) => {
      growwEntry = { data, ts: Date.now() }
      return data
    })
    .catch(() => {
      growwEntry = { data: GROWW_DISABLED, ts: Date.now() }
      return GROWW_DISABLED
    })
    .finally(() => {
      growwInFlight = null
    })

  return growwInFlight
}

export async function fetchTapetideStatusCached(force = false): Promise<TapetideStatusResponse> {
  if (!force && isFresh(tapetideEntry)) return tapetideEntry.data
  if (!force && tapetideInFlight) return tapetideInFlight

  tapetideInFlight = getTapetideStatus()
    .then((data) => {
      tapetideEntry = { data, ts: Date.now() }
      return data
    })
    .catch(() => {
      tapetideEntry = { data: TAPETIDE_DISABLED, ts: Date.now() }
      return TAPETIDE_DISABLED
    })
    .finally(() => {
      tapetideInFlight = null
    })

  return tapetideInFlight
}

export async function fetchGoogleDriveStatusCached(force = false): Promise<GoogleDriveStatusResponse> {
  if (!force && isFresh(driveEntry)) return driveEntry.data
  if (!force && driveInFlight) return driveInFlight

  driveInFlight = getGoogleDriveStatus()
    .then((data) => {
      driveEntry = { data, ts: Date.now() }
      return data
    })
    .catch(() => {
      driveEntry = { data: DRIVE_DISABLED, ts: Date.now() }
      return DRIVE_DISABLED
    })
    .finally(() => {
      driveInFlight = null
    })

  return driveInFlight
}

export async function fetchAuthStatusCached(force = false): Promise<AuthStatusResponse> {
  if (!force && isFresh(authEntry, AUTH_STATUS_TTL_MS)) return authEntry.data
  if (!force && authInFlight) return authInFlight

  authInFlight = getAuthStatus()
    .then((data) => {
      authEntry = { data, ts: Date.now() }
      return data
    })
    .catch(() => {
      authEntry = { data: AUTH_DISABLED, ts: Date.now() }
      return AUTH_DISABLED
    })
    .finally(() => {
      authInFlight = null
    })

  return authInFlight
}
