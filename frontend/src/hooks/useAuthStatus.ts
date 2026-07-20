import { useCallback, useEffect, useState } from 'react'
import { fetchAuthStatusCached } from '@/lib/statusCache'
import type { AuthStatusResponse } from '@/types/api'

const DISABLED_STATUS: AuthStatusResponse = {
  authenticated: false,
  owner_auth_configured: false,
  has_passkey: false,
}

export function useAuthStatus() {
  const [status, setStatus] = useState<AuthStatusResponse | null>(null)
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
        const data = await fetchAuthStatusCached(refreshKey > 0)
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

  const authenticated = Boolean(status?.authenticated)
  const gateConfigured = Boolean(status?.owner_auth_configured)

  return { status, loading, authenticated, gateConfigured, refetch }
}
