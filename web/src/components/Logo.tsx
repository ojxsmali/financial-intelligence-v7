import { useMemo } from 'react'
import { markFaces } from '../lib/brandMark'

type Tone = 'bone' | 'cobalt' | 'ink'

/** The isometric three-column mark on an ink tile. `plain` drops the tile (for use on cobalt or ink panels). */
export function LogoMark({ size = 34, plain = false, tones, className = '' }: { size?: number; plain?: boolean; tones?: Tone[]; className?: string }) {
  const faces = useMemo(() => markFaces(plain ? 32 : 22, tones), [plain, tones])
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false" className={`brand-mark ${className}`}>
      {!plain && <rect width="32" height="32" rx="7.5" fill="#0B0B0D" />}
      <g transform={plain ? undefined : 'translate(5 5)'} strokeLinejoin="round">
        {faces.map((f, i) => <polygon key={i} points={f.points} fill={f.fill} className={`mk mk-${Math.floor(i / 3)}`} />)}
      </g>
    </svg>
  )
}

/** Wordmark: the plain statement in Geist, the second word in the serif italic the site uses for its one editorial phrase. */
export function Wordmark({ className = '' }: { className?: string }) {
  return <span className={`wordmark ${className}`}>Financial <em>Intelligence</em></span>
}
