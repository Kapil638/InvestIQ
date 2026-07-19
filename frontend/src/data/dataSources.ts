import type { LucideIcon } from 'lucide-react'
import { Activity, Briefcase, Database, LineChart, Newspaper } from 'lucide-react'

export interface DataSourceItem {
  id: string
  icon: LucideIcon
  title: string
  provider: string
  description: string
  status: 'live' | 'planned' | 'auth'
}

/** InvestIQ data plane — single source of truth for trust layer UI */
export const DATA_SOURCES: DataSourceItem[] = [
  {
    id: 'fundamentals',
    icon: LineChart,
    title: 'Company fundamentals',
    provider: 'Yahoo Finance',
    description: 'NSE/BSE financials, ratios, and company profile for research snapshots.',
    status: 'live',
  },
  {
    id: 'market-data',
    icon: Activity,
    title: 'Live market data',
    provider: 'Kite Connect',
    description: 'Real-time quotes, depth, and session prices for Indian equities.',
    status: 'planned',
  },
  {
    id: 'portfolio',
    icon: Briefcase,
    title: 'Portfolio holdings',
    provider: 'Kite Connect',
    description: 'Linked positions and allocation context for personalized research.',
    status: 'planned',
  },
  {
    id: 'news',
    icon: Newspaper,
    title: 'News & sentiment',
    provider: 'Tavily',
    description: 'Live headlines, filings context, and macro news from web search.',
    status: 'live',
  },
  {
    id: 'memory',
    icon: Database,
    title: 'Reports & memory',
    provider: 'Supabase + ChromaDB',
    description: 'Persistent report history and semantic recall of past theses.',
    status: 'live',
  },
]
