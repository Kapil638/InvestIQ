import { ArrowUpRight, FileSearch } from 'lucide-react'
import type { IndianCompany } from '@/data/indianCompanies'
import { findCompanyByTicker } from '@/data/indianCompanies'
import type { StockRecommendation } from '@/types/api'
import { formatDataSourceLabel } from '@/lib/sourceLabels'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface AdvisorStockCardProps {
  recommendation: StockRecommendation
  onOpenOverview: (company: IndianCompany) => void
  onRunResearch: (company: IndianCompany) => void
  className?: string
}

export function AdvisorStockCard({
  recommendation: rec,
  onOpenOverview,
  onRunResearch,
  className,
}: AdvisorStockCardProps) {
  const company = toCompany(rec)
  const overall = rec.overall_match_score ?? rec.match_score

  return (
    <article
      className={cn(
        'glass-card rounded-2xl border border-border/60 p-5 transition hover:border-primary/30',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-sm font-bold text-primary">
            #{rec.rank}
          </div>
          <div>
            <h4 className="font-semibold tracking-tight">{rec.company_name}</h4>
            <p className="text-sm text-muted-foreground">
              {rec.symbol}
              {rec.sector ? ` · ${rec.sector}` : ''}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-violet-500/40 text-violet-200">
            Overall {overall}%
          </Badge>
          <Badge variant="outline" className="border-violet-500/30 text-violet-200/90">
            Theme {rec.theme_match_score ?? rec.match_score}%
          </Badge>
          <Badge className="bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/20">
            {rec.suggested_allocation_percent}% alloc.
          </Badge>
        </div>
      </div>

      {rec.matched_themes && rec.matched_themes.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {rec.matched_themes.map((theme) => (
            <Badge
              key={theme}
              variant="outline"
              className="border-violet-500/30 bg-violet-500/10 text-xs text-violet-200"
            >
              {theme}
            </Badge>
          ))}
        </div>
      )}

      {rec.theme_match_reason && rec.theme_match_reason !== 'Not available' && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Why it matches your prompt
          </p>
          <p className="mt-1.5 text-sm text-muted-foreground">{rec.theme_match_reason}</p>
        </div>
      )}

      {rec.why_it_fits.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Why it may fit
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
            {rec.why_it_fits.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-primary">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rec.key_evidence && rec.key_evidence.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-primary/80">
            Key evidence
          </p>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {rec.key_evidence.map((item) => (
              <li key={item}>— {item}</li>
            ))}
          </ul>
        </div>
      )}

      {rec.key_risks.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-400/80">Key risks</p>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {rec.key_risks.map((risk) => (
              <li key={risk}>— {risk}</li>
            ))}
          </ul>
        </div>
      )}

      {rec.data_sources.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {rec.data_sources.map((source) => (
            <Badge key={source} variant="outline" className="text-xs">
              {formatDataSourceLabel(source)}
            </Badge>
          ))}
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => onOpenOverview(company)}>
          <ArrowUpRight className="size-3.5" />
          Open Stock Overview
        </Button>
        <Button
          size="sm"
          className="bg-violet-600/80 text-white hover:bg-violet-500"
          onClick={() => onRunResearch(company)}
        >
          <FileSearch className="size-3.5" />
          Run Full AI Research
        </Button>
      </div>
    </article>
  )
}

function toCompany(rec: StockRecommendation): IndianCompany {
  const known = findCompanyByTicker(rec.symbol)
  if (known) return known
  return {
    name: rec.company_name,
    ticker: rec.symbol,
    exchange: 'NSE',
    sector: rec.sector,
  }
}
