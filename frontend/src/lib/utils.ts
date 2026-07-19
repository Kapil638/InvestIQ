import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function formatINR(value: number | null | undefined, compact = false): string {
  if (value == null || Number.isNaN(value)) return '—'
  if (compact) {
    if (value >= 1e12) return `₹${(value / 1e12).toFixed(2)}T`
    if (value >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`
    if (value >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value)
}

/** Yahoo Finance often returns ratios as decimals (0.12 = 12%). */
export function toPercentValue(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null
  return Math.abs(value) <= 1 ? value * 100 : value
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  const pct = toPercentValue(value)
  if (pct == null) return '—'
  return `${pct.toFixed(digits)}%`
}
