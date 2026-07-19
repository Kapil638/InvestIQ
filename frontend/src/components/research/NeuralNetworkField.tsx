import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface NeuralNetworkFieldProps {
  className?: string
  /** Boost intensity while research is running */
  active?: boolean
}

interface Node {
  x: number
  y: number
  r: number
  phase: number
  speed: number
  hub: 'green' | 'purple' | 'blue'
  baseX: number
  baseY: number
  wobble: number
}

interface Edge {
  a: number
  b: number
  curve: number
}

interface Pulse {
  edge: number
  t: number
  speed: number
  hue: 'green' | 'purple' | 'blue'
}

function mulberry32(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildGraph(w: number, h: number): { nodes: Node[]; edges: Edge[] } {
  const rand = mulberry32(42)
  const nodes: Node[] = []

  const pushHub = (
    cx: number,
    cy: number,
    count: number,
    hub: Node['hub'],
    spreadX: number,
    spreadY: number,
  ) => {
    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + rand() * 0.4
      const dist = 0.15 + rand() * 0.85
      const x = cx + Math.cos(angle) * spreadX * dist
      const y = cy + Math.sin(angle) * spreadY * dist
      nodes.push({
        x,
        y,
        baseX: x,
        baseY: y,
        r: 1.4 + rand() * 2.8,
        phase: rand() * Math.PI * 2,
        speed: 1.6 + rand() * 2.4,
        hub,
        wobble: 2 + rand() * 5,
      })
    }
    // bright hub core
    nodes.push({
      x: cx,
      y: cy,
      baseX: cx,
      baseY: cy,
      r: 4.5 + rand() * 1.5,
      phase: rand() * Math.PI * 2,
      speed: 2.2,
      hub,
      wobble: 1.5,
    })
  }

  // Full-stage hubs — green left, purple right, blue bridge (matches reference fill)
  pushHub(w * 0.28, h * 0.42, 18, 'green', w * 0.22, h * 0.36)
  pushHub(w * 0.74, h * 0.52, 22, 'purple', w * 0.24, h * 0.38)
  // bridging + scatter nodes across the full width
  for (let i = 0; i < 16; i++) {
    const t = i / 15
    const x = w * (0.12 + t * 0.76) + (rand() - 0.5) * w * 0.06
    const y = h * (0.2 + rand() * 0.6)
    nodes.push({
      x,
      y,
      baseX: x,
      baseY: y,
      r: 1.2 + rand() * 2.2,
      phase: rand() * Math.PI * 2,
      speed: 1.8 + rand() * 2,
      hub: i % 3 === 0 ? 'green' : i % 3 === 1 ? 'purple' : 'blue',
      wobble: 3 + rand() * 4,
    })
  }

  const edges: Edge[] = []
  const maxDist = Math.min(w, h) * 0.34
  for (let i = 0; i < nodes.length; i++) {
    const candidates: { j: number; d: number }[] = []
    for (let j = i + 1; j < nodes.length; j++) {
      const dx = nodes[i].x - nodes[j].x
      const dy = nodes[i].y - nodes[j].y
      const d = Math.hypot(dx, dy)
      if (d < maxDist) candidates.push({ j, d })
    }
    candidates.sort((a, b) => a.d - b.d)
    const limit = Math.min(5, candidates.length)
    for (let k = 0; k < limit; k++) {
      if (rand() > 0.18) {
        edges.push({
          a: i,
          b: candidates[k].j,
          curve: (rand() - 0.5) * 32,
        })
      }
    }
  }

  return { nodes, edges }
}

function hubColor(hub: Node['hub'], alpha: number): string {
  if (hub === 'green') return `rgba(34, 255, 140, ${alpha})`
  if (hub === 'purple') return `rgba(200, 120, 255, ${alpha})`
  return `rgba(80, 180, 255, ${alpha})`
}

function curvedPoint(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  curve: number,
  t: number,
): { x: number; y: number } {
  const mx = (ax + bx) / 2
  const my = (ay + by) / 2
  const dx = bx - ax
  const dy = by - ay
  const len = Math.hypot(dx, dy) || 1
  const nx = (-dy / len) * curve
  const ny = (dx / len) * curve
  const cx = mx + nx
  const cy = my + ny
  const u = 1 - t
  return {
    x: u * u * ax + 2 * u * t * cx + t * t * bx,
    y: u * u * ay + 2 * u * t * cy + t * t * by,
  }
}

export function NeuralNetworkField({ className, active = true }: NeuralNetworkFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const frameRef = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let nodes: Node[] = []
    let edges: Edge[] = []
    let pulses: Pulse[] = []
    let width = 0
    let height = 0
    let dpr = 1
    let last = performance.now()

    const resize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = parent.clientWidth
      height = parent.clientHeight
      canvas.width = Math.max(1, Math.floor(width * dpr))
      canvas.height = Math.max(1, Math.floor(height * dpr))
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const graph = buildGraph(width, height)
      nodes = graph.nodes
      edges = graph.edges
      pulses = edges.slice(0, Math.min(edges.length, 40)).map((edge, i) => ({
        edge: i % edges.length,
        t: Math.random(),
        speed: 0.35 + Math.random() * 0.85,
        hue: nodes[edge.a]?.hub ?? 'purple',
      }))
    }

    resize()
    const ro = new ResizeObserver(resize)
    if (canvas.parentElement) ro.observe(canvas.parentElement)

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      const energy = active ? 1 : 0.35
      const speedMul = reduceMotion ? 0.15 : active ? 1.35 : 0.45

      ctx.clearRect(0, 0, width, height)

      // ambient full-stage glow (green left → purple right)
      const g1 = ctx.createRadialGradient(width * 0.28, height * 0.42, 0, width * 0.28, height * 0.42, width * 0.42)
      g1.addColorStop(0, `rgba(34, 255, 140, ${0.16 * energy})`)
      g1.addColorStop(1, 'rgba(34, 255, 140, 0)')
      ctx.fillStyle = g1
      ctx.fillRect(0, 0, width, height)

      const g2 = ctx.createRadialGradient(width * 0.74, height * 0.52, 0, width * 0.74, height * 0.52, width * 0.45)
      g2.addColorStop(0, `rgba(200, 100, 255, ${0.2 * energy})`)
      g2.addColorStop(1, 'rgba(200, 100, 255, 0)')
      ctx.fillStyle = g2
      ctx.fillRect(0, 0, width, height)

      // node drift
      for (const n of nodes) {
        n.phase += dt * n.speed * speedMul
        n.x = n.baseX + Math.sin(n.phase) * n.wobble * 0.35
        n.y = n.baseY + Math.cos(n.phase * 0.85) * n.wobble * 0.45
      }

      // edges
      for (const edge of edges) {
        const a = nodes[edge.a]
        const b = nodes[edge.b]
        if (!a || !b) continue
        const len = Math.hypot(b.x - a.x, b.y - a.y) || 1
        const ctrlX = (a.x + b.x) / 2 + (-(b.y - a.y) / len) * edge.curve
        const ctrlY = (a.y + b.y) / 2 + ((b.x - a.x) / len) * edge.curve
        const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y)
        grad.addColorStop(0, hubColor(a.hub, 0.35 * energy))
        grad.addColorStop(0.5, hubColor(b.hub === a.hub ? a.hub : 'blue', 0.55 * energy))
        grad.addColorStop(1, hubColor(b.hub, 0.35 * energy))

        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.quadraticCurveTo(ctrlX, ctrlY, b.x, b.y)
        ctx.strokeStyle = grad
        ctx.lineWidth = 0.9 + energy * 0.6
        ctx.shadowColor = hubColor(a.hub, 0.45)
        ctx.shadowBlur = 6 * energy
        ctx.stroke()
        ctx.shadowBlur = 0
      }

      // traveling pulses
      for (const pulse of pulses) {
        const edge = edges[pulse.edge]
        if (!edge) continue
        const a = nodes[edge.a]
        const b = nodes[edge.b]
        if (!a || !b) continue
        pulse.t += dt * pulse.speed * speedMul
        if (pulse.t > 1) {
          pulse.t = 0
          pulse.edge = Math.floor(Math.random() * edges.length)
          pulse.speed = 0.4 + Math.random() * 1.1
          const next = edges[pulse.edge]
          pulse.hue = nodes[next?.a ?? 0]?.hub ?? 'purple'
        }
        const p = curvedPoint(a.x, a.y, b.x, b.y, edge.curve, pulse.t)
        const color = hubColor(pulse.hue, 0.95)
        ctx.beginPath()
        ctx.arc(p.x, p.y, 2.2 + energy, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.shadowColor = color
        ctx.shadowBlur = 14 * energy
        ctx.fill()
        ctx.shadowBlur = 0
      }

      // nodes
      for (const n of nodes) {
        const pulse = 0.55 + 0.45 * Math.sin(n.phase * 1.6)
        const radius = n.r * (0.75 + pulse * 0.55) * (0.85 + energy * 0.25)
        const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, radius * 4)
        glow.addColorStop(0, hubColor(n.hub, 0.7 * pulse * energy))
        glow.addColorStop(0.4, hubColor(n.hub, 0.25 * energy))
        glow.addColorStop(1, hubColor(n.hub, 0))
        ctx.fillStyle = glow
        ctx.beginPath()
        ctx.arc(n.x, n.y, radius * 4, 0, Math.PI * 2)
        ctx.fill()

        ctx.beginPath()
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2)
        ctx.fillStyle = hubColor(n.hub, 0.85)
        ctx.shadowColor = hubColor(n.hub, 1)
        ctx.shadowBlur = 12 * energy
        ctx.fill()
        ctx.shadowBlur = 0

        ctx.beginPath()
        ctx.arc(n.x, n.y, Math.max(0.8, radius * 0.35), 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255, 255, 255, ${0.55 + pulse * 0.35})`
        ctx.fill()
      }

      frameRef.current = requestAnimationFrame(draw)
    }

    frameRef.current = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(frameRef.current)
      ro.disconnect()
    }
  }, [active])

  return (
    <div
      className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}
      aria-hidden
    >
      <canvas ref={canvasRef} className="absolute inset-0 size-full" />
    </div>
  )
}
