import { useEffect, useRef } from 'react'
import { loadSpotifyIframeApi } from '@/lib/spotifyIframeApi'

interface SpotifyBackgroundPlayerProps {
  /** Spotify URI, e.g. "spotify:track:6h6PlGTisMcE6G8GiS31fR" */
  uri: string
  /** Seconds to jump to whenever playback (re)starts, e.g. 11 to skip a
   * 10-second intro. Re-applied on every playback_started event, so this
   * also takes effect on repeat plays within the same modal session. */
  startAtSeconds?: number
  onReady: (controller: SpotifyEmbedController) => void
}

/**
 * No visible UI - this is a fixed background track, not a widget the user
 * interacts with. Renders as soon as it mounts (parent controls that by
 * conditionally rendering the whole modal) so the controller is already
 * created and ready by the time the user clicks "Generate full report" -
 * calling .play() then happens synchronously inside that click handler,
 * which is what lets the browser's autoplay policy allow it. Creating the
 * controller earlier, while the container is hidden, does not itself start
 * any audio - CSS visibility has no bearing on that policy either way.
 *
 * The container is visually hidden via off-screen absolute positioning
 * (not display:none), since some browsers deprioritize or unload iframes
 * that are display:none.
 */
export function SpotifyBackgroundPlayer({ uri, startAtSeconds, onReady }: SpotifyBackgroundPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const controllerRef = useRef<SpotifyEmbedController | null>(null)

  useEffect(() => {
    if (controllerRef.current || !containerRef.current) return

    let cancelled = false
    loadSpotifyIframeApi().then((IFrameAPI) => {
      if (cancelled || !containerRef.current) return
      IFrameAPI.createController(containerRef.current, { uri, width: '300', height: '80' }, (controller) => {
        if (cancelled) {
          controller.destroy()
          return
        }
        controllerRef.current = controller
        if (startAtSeconds != null) {
          controller.addListener('playback_started', () => controller.seek(startAtSeconds))
        }
        onReady(controller)
      })
    })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uri])

  useEffect(() => {
    return () => {
      controllerRef.current?.destroy()
      controllerRef.current = null
    }
  }, [])

  return (
    <div className="pointer-events-none fixed left-[-9999px] top-[-9999px] size-px overflow-hidden opacity-0">
      <div ref={containerRef} />
    </div>
  )
}
