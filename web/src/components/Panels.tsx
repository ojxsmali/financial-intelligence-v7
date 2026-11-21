import type { FilingEvent, Health } from '../lib/api'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-11-03" -> "3 Nov 2026" (no time-zone shifting: SEC dates are calendar dates). */
export function niceDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}` : iso
}

/** "3 days ago" style relative date against today (UTC calendar days). */
export function daysAgo(iso: string, today = new Date()): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  if (!m) return ''
  const then = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  const now = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())
  const d = Math.round((now - then) / 86_400_000)
  if (d <= 0) return 'today'
  if (d === 1) return 'yesterday'
  if (d < 31) return `${d} days ago`
  if (d < 365) return `${Math.round(d / 30.4)} months ago`
  return `${Math.round(d / 365)} years ago`
}

const IMPORTANCE_LABEL: Record<string, string> = { alert: 'Important', high: 'Key filing' }

export function FilingsList({ events, since, compact = false }: { events: FilingEvent[]; since?: string; compact?: boolean }) {
  if (!events.length) return <p className="caption">No recent filings found.</p>
  return (
    <ol className={compact ? 'filings compact' : 'filings'}>
      {events.map(e => {
        const isNew = since !== undefined && e.filing_date > since
        return (
          <li key={e.accession} className={`filing ${e.importance}`}>
            <div className="filing-date">
              <time dateTime={e.filing_date}>{niceDate(e.filing_date)}</time>
              <span className="muted">{daysAgo(e.filing_date)}</span>
            </div>
            <div className="filing-body">
              <div className="filing-title">
                <a href={e.url} target="_blank" rel="noopener noreferrer">{e.title}</a>
                {isNew && <span className="chip ok">New</span>}
                {IMPORTANCE_LABEL[e.importance] && <span className={e.importance === 'alert' ? 'chip bad' : 'chip info'}>{IMPORTANCE_LABEL[e.importance]}</span>}
              </div>
              {!compact && <p className="filing-detail">{e.detail} <span className="muted">Form {e.form}.</span></p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

const VERDICT_CLASS: Record<string, string> = { Strong: 'ok', Average: 'info', Weak: 'bad', 'Not enough data': '' }

export function HealthPanel({ health }: { health: Health }) {
  const groups = [...new Set(health.checks.map(c => c.group))]
  return (
    <div className="health">
      <div className="health-head">
        <div className="health-score" role="img" aria-label={`${health.passed} of ${health.available} checks passed`}>
          <span className="big">{health.passed}</span><span className="of">/ {health.available}</span>
        </div>
        <div>
          <span className={`chip ${VERDICT_CLASS[health.verdict]}`}>{health.verdict}</span>
          <p className="health-summary">{health.summary}</p>
          <div className="pips" aria-hidden="true">
            {health.checks.map(c => <span key={c.key} className={c.passed === null ? 'pip na' : c.passed ? 'pip yes' : 'pip no'} />)}
          </div>
        </div>
      </div>
      {groups.map(g => (
        <div key={g} className="health-group">
          <h3>{g}</h3>
          <ul>
            {health.checks.filter(c => c.group === g).map(c => (
              <li key={c.key} className={c.passed === null ? 'na' : c.passed ? 'yes' : 'no'}>
                <span className="mark-icon" aria-hidden="true">{c.passed === null ? '–' : c.passed ? '✓' : '✗'}</span>
                <div>
                  <p className="q">{c.question} <span className="sr-only">{c.passed === null ? 'Not available.' : c.passed ? 'Yes.' : 'No.'}</span></p>
                  <p className="d">{c.detail}</p>
                  <details><summary>Why it matters</summary><p>{c.why}</p></details>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <p className="caption">Method: the Piotroski F-score, nine yes/no tests on reported annual figures comparing the latest year with the one before. A fixed rule set — not AI, not a forecast or recommendation. Tests the filing data can't support are skipped, not failed.</p>
    </div>
  )
}
