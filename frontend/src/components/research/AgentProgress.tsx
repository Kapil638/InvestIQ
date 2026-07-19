import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentStageId =
  | 'financial'
  | 'news'
  | 'analysis'
  | 'risk'
  | 'recommendation'
  | 'guardrails'

export type AgentStageStatus = 'waiting' | 'running' | 'completed' | 'failed'

export interface AgentStageDefinition {
  id: AgentStageId
  title: string
  description: string
  icon: string
}

export const RESEARCH_AGENT_STAGES: AgentStageDefinition[] = [
  {
    id: 'financial',
    title: 'Financial Agent',
    description: 'Reading fundamentals and price data',
    icon: '📊',
  },
  {
    id: 'news',
    title: 'News Agent',
    description: 'Reading latest news',
    icon: '📰',
  },
  {
    id: 'analysis',
    title: 'Analysis Agent',
    description: 'Building investment thesis',
    icon: '🧠',
  },
  {
    id: 'risk',
    title: 'Risk Agent',
    description: 'Extracting structured risks from analysis',
    icon: '⚠️',
  },
  {
    id: 'guardrails',
    title: 'Guardrails',
    description: 'Validating completeness and hallucination risks',
    icon: '🛡️',
  },
  {
    id: 'recommendation',
    title: 'Recommendation Agent',
    description: 'Preparing final view',
    icon: '🎯',
  },
]

export const AGENT_STAGE_SEQUENCE: AgentStageId[] = RESEARCH_AGENT_STAGES.map((s) => s.id)

export function deriveAgentStageStatusesFromTrace(
  trace: Array<{ stage: string; status: string }>,
): Record<AgentStageId, AgentStageStatus> {
  const statuses = {} as Record<AgentStageId, AgentStageStatus>
  const traceMap = new Map(trace.map((entry) => [entry.stage, entry.status]))

  for (const stage of RESEARCH_AGENT_STAGES) {
    const raw = traceMap.get(stage.id)
    if (!raw) {
      statuses[stage.id] = 'waiting'
      continue
    }
    if (raw === 'completed') statuses[stage.id] = 'completed'
    else if (raw === 'failed') statuses[stage.id] = 'failed'
    else if (raw === 'skipped') statuses[stage.id] = 'completed'
    else if (raw === 'running') statuses[stage.id] = 'running'
    else statuses[stage.id] = 'waiting'
  }

  const committeeStatus = traceMap.get('committee')
  if (committeeStatus === 'completed') {
    for (const stage of RESEARCH_AGENT_STAGES) {
      if (statuses[stage.id] !== 'failed') {
        statuses[stage.id] = 'completed'
      }
    }
  }

  return statuses
}

export function activeStageIndexFromTrace(
  trace: Array<{ stage: string; status: string }>,
): number {
  const order = AGENT_STAGE_SEQUENCE
  let lastCompleted = -1
  for (let i = 0; i < order.length; i++) {
    const entry = trace.find((t) => t.stage === order[i])
    if (entry?.status === 'completed' || entry?.status === 'skipped') {
      lastCompleted = i
    } else if (entry?.status === 'running') {
      return i
    }
  }
  return Math.max(0, lastCompleted + 1)
}

export function deriveAgentStageStatuses(
  activeIndex: number,
  options: { loading: boolean; failed: boolean; complete: boolean },
): Record<AgentStageId, AgentStageStatus> {
  const statuses = {} as Record<AgentStageId, AgentStageStatus>

  for (let i = 0; i < RESEARCH_AGENT_STAGES.length; i++) {
    const id = RESEARCH_AGENT_STAGES[i].id
    if (options.complete) {
      statuses[id] = 'completed'
    } else if (options.failed && i === activeIndex) {
      statuses[id] = 'failed'
    } else if (i < activeIndex) {
      statuses[id] = 'completed'
    } else if (options.loading && i === activeIndex) {
      statuses[id] = 'running'
    } else {
      statuses[id] = 'waiting'
    }
  }

  return statuses
}

interface AgentProgressProps {
  activeStageIndex: number
  loading?: boolean
  failed?: boolean
  complete?: boolean
  stageStatuses?: Partial<Record<AgentStageId, AgentStageStatus>>
  className?: string
}

const statusLabel: Record<AgentStageStatus, string> = {
  waiting: 'Waiting',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
}

const statusStyle: Record<AgentStageStatus, string> = {
  waiting: 'bg-muted/60 text-muted-foreground',
  running: 'bg-primary/15 text-primary ring-1 ring-primary/30',
  completed: 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/20',
  failed: 'bg-destructive/15 text-red-300 ring-1 ring-destructive/30',
}

function StatusIcon({ status }: { status: AgentStageStatus }) {
  if (status === 'completed') return <CheckCircle2 className="size-5 text-emerald-400" />
  if (status === 'running') return <Loader2 className="size-5 animate-spin text-primary" />
  if (status === 'failed') return <XCircle className="size-5 text-red-400" />
  return <Circle className="size-5 text-muted-foreground/50" />
}

export function AgentProgress({
  activeStageIndex,
  loading = false,
  failed = false,
  complete = false,
  stageStatuses,
  className,
}: AgentProgressProps) {
  const derived = deriveAgentStageStatuses(activeStageIndex, { loading, failed, complete })

  return (
    <div className={cn('glass-card rounded-2xl p-5', className)}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold text-foreground">Agent pipeline</h3>
        <span className="text-xs text-muted-foreground">Typically 1–3 minutes</span>
      </div>
      <ul className="space-y-3">
        {RESEARCH_AGENT_STAGES.map((stage) => {
          const status = stageStatuses?.[stage.id] ?? derived[stage.id]
          return (
            <li
              key={stage.id}
              className={cn(
                'flex items-start gap-3 rounded-xl px-3 py-3 transition-colors',
                status === 'running' && 'bg-primary/10',
                status === 'failed' && 'bg-destructive/10',
              )}
            >
              <StatusIcon status={status} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-lg leading-none">{stage.icon}</span>
                  <p className="font-medium text-foreground">{stage.title}</p>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                      statusStyle[status],
                      status === 'running' && 'animate-pulse',
                    )}
                  >
                    {statusLabel[status]}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{stage.description}</p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function useSimulatedAgentProgress(loading: boolean, _failed: boolean, _complete: boolean) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    if (!loading) {
      setActiveIndex(0)
      return
    }

    let index = 0
    setActiveIndex(0)
    const interval = window.setInterval(() => {
      index = Math.min(index + 1, AGENT_STAGE_SEQUENCE.length - 1)
      setActiveIndex(index)
    }, 22000)

    return () => window.clearInterval(interval)
  }, [loading])

  return activeIndex
}
