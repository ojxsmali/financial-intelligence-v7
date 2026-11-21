import { useId } from 'react'
import { niceTicks, tickText } from '../lib/scale'

// Accessible, responsive charts without a charting library.
// * One scale per chart, stated in the header; straight segments between fiscal years (no smoothing).
// * Legend for 2+ series; each category (fiscal year) is ONE keyboard stop whose tooltip lists every series.
// * A "Data table" disclosure always carries the exact values.
// * Layout is in CSS percentages so labels stay legible from 320 px up.

// Colour-blind-validated categorical order (OKLab ΔE checks for protan/deutan/tritan, ≥3:1 on the surface).
// The hex values live in styles.css (--s1…--s6) so each theme can carry its own validated set.
export const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)']

export type ChartSeries = { label: string; color: string; values: (number | null)[]; texts: string[] }

function Legend({ series, kind }: { series: ChartSeries[]; kind: 'bar' | 'line' }) {
  if (series.length < 2) return null
  return (
    <ul className="legend" aria-label="Legend">
      {series.map(s => (
        <li key={s.label}><span className={kind === 'line' ? 'sw line' : 'sw'} style={{ background: s.color }} aria-hidden="true" />{s.label}</li>
      ))}
    </ul>
  )
}

export function DataTable({ title, categories, series, first = 'Fiscal year' }:
  { title: string; categories: string[]; series: ChartSeries[]; first?: string }) {
  return (
    <details className="datatable">
      <summary>Data table</summary>
      <div className="table-wrap">
        <table className="table">
          <caption>{title}</caption>
          <thead><tr><th scope="col">{first}</th>{series.map(s => <th scope="col" key={s.label}>{s.label}</th>)}</tr></thead>
          <tbody>
            {categories.map((c, i) => (
              <tr key={c}>
                <th scope="row">{c}</th>
                {series.map(s => {
                  const v = s.values[i]
                  return <td key={s.label} className={v === null ? 'na' : v < 0 ? 'neg' : ''}>{s.texts[i]}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

export function ColumnChart({ title, categories, series: all, kind = 'bar', unitText = '', prefix = '', suffix = '', height = 260 }: {
  title: string; categories: string[]; series: ChartSeries[]; kind?: 'bar' | 'line'
  unitText?: string; prefix?: string; suffix?: string; height?: number
}) {
  const figId = useId()
  const series = all.filter(s => s.values.some(v => v !== null))
  if (!series.length || !categories.length) {
    return <p className="chart-empty" role="note">No reported values to chart for this selection.</p>
  }
  const values = series.flatMap(s => s.values.filter((v): v is number => v !== null))
  const ticks = niceTicks(Math.min(...values), Math.max(...values))
  const lo = ticks[0]
  const hi = ticks[ticks.length - 1]
  const span = hi - lo || 1
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1
  const pct = (v: number) => ((v - lo) / span) * 100
  const n = categories.length
  const colW = 100 / n
  const group = 72
  const barW = group / series.length

  const lines = kind === 'line'
    ? series.map(s => {
        const segments: [number, number][][] = []
        let cur: [number, number][] = []
        s.values.forEach((v, i) => {
          if (v === null) { if (cur.length > 1) segments.push(cur); cur = []; return }
          cur.push([(i + 0.5) * colW, 100 - pct(v)])
        })
        if (cur.length > 1) segments.push(cur)
        return { color: s.color, segments }
      })
    : []

  return (
    <figure className="fig" aria-labelledby={`${figId}-t`}>
      <figcaption id={`${figId}-t`} className="sr-only">{title}</figcaption>
      <div className="fig-head"><Legend series={series} kind={kind} /><span className="fig-unit">{unitText}</span></div>
      <div className="chart" style={{ ['--h' as string]: `${height}px` }}>
        {ticks.map(t => (
          <div key={t} className={t === 0 ? 'grid zero' : 'grid'} style={{ bottom: `${pct(t)}%` }}>
            <span>{tickText(t, step, prefix, suffix)}</span>
          </div>
        ))}
        {kind === 'line' && (
          <svg className="lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
            {lines.flatMap((l, li) => l.segments.map((seg, si) => (
              <polyline key={`${li}-${si}`} fill="none" stroke={l.color} strokeWidth={2} strokeLinejoin="round"
                vectorEffect="non-scaling-stroke" points={seg.map(([x, y]) => `${x},${y}`).join(' ')} />
            )))}
          </svg>
        )}
        {kind === 'line' && series.flatMap(s => s.values.map((v, i) => v === null ? null : (
          <span key={`${s.label}-${i}`} className="pt" style={{ left: `${(i + 0.5) * colW}%`, bottom: `${pct(v)}%`, background: s.color, color: s.color, ['--i' as string]: i }} />
        )))}
        {categories.map((cat, i) => {
          const label = `${cat}: ` + series.map(s => `${s.label} ${s.texts[i]}`).join('; ')
          return (
            <div key={cat} className={i === n - 1 && n > 1 ? 'col last' : 'col'} tabIndex={0} role="img" aria-label={label}
              style={{ left: `${i * colW}%`, width: `${colW}%` }}>
              {kind === 'bar' && series.map((s, j) => {
                const v = s.values[i]
                if (v === null) return null
                return (
                  <span key={s.label} className={v < 0 ? 'bar neg' : 'bar pos'} style={{
                    left: `${(100 - group) / 2 + j * barW}%`, width: `calc(${barW}% - 2px)`,
                    bottom: `${pct(Math.min(v, 0))}%`, height: `${(Math.abs(v) / span) * 100}%`, background: s.color, ['--i' as string]: i,
                  }} />
                )
              })}
              <span className="x" aria-hidden="true">{cat}</span>
              <span className="tip" aria-hidden="true">
                <b>{cat}</b>
                {series.map(s => <span key={s.label} className="tip-row"><i style={{ background: s.color }} />{s.label}: {s.texts[i]}</span>)}
              </span>
            </div>
          )
        })}
      </div>
      <DataTable title={title} categories={categories} series={series} />
    </figure>
  )
}

export type HBarItem = { key: string; label: string; sub?: string; value: number | null; text: string; color: string }

/** Horizontal bars across entities, largest first; every bar carries its exact value as text. */
export function HBars({ title, unitText, items }: { title: string; unitText: string; items: HBarItem[] }) {
  const present = items.filter((i): i is HBarItem & { value: number } => i.value !== null).sort((a, b) => b.value - a.value)
  const missing = items.filter(i => i.value === null).map(i => i.label)
  if (!present.length) return <p className="chart-empty" role="note">None of the selected companies reports {title.toLowerCase()}.</p>
  const lo = Math.min(0, ...present.map(i => i.value))
  const hi = Math.max(0, ...present.map(i => i.value))
  const span = hi - lo || 1
  const zero = ((0 - lo) / span) * 100
  return (
    <figure className="fig" aria-label={title}>
      <div className="fig-head"><span className="fig-unit">{unitText}</span></div>
      <ul className="hbars">
        {present.map(i => (
          <li key={i.key}>
            <span className="lab">{i.label} {i.sub && <small>{i.sub}</small>}</span>
            <span className="track" aria-hidden="true">
              <span className="axis" style={{ left: `${zero}%` }} />
              <span className="fill" style={{ left: `${((Math.min(i.value, 0) - lo) / span) * 100}%`, width: `${Math.max((Math.abs(i.value) / span) * 100, 0.4)}%`, background: i.color }} />
            </span>
            <span className={i.value < 0 ? 'val neg' : 'val'}>{i.text}</span>
          </li>
        ))}
      </ul>
      {missing.length > 0 && <p className="fig-unit note">Not reported: {missing.join(', ')}</p>}
    </figure>
  )
}
