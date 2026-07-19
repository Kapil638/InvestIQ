import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const ASK_STEPS = [
  { id: 'context', label: 'Reading report context', accent: 'text-violet-300' },
  { id: 'metrics', label: 'Checking financial metrics', accent: 'text-sky-300' },
  { id: 'answer', label: 'Preparing answer', accent: 'text-emerald-300' },
] as const

type StepStatus = 'waiting' | 'running' | 'completed'

interface AskAnalyzingStateProps {
  question?: string
  className?: string
}

export function AskAnalyzingState({ question, className }: AskAnalyzingStateProps) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    setActiveIndex(0)
    const interval = window.setInterval(() => {
      setActiveIndex((prev) => Math.min(prev + 1, ASK_STEPS.length - 1))
    }, 2400)
    return () => window.clearInterval(interval)
  }, [question])

  function stepStatus(index: number): StepStatus {
    if (index < activeIndex) return 'completed'
    if (index === activeIndex) return 'running'
    return 'waiting'
  }

  return (
    <div
      className={cn(
        'avengers-pipeline relative overflow-hidden rounded-2xl border border-violet-500/30 bg-[#070b14]/90 p-5',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(124,58,237,0.14),transparent_50%)]" />

      <div className="relative flex items-center gap-4">
        <div className="relative flex size-14 shrink-0 items-center justify-center">
          <div className="avengers-reactor-core absolute inset-2 rounded-full" />
          <Loader2 className="relative size-6 animate-spin text-violet-300" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="avengers-title-glow text-sm font-bold uppercase tracking-[0.2em] text-violet-100">
            Quick Intel Scan
          </p>
          <p className="mt-1 text-sm text-slate-300">InvestIQ agents are analyzing your question…</p>
          {question && (
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">{question}</p>
          )}
        </div>
      </div>

      <ul className="relative mt-5 space-y-2">
        {ASK_STEPS.map((step, index) => {
          const status = stepStatus(index)
          return (
            <li
              key={step.id}
              className={cn(
                'flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-all duration-300',
                status === 'running' && 'border-violet-400/40 bg-violet-500/10 avengers-card-running',
                status === 'completed' && 'border-emerald-400/20 bg-emerald-500/5',
                status === 'waiting' && 'border-white/5 bg-black/20 opacity-60',
              )}
            >
              {status === 'completed' ? (
                <CheckCircle2 className="size-4 shrink-0 text-emerald-400" />
              ) : status === 'running' ? (
                <Loader2 className="size-4 shrink-0 animate-spin text-violet-300" />
              ) : (
                <Circle className="size-4 shrink-0 text-slate-600" />
              )}
              <span
                className={cn(
                  status === 'running' && cn('font-medium', step.accent),
                  status === 'completed' && 'text-emerald-200/80',
                  status === 'waiting' && 'text-slate-500',
                )}
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ul>

      <div className="relative mt-4 h-1.5 overflow-hidden rounded-full bg-white/5">
        <div
          className="avengers-progress-bar h-full rounded-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-violet-600 transition-all duration-500"
          style={{ width: `${((activeIndex + 1) / ASK_STEPS.length) * 100}%` }}
        />
      </div>
    </div>
  )
}
