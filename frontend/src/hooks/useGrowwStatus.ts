import { useCallback, useEffect, useState } from 'react'
import { fetchGrowwStatusCached } from '@/lib/statusCache'
import type { GrowwStatusResponse } from '@/types/api'

const DISABLED_STATUS: GrowwStatusResponse = {
  enabled: false,
  read_only: true,
  credentials_configured: false,
  connected: false,
  message: 'Groww is not enabled.',
}

export function useGrowwStatus() {
  const [status, setStatus] = useState<GrowwStatusResponse | null>(null)
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
        const data = await fetchGrowwStatusCached(refreshKey > 0)
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

  const growwLive = Boolean(status?.enabled && status.connected)

  return { status, loading, growwLive, refetch }
}
