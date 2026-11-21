import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import type { Insight } from '../lib/api'

export function PageHeader({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <header className="page-head">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      {sub && <p className="sub">{sub}</p>}
    </header>
  )
}

export function Section({ title, sub, children, aside }: { title: string; sub?: string; children: ReactNode; aside?: ReactNode }) {
  const id = useId()
  return (
    <section className="section" aria-labelledby={id}>
      <div className="section-head">
        <div><h2 id={id}>{title}</h2>{sub && <p className="section-sub">{sub}</p>}</div>
        {aside}
      </div>
      {children}
    </section>
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

export type Kpi = { label: string; value: string; delta?: string; direction?: 'up' | 'down' | 'flat'; foot?: string; tip?: string; available?: boolean }

const GLYPH = { up: '▲', down: '▼', flat: '' }

export function KpiStrip({ items, label }: { items: Kpi[]; label: string }) {
  return (
    <dl className="kpis" aria-label={label}>
      {items.map(k => (
        <div key={k.label} className={k.available === false ? 'kpi na' : 'kpi'}>
          <dt className="kpi-label">
            {k.label}
            {k.tip && <abbr className="def" title={k.tip} aria-label={`Definition: ${k.tip}`}>i</abbr>}
          </dt>
          <dd className="kpi-value">{k.value}</dd>
          <dd className="kpi-foot">
            {k.delta && <span className={`delta ${k.direction ?? 'flat'}`}>{k.direction && GLYPH[k.direction] && <span aria-hidden="true">{GLYPH[k.direction]} </span>}{k.delta}</span>}
            {k.foot && <span>{k.foot}</span>}
          </dd>
        </div>
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
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <EmptyState kicker="Request failed" title="This data could not be loaded" action={retry && <button className="btn" onClick={retry}>Try again</button>}>
      {message}
    </EmptyState>
  )
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
          <div className="insight-head"><span className={it.category === 'Flag' ? 'cat flag' : 'cat'}>{it.category}</span><h3>{it.title}</h3></div>
          <p>{it.detail}</p>
          <div className="rule"><span>Rule <code>{it.rule}</code></span><span>Evidence: {it.evidence}</span></div>
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
