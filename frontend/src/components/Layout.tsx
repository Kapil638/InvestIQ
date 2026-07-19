import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { BarChart3, Briefcase, History, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Layout({ children }: { children: ReactNode }) {
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
        </div>
      </header>
      <main className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  )
}
