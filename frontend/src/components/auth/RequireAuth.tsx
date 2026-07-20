import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuthStatus } from '@/hooks/useAuthStatus'

// UX-only. Real enforcement is server-side (require_owner_session in
// backend/app/api/dependencies.py) — this just avoids a flash of protected
// content / wasted API calls before the SPA even has a session.
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation()
  const { authenticated, gateConfigured, loading } = useAuthStatus()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (gateConfigured && !authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
