import type { ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { BarChart3, Briefcase, History, LogOut, Search, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStatus } from '@/hooks/useAuthStatus'
import { logout } from '@/lib/api'
import { invalidateAuthStatusCache } from '@/lib/statusCache'
import { Button } from '@/components/ui/button'

export function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { status, gateConfigured } = useAuthStatus()

  async function handleLogout() {
    try {
      await logout()
    } finally {
      invalidateAuthStatusCache()
      navigate('/login', { replace: true })
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,_oklch(0.22_0.04_155/_0.35),_transparent_50%)]" />
      <header className="sticky top-0 z-50 border-b border-border/60 bg-card/40 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5 font-semibold text-foreground">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary/15">
              <BarChart3 className="size-4 text-primary" />
            </span>
            InvestIQ
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                )
              }
            >
              <Search className="size-4" />
              Research
            </NavLink>
            <NavLink
              to="/portfolio"
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                )
              }
            >
              <Briefcase className="size-4" />
              Portfolio
            </NavLink>
            <NavLink
              to="/reports"
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                )
              }
            >
              <History className="size-4" />
              History
            </NavLink>
          </nav>
          {gateConfigured && (
            <div className="flex items-center gap-2">
              {status?.picture_url ? (
                <img
                  src={status.picture_url}
                  alt={status.display_name || status.email || 'Account'}
                  className="size-8 rounded-full"
                />
              ) : (
                <span className="flex size-8 items-center justify-center rounded-full bg-muted">
                  <User className="size-4 text-muted-foreground" />
                </span>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="gap-2"
                onClick={() => void handleLogout()}
              >
                <LogOut className="size-4" />
                Log out
              </Button>
            </div>
          )}
        </div>
      </header>
      <main className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  )
}
