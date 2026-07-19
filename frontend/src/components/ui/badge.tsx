import type * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/15 text-primary',
        buy: 'border-transparent bg-emerald-500/15 text-emerald-400',
        hold: 'border-transparent bg-amber-500/15 text-amber-400',
        avoid: 'border-transparent bg-red-500/15 text-red-400',
        sell: 'border-transparent bg-orange-500/15 text-orange-400',
        watchlist: 'border-transparent bg-sky-500/15 text-sky-400',
        outline: 'border-border text-foreground',
        muted: 'border-transparent bg-muted text-muted-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}
