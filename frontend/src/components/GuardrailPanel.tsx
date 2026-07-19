import type { GuardrailResult } from '@/types/api'
import { Alert } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface GuardrailPanelProps {
  guardrails: GuardrailResult
  title?: string
}

export function GuardrailPanel({ guardrails, title = 'Guardrails' }: GuardrailPanelProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{title}</CardTitle>
          <Badge variant={guardrails.passed ? 'buy' : 'avoid'}>
            {guardrails.passed ? 'Passed' : 'Failed'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {guardrails.blocked_reason && (
          <Alert variant="destructive" title="Blocked">
            {guardrails.blocked_reason}
          </Alert>
        )}
        {guardrails.retry_count > 0 && (
          <p className="text-sm text-muted-foreground">
            Analysis retried {guardrails.retry_count} time(s) after guardrail feedback.
          </p>
        )}
        {guardrails.issues.length > 0 ? (
          <ul className="space-y-2">
            {guardrails.issues.map((issue) => (
              <li
                key={`${issue.code}-${issue.message}`}
                className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm"
              >
                <span
                  className={
                    issue.severity === 'error' ? 'text-red-400' : 'text-amber-400'
                  }
                >
                  [{issue.severity}]
                </span>{' '}
                <span className="font-medium">{issue.code}</span>
                <p className="mt-1 text-muted-foreground">{issue.message}</p>
              </li>
            ))}
          </ul>
        ) : (
          <Alert variant="success" title="All checks passed">
            No guardrail issues detected.
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
