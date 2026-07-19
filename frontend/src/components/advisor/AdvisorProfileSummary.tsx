import type { InvestorProfile, ProfileFieldDisplay } from '@/types/api'
import { cn } from '@/lib/utils'

interface AdvisorProfileSummaryProps {
  intent: string
  profileFields: ProfileFieldDisplay[]
  assumptionsUsed?: string[]
  missingInputs?: string[]
  profile?: InvestorProfile
  className?: string
}

const INTENT_LABELS: Record<string, string> = {
  MARKET_RECOMMENDATION: 'Market recommendation',
  THEME_DISCOVERY: 'Theme discovery',
  PERSONALIZED_PORTFOLIO: 'Personalized portfolio',
  COMPANY_RESEARCH: 'Company research',
  FOLLOW_UP: 'Follow-up',
  UNKNOWN: 'General research',
}

export function AdvisorProfileSummary({
  intent,
  profileFields,
  assumptionsUsed = [],
  missingInputs = [],
  className,
}: AdvisorProfileSummaryProps) {
  const intentLabel = INTENT_LABELS[intent] ?? intent

  return (
    <section className={cn('glass-card rounded-2xl border border-border/60 p-5 sm:p-6', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-primary">Advisor context</h3>
        <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-3 py-1 text-xs text-violet-200">
          {intentLabel}
        </span>
      </div>

      <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {profileFields.map((field) => (
          <div key={field.label}>
            <dt className="text-xs text-muted-foreground">{field.label}</dt>
            <dd className="mt-1 text-sm font-medium">
              {field.value ?? (
                <span className="text-muted-foreground/70">Not provided</span>
              )}
            </dd>
            <p className="mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground/60">
              {field.source === 'user'
                ? 'You provided'
                : field.source === 'assumed'
                  ? 'Assumption'
                  : 'Missing'}
            </p>
          </div>
        ))}
      </dl>

      {assumptionsUsed.length > 0 && (
        <div className="mt-5 rounded-xl border border-border/50 bg-background/30 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Assumptions used
          </p>
          <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
            {assumptionsUsed.map((item) => (
              <li key={item}>— {item}</li>
            ))}
          </ul>
        </div>
      )}

      {missingInputs.length > 0 && (
        <div className="mt-4">
          <p className="text-xs text-muted-foreground">Optional improvements</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {missingInputs.map((item) => (
              <span
                key={item}
                className="rounded-full border border-border/60 px-2.5 py-1 text-xs text-muted-foreground"
              >
                Add {item.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
