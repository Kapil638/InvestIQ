import { useEffect, useRef } from 'react'
import { loadSpotifyIframeApi } from '@/lib/spotifyIframeApi'
import { cn } from '@/lib/utils'

interface SpotifyBackgroundPlayerProps {
  /** Spotify URI, e.g. "spotify:artist:4bvGDTEPFnllKiJaEZGuXk" */
  uri: string
  visible: boolean
  onReady: (controller: SpotifyEmbedController) => void
}

/**
 * Renders as soon as it mounts (parent controls that by conditionally
 * rendering the whole modal) so the controller is already created and ready
 * by the time the user clicks "Generate full report" - calling .play() then
 * happens synchronously inside that click handler, which is what lets the
 * browser's autoplay policy allow it. Creating the controller earlier, while
 * hidden, does not itself start any audio.
 */
export function SpotifyBackgroundPlayer({ uri, visible, onReady }: SpotifyBackgroundPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const controllerRef = useRef<SpotifyEmbedController | null>(null)

  useEffect(() => {
    if (controllerRef.current || !containerRef.current) return

    let cancelled = false
    loadSpotifyIframeApi().then((IFrameAPI) => {
      if (cancelled || !containerRef.current) return
      IFrameAPI.createController(containerRef.current, { uri, width: '100%', height: '80' }, (controller) => {
        if (cancelled) {
          controller.destroy()
          return
        }
        controllerRef.current = controller
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
    <div
      className={cn(
        'fixed bottom-4 right-4 z-[110] w-72 overflow-hidden rounded-xl border border-violet-500/20 bg-violet-950/60 shadow-2xl backdrop-blur-md transition-opacity duration-300',
        visible ? 'opacity-100' : 'pointer-events-none opacity-0',
      )}
    >
      <div ref={containerRef} />
    </div>
  )
}
