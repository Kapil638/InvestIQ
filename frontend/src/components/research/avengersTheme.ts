/** Design tokens from Avengers Agent Pipeline UI spec */

export const AVENGERS = {
  bg: '#0B0F1A',
  cardBg: 'rgba(16, 20, 36, 0.7)',
  cardBorder: 'rgba(255, 255, 255, 0.06)',
  textPrimary: '#E5E7EB',
  textSecondary: '#9CA3AF',
  green: '#22C55E',
  purple: '#A855F7',
  blue: '#3B82F6',
  yellow: '#FACC15',
  red: '#EF4444',
  teal: '#14B1A6',
  radius: '16px',
} as const

export const AGENT_COLORS = {
  financial: {
    accent: AVENGERS.green,
    glow: '0 0 24px rgba(34, 197, 94, 0.35)',
    bg: 'rgba(34, 197, 94, 0.12)',
    border: 'rgba(34, 197, 94, 0.45)',
  },
  news: {
    accent: AVENGERS.purple,
    glow: '0 0 28px rgba(168, 85, 247, 0.45)',
    bg: 'rgba(168, 85, 247, 0.12)',
    border: 'rgba(168, 85, 247, 0.5)',
  },
  analysis: {
    accent: AVENGERS.blue,
    glow: '0 0 24px rgba(59, 130, 246, 0.35)',
    bg: 'rgba(59, 130, 246, 0.12)',
    border: 'rgba(59, 130, 246, 0.45)',
  },
  risk: {
    accent: AVENGERS.yellow,
    glow: '0 0 24px rgba(250, 204, 21, 0.35)',
    bg: 'rgba(250, 204, 21, 0.12)',
    border: 'rgba(250, 204, 21, 0.45)',
  },
  recommendation: {
    accent: AVENGERS.red,
    glow: '0 0 28px rgba(239, 68, 68, 0.4)',
    bg: 'rgba(239, 68, 68, 0.12)',
    border: 'rgba(239, 68, 68, 0.45)',
  },
  market: {
    accent: AVENGERS.teal,
    glow: '0 0 20px rgba(20, 177, 166, 0.35)',
    bg: 'rgba(20, 177, 166, 0.12)',
    border: 'rgba(20, 177, 166, 0.45)',
  },
} as const
