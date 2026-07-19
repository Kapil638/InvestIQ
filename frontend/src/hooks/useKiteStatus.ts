import { useCallback, useEffect, useState } from 'react'
import { fetchKiteStatusCached } from '@/lib/statusCache'
import type { KiteStatusResponse } from '@/types/api'

const DISABLED_STATUS: KiteStatusResponse = {
  enabled: false,
  read_only: true,
  authenticated: false,
  connected: false,
  message: 'Kite Connect is not enabled.',
  excluded_tools: [],
  available_read_tools: [],
}

export function useKiteStatus() {
  const [status, setStatus] = useState<KiteStatusResponse | null>(null)
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
        const data = await fetchKiteStatusCached(refreshKey > 0)
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

  const kiteLive = Boolean(status?.enabled && status.authenticated && status.connected)

  return { status, loading, kiteLive, refetch }
}
