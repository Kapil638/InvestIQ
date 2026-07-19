import type { RecommendationRating } from '@/types/api'
import type { CommitteeRecommendation } from '@/types/investmentCommittee'
import { Badge } from '@/components/ui/badge'

type DisplayRating = RecommendationRating | CommitteeRecommendation | string

const ratingVariant: Record<string, 'buy' | 'hold' | 'sell' | 'avoid' | 'watchlist' | 'outline'> = {
  Buy: 'buy',
  BUY: 'buy',
  Hold: 'hold',
  HOLD: 'hold',
  Sell: 'sell',
  SELL: 'sell',
  Avoid: 'avoid',
  AVOID: 'avoid',
  Watchlist: 'watchlist',
}

function formatRatingLabel(rating: string): string {
  const upper = rating.toUpperCase()
  if (upper === 'BUY' || upper === 'HOLD' || upper === 'SELL' || upper === 'AVOID') {
    return upper
  }
  return rating
}

interface RecommendationBadgeProps {
  rating: DisplayRating | null | undefined
  confidence?: number | null
}

export function RecommendationBadge({ rating, confidence }: RecommendationBadgeProps) {
  if (!rating) {
    return <Badge variant="muted">No rating</Badge>
  }

  const variant = ratingVariant[rating] ?? ratingVariant[rating.toUpperCase()] ?? 'outline'

  return (
    <div className="flex items-center gap-2">
      <Badge variant={variant}>{formatRatingLabel(rating)}</Badge>
      {confidence != null && (
        <span className="text-sm text-muted-foreground">{Math.round(confidence)}% confidence</span>
      )}
    </div>
  )
}
