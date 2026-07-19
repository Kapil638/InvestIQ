import { cn } from '@/lib/utils'

export type AgentId = 'financial' | 'news' | 'analysis' | 'recommendation'
export type AgentStatus = 'waiting' | 'running' | 'completed'

export interface AgentStep {
  id: AgentId
  title: string
  description: string
  icon: string
}

export const AGENT_STEPS: AgentStep[] = [
  {
    id: 'financial',
    title: 'Financial Agent',
    description: 'Pulls NSE/BSE fundamentals, ratios, and market data.',
    icon: '📊',
  },
  {
    id: 'news',
    title: 'News Agent',
    description: 'Scans latest headlines, sentiment, and macro context.',
    icon: '📰',
  },
  {
    id: 'analysis',
    title: 'Analysis Agent',
    description: 'Builds an institutional-style investment thesis.',
    icon: '🧠',
  },
  {
    id: 'recommendation',
    title: 'Recommendation Agent',
    description: 'Issues Buy / Hold / Avoid with confidence scoring.',
    icon: '🎯',
  },
]

interface AgentPipelineProps {
  agentStatus: Record<AgentId, AgentStatus>
}

const statusLabel: Record<AgentStatus, string> = {
  waiting: 'Waiting',
  running: 'Running',
  completed: 'Completed',
}

const statusStyle: Record<AgentStatus, string> = {
  waiting: 'bg-muted/60 text-muted-foreground',
  running: 'bg-primary/15 text-primary ring-1 ring-primary/30',
  completed: 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/20',
}

export function AgentPipeline({ agentStatus }: AgentPipelineProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {AGENT_STEPS.map((agent) => {
        const status = agentStatus[agent.id]
        return (
          <div
            key={agent.id}
            className={cn(
              'glass-card group rounded-2xl p-5 transition-all duration-300 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5',
              status === 'running' && 'border-primary/40 shadow-lg shadow-primary/10',
            )}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-background/60 text-xl">
                {agent.icon}
              </span>
              <span
                className={cn(
                  'rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider',
                  statusStyle[status],
                  status === 'running' && 'animate-pulse',
                )}
              >
                {statusLabel[status]}
              </span>
            </div>
            <h3 className="font-semibold text-foreground">{agent.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{agent.description}</p>
          </div>
        )
      })}
    </div>
  )
}
