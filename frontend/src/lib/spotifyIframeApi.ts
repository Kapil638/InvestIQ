// Loads the Spotify iFrame API directly (no npm wrapper), matching this
// project's existing hand-rolled-script style for Google Identity.

const SPOTIFY_IFRAME_API_SRC = 'https://open.spotify.com/embed/iframe-api/v1'

let apiLoadPromise: Promise<SpotifyIFrameAPI> | null = null

export function loadSpotifyIframeApi(): Promise<SpotifyIFrameAPI> {
  if (apiLoadPromise) return apiLoadPromise

  apiLoadPromise = new Promise((resolve, reject) => {
    window.onSpotifyIframeApiReady = (IFrameAPI) => resolve(IFrameAPI)

    const script = document.createElement('script')
    script.src = SPOTIFY_IFRAME_API_SRC
    script.async = true
    script.onerror = () => reject(new Error('Failed to load Spotify iFrame API script.'))
    document.head.appendChild(script)
  })

  return apiLoadPromise
}
