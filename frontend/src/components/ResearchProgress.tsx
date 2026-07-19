import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export type ResearchProgressStep =
  | 'collecting_financials'
  | 'reading_news'
  | 'building_thesis'
  | 'running_guardrails'
  | 'preparing_recommendation'

export const PROGRESS_STEPS: { id: ResearchProgressStep; label: string }[] = [
  { id: 'collecting_financials', label: 'Collecting financial data' },
  { id: 'reading_news', label: 'Reading latest news' },
  { id: 'building_thesis', label: 'Building analyst thesis' },
  { id: 'running_guardrails', label: 'Running guardrails' },
  { id: 'preparing_recommendation', label: 'Preparing final recommendation' },
]

interface ResearchProgressProps {
  activeStep: ResearchProgressStep
  isComplete?: boolean
}

function stepIndex(step: ResearchProgressStep): number {
  return PROGRESS_STEPS.findIndex((s) => s.id === step)
}

export function ResearchProgress({ activeStep, isComplete }: ResearchProgressProps) {
  const activeIdx = stepIndex(activeStep)

  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold text-foreground">Live pipeline progress</h3>
        <span className="text-xs text-muted-foreground">Typically 1–3 minutes</span>
      </div>
      <ul className="space-y-3">
        {PROGRESS_STEPS.map((step, idx) => {
          const done = isComplete || idx < activeIdx
          const running = !isComplete && idx === activeIdx

          return (
            <li
              key={step.id}
              className={cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors',
                running && 'bg-primary/10',
              )}
            >
              {done ? (
                <CheckCircle2 className="size-5 shrink-0 text-emerald-400" />
              ) : running ? (
                <Loader2 className="size-5 shrink-0 animate-spin text-primary" />
              ) : (
                <Circle className="size-5 shrink-0 text-muted-foreground/50" />
              )}
              <span
                className={cn(
                  'text-sm',
                  done && 'text-foreground',
                  running && 'font-medium text-primary',
                  !done && !running && 'text-muted-foreground',
                )}
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function deriveAgentStatus(
  activeStep: ResearchProgressStep,
  isComplete: boolean,
): Record<'financial' | 'news' | 'analysis' | 'recommendation', 'waiting' | 'running' | 'completed'> {
  if (isComplete) {
    return {
      financial: 'completed',
      news: 'completed',
      analysis: 'completed',
      recommendation: 'completed',
    }
  }

  const step = stepIndex(activeStep)

  return {
    financial: step > 0 ? 'completed' : 'running',
    news: step > 1 ? 'completed' : step === 1 ? 'running' : 'waiting',
    analysis: step > 3 ? 'completed' : step >= 2 ? 'running' : 'waiting',
    recommendation: step >= 4 ? 'running' : 'waiting',
  }
}
