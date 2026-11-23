import { motion } from 'motion/react'
import { Component, useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { MESSAGES, RequestError, reportClientError, type Insight } from '../lib/api'

/** Poster-sized page title: a plain statement, optionally closed by one serif-italic phrase. */
export function PageHeader({ eyebrow, title, accent, sub }: { eyebrow: string; title: string; accent?: string; sub?: string }) {
  return (
    <header className="page-head">
      <div className="eyebrow">{eyebrow}</div>
      <motion.h1 initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 200, damping: 24 }}>
        {title}{accent && <> <em>{accent}</em></>}
      </motion.h1>
      {sub && <p className="sub">{sub}</p>}
    </header>
  )
}

/** A numbered report section; it rises into place the first time it scrolls into view. */
export function Section({ title, sub, children, aside }: { title: string; sub?: string; children: ReactNode; aside?: ReactNode }) {
  const id = useId()
  return (
    <motion.section className="section" aria-labelledby={id}
      initial={{ opacity: 0, y: 30, filter: 'blur(4px)' }} whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once: true, margin: '0px 0px -8% 0px' }} transition={{ type: 'spring', stiffness: 120, damping: 20 }}>
      <div className="section-head">
        <div><h2 id={id}>{title}</h2>{sub && <p className="section-sub">{sub}</p>}</div>
        {aside}
      </div>
      {children}
    </motion.section>
  )
}

export function Notice({ kind = 'warn', children }: { kind?: 'warn' | 'info' | 'bad'; children: ReactNode }) {
  const label = kind === 'info' ? 'Note' : kind === 'bad' ? 'Problem' : 'Caveat'
  return <div className={`notice ${kind}`} role={kind === 'bad' ? 'alert' : 'status'}><b>{label}:</b> {children}</div>
}

export function EmptyState({ kicker = 'Nothing to show', title, children, action }: { kicker?: string; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty" role="status">
      <div className="empty-k">{kicker}</div>
      <h2>{title}</h2>
      {children && <div className="empty-b">{children}</div>}
      {action && <div className="empty-a">{action}</div>}
    </div>
  )
}

export function Chip({ kind = '', dot = false, children }: { kind?: string; dot?: boolean; children: ReactNode }) {
  return <span className={`chip ${kind}`}>{dot && <span className="dot" aria-hidden="true" />}{children}</span>
}

/** Splits a formatted figure ("$478.83B", "+5.53%", "27.60%") into prefix, number and suffix. Null if it isn't one. */
export function parseFigure(text: string): { prefix: string; value: number; decimals: number; grouped: boolean; suffix: string } | null {
  const m = /^([^\d+\-−]*)([+\-−]?)([\d,]*\.?\d+)(.*)$/.exec(text)
  if (!m) return null
  const digits = m[3]
  const value = Number(digits.replace(/,/g, '')) * (m[2] === '-' || m[2] === '−' ? -1 : 1)
  if (!Number.isFinite(value)) return null
  const dot = digits.indexOf('.')
  return { prefix: m[1], value, decimals: dot === -1 ? 0 : digits.length - dot - 1, grouped: digits.includes(','), suffix: m[4] }
}

const reduceMotion = () => typeof window === 'undefined' || typeof window.matchMedia !== 'function' || window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * A reported figure that counts up once (≈0.9 s) when it first renders, then settles on the exact
 * reported text. Skipped entirely for reduced motion.
 */
export function Figure({ text, duration = 900 }: { text: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    const el = ref.current
    const f = parseFigure(text)
    if (!el || !f || reduceMotion() || typeof requestAnimationFrame !== 'function') return
    const sign = text.match(/^[^\d]*?([+\-−])/)?.[1] ?? ''
    const fmt = (n: number) => {
      const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: f.decimals, maximumFractionDigits: f.decimals, useGrouping: f.grouped })
      return f.prefix + (sign ? sign : '') + abs + f.suffix
    }
    let raf = 0
    let start = 0
    const tick = (ts: number) => {
      if (!start) start = ts
      const p = Math.min(1, (ts - start) / duration)
      el.textContent = p < 1 ? fmt(f.value * (1 - Math.pow(2, -10 * p))) : text
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); el.textContent = text }
  }, [text, duration])
  return <span ref={ref}>{text}</span>
}

/** Pointer position → --mx/--my for the KPI spotlight. */
const spotlight = (e: React.PointerEvent<HTMLElement>) => {
  const r = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
}

export type Kpi = { label: string; value: string; delta?: string; direction?: 'up' | 'down' | 'flat'; foot?: string; tip?: string; available?: boolean }

const GLYPH = { up: '▲', down: '▼', flat: '' }

export function KpiStrip({ items, label }: { items: Kpi[]; label: string }) {
  return (
    <dl className="kpis" aria-label={label}>
      {items.map((k, i) => (
        <motion.div key={k.label} className={k.available === false ? 'kpi na' : 'kpi'}
          drag dragSnapToOrigin dragElastic={0.45} dragTransition={{ bounceStiffness: 420, bounceDamping: 14 }}
          whileDrag={{ scale: 1.06, rotate: -1.5, zIndex: 5 }} whileHover={{ y: -4 }} whileTap={{ scale: 0.97 }}
          initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 260, damping: 24, delay: i * 0.05 }}
          onPointerMove={spotlight}>
          <dt className="kpi-label">
            {k.label}
            {k.tip && <abbr className="def" title={k.tip} aria-label={`Definition: ${k.tip}`}>i</abbr>}
          </dt>
          <dd className="kpi-value"><Figure text={k.value} /></dd>
          <dd className="kpi-foot">
            {k.delta && <span className={`delta ${k.direction ?? 'flat'}`}>{k.direction && GLYPH[k.direction] && <span aria-hidden="true">{GLYPH[k.direction]} </span>}{k.delta}</span>}
            {k.foot && <span>{k.foot}</span>}
          </dd>
        </motion.div>
      ))}
    </dl>
  )
}

export function Skeleton({ message = 'Loading annual filings from SEC EDGAR…' }: { message?: string }) {
  return (
    <div role="status" aria-live="polite" className="skeleton">
      <p className="loading">{message}</p>
      <div className="kpis" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => <div className="kpi" key={i}><div className="skel" style={{ height: 12, width: '60%' }} /><div className="skel" style={{ height: 26, width: '80%', marginTop: 10 }} /></div>)}
      </div>
      <div className="skel" style={{ height: 260 }} aria-hidden="true" />
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  // Only visitor-safe text is ever shown; RequestError messages are already curated, anything else is generic.
  const message = error instanceof RequestError ? error.message : MESSAGES.internal
  const ref = error instanceof RequestError ? error.ref : ''
  const title = error instanceof RequestError && ['upstream', 'unavailable', 'timeout'].includes(error.kind)
    ? 'Temporarily unavailable' : error instanceof RequestError && error.kind === 'network' ? 'You appear to be offline'
    : 'This couldn’t be loaded'
  return (
    <EmptyState kicker="Please try again" title={title} action={retry && <button className="btn" onClick={retry}>Try again</button>}>
      <p>{message}</p>
      {ref && <p className="ref">Reference: <span className="mono">{ref}</span></p>}
    </EmptyState>
  )
}

/** Catches rendering crashes so one broken view never blanks the site; reports privately, shows a calm message. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, { failed: boolean; resetKey?: string }> {
  state: { failed: boolean; resetKey?: string } = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  static getDerivedStateFromProps(props: { resetKey?: string }, state: { failed: boolean; resetKey?: string }) {
    return props.resetKey !== state.resetKey ? { failed: false, resetKey: props.resetKey } : null
  }

  componentDidCatch(error: unknown) {
    reportClientError(error instanceof Error ? `${error.name}: ${error.message}` : 'Unknown render error', 'render')
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <EmptyState kicker="Please try again" title="This page couldn’t be displayed"
        action={<button className="btn" onClick={() => location.reload()}>Reload the page</button>}>
        <p>{MESSAGES.internal}</p>
      </EmptyState>
    )
  }
}

/** WAI-ARIA tabs with roving focus (Arrow keys, Home, End). */
export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void; label: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: KeyboardEvent, i: number) => {
    const last = tabs.length - 1
    const next = e.key === 'ArrowRight' ? (i === last ? 0 : i + 1) : e.key === 'ArrowLeft' ? (i === 0 ? last : i - 1)
      : e.key === 'Home' ? 0 : e.key === 'End' ? last : -1
    if (next < 0) return
    e.preventDefault()
    onChange(tabs[next].id)
    refs.current[next]?.focus()
  }
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t, i) => (
        <button key={t.id} ref={el => { refs.current[i] = el }} role="tab" id={`tab-${t.id}`} aria-controls={`panel-${t.id}`}
          aria-selected={value === t.id} tabIndex={value === t.id ? 0 : -1} onClick={() => onChange(t.id)} onKeyDown={e => onKey(e, i)}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  return <div role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} tabIndex={0} className="tabpanel">{children}</div>
}

/** Single-choice button group exposed as a radio group. */
export function Segmented<T extends string>({ options, value, onChange, label, size = '' }:
  { options: { id: T; label: string }[]; value: T; onChange: (v: T) => void; label: string; size?: string }) {
  return (
    <div className={`segmented ${size}`} role="radiogroup" aria-label={label}>
      {options.map(o => (
        <button key={o.id} type="button" role="radio" aria-checked={value === o.id} onClick={() => onChange(o.id)}>{o.label}</button>
      ))}
    </div>
  )
}

export function InsightList({ items }: { items: Insight[] }) {
  return (
    <ul className="insights">
      {items.map((it, i) => (
        <li key={i} className="insight">
          <div className="insight-head"><span className={it.category === 'Flag' ? 'cat flag' : 'cat'}>{it.category === 'Calculation' ? 'Worked out' : it.category === 'Flag' ? 'Worth a look' : 'Reported'}</span><h3>{it.title}</h3></div>
          <p>{it.detail}</p>
          {(it.how || it.source) && (
            <dl className="explain">
              {it.how && <div><dt>How it's worked out</dt><dd>{it.how}</dd></div>}
              {it.source && <div><dt>Source</dt><dd>{it.source}</dd></div>}
            </dl>
          )}
          {it.rule && it.rule !== '—' && it.rule !== 'Methodology' && (
            <details className="formula"><summary>Formula</summary><code>{it.rule}</code></details>
          )}
        </li>
      ))}
    </ul>
  )
}

export type Row = { cells: string[]; cls?: string; neg?: boolean[]; marks?: string[] }

export function StatTable({ header, rows, caption }: { header: string[]; rows: Row[]; caption?: string }) {
  return (
    <div className="table-wrap" role="region" aria-label={caption ?? header[0]} tabIndex={0}>
      <table className="table">
        {caption && <caption>{caption}</caption>}
        <thead><tr>{header.map((h, i) => <th key={i} scope="col">{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className={r.cls}>
              {r.cells.map((c, i) => {
                const cls = [c === '—' || c === 'n/a' ? 'na' : '', r.neg?.[i] ? 'neg' : ''].join(' ').trim()
                const mark = r.marks?.[i]
                const content = <>{c}{mark && <span className="mark" title={mark} role="img" aria-label={mark}>●</span>}</>
                return i === 0 ? <th key={i} scope="row" className={cls}>{content}</th> : <td key={i} className={cls}>{content}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
