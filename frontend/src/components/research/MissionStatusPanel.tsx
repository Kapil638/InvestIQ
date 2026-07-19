import { Timer } from 'lucide-react'
import type { AgentStageId, AgentStageStatus } from '@/components/research/AgentProgress'
import { AVENGERS } from '@/components/research/avengersTheme'
import { NeuralNetworkField } from '@/components/research/NeuralNetworkField'
import { cn } from '@/lib/utils'

interface MissionStatusPanelProps {
  companyName: string
  ticker: string
  statuses: Record<AgentStageId, AgentStageStatus>
  agentsActive: number
  totalAgents?: number
  dataPoints: number
  estRemaining: number
  progressPercent: number
  complete?: boolean
  compact?: boolean
  className?: string
}

function formatTime(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60)
  const secs = totalSeconds % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function AvengersLogoHero({ compact }: { compact?: boolean }) {
  return (
    <div className={cn('relative', compact ? 'size-11 sm:size-12' : 'size-[4.5rem] sm:size-[5.5rem]')}>
      <div
        className="avengers-logo-halo absolute inset-0 rounded-full blur-2xl"
        style={{ background: 'rgba(168, 85, 247, 0.25)' }}
      />
      <svg viewBox="0 0 80 80" className="relative size-full" aria-hidden>
        <defs>
          <linearGradient id="avengers-a-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#C4B5FD" />
            <stop offset="45%" stopColor="#A855F7" />
            <stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
          <filter id="avengers-glow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <circle cx="40" cy="40" r="36" fill="none" stroke="url(#avengers-a-grad)" strokeWidth="1.2" opacity="0.4" />
        <circle cx="40" cy="40" r="28" fill="none" stroke="url(#avengers-a-grad)" strokeWidth="0.8" opacity="0.25" className="avengers-logo-ring" />
        <path
          d="M40 14 L54 62 H46 L40 44 L34 62 H26 Z"
          fill="url(#avengers-a-grad)"
          filter="url(#avengers-glow)"
          className="avengers-logo-pulse"
        />
      </svg>
    </div>
  )
}

function EkgWave() {
  return (
    <svg viewBox="0 0 60 16" className="avengers-ekg h-4 w-14" style={{ color: AVENGERS.green }} aria-hidden>
      <polyline
        points="0,8 10,8 14,2 18,14 22,8 30,8 34,1 38,15 42,8 60,8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function DataDotsGrid() {
  return (
    <div className="avengers-data-dots mx-auto grid grid-cols-5 gap-1">
      {Array.from({ length: 15 }).map((_, i) => (
        <span
          key={i}
          className="size-1 rounded-[1px]"
          style={{ backgroundColor: AVENGERS.purple, animationDelay: `${i * 0.09}s` }}
        />
      ))}
    </div>
  )
}

function NeuralStage({
  active = true,
  compact,
}: {
  active?: boolean
  compact?: boolean
}) {
  return (
    <div
      className={cn(
        'avengers-reactor-stage relative mx-auto h-full w-full min-h-0 overflow-hidden',
        compact ? 'max-h-[170px] min-h-[140px]' : 'max-h-[280px] min-h-[210px]',
      )}
    >
      <NeuralNetworkField active={active} className="z-[1]" />
    </div>
  )
}

export function MissionStatusPanel({
  companyName,
  ticker,
  statuses: _statuses,
  agentsActive,
  totalAgents = 5,
  dataPoints,
  estRemaining,
  progressPercent,
  complete = false,
  compact = false,
  className,
}: MissionStatusPanelProps) {
  return (
    <div
      className={cn(
        'avengers-mission-panel relative flex h-full min-h-0 flex-col overflow-hidden backdrop-blur-md',
        className,
      )}
      style={{
        background: AVENGERS.cardBg,
        border: `1px solid ${AVENGERS.cardBorder}`,
        borderRadius: AVENGERS.radius,
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 50% 25%, rgba(168, 85, 247, 0.1) 0%, transparent 55%), radial-gradient(ellipse at 50% 85%, rgba(59, 130, 246, 0.06) 0%, transparent 50%)',
        }}
      />
      <div className="avengers-scanlines pointer-events-none absolute inset-0 opacity-[0.06]" />

      <div
        className={cn(
          'relative z-10 flex shrink-0 flex-col items-center px-2 text-center',
          compact ? 'pb-0.5 pt-1.5' : 'px-4 pb-2 pt-5',
        )}
      >
        <AvengersLogoHero compact={compact} />
        <h3
          className={cn(
            'avengers-gradient-title font-black uppercase italic tracking-[0.18em]',
            compact ? 'mt-1 text-sm sm:text-base' : 'mt-4 text-lg sm:text-[1.35rem]',
          )}
        >
          {complete ? 'Intelligence Gathered' : 'Gathering Intelligence'}
        </h3>
        <p
          className={cn(
            'max-w-xs leading-snug',
            compact ? 'mt-0.5 text-[10px] line-clamp-2' : 'mt-2 text-xs',
          )}
          style={{ color: AVENGERS.textSecondary }}
        >
          {complete ? (
            <>
              Analysis complete for{' '}
              <span className="font-semibold" style={{ color: AVENGERS.textPrimary }}>
                {companyName || ticker}
              </span>
              . Your institutional report is ready.
            </>
          ) : (
            <>
              Our AI squad is working together to analyze{' '}
              <span className="font-semibold" style={{ color: AVENGERS.textPrimary }}>
                {companyName || ticker}
              </span>
            </>
          )}
        </p>
      </div>

      <div className="relative z-10 flex min-h-0 flex-1 items-center justify-center overflow-hidden px-1 py-0.5">
        <NeuralStage compact={compact} active={!complete} />
      </div>

      <div className="relative z-10 mt-auto shrink-0 px-2 pb-0.5">
        <div
          className={cn(
            'grid grid-cols-3 gap-0 rounded-lg px-1 backdrop-blur-sm',
            compact ? 'py-1.5' : 'py-3',
          )}
          style={{ background: 'rgba(0,0,0,0.35)', border: `1px solid ${AVENGERS.cardBorder}` }}
        >
          <div className="px-2 text-center">
            <p className="text-[9px] font-bold uppercase tracking-[0.14em]" style={{ color: AVENGERS.green }}>
              Agents Active
            </p>
            <p className={cn('mt-0.5 font-mono font-bold', compact ? 'text-base' : 'text-xl')} style={{ color: AVENGERS.textPrimary }}>
              {agentsActive}
              <span className={cn('font-normal', compact ? 'text-xs' : 'text-base')} style={{ color: AVENGERS.textSecondary }}>
                {' '}
                / {totalAgents}
              </span>
            </p>
            <div className={compact ? 'mt-1' : 'mt-2'}>
              <EkgWave />
            </div>
          </div>
          <div className="border-x px-2 text-center" style={{ borderColor: AVENGERS.cardBorder }}>
            <p className="text-[9px] font-bold uppercase tracking-[0.14em]" style={{ color: AVENGERS.purple }}>
              Data Points
            </p>
            <p className={cn('mt-0.5 font-mono font-bold', compact ? 'text-base' : 'text-xl')} style={{ color: AVENGERS.textPrimary }}>
              {dataPoints.toLocaleString()}+
            </p>
            <div className={compact ? 'mt-1' : 'mt-2.5'}>
              <DataDotsGrid />
            </div>
          </div>
          <div className="px-2 text-center">
            <p className="text-[9px] font-bold uppercase tracking-[0.14em]" style={{ color: AVENGERS.blue }}>
              Est. Time Left
            </p>
            <p className={cn('mt-0.5 font-mono font-bold', compact ? 'text-base' : 'text-xl')} style={{ color: AVENGERS.textPrimary }}>
              {formatTime(estRemaining)}
            </p>
            <div className={cn('flex justify-center', compact ? 'mt-1' : 'mt-2.5')} style={{ color: AVENGERS.blue }}>
              <Timer className={cn('avengers-timer-pulse', compact ? 'size-3.5' : 'size-5')} strokeWidth={2} />
            </div>
          </div>
        </div>
      </div>

      <div className={cn('relative z-10 shrink-0 px-2', compact ? 'pb-1.5 pt-0.5' : 'px-3 pb-4 pt-1')}>
        <div className={cn('overflow-hidden rounded-full', compact ? 'h-2.5' : 'h-4')} style={{ background: 'rgba(255,255,255,0.06)' }}>
          <div
            className="avengers-main-progress h-full rounded-full transition-all duration-700"
            style={{
              width: `${progressPercent}%`,
              background: `linear-gradient(90deg, ${AVENGERS.purple} 0%, #818CF8 50%, ${AVENGERS.blue} 100%)`,
              boxShadow: `0 0 20px rgba(168, 85, 247, 0.55)`,
            }}
          />
        </div>
        <p
          className={cn(
            'text-center font-bold uppercase tracking-[0.28em]',
            compact ? 'mt-1 text-[8px]' : 'mt-3 text-[10px]',
          )}
          style={{ color: complete ? AVENGERS.green : AVENGERS.purple }}
        >
          {complete ? 'Intelligence gathering complete' : 'Intelligence gathering in progress…'}
        </p>
      </div>
    </div>
  )
}
