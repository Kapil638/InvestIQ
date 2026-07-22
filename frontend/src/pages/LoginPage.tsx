import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { BarChart3, Fingerprint, Loader2 } from 'lucide-react'
import { googleSignIn } from '@/lib/api'
import { initGoogleSignIn, renderGoogleButton } from '@/lib/googleIdentity'
import { authenticateWithPasskey, isPlatformAuthenticatorAvailable } from '@/lib/webauthn'
import { invalidateAuthStatusCache } from '@/lib/statusCache'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { MarketTicker } from '@/components/MarketTicker'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_SIGNIN_CLIENT_ID as string | undefined

// A local hint only — not a security boundary. Real verification always
// happens server-side; this just decides whether to show the fingerprint CTA
// as the primary action on this browser, vs. falling back to Google.
const PASSKEY_HINT_KEY = 'investiq_passkey_hint'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const googleButtonRef = useRef<HTMLDivElement>(null)

  const [error, setError] = useState<string | null>(null)
  const [checkingPasskey, setCheckingPasskey] = useState(true)
  const [showFingerprintPrimary, setShowFingerprintPrimary] = useState(false)
  const [unlocking, setUnlocking] = useState(false)

  const redirectTo = (location.state as { from?: string } | null)?.from || '/'

  useEffect(() => {
    let cancelled = false

    async function checkPasskeyAvailability() {
      const hasHint = localStorage.getItem(PASSKEY_HINT_KEY) === '1'
      const available = await isPlatformAuthenticatorAvailable()
      if (!cancelled) {
        setShowFingerprintPrimary(hasHint && available)
        setCheckingPasskey(false)
      }
    }

    void checkPasskeyAvailability()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !googleButtonRef.current) return

    let cancelled = false
    void initGoogleSignIn(GOOGLE_CLIENT_ID, (idToken) => {
      void handleGoogleCredential(idToken)
    }).then(() => {
      if (!cancelled && googleButtonRef.current) {
        renderGoogleButton(googleButtonRef.current)
      }
    })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleGoogleCredential(idToken: string) {
    setError(null)
    try {
      await googleSignIn(idToken)
      invalidateAuthStatusCache()
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google Sign-In failed')
    }
  }

  async function handleFingerprintUnlock() {
    setError(null)
    setUnlocking(true)
    try {
      await authenticateWithPasskey()
      localStorage.setItem(PASSKEY_HINT_KEY, '1')
      invalidateAuthStatusCache()
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fingerprint unlock failed')
    } finally {
      setUnlocking(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <MarketTicker />
      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-4">
        <div className="pointer-events-none absolute inset-0 login-bg-grid" />
        <div className="pointer-events-none absolute -left-24 top-16 size-72 rounded-full bg-primary/20 blur-[100px] login-blob-1" />
        <div className="pointer-events-none absolute -right-20 bottom-10 size-80 rounded-full bg-blue-500/15 blur-[110px] login-blob-2" />
        <svg
          className="pointer-events-none absolute inset-0 size-full"
          viewBox="0 0 1200 800"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polyline
            className="login-chart-line text-primary"
            points="0,600 100,560 200,610 300,500 400,530 500,420 600,460 700,380 800,410 900,320 1000,350 1100,270 1200,300"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          />
          <polyline
            className="login-chart-line-delayed text-blue-400"
            points="0,700 150,680 300,690 450,650 600,660 750,600 900,620 1050,560 1200,580"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          />
        </svg>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_oklch(0.22_0.04_155/_0.35),_transparent_50%)]" />

        <div className="glass-card relative w-full max-w-sm rounded-2xl p-8">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <span className="flex size-12 items-center justify-center rounded-xl bg-primary/15">
            <BarChart3 className="size-6 text-primary" />
          </span>
          <div>
            <h1 className="text-xl font-semibold text-foreground">InvestIQ</h1>
            <p className="mt-1 text-sm text-muted-foreground">Sign in to continue</p>
          </div>
        </div>

        {error && (
          <div className="mb-4">
            <Alert variant="destructive" title="Sign-in failed">
              {error}
            </Alert>
          </div>
        )}

        {!checkingPasskey && showFingerprintPrimary && (
          <div className="mb-4 flex flex-col items-center gap-3">
            <Button
              type="button"
              size="lg"
              className="w-full gap-2"
              disabled={unlocking}
              onClick={() => void handleFingerprintUnlock()}
            >
              {unlocking ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Fingerprint className="size-4" />
              )}
              {unlocking ? 'Unlocking…' : 'Unlock with fingerprint'}
            </Button>
            <div className="flex w-full items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-border" />
              or sign in with a different account
              <span className="h-px flex-1 bg-border" />
            </div>
          </div>
        )}

        <div className="flex justify-center">
          {GOOGLE_CLIENT_ID ? (
            <div ref={googleButtonRef} />
          ) : (
            <p className="text-center text-xs text-muted-foreground">
              Google Sign-In is not configured. Set VITE_GOOGLE_SIGNIN_CLIENT_ID.
            </p>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}
