import { useEffect, useRef } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import type { HistoricalCandle } from '@/types/api'

const EMPTY_OVERLAYS: ChartOverlayLayer[] = []

export interface ChartOverlayLayer {
  id: string
  render: (chart: IChartApi) => void | (() => void)
}

interface CandlestickChartProps {
  candles: HistoricalCandle[]
  className?: string
  /** Reserved for future buy signals, AI annotations, earnings markers, etc. */
  overlays?: ChartOverlayLayer[]
}

function parseTimestamp(value: string): Time {
  if (value.includes('T')) {
    return Math.floor(new Date(value).getTime() / 1000) as Time
  }
  return value.slice(0, 10) as Time
}

export function CandlestickChart({ candles, className, overlays = EMPTY_OVERLAYS }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.08)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.08)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(148, 163, 184, 0.15)',
      },
      timeScale: {
        borderColor: 'rgba(148, 163, 184, 0.15)',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1,
      },
      handleScroll: true,
      handleScale: true,
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    volumeSeriesRef.current = volumeSeries

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      chart.applyOptions({ width, height })
    })
    resizeObserver.observe(container)

    const cleanupOverlays: Array<void | (() => void)> = overlays.map((layer) => layer.render(chart))

    return () => {
      resizeObserver.disconnect()
      cleanupOverlays.forEach((cleanup) => {
        if (typeof cleanup === 'function') cleanup()
      })
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [overlays])

  useEffect(() => {
    const candleSeries = candleSeriesRef.current
    const volumeSeries = volumeSeriesRef.current
    const chart = chartRef.current
    if (!candleSeries || !volumeSeries || !chart || candles.length === 0) return

    const ohlc = candles
      .filter((c) => c.open != null && c.high != null && c.low != null && c.close != null)
      .map((c) => ({
        time: parseTimestamp(c.timestamp),
        open: c.open as number,
        high: c.high as number,
        low: c.low as number,
        close: c.close as number,
      }))

    const volume = candles
      .filter((c) => c.volume != null)
      .map((c) => ({
        time: parseTimestamp(c.timestamp),
        value: c.volume as number,
        color:
          (c.close ?? 0) >= (c.open ?? 0) ? 'rgba(34, 197, 94, 0.45)' : 'rgba(239, 68, 68, 0.45)',
      }))

    candleSeries.setData(ohlc)
    volumeSeries.setData(volume)
    chart.timeScale().fitContent()
  }, [candles])

  return (
    <div className={className}>
      <div ref={containerRef} className="h-full w-full" />
      {/* Overlay mount point for future markers (buy signals, earnings, news, dividends) */}
      <div
        data-chart-overlay-layer
        className="pointer-events-none absolute inset-0"
        aria-hidden
      />
    </div>
  )
}
