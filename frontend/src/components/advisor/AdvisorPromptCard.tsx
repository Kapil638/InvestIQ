import { useState, type FormEvent } from 'react'
import { Loader2, Sparkles, Wand2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export const ADVISOR_PROMPT_CHIPS = [
  'Best stocks for 3 years with moderate risk',
  'Build me a ₹5 lakh portfolio',
  'Low-risk large-cap stocks',
  'High-growth stocks for 5 years',
  'Dividend stocks for passive income',
  'AI and defence theme stocks',
] as const

interface AdvisorPromptCardProps {
  onSubmit: (prompt: string) => void
  loading?: boolean
  className?: string
}

export function AdvisorPromptCard({ onSubmit, loading = false, className }: AdvisorPromptCardProps) {
  const [prompt, setPrompt] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = prompt.trim()
    if (trimmed.length < 10 || loading) return
    onSubmit(trimmed)
  }

  function applyChip(chip: string) {
    setPrompt(chip)
  }

  return (
    <div
      className={cn(
        'glass-card relative overflow-hidden rounded-3xl border border-violet-500/20 p-6 sm:p-8',
        className,
      )}
    >
      <div className="pointer-events-none absolute -left-12 top-0 size-40 rounded-full bg-violet-500/10 blur-3xl" />
      <div className="pointer-events-none absolute -right-8 bottom-0 size-32 rounded-full bg-primary/10 blur-3xl" />

      <div className="relative">
        <div className="mb-4 flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-xl bg-violet-500/15 text-violet-300">
            <Wand2 className="size-4" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-300/90">
              AI advisor
            </p>
            <h2 className="text-lg font-semibold tracking-tight sm:text-xl">Ask InvestIQ Advisor</h2>
          </div>
        </div>

        <p className="mb-4 text-sm text-muted-foreground">
          Describe your goals, capital, horizon, and risk appetite. InvestIQ will suggest Indian stocks
          worth researching — not trade execution.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={5}
            placeholder="Example: I have ₹5 lakh to invest for 3 years. Moderate risk. Suggest Indian stocks with strong fundamentals."
            className="w-full resize-none rounded-2xl border border-border/60 bg-background/40 px-4 py-3 text-sm leading-relaxed placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40"
            disabled={loading}
          />

          <div className="flex flex-wrap gap-2">
            {ADVISOR_PROMPT_CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => applyChip(chip)}
                disabled={loading}
                className="rounded-full border border-border/60 bg-background/30 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-violet-500/40 hover:text-foreground disabled:opacity-50"
              >
                {chip}
              </button>
            ))}
          </div>

          <Button
            type="submit"
            disabled={loading || prompt.trim().length < 10}
            className="w-full bg-gradient-to-r from-emerald-600 to-emerald-500 text-white hover:from-emerald-500 hover:to-emerald-400 sm:w-auto"
          >
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Analyzing goals…
              </>
            ) : (
              <>
                <Sparkles className="size-4" />
                Get AI Suggestions
              </>
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}
