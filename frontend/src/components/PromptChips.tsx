import { cn } from '@/lib/utils'

export interface PromptChip {
  label: string
  value: string
}

export const SUGGESTED_PROMPTS: PromptChip[] = [
  { label: 'Is INFY undervalued?', value: 'INFY' },
  { label: 'Compare TCS vs INFY', value: 'TCS' },
  { label: 'What are the key risks in HDFCBANK?', value: 'HDFCBANK' },
  { label: 'Summarize latest news for RELIANCE', value: 'RELIANCE' },
  { label: 'Give me a 3-year view on SBIN', value: 'SBIN' },
]

interface PromptChipsProps {
  onSelect: (chip: PromptChip) => void
  disabled?: boolean
}

export function PromptChips({ onSelect, disabled }: PromptChipsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {SUGGESTED_PROMPTS.map((chip) => (
        <button
          key={chip.label}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(chip)}
          className={cn(
            'rounded-full border border-border/80 bg-background/40 px-3.5 py-1.5 text-sm text-muted-foreground',
            'transition-all hover:border-primary/40 hover:bg-primary/10 hover:text-foreground',
            'disabled:pointer-events-none disabled:opacity-50',
          )}
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}
