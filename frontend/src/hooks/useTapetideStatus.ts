import { useCallback, useEffect, useState } from 'react'
import { fetchTapetideStatusCached } from '@/lib/statusCache'
import type { TapetideStatusResponse } from '@/types/api'

const DISABLED_STATUS: TapetideStatusResponse = {
  enabled: false,
  read_only: true,
  connected: false,
  message: 'Tapetide NSE/BSE MCP is not enabled.',
  token_configured: false,
  available_read_tools: [],
}

export function useTapetideStatus() {
  const [status, setStatus] = useState<TapetideStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  const refetch = useCallback(() => {
    setRefreshKey((key) => key + 1)
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const data = await fetchTapetideStatusCached(refreshKey > 0)
        if (!cancelled) setStatus(data)
      } catch {
        if (!cancelled) setStatus(DISABLED_STATUS)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  const tapetideLive = Boolean(status?.enabled && status.connected && status.token_configured)

  return { status, loading, tapetideLive, refetch }
}
