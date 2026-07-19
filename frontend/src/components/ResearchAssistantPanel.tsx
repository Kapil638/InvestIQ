import type { ReactNode } from 'react'
import { Bot, Lock, MessageSquare, Send } from 'lucide-react'
import type { ResearchReportResponse } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const FOLLOW_UP_SUGGESTIONS = [
  'What would change your rating?',
  'Explain the biggest risk in simpler terms',
  'How does valuation compare to sector peers?',
  'Summarize this for a 3-year investor',
]

interface ResearchAssistantPanelProps {
  report: ResearchReportResponse | null
  loading?: boolean
}

export function ResearchAssistantPanel({ report, loading }: ResearchAssistantPanelProps) {
  const ticker = report?.ticker

  return (
    <aside className="glass-card sticky top-6 flex h-fit flex-col rounded-2xl border-border/80">
      <div className="border-b border-border/60 p-5">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
            <Bot className="size-5" />
          </div>
          <div>
            <h3 className="font-semibold">AI Research Assistant</h3>
            <p className="text-xs text-muted-foreground">Follow-up Q&A (coming soon)</p>
          </div>
        </div>
      </div>

      <div className="flex max-h-[420px] flex-1 flex-col gap-4 overflow-y-auto p-5">
        {!report && !loading && (
          <div className="rounded-xl border border-dashed border-border/80 bg-background/20 p-4 text-sm text-muted-foreground">
            Generate a report to unlock contextual follow-up questions about the thesis, risks, and
            valuation.
          </div>
        )}

        {loading && (
          <div className="space-y-3">
            <AssistantBubble role="system">
              InvestIQ agents are working on your request. You&apos;ll be able to ask follow-ups once
              the report is ready.
            </AssistantBubble>
            <div className="h-16 animate-pulse rounded-xl bg-muted/40" />
            <div className="h-10 w-3/4 animate-pulse rounded-xl bg-muted/30" />
          </div>
        )}

        {report && !loading && (
          <>
            <AssistantBubble role="assistant">
              I&apos;ve reviewed the {ticker} research package
              {report.financial_data?.profile?.company_name
                ? ` for ${report.financial_data.profile.company_name}`
                : ''}
              . Ask follow-up questions about this report.
            </AssistantBubble>
            <div className="flex flex-wrap gap-2">
              {FOLLOW_UP_SUGGESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled
                  className="rounded-full border border-border/70 bg-background/30 px-3 py-1.5 text-left text-xs text-muted-foreground"
                  title="Coming soon"
                >
                  {q}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="border-t border-border/60 p-4">
        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Lock className="size-3.5" />
          Ask follow-up questions about this report
        </div>
        <div className="flex gap-2">
          <Input
            disabled
            placeholder={report ? `Ask about ${report.ticker}…` : 'Generate a report first…'}
            className="bg-background/40"
          />
          <Button disabled size="default" className="shrink-0 px-3" aria-label="Send message">
            <Send className="size-4" />
          </Button>
        </div>
      </div>
    </aside>
  )
}

function AssistantBubble({
  role,
  children,
}: {
  role: 'assistant' | 'system'
  children: ReactNode
}) {
  return (
    <div
      className={
        role === 'assistant'
          ? 'rounded-2xl rounded-tl-sm border border-border/60 bg-background/40 p-3 text-sm text-foreground'
          : 'rounded-xl bg-muted/30 p-3 text-sm text-muted-foreground'
      }
    >
      <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <MessageSquare className="size-3" />
        {role === 'assistant' ? 'InvestIQ' : 'Status'}
      </div>
      {children}
    </div>
  )
}
