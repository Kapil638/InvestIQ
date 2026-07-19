import { Bot } from 'lucide-react'
import type { ResearchAskResponse } from '@/types/api'
import { AIAnswerRenderer } from '@/components/research/AIAnswerRenderer'
import { formatDate } from '@/lib/utils'

interface ResearchAnswerCardProps {
  response: ResearchAskResponse
}

export function ResearchAnswerCard({ response }: ResearchAnswerCardProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-violet-400/30 bg-violet-500/10 px-4 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-300">
          Your question
        </p>
        <p className="mt-1 text-sm font-medium text-violet-50">{response.question}</p>
      </div>

      <div className="glass-card rounded-2xl border border-violet-500/20 p-6 sm:p-7">
        <div className="mb-5 flex items-center gap-2 border-b border-violet-500/15 pb-4">
          <div className="flex size-9 items-center justify-center rounded-lg bg-violet-500/20">
            <Bot className="size-4 text-violet-300" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-foreground">InvestIQ answer</h3>
            <p className="text-xs text-muted-foreground">{formatDate(response.generated_at)}</p>
          </div>
        </div>
        <AIAnswerRenderer content={response.answer} sources={response.data_sources} />
      </div>
    </div>
  )
}
