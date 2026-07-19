export type ChartTimeframe = '1D' | '5D' | '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y'

export type HistoryInterval = 'minute' | '5minute' | '15minute' | 'day' | 'week' | 'month'

export interface TimeframeConfig {
  label: ChartTimeframe
  interval: HistoryInterval
  days: number
}

export const CHART_TIMEFRAMES: TimeframeConfig[] = [
  { label: '1D', interval: '5minute', days: 1 },
  { label: '5D', interval: '15minute', days: 5 },
  { label: '1M', interval: 'day', days: 30 },
  { label: '3M', interval: 'day', days: 90 },
  { label: '6M', interval: 'day', days: 180 },
  { label: '1Y', interval: 'day', days: 365 },
  { label: '3Y', interval: 'week', days: 365 * 3 },
  { label: '5Y', interval: 'week', days: 365 * 5 },
]

export function resolveChartRange(timeframe: ChartTimeframe): {
  interval: HistoryInterval
  from: string
  to: string
} {
  const config = CHART_TIMEFRAMES.find((item) => item.label === timeframe) ?? CHART_TIMEFRAMES[5]
  const end = new Date()
  const start = new Date(end)
  start.setDate(start.getDate() - config.days)

  return {
    interval: config.interval,
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  }
}
