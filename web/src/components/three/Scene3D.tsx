/**
 * Lazy entry points for the 3D layer. three.js is fetched only when a scene is on the page and the
 * browser can do WebGL; otherwise — or if the GPU context dies — the caller's flat fallback stays.
 */
import { Component, lazy, Suspense, type ReactNode } from 'react'
import { canUseWebGL, useCompact3D, useReducedMotion } from './webgl'

const LazySkyline = lazy(() => import('./Skyline').then(m => ({ default: m.SkylineScene })))
const LazyMark = lazy(() => import('./Skyline').then(m => ({ default: m.MarkScene })))

class Guard extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export type SkylineProps = {
  values: (number | null)[]
  selected: number
  onPick: (i: number) => void
  label: string
  fallback: ReactNode
}

/** The Overview hero: each fiscal year as a column on a blueprint floor. Drag to turn it, tap a column to read it. */
export function Skyline3D({ fallback, ...props }: SkylineProps) {
  const compact = useCompact3D()
  const calm = useReducedMotion()
  if (!canUseWebGL()) return <>{fallback}</>
  return (
    <Guard fallback={fallback}>
      <Suspense fallback={fallback}>
        <LazySkyline {...props} compact={compact} calm={calm} />
      </Suspense>
    </Guard>
  )
}

/** The logo as an object: flick it to spin, tap it and the columns jump. */
export function Mark3D({ fallback, className = '' }: { fallback: ReactNode; className?: string }) {
  const compact = useCompact3D()
  const calm = useReducedMotion()
  if (!canUseWebGL()) return <>{fallback}</>
  return (
    <Guard fallback={fallback}>
      <Suspense fallback={fallback}>
        <LazyMark compact={compact} calm={calm} className={className} />
      </Suspense>
    </Guard>
  )
}
