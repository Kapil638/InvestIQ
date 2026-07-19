import { cn } from '@/lib/utils'

export type StockTabId = 'overview' | 'chart' | 'financials' | 'pros-cons' | 'news' | 'ai'

const TABS: { id: StockTabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'chart', label: 'Chart' },
  { id: 'financials', label: 'Financials' },
  { id: 'pros-cons', label: 'Pros & Cons' },
  { id: 'news', label: 'News' },
  { id: 'ai', label: 'AI' },
]

interface StockTabsProps {
  activeTab: StockTabId
  onChange: (tab: StockTabId) => void
}

export function StockTabs({ activeTab, onChange }: StockTabsProps) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-xl border border-border/60 bg-background/30 p-1">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            'shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-all',
            activeTab === tab.id
              ? 'bg-primary/15 text-primary shadow-sm'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
