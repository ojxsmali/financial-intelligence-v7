import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Chip, EmptyState, ErrorState, PageHeader } from '../components/ui'
import { api } from '../lib/api'
import { useSettings } from '../lib/settings'

function MultiSelect({ label, options, value, onChange, allLabel }: { label: string; options: string[]; value: string[]; onChange: (v: string[]) => void; allLabel: string }) {
  const id = useId()
  const summary = value.length === 0 ? allLabel : value.length === 1 ? value[0] : `${value.length} selected`
  return (
    <details className="multi">
      <summary aria-describedby={`${id}-l`}><span id={`${id}-l`} className="multi-label">{label}</span><span className="multi-value">{summary}</span></summary>
      <fieldset>
        <legend className="sr-only">{label}</legend>
        {options.map(o => (
          <label key={o} className="check">
            <input type="checkbox" checked={value.includes(o)} onChange={e => onChange(e.target.checked ? [...value, o] : value.filter(x => x !== o))} />
            {o}
          </label>
        ))}
        {value.length > 0 && <button type="button" className="btn ghost sm" onClick={() => onChange([])}>Clear</button>}
      </fieldset>
    </details>
  )
}

export function Explorer() {
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 10 * 60_000 })
  const { setSymbol, addToCompare, notify } = useSettings()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [exchange, setExchange] = useState<string[]>([])
  const [types, setTypes] = useState<string[]>(['Common stock', 'ADR / foreign issuer'])
  const [sectors, setSectors] = useState<string[]>([])
  const [filers, setFilers] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => { const t = window.setTimeout(() => setQuery(text.trim()), 220); return () => window.clearTimeout(t) }, [text])
  useEffect(() => setPage(1), [query, exchange, types, sectors, filers])

  const res = useQuery({
    queryKey: ['search', query, exchange, types, sectors, filers, page],
    queryFn: () => api.search({ q: query, exchange, type: types, sector: sectors, filers, page }),
    placeholderData: keepPreviousData, staleTime: 5 * 60_000,
  })
  const u = meta.data?.universe

  return (
    <>
      <PageHeader eyebrow="Explorer" title="Search every US‑listed" accent="security."
        sub={u ? `${u.total.toLocaleString('en-US')} securities from Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe BZX and IEX — ${u.companies.toLocaleString('en-US')} operating companies. Rebuilt from official exchange directories.` : 'Securities from Nasdaq, NYSE, NYSE American, NYSE Arca, Cboe BZX and IEX.'} />
      <div className="search-bar">
        <label htmlFor="ex-q" className="sr-only">Search by ticker or company name</label>
        <input id="ex-q" type="search" value={text} maxLength={80} onChange={e => setText(e.target.value)}
          placeholder="Ticker or company name — e.g. BRK.B, nvidia, Toyota, JPM" />
      </div>
      <div className="filters">
        <MultiSelect label="Exchange" allLabel="All exchanges" options={u?.exchanges ?? []} value={exchange} onChange={setExchange} />
        <MultiSelect label="Instrument type" allLabel="All types" options={meta.data?.instrument_types ?? []} value={types} onChange={setTypes} />
        <MultiSelect label="Sector (SEC SIC)" allLabel="All sectors" options={meta.data?.sectors ?? []} value={sectors} onChange={setSectors} />
        <label className="switch"><input type="checkbox" checked={filers} onChange={e => setFilers(e.target.checked)} /> SEC filers only</label>
      </div>

      {res.isError ? <ErrorState error={res.error} retry={() => res.refetch()} /> : !res.data ? <p className="loading" role="status">Searching…</p> : (
        <>
          <div className="tags" aria-live="polite">
            <Chip kind="info">{res.data.total.toLocaleString('en-US')} {res.data.total === 1 ? 'match' : 'matches'}</Chip>
            {query && <Chip>query: {query}</Chip>}
            {Object.entries(res.data.by_exchange).slice(0, 4).map(([k, v]) => <Chip key={k}>{k}: {v.toLocaleString('en-US')}</Chip>)}
          </div>
          {res.data.total === 0 ? (
            <EmptyState kicker="No match" title="No matching securities">Try a shorter query, a different spelling, or clear the filters. Tickers match with or without separators (BRK.B = BRK-B = BRKB).</EmptyState>
          ) : (
            <>
              <div className="table-wrap" role="region" aria-label="Search results" tabIndex={0}>
                <table className="table results">
                  <caption className="sr-only">Search results, page {res.data.page} of {res.data.pages}</caption>
                  <thead><tr><th scope="col">Symbol</th><th scope="col">Company</th><th scope="col">Exchange</th><th scope="col">Type</th><th scope="col">Sector</th><th scope="col">Country</th><th scope="col">CIK</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                  <tbody>
                    {res.data.rows.map(r => {
                      const usable = r.is_company && r.cik !== null
                      return (
                        <tr key={r.symbol}>
                          <th scope="row" className="mono">{r.symbol}</th>
                          <td className="name">{r.name}</td><td>{r.exchange}</td><td>{r.instrument_type}</td>
                          <td>{r.sector === 'Unclassified' ? '—' : r.sector}</td><td>{r.country || '—'}</td><td className="mono">{r.cik ?? '—'}</td>
                          <td className="actions">
                            <button className="btn sm" onClick={() => { setSymbol(r.symbol); navigate({ pathname: '/overview', search: `?t=${r.symbol}` }) }} aria-label={`Open ${r.symbol} in Overview`}>Open</button>
                            {usable && <button className="btn ghost sm" aria-label={`Add ${r.symbol} to comparison`}
                              onClick={() => notify(addToCompare(r.symbol) === 'added' ? `${r.symbol} added to the comparison` : `${r.symbol} is already in the comparison`)}>Compare</button>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <nav className="pager" aria-label="Result pages">
                <button className="btn ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</button>
                <span>Page {res.data.page} of {res.data.pages.toLocaleString('en-US')}</span>
                <button className="btn ghost" disabled={page >= res.data.pages} onClick={() => setPage(p => p + 1)}>Next</button>
              </nav>
            </>
          )}
        </>
      )}
      {u && (
        <details className="disclosure">
          <summary>Universe composition and sources</summary>
          <div className="grid-2">
            <table className="table"><caption>By exchange</caption><tbody>{Object.entries(u.by_exchange).map(([k, v]) => <tr key={k}><th scope="row">{k}</th><td>{v.toLocaleString('en-US')}</td></tr>)}</tbody></table>
            <table className="table"><caption>By instrument type</caption><tbody>{Object.entries(u.by_type).map(([k, v]) => <tr key={k}><th scope="row">{k}</th><td>{v.toLocaleString('en-US')}</td></tr>)}</tbody></table>
          </div>
          <p className="caption">Nasdaq Trader files created {u.nasdaq_file_created || '?'} / {u.other_file_created || '?'} (MMDDYYYYHHMM, US Eastern). Universe built {u.built_at || '?'} · origin: {u.origin}. Listings missing from the exchange directories are treated as delisted.</p>
        </details>
      )}
    </>
  )
}
