import { useCallback, useEffect, useState } from 'react'
import { fetchGoogleDriveStatusCached } from '@/lib/statusCache'
import type { GoogleDriveStatusResponse } from '@/types/api'

const DISABLED_STATUS: GoogleDriveStatusResponse = {
  enabled: false,
  oauth_configured: false,
  authenticated: false,
  connected: false,
  message: 'Google Drive is not enabled.',
}

export function useGoogleDriveStatus() {
  const [status, setStatus] = useState<GoogleDriveStatusResponse | null>(null)
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
        const data = await fetchGoogleDriveStatusCached(refreshKey > 0)
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

  const driveConnected = Boolean(status?.enabled && status.connected)

  return { status, loading, driveConnected, refetch }
}
