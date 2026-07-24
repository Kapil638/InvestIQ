import type { GrowwStatusResponse, KiteStatusResponse, TapetideStatusResponse } from '@/types/api'
import { DATA_SOURCES, type DataSourceItem } from '@/data/dataSources'

export type KiteBadgeStatus = 'live' | 'auth' | 'soon'

export function resolveKiteBadge(status: KiteStatusResponse | null): KiteBadgeStatus {
  if (!status?.enabled) return 'soon'
  if (status.authenticated && status.connected) return 'live'
  return 'auth'
}

// Simpler than Kite's badge: no browser OAuth step, so there's no separate
// "auth required" state - Groww is either connected (env credentials valid)
// or not enabled/reachable yet.
export function resolveGrowwBadge(status: GrowwStatusResponse | null): 'live' | 'soon' {
  return status?.enabled && status.connected ? 'live' : 'soon'
}

export function resolveDataSources(
  kiteStatus: KiteStatusResponse | null,
  tapetideStatus: TapetideStatusResponse | null = null,
): DataSourceItem[] {
  const kiteBadge = resolveKiteBadge(kiteStatus)
  const tapetideLive = Boolean(
    tapetideStatus?.enabled && tapetideStatus.connected && tapetideStatus.token_configured,
  )

  return DATA_SOURCES.map((source) => {
    if (source.id === 'fundamentals') {
      return {
        ...source,
        provider: tapetideLive ? 'Tapetide NSE/BSE MCP' : 'Yahoo Finance',
        status: 'live' as const,
        description: tapetideLive
          ? 'Official NSE/BSE exchange metadata and fundamentals via Tapetide MCP.'
          : 'NSE/BSE financials, ratios, and company profile for research snapshots.',
      }
    }

    if (source.id === 'market-data' || source.id === 'portfolio') {
      const status =
        kiteBadge === 'live'
          ? ('live' as const)
          : kiteBadge === 'auth'
            ? ('auth' as const)
            : tapetideLive && source.id === 'market-data'
              ? ('live' as const)
              : ('planned' as const)

      return {
        ...source,
        status,
        description:
          source.id === 'market-data'
            ? kiteBadge === 'live'
              ? 'Real-time broker quotes from Kite Connect.'
              : tapetideLive
                ? 'Live NSE/BSE exchange quotes via Tapetide MCP with Yahoo fallback.'
                : kiteBadge === 'auth'
                  ? 'Connect Zerodha via Kite to unlock broker live quotes.'
                  : 'Real-time quotes, depth, and session prices for Indian equities.'
            : kiteBadge === 'live'
              ? 'Linked positions and allocation context from Kite Connect.'
              : kiteBadge === 'auth'
                ? 'Authenticate with Zerodha to view portfolio holdings.'
                : 'Linked positions and allocation context for personalized research.',
      }
    }
    return source
  })
}

export function kiteBadgeLabel(status: DataSourceItem['status']): string {
  if (status === 'live') return 'Live'
  if (status === 'auth') return 'Auth required'
  return 'Soon'
}
