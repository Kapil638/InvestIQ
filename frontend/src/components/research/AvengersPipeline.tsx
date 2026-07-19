import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronRight,
  Globe,
  Hourglass,
  Shield,
  XCircle,
} from 'lucide-react'
import {
  AGENT_STAGE_SEQUENCE,
  deriveAgentStageStatuses,
  deriveAgentStageStatusesFromTrace,
  type AgentStageId,
  type AgentStageStatus,
} from '@/components/research/AgentProgress'
import { AGENT_COLORS, AVENGERS } from '@/components/research/avengersTheme'
import { MissionStatusPanel } from '@/components/research/MissionStatusPanel'
import { cn } from '@/lib/utils'

interface AvengersPipelineProps {
  companyName: string
  ticker: string
  activeStageIndex: number
  loading?: boolean
  failed?: boolean
  complete?: boolean
  fullscreen?: boolean
  reportRevealed?: boolean
  pipelineTrace?: Array<{ stage: string; status: string }>
  onShowReport?: () => void
  className?: string
}

interface PipelineAgent {
  id: AgentStageId
  title: string
  description: string
  colors: (typeof AGENT_COLORS)[keyof typeof AGENT_COLORS]
  icon: ReactNode
}

const PIPELINE_AGENTS: PipelineAgent[] = [
  {
    id: 'financial',
    title: 'Financial Agent',
    description: 'Reading fundamentals and price data',
    colors: AGENT_COLORS.financial,
    icon: <BarChart3 className="size-5" strokeWidth={2} />,
  },
  {
    id: 'news',
    title: 'News Agent',
    description: 'Scanning latest news and market sentiment',
    colors: AGENT_COLORS.news,
    icon: <Globe className="size-5" strokeWidth={2} />,
  },
  {
    id: 'analysis',
    title: 'Analysis Agent',
    description: 'Building investment thesis and projections',
    colors: AGENT_COLORS.analysis,
    icon: <Brain className="size-5" strokeWidth={2} />,
  },
  {
    id: 'risk',
    title: 'Risk Agent',
    description: 'Extracting structured risks from analysis',
    colors: AGENT_COLORS.risk,
    icon: <Shield className="size-5" strokeWidth={2} />,
  },
  {
    id: 'guardrails',
    title: 'Guardrails',
    description: 'Validating completeness and hallucination risks',
    colors: AGENT_COLORS.analysis,
    icon: <Shield className="size-5" strokeWidth={2} />,
  },
  {
    id: 'recommendation',
    title: 'Recommendation Agent',
    description: 'Crafting final recommendation',
    colors: AGENT_COLORS.recommendation,
    icon: <IronHelmetIcon className="size-5" />,
  },
]

function IronHelmetIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M12 2C8.5 2 6 4.2 5 7.2V9c0 3.3 2.4 6 5.5 6.4V20h3v-4.6c3.1-.4 5.5-3.1 5.5-6.4V7.2C18 4.2 15.5 2 12 2zm0 2c2.2 0 3.8 1.4 4.3 3.2H7.7C8.2 5.4 9.8 4 12 4zM7 9.2c.5 2.2 2.6 3.8 5 3.8s4.5-1.6 5-3.8V8H7v1.2z" />
    </svg>
  )
}

function formatTime(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60)
  const secs = totalSeconds % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function StatusBadge({ status, dense }: { status: AgentStageStatus; dense?: boolean }) {
  const styles: Record<AgentStageStatus, React.CSSProperties> = {
    waiting: { background: 'rgba(255,255,255,0.05)', color: AVENGERS.textSecondary, border: `1px solid ${AVENGERS.cardBorder}` },
    running: { background: 'rgba(168, 85, 247, 0.2)', color: '#E9D5FF', border: `1px solid ${AVENGERS.purple}` },
    completed: { background: 'rgba(34, 197, 94, 0.15)', color: AVENGERS.green, border: `1px solid ${AVENGERS.green}` },
    failed: { background: 'rgba(239, 68, 68, 0.15)', color: AVENGERS.red, border: `1px solid ${AVENGERS.red}` },
  }
  const labels: Record<AgentStageStatus, string> = {
    waiting: 'WAITING',
    running: 'RUNNING',
    completed: 'COMPLETED',
    failed: 'FAILED',
  }
  return (
    <span
      className={cn(
        'shrink-0 rounded font-bold tracking-widest',
        dense ? 'px-1.5 py-px text-[8px]' : 'px-2 py-0.5 text-[10px]',
        status === 'running' && 'avengers-badge-pulse',
      )}
      style={styles[status]}
    >
      {labels[status]}
    </span>
  )
}

function RunningRadar({ accent, dense }: { accent: string; dense?: boolean }) {
  const size = dense ? 'size-8' : 'size-12'
  return (
    <div className={cn('avengers-radar-rotate relative shrink-0', size)}>
      <div className="absolute inset-0 rounded-full border" style={{ borderColor: `${accent}66` }} />
      <div className="absolute inset-1.5 rounded-full border opacity-50" style={{ borderColor: `${accent}44` }} />
      <div className="avengers-radar-sweep absolute inset-0 rounded-full" />
      <div
        className="absolute inset-[30%] rounded-full"
        style={{ background: accent, boxShadow: `0 0 14px ${accent}` }}
      />
    </div>
  )
}

function AgentPipelineCard({
  agent,
  index,
  status,
  elapsed,
  dense,
}: {
  agent: PipelineAgent
  index: number
  status: AgentStageStatus
  elapsed: number
  dense?: boolean
}) {
  const isRunning = status === 'running'
  const isCompleted = status === 'completed'
  const isFailed = status === 'failed'
  const isWaiting = status === 'waiting'
  const c = agent.colors

  return (
    <li className={cn('relative flex gap-2', dense && 'min-h-0')}>
      <div className={cn('relative z-10 flex w-3 shrink-0 flex-col items-center', dense ? 'pt-4' : 'pt-6')}>
        <div
          className={cn('flex size-3 items-center justify-center rounded-full border-2', isRunning && 'avengers-node-pulse')}
          style={{
            background: AVENGERS.bg,
            borderColor: isCompleted ? AVENGERS.green : isRunning ? AVENGERS.purple : isFailed ? AVENGERS.red : 'rgba(255,255,255,0.15)',
            boxShadow: isRunning ? `0 0 8px ${AVENGERS.purple}` : isCompleted ? `0 0 6px ${AVENGERS.green}` : 'none',
          }}
        >
          {isCompleted && <span className="size-1.5 rounded-full" style={{ background: AVENGERS.green }} />}
          {isRunning && <span className="size-1.5 rounded-full" style={{ background: AVENGERS.purple }} />}
        </div>
      </div>

      <article
        className={cn(
          'min-w-0 flex-1 overflow-hidden backdrop-blur-md transition-all duration-500',
          isRunning && 'avengers-card-running',
          dense && 'flex h-full min-h-0 flex-col justify-center',
        )}
        style={{
          background: AVENGERS.cardBg,
          border: `1px solid ${isRunning ? AVENGERS.purple : AVENGERS.cardBorder}`,
          borderLeft: `3px solid ${c.accent}`,
          borderRadius: dense ? '10px' : '12px',
          boxShadow: isRunning ? c.glow : isCompleted ? `inset 0 0 20px rgba(34,197,94,0.05)` : 'none',
          opacity: isWaiting ? 0.5 : 1,
          padding: dense ? (isRunning ? '8px 10px' : '7px 10px') : isRunning ? '14px 16px' : '11px 14px',
        }}
      >
        <div className="flex items-start justify-between gap-1.5">
          <div className="flex min-w-0 items-start gap-2">
            <div
              className={cn(
                'avengers-hex flex shrink-0 items-center justify-center',
                dense ? 'size-7' : 'size-9',
              )}
              style={{ background: c.bg, borderColor: c.border, color: c.accent, boxShadow: isRunning ? c.glow : 'none' }}
            >
              {dense ? (
                <span className="scale-90">{agent.icon}</span>
              ) : (
                agent.icon
              )}
            </div>
            <div className="min-w-0">
              <h4
                className={cn('font-semibold leading-tight', dense ? 'text-[11px]' : 'text-sm')}
                style={{ color: AVENGERS.textPrimary }}
              >
                {agent.title}
              </h4>
              <p
                className={cn('leading-snug', dense ? 'mt-0 text-[9px] line-clamp-1' : 'mt-0.5 text-xs')}
                style={{ color: AVENGERS.textSecondary }}
              >
                {agent.description}
              </p>
            </div>
          </div>
          <StatusBadge status={status} dense={dense} />
        </div>

        <div className={cn('flex items-center gap-2', dense ? 'mt-1.5' : 'mt-2', isRunning && !dense && 'mt-3')}>
          {isRunning ? (
            <>
              <div className="h-1 min-w-0 flex-1 overflow-hidden rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                <div
                  className="avengers-progress-fill h-full rounded-full"
                  style={{ background: `linear-gradient(90deg, ${AVENGERS.purple}, #C084FC)` }}
                />
              </div>
              <div className="flex shrink-0 flex-col items-center gap-0.5">
                <RunningRadar accent={AVENGERS.purple} dense={dense} />
                <span className="font-mono text-[9px]" style={{ color: '#E9D5FF' }}>
                  {formatTime(elapsed)}
                </span>
              </div>
            </>
          ) : (
            <div className="ml-auto flex items-center gap-1.5">
              {isCompleted && (
                <>
                  <CheckCircle2 className={dense ? 'size-3' : 'size-4'} style={{ color: AVENGERS.green }} />
                  <span className={cn('font-mono', dense ? 'text-[10px]' : 'text-xs')} style={{ color: AVENGERS.green }}>
                    {formatTime(Math.max(12, 18 + index * 14))}
                  </span>
                </>
              )}
              {isFailed && (
                <>
                  <XCircle className={dense ? 'size-3' : 'size-4'} style={{ color: AVENGERS.red }} />
                  <span className={dense ? 'text-[10px]' : 'text-xs'} style={{ color: AVENGERS.red }}>
                    Interrupted
                  </span>
                </>
              )}
              {isWaiting && (
                <Hourglass className={dense ? 'size-3' : 'size-4'} style={{ color: AVENGERS.textSecondary }} />
              )}
            </div>
          )}
        </div>
      </article>
    </li>
  )
}

export function AvengersPipeline({
  companyName: _companyName,
  ticker,
  activeStageIndex,
  loading = true,
  failed = false,
  complete = false,
  fullscreen = false,
  reportRevealed = false,
  pipelineTrace,
  onShowReport,
  className,
}: AvengersPipelineProps) {
  const [elapsed, setElapsed] = useState(0)
  const derivedStatuses = pipelineTrace?.length
    ? deriveAgentStageStatusesFromTrace(pipelineTrace)
    : deriveAgentStageStatuses(activeStageIndex, { loading, failed, complete })
  const statuses = derivedStatuses

  useEffect(() => {
    if (!loading) return
    setElapsed(0)
    const started = Date.now()
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [loading])

  const agentsActive = useMemo(() => {
    if (complete) return PIPELINE_AGENTS.length
    const completed = PIPELINE_AGENTS.filter((a) => statuses[a.id] === 'completed').length
    const running = PIPELINE_AGENTS.some((a) => statuses[a.id] === 'running') ? 1 : 0
    return completed + running
  }, [statuses, complete])

  const dataPoints = useMemo(() => {
    if (complete) return 14872
    const base = 12400 + activeStageIndex * 2100
    return base + (elapsed % 9) * 137
  }, [activeStageIndex, elapsed, complete])

  const estRemaining = complete ? 0 : Math.max(0, 118 - elapsed)
  const progressPercent = complete ? 100 : Math.min(100, ((activeStageIndex + 1) / AGENT_STAGE_SEQUENCE.length) * 100)

  const showReportFooter = complete && onShowReport && !reportRevealed

  return (
    <div
      className={cn(
        'avengers-pipeline relative',
        fullscreen ? 'flex h-full min-h-0 flex-col overflow-hidden' : 'overflow-hidden',
        className,
      )}
      style={{
        background: AVENGERS.bg,
        borderRadius: fullscreen ? 0 : AVENGERS.radius,
        border: fullscreen ? 'none' : `1px solid ${AVENGERS.cardBorder}`,
        padding: fullscreen ? (showReportFooter ? '6px 10px 0' : '6px 10px') : '20px 24px',
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 avengers-particle-flow-bg"
        style={{
          background: `radial-gradient(ellipse at 20% 0%, rgba(168,85,247,0.08) 0%, transparent 50%), radial-gradient(ellipse at 90% 50%, rgba(59,130,246,0.05) 0%, transparent 40%)`,
        }}
      />

      <div
        className={cn(
          'relative grid min-h-0 flex-1 overflow-hidden',
          fullscreen
            ? 'h-full grid-cols-1 items-stretch gap-2 lg:grid-cols-2 lg:gap-3'
            : 'grid-cols-1 gap-5 lg:grid-cols-2',
        )}
      >
        <div className="flex min-h-0 flex-col overflow-hidden">
          <div className={cn('shrink-0', fullscreen ? 'mb-1' : 'mb-2')}>
            <p className="text-[10px] font-bold uppercase tracking-[0.28em]" style={{ color: AVENGERS.textSecondary }}>
              Agent Pipeline
            </p>
            <p className={cn('leading-snug', fullscreen ? 'text-[10px]' : 'mt-0.5 text-xs')} style={{ color: AVENGERS.textSecondary }}>
              {complete
                ? 'All agents have completed their analysis.'
                : 'AI squad is analyzing and gathering intelligence…'}
            </p>
          </div>

          <ol
            className={cn(
              'relative min-h-0 flex-1',
              fullscreen
                ? 'grid grid-rows-6 gap-1 overflow-hidden'
                : 'avengers-agent-list space-y-1.5 overflow-y-auto overscroll-contain pr-1',
            )}
          >
            <div
              className="absolute bottom-2 left-[0.45rem] top-2 w-px"
              style={{
                background: `linear-gradient(180deg, ${AVENGERS.green}88 0%, ${AVENGERS.purple}55 40%, rgba(255,255,255,0.08) 100%)`,
              }}
            />
            {PIPELINE_AGENTS.map((agent, index) => (
              <AgentPipelineCard
                key={agent.id}
                agent={agent}
                index={index}
                status={statuses[agent.id]}
                elapsed={elapsed}
                dense={fullscreen}
              />
            ))}
          </ol>
        </div>

        <MissionStatusPanel
          className="h-full min-h-0 w-full"
          companyName={_companyName}
          ticker={ticker}
          statuses={statuses}
          agentsActive={agentsActive}
          totalAgents={PIPELINE_AGENTS.length}
          dataPoints={dataPoints}
          estRemaining={estRemaining}
          progressPercent={progressPercent}
          complete={complete}
          compact={fullscreen}
        />
      </div>

      {showReportFooter && (
        <div
          className="relative z-20 mt-auto shrink-0 border-t px-4 py-3 sm:px-6"
          style={{
            borderColor: AVENGERS.cardBorder,
            background: 'linear-gradient(180deg, rgba(16, 20, 36, 0.85) 0%, rgba(11, 15, 26, 0.95) 100%)',
          }}
        >
          <button
            type="button"
            onClick={onShowReport}
            className="avengers-show-report-btn group mx-auto flex w-full max-w-lg items-center justify-center gap-2 rounded-xl px-6 py-3 text-sm font-bold uppercase tracking-[0.2em] transition-transform hover:scale-[1.02] active:scale-[0.98]"
            style={{
              background: `linear-gradient(90deg, ${AVENGERS.purple} 0%, #818CF8 50%, ${AVENGERS.blue} 100%)`,
              color: '#fff',
              boxShadow: '0 0 32px rgba(168, 85, 247, 0.45)',
            }}
          >
            Show Report
            <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      )}
    </div>
  )
}
