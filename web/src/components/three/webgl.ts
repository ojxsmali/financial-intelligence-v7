import { useEffect, useState, useSyncExternalStore, type RefObject } from 'react'

let webgl: boolean | null = null
/** True when the browser can create a WebGL context. Checked once, cached. */
export function canUseWebGL() {
  if (webgl !== null) return webgl
  try {
    const c = document.createElement('canvas')
    webgl = !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')))
  } catch {
    webgl = false
  }
  return webgl
}

function media(query: string) {
  const subscribe = (cb: () => void) => {
    if (typeof window === 'undefined' || !window.matchMedia) return () => {}
    const mq = window.matchMedia(query)
    mq.addEventListener?.('change', cb)
    return () => mq.removeEventListener?.('change', cb)
  }
  const read = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false)
  return { subscribe, read }
}
const narrow = media('(max-width: 767px), (pointer: coarse)')
const reduce = media('(prefers-reduced-motion: reduce)')

/** Phones and touch screens: fewer objects, lower pixel ratio, no shadows, no pointer parallax. */
export function useCompact3D() {
  return useSyncExternalStore(narrow.subscribe, narrow.read, () => false)
}

export function useReducedMotion() {
  return useSyncExternalStore(reduce.subscribe, reduce.read, () => false)
}

/** Whether an element is on screen and the tab is visible — scenes stop rendering otherwise. */
export function useOnScreen(ref: RefObject<HTMLElement | null>) {
  const [seen, setSeen] = useState(true)
  const [tab, setTab] = useState(true)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver !== 'function') return
    const io = new IntersectionObserver(([e]) => setSeen(e.isIntersecting), { rootMargin: '80px' })
    io.observe(el)
    return () => io.disconnect()
  }, [ref])
  useEffect(() => {
    const on = () => setTab(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', on)
    return () => document.removeEventListener('visibilitychange', on)
  }, [])
  return seen && tab
}
