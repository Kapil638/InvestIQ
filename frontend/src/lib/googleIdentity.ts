// Loads Google Identity Services directly (no @react-oauth/google wrapper),
// matching this project's existing hand-rolled-OAuth style for the Kite/Drive
// flows rather than adding an SDK for what's fundamentally a script tag + a
// button render call.

const GSI_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

let scriptLoadPromise: Promise<void> | null = null

function loadGsiScript(): Promise<void> {
  if (scriptLoadPromise) return scriptLoadPromise

  scriptLoadPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = GSI_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Google Identity Services script.'))
    document.head.appendChild(script)
  })

  return scriptLoadPromise
}

export async function initGoogleSignIn(
  clientId: string,
  onCredential: (idToken: string) => void,
): Promise<void> {
  await loadGsiScript()
  window.google!.accounts.id.initialize({
    client_id: clientId,
    callback: (response: { credential: string }) => onCredential(response.credential),
  })
}

export function renderGoogleButton(container: HTMLElement): void {
  window.google?.accounts.id.renderButton(container, {
    type: 'standard',
    theme: 'filled_black',
    size: 'large',
    shape: 'pill',
    text: 'signin_with',
    width: 320,
  })
}
