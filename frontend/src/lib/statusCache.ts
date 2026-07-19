import { getGoogleDriveStatus, getKiteStatus, getTapetideStatus } from '@/lib/api'
import type { GoogleDriveStatusResponse, KiteStatusResponse, TapetideStatusResponse } from '@/types/api'

const STATUS_TTL_MS = 60_000

type CacheEntry<T> = {
  data: T
  ts: number
}

let kiteEntry: CacheEntry<KiteStatusResponse> | null = null
let tapetideEntry: CacheEntry<TapetideStatusResponse> | null = null
let driveEntry: CacheEntry<GoogleDriveStatusResponse> | null = null
let kiteInFlight: Promise<KiteStatusResponse> | null = null
let tapetideInFlight: Promise<TapetideStatusResponse> | null = null
let driveInFlight: Promise<GoogleDriveStatusResponse> | null = null

const KITE_DISABLED: KiteStatusResponse = {
  enabled: false,
  read_only: true,
  authenticated: false,
  connected: false,
  message: 'Kite Connect is not enabled.',
  excluded_tools: [],
  available_read_tools: [],
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

function isFresh<T>(entry: CacheEntry<T> | null): entry is CacheEntry<T> {
  return entry !== null && Date.now() - entry.ts < STATUS_TTL_MS
}

export function invalidateStatusCache(): void {
  kiteEntry = null
  tapetideEntry = null
  driveEntry = null
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
