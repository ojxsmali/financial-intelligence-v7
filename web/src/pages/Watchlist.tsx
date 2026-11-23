import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { CompanyPicker } from '../components/CompanyPicker'
import { FilingsList, niceDate } from '../components/Panels'
import { EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { MAX_WATCH, useSettings } from '../lib/settings'

export function Watchlist() {
  const { watchlist, toggleWatch, lastSeen, markSeen, notify, setSymbol } = useSettings()
  const q = useQuery({
    queryKey: ['watchlist', watchlist.join(',')], queryFn: () => api.watchlist(watchlist),
    enabled: watchlist.length > 0, staleTime: 5 * 60_000, refetchInterval: 15 * 60_000,   // keeps itself up to date
  })
  // Snapshot "last seen" once per load, so "New" badges stay visible while the visitor reads them.
  const seenAtLoad = useRef<Record<string, string> | null>(null)
  if (seenAtLoad.current === null) seenAtLoad.current = { ...lastSeen }
  useEffect(() => {
    if (!q.data) return
    const latest: Record<string, string> = {}
    for (const item of q.data.items) if (item.events[0]) latest[item.symbol] = item.events[0].filing_date
    markSeen(latest)
  }, [q.data, markSeen])

  const add = (s: string) => {
    const r = toggleWatch(s)
    notify(r === 'full' ? `Your watchlist holds ${MAX_WATCH} companies; remove one first` : `${s} added to your watchlist`)
  }
  const items = q.data?.items ?? []
  const newCount = items.filter(i => {
    const seen = seenAtLoad.current?.[i.symbol]
    return seen !== undefined && i.events.some(e => e.filing_date > seen)
  }).length

  return (
    <>
      <PageHeader eyebrow="Watchlist" title="What’s new at the companies" accent="you follow."
        sub="Every filing a company makes with the SEC — results, annual and quarterly reports, executive changes, deals, warnings — explained in plain English and updated automatically. Your list is saved in this browser." />
      <div className="compare-pick">
        <ul className="pills-list" aria-label="Companies on your watchlist">
          {watchlist.map(s => (
            <li key={s}><span>{s}</span><button type="button" aria-label={`Stop following ${s}`} onClick={() => { toggleWatch(s); notify(`${s} removed from your watchlist`) }}>×</button></li>
          ))}
        </ul>
        <CompanyPicker label={`Follow a company (up to ${MAX_WATCH})`} onPick={add} exclude={watchlist} />
      </div>
      {!watchlist.length ? (
        <EmptyState kicker="Watchlist" title="You're not following any companies yet">Search above, or use “Follow” on any company page.</EmptyState>
      ) : q.isPending ? <Skeleton message="Checking SEC for new filings…" /> : q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : (
        <>
          <p className="caption" aria-live="polite">
            {newCount ? `${newCount} ${newCount === 1 ? 'company has' : 'companies have'} new filings since your last visit.` : 'No new filings since your last visit.'}
            {' '}Checked against SEC every 15 minutes while this page is open.
          </p>
          <div className="watch-grid">
            {items.map(item => (
              <article key={item.symbol} className="watch-card" aria-labelledby={`w-${item.symbol}`}>
                <header>
                  <span className="ticker">{item.symbol}</span>
                  <h2 id={`w-${item.symbol}`}>{item.name}</h2>
                  {item.ok && <Link className="more" to={{ pathname: '/', search: `?t=${item.symbol}` }} onClick={() => setSymbol(item.symbol)}>Open →</Link>}
                </header>
                {item.ok ? <FilingsList events={item.events} since={seenAtLoad.current?.[item.symbol]} compact />
                  : <p className="caption">{item.error}</p>}
                {item.events[0] && <p className="caption">Latest filing {niceDate(item.events[0].filing_date)}.</p>}
              </article>
            ))}
          </div>
        </>
      )}
    </>
  )
}
