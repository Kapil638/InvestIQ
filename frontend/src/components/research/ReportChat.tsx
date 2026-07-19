import { memo, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Bot, Loader2, Send, User } from 'lucide-react'
import type { ReportChatResponse, ChatTurn } from '@/types/api'
import { chatAboutReport } from '@/lib/api'
import { AIAnswerRenderer } from '@/components/research/AIAnswerRenderer'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

const FOLLOW_UP_CHIPS = [
  'Why is this stock a Buy/Hold/Avoid?',
  'What are the biggest risks?',
  'Compare this with TCS',
  'What changed from the last report?',
  'Is this suitable for a 3-year investment?',
  'Explain valuation in simple language',
]

interface ChatMessage extends ChatTurn {
  sources?: string[]
}

interface ReportChatProps {
  reportId: string | null | undefined
  className?: string
}

function ReportChatInner({ reportId, className }: ReportChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const disabled = !reportId || loading

  async function sendQuestion(question: string) {
    const trimmed = question.trim()
    if (!trimmed || !reportId) return

    setError(null)
    setLoading(true)
    const history = messages
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    setInput('')

    try {
      const response: ReportChatResponse = await chatAboutReport(reportId, trimmed, history)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.answer, sources: response.sources },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get answer')
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void sendQuestion(input)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendQuestion(input)
    }
  }

  if (!reportId) {
    return (
      <div className={cn('glass-card rounded-2xl p-5 text-sm text-muted-foreground', className)}>
        Save the report to ask follow-up questions. Report chat requires a stored report ID.
      </div>
    )
  }

  return (
    <div className={cn('glass-card flex flex-col rounded-2xl border-violet-500/20', className)}>
      <div className="border-b border-border/60 p-4">
        <div className="flex items-center gap-2">
          <Bot className="size-5 text-violet-300" />
          <h3 className="font-semibold">Follow-up research chat</h3>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Ask questions about this specific report — powered by stored context and report memory.
        </p>
      </div>

      <div className="max-h-96 flex-1 space-y-4 overflow-y-auto scroll-smooth p-4">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Pick a suggested question or type your own below.
          </p>
        )}
        {messages.map((msg, idx) => (
          <div
            key={`${msg.role}-${idx}`}
            className={cn(
              msg.role === 'user'
                ? 'ml-8 rounded-xl bg-background/50 px-4 py-3'
                : 'mr-2 rounded-2xl border border-violet-500/20 bg-violet-500/10 p-4',
            )}
          >
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {msg.role === 'user' ? <User className="size-3" /> : <Bot className="size-3" />}
              {msg.role === 'user' ? 'You' : 'InvestIQ answer'}
            </div>
            {msg.role === 'user' ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                {msg.content}
              </p>
            ) : (
              <AIAnswerRenderer content={msg.content} sources={msg.sources} />
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            InvestIQ is analyzing…
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 pb-2">
          <Alert variant="destructive" title="Chat failed">
            {error}
          </Alert>
        </div>
      )}

      <div className="border-t border-border/60 p-4">
        <div className="mb-3 flex flex-wrap gap-2">
          {FOLLOW_UP_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              disabled={disabled}
              onClick={() => void sendQuestion(chip)}
              className="rounded-full border border-border/70 bg-background/30 px-3 py-1 text-left text-xs text-muted-foreground transition-colors hover:border-violet-400/40 hover:text-foreground disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            rows={2}
            placeholder="Ask a follow-up question about this report…"
            className={cn(
              'flex-1 resize-none rounded-xl border border-violet-500/20 bg-background/40 px-3 py-2.5',
              'text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/40',
              'disabled:cursor-not-allowed disabled:opacity-50',
            )}
          />
          <Button
            type="submit"
            disabled={disabled || input.trim().length < 3}
            className="h-10 shrink-0 bg-emerald-600 px-3 text-white hover:bg-emerald-500"
          >
            <Send className="size-4" />
          </Button>
        </form>
      </div>
    </div>
  )
}

export const ReportChat = memo(ReportChatInner)
