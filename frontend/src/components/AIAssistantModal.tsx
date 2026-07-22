import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Bot, Check, Loader2, Send, Sparkles, X, Zap } from 'lucide-react'
import type { IndianCompany } from '@/data/indianCompanies'
import type { ResearchAskResponse, ResearchReportResponse } from '@/types/api'
import { AvengersPipeline } from '@/components/research/AvengersPipeline'
import { useSimulatedAgentProgress, AGENT_STAGE_SEQUENCE, activeStageIndexFromTrace } from '@/components/research/AgentProgress'
import { AskAnalyzingState } from '@/components/research/AskAnalyzingState'
import { ProfessionalReport } from '@/components/research/ProfessionalReport'
import { ReportChat } from '@/components/research/ReportChat'
import { SpotifyBackgroundPlayer } from '@/components/research/SpotifyBackgroundPlayer'
import { ResearchAnswerCard } from '@/components/ResearchAnswerCard'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const AI_PROMPTS = [
  { id: 'business-model', label: 'Explain the business model of this company' },
  { id: 'red-flags', label: 'What are the red flags in this company?' },
  { id: 'evolution', label: 'Evolution of the company over last 3 years' },
  { id: 'growth', label: 'Growth outlook for next 3 years' },
  { id: 'commentary', label: "What is management's recent commentary?" },
  { id: 'segments', label: 'Create a table of key products / business segments' },
  { id: 'performance', label: 'How is the stock expected to perform?' },
  { id: 'guidance', label: 'Management guidance vs delivery' },
  { id: 'full-report', label: 'Generate full institutional report', action: 'report' as const },
  { id: '3year', label: 'Is this stock suitable for a 3-year investment?' },
] as const

// Background music played while the report pipeline runs (~1 min), stops
// once the report is revealed. No visible player - see SpotifyBackgroundPlayer
// for why the controller is created on modal open but only .play()'d from
// inside the "Generate full report" click handler. Starts at 11s to skip
// the track's 10-second intro.
const PIPELINE_MUSIC_URI = 'spotify:track:6h6PlGTisMcE6G8GiS31fR'
const PIPELINE_MUSIC_START_SECONDS = 11

type AiPrompt = (typeof AI_PROMPTS)[number]

interface AIAssistantModalProps {
  open: boolean
  company: IndianCompany
  askLoading: boolean
  askError: string | null
  askAnswer: ResearchAskResponse | null
  reportLoading: boolean
  reportError: string | null
  report: ResearchReportResponse | null
  onClose: () => void
  onAskQuestion: (question: string) => void
  onGenerateReport: () => void
}

export function AIAssistantModal({
  open,
  company,
  askLoading,
  askError,
  askAnswer,
  reportLoading,
  reportError,
  report,
  onClose,
  onAskQuestion,
  onGenerateReport,
}: AIAssistantModalProps) {
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(null)
  const [inputText, setInputText] = useState('')
  const [reportRevealed, setReportRevealed] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const spotifyControllerRef = useRef<SpotifyEmbedController | null>(null)

  const loading = askLoading || reportLoading
  const isFullReport = selectedPromptId === 'full-report'
  const canSubmit = inputText.trim().length >= 3 && !loading
  const reportComplete = Boolean(report && !reportLoading)
  const inReportFlow = reportLoading || reportComplete
  const isPipelineFullscreen = reportLoading || (reportComplete && !reportRevealed)
  const pipelineComplete = reportComplete && !reportLoading
  const hasPipelineTrace = Boolean(report?.pipeline_trace && report.pipeline_trace.length > 0)
  const simulatedStageIndex = useSimulatedAgentProgress(
    reportLoading && !hasPipelineTrace,
    Boolean(reportError),
    reportComplete,
  )
  const agentStageIndex =
    pipelineComplete && hasPipelineTrace && report?.pipeline_trace
      ? activeStageIndexFromTrace(report.pipeline_trace)
      : pipelineComplete
        ? AGENT_STAGE_SEQUENCE.length - 1
        : simulatedStageIndex

  useEffect(() => {
    if (!open) {
      setSelectedPromptId(null)
      setInputText('')
      setReportRevealed(false)
    }
  }, [open])

  useEffect(() => {
    if (reportLoading) {
      setReportRevealed(false)
    }
  }, [reportLoading])

  useEffect(() => {
    if (!reportLoading) {
      spotifyControllerRef.current?.pause()
    }
  }, [reportLoading])

  useEffect(() => {
    function onKeyDown(e: globalThis.KeyboardEvent) {
      if (e.key === 'Escape' && open) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null

  const hasConversation = Boolean(askAnswer || report)

  function handlePromptSelect(prompt: AiPrompt) {
    setSelectedPromptId(prompt.id)
    setInputText(prompt.label)
    textareaRef.current?.focus()
  }

  function handleInputChange(value: string) {
    setInputText(value)
    const match = AI_PROMPTS.find((p) => p.label === value)
    setSelectedPromptId(match?.id ?? null)
  }

  function handleRun() {
    const question = inputText.trim()
    if (!question || loading) return

    if (isFullReport) {
      // Calling .play() synchronously inside this click handler (not after
      // an await) is what lets the browser's autoplay policy allow it -
      // this click is a direct user gesture.
      spotifyControllerRef.current?.play()
      onGenerateReport()
    } else {
      onAskQuestion(question)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    handleRun()
  }

  function handleTextareaKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleRun()
    }
  }

  return (
    <div
      className={cn(
        'fixed inset-0 z-[100]',
        inReportFlow ? 'p-0' : 'flex items-end justify-center p-0 sm:items-center sm:p-4',
      )}
    >
      <button
        type="button"
        aria-label="Close modal"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      <SpotifyBackgroundPlayer
        uri={PIPELINE_MUSIC_URI}
        startAtSeconds={PIPELINE_MUSIC_START_SECONDS}
        onReady={(controller) => {
          spotifyControllerRef.current = controller
        }}
      />

      <div
        className={cn(
          'ai-modal relative flex w-full flex-col overflow-hidden shadow-2xl',
          inReportFlow
            ? 'h-[100dvh] max-h-none w-full max-w-none rounded-none border-0'
            : 'h-[92vh] max-h-[900px] rounded-none border-0 sm:h-[88vh] sm:w-[95vw] sm:max-w-[1400px]',
        )}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          className={cn(
            'flex shrink-0 items-start justify-between gap-3 border-b border-violet-500/15 bg-violet-950/40 px-4 sm:px-5',
            isPipelineFullscreen ? 'py-2' : 'px-5 py-4 sm:px-6',
          )}
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-violet-400/30 bg-violet-500/20 text-violet-200">
                InvestIQ AI
              </Badge>
              <span className="font-mono text-xs text-violet-300/80">{company.ticker}</span>
            </div>
            <h2
              className={cn(
                'mt-1 font-semibold text-foreground',
                isPipelineFullscreen ? 'truncate text-base sm:text-lg' : 'mt-2 text-lg sm:text-xl',
              )}
            >
              {company.name}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
          >
            <X className="size-5" />
          </button>
        </div>

        <div
          className={cn(
            'flex min-h-0 flex-1 flex-col',
            isPipelineFullscreen
              ? 'overflow-hidden'
              : 'overflow-y-auto scroll-smooth px-5 py-5 sm:px-6',
          )}
        >
          {!isPipelineFullscreen && !hasConversation && !loading && (
            <div className="mb-6 flex items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-300">
                <Bot className="size-5" />
              </div>
              <div>
                <p className="text-base font-medium sm:text-lg">
                  Hello, how can I help you with this stock?
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Pick a prompt or type your own question below.
                </p>
              </div>
            </div>
          )}

          {inReportFlow && (
            <AvengersPipeline
              className={reportRevealed ? 'mb-6 shrink-0' : 'min-h-0 flex-1'}
              fullscreen={isPipelineFullscreen}
              companyName={company.name}
              ticker={company.ticker}
              activeStageIndex={agentStageIndex}
              loading={reportLoading}
              complete={pipelineComplete}
              failed={Boolean(reportError)}
              reportRevealed={reportRevealed}
              pipelineTrace={report?.pipeline_trace}
              onShowReport={() => setReportRevealed(true)}
            />
          )}

          {!isPipelineFullscreen && askLoading && <AskAnalyzingState question={inputText} className="mb-6" />}

          {!isPipelineFullscreen && (
            <>
              {askError && (
                <Alert variant="destructive" title="Could not get answer" className="mb-4">
                  {askError}
                </Alert>
              )}

              {reportError && (
                <Alert variant="destructive" title="Research failed" className="mb-4">
                  {reportError}
                </Alert>
              )}

              {askAnswer && !askLoading && (
                <div className="mb-6">
                  <ResearchAnswerCard response={askAnswer} />
                </div>
              )}

              {reportComplete && reportRevealed && report && (
                <div className="mb-6 space-y-6">
                  <ProfessionalReport report={report} />
                  <ReportChat reportId={report.id} />
                </div>
              )}

              {(!inReportFlow || reportRevealed) && (
                <section className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">
                    {hasConversation ? 'Ask another question' : 'Suggested prompts'}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {AI_PROMPTS.map((prompt) => {
                      const isSelected = selectedPromptId === prompt.id
                      return (
                        <button
                          key={prompt.id}
                          type="button"
                          disabled={loading}
                          onClick={() => handlePromptSelect(prompt)}
                          className={cn(
                            'relative rounded-xl border px-4 py-3 text-left text-sm transition-all',
                            isSelected
                              ? 'border-violet-400 bg-violet-500/25 text-violet-50 ring-2 ring-violet-400/60'
                              : prompt.id === 'full-report'
                                ? 'border-violet-400/40 bg-violet-500/10 text-violet-100 hover:bg-violet-500/20'
                                : 'border-border/60 bg-background/30 text-muted-foreground hover:border-violet-400/30 hover:bg-violet-500/10 hover:text-foreground',
                            loading && 'pointer-events-none opacity-50',
                          )}
                        >
                          {isSelected && (
                            <Check className="absolute right-3 top-3 size-4 text-violet-300" />
                          )}
                          {prompt.label}
                        </button>
                      )
                    })}
                  </div>
                </section>
              )}
            </>
          )}
        </div>

        {!isPipelineFullscreen && (
        <div className="shrink-0 border-t border-violet-500/15 bg-violet-950/50 px-5 py-4 backdrop-blur-md sm:px-6">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled
              className="border-violet-500/30 bg-violet-500/10 text-violet-200"
            >
              <Zap className="size-3.5" />
              Fast
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled
              className="border-violet-500/30 text-violet-200"
            >
              <Sparkles className="size-3.5" />
              Intelligent
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={inputText}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleTextareaKeyDown}
              disabled={loading}
              rows={2}
              placeholder={`Ask anything about ${company.name}…`}
              className={cn(
                'flex-1 resize-none rounded-xl border border-violet-500/20 bg-background/40 px-3 py-2.5',
                'text-sm text-foreground placeholder:text-muted-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/40',
                'disabled:cursor-not-allowed disabled:opacity-50',
              )}
            />
            <Button
              type="submit"
              disabled={!canSubmit}
              size="default"
              className="h-10 shrink-0 bg-emerald-600 px-3 text-white hover:bg-emerald-500 disabled:opacity-40"
              aria-label={isFullReport ? 'Generate full report' : 'Send question'}
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            </Button>
          </form>
          <p className="mt-2 text-[10px] text-muted-foreground">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
        )}
      </div>
    </div>
  )
}
