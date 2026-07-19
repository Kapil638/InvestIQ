import type { ReactNode } from 'react'
import type { PortfolioAnalyzeResponse } from '@/types/api'
import { cn } from '@/lib/utils'

interface PortfolioAnalysisProps {
  analysis: PortfolioAnalyzeResponse
  className?: string
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="glass-card rounded-2xl p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">{title}</h3>
      {children}
    </section>
  )
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">Not available in this analysis.</p>
  }
  return (
    <ul className="space-y-2 text-sm text-muted-foreground">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export function PortfolioAnalysis({ analysis, className }: PortfolioAnalysisProps) {
  return (
    <div className={cn('space-y-4', className)}>
      <Section title="Portfolio Summary">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
          {analysis.summary}
        </p>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Concentration Risk">
          <p className="text-sm leading-relaxed text-muted-foreground">{analysis.concentration_risk}</p>
        </Section>
        <Section title="3-Year View">
          <p className="text-sm leading-relaxed text-muted-foreground">{analysis.three_year_view}</p>
        </Section>
        <Section title="Strong Holdings">
          <BulletList items={analysis.strong_holdings} />
        </Section>
        <Section title="Weak Holdings">
          <BulletList items={analysis.weak_holdings} />
        </Section>
        <Section title="Sector Exposure">
          {analysis.sector_exposure.length === 0 ? (
            <p className="text-sm text-muted-foreground">Not available in this analysis.</p>
          ) : (
            <ul className="space-y-2 text-sm text-muted-foreground">
              {analysis.sector_exposure.map((item) => (
                <li key={item.sector}>
                  <span className="font-medium text-foreground">{item.sector}</span>
                  {' — '}
                  {item.allocation_percent.toFixed(1)}%
                  {item.holdings.length > 0 && (
                    <span className="text-xs"> ({item.holdings.join(', ')})</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Rebalancing Suggestions">
          <BulletList items={analysis.rebalance_suggestions} />
        </Section>
      </div>

      <Section title="Watchlist Actions">
        <BulletList items={analysis.watchlist_actions} />
      </Section>
    </div>
  )
}
