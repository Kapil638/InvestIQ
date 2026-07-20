import { useEffect, useState } from 'react'
import { Fingerprint, X } from 'lucide-react'
import { useAuthStatus } from '@/hooks/useAuthStatus'
import { registerPasskey, isPlatformAuthenticatorAvailable } from '@/lib/webauthn'
import { invalidateAuthStatusCache } from '@/lib/statusCache'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const PASSKEY_HINT_KEY = 'investiq_passkey_hint'
const DISMISSED_KEY = 'investiq_passkey_banner_dismissed'

export function PasskeyEnrollBanner() {
  const { status, authenticated, refetch } = useAuthStatus()
  const [platformAvailable, setPlatformAvailable] = useState(false)
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISSED_KEY) === '1',
  )
  const [enrolling, setEnrolling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void isPlatformAuthenticatorAvailable().then(setPlatformAvailable)
  }, [])

  if (!authenticated || status?.has_passkey || !platformAvailable || dismissed) {
    return null
  }

  async function handleEnroll() {
    setError(null)
    setEnrolling(true)
    try {
      await registerPasskey()
      localStorage.setItem(PASSKEY_HINT_KEY, '1')
      invalidateAuthStatusCache()
      refetch()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Passkey registration failed')
    } finally {
      setEnrolling(false)
    }
  }

  function handleDismiss() {
    sessionStorage.setItem(DISMISSED_KEY, '1')
    setDismissed(true)
  }

  return (
    <Card className="border-primary/20 bg-primary/5">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-3">
          <Fingerprint className="size-5 text-primary" />
          <div>
            <p className="text-sm font-medium text-foreground">Enable fingerprint unlock</p>
            <p className="text-xs text-muted-foreground">
              Skip Google sign-in next time on this device.
            </p>
            {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleDismiss}>
            Not now
          </Button>
          <Button size="sm" disabled={enrolling} onClick={() => void handleEnroll()}>
            {enrolling ? 'Enrolling…' : 'Enable'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 p-0"
            onClick={handleDismiss}
            aria-label="Dismiss"
          >
            <X className="size-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
