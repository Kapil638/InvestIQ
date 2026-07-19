import { Badge } from '@/components/ui/badge'
import type { CommitteeRecommendation } from '@/types/investmentCommittee'
import { cn } from '@/lib/utils'

const variantMap: Record<
  CommitteeRecommendation,
  'buy' | 'hold' | 'sell' | 'avoid'
> = {
  BUY: 'buy',
  HOLD: 'hold',
  SELL: 'sell',
  AVOID: 'avoid',
}

interface CommitteeRecommendationBadgeProps {
  recommendation: CommitteeRecommendation | string | null | undefined
  className?: string
}

export function CommitteeRecommendationBadge({
  recommendation,
  className,
}: CommitteeRecommendationBadgeProps) {
  if (!recommendation) {
    return <Badge variant="muted" className={className}>Pending</Badge>
  }

  const key = recommendation.toUpperCase() as CommitteeRecommendation
  const variant = variantMap[key] ?? 'outline'

  return (
    <Badge variant={variant} className={cn('tracking-wide', className)}>
      {key}
    </Badge>
  )
}
