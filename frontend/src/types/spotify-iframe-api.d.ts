// Minimal ambient types for the Spotify iFrame API (loaded via a <script> tag
// in lib/spotifyIframeApi.ts, not an npm package) - just enough surface for
// what this app actually calls. See:
// https://developer.spotify.com/documentation/embeds/references/iframe-api
export {}

declare global {
  interface SpotifyEmbedController {
    play: () => void
    pause: () => void
    resume: () => void
    togglePlay: () => void
    seek: (seconds: number) => void
    destroy: () => void
    addListener: (event: 'ready' | 'playback_started' | 'playback_update', cb: () => void) => void
  }

  interface SpotifyIFrameAPI {
    createController: (
      element: HTMLElement,
      options: { uri: string; width?: string | number; height?: string | number },
      callback: (controller: SpotifyEmbedController) => void,
    ) => void
  }

  interface Window {
    onSpotifyIframeApiReady?: (IFrameAPI: SpotifyIFrameAPI) => void
  }
}
