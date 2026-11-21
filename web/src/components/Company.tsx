import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, type Company, type Financials, type Year } from '../lib/api'
import { useSettings } from '../lib/settings'
import { Chip, EmptyState, ErrorState, Notice, Skeleton } from './ui'

const ORIGIN: Record<string, [string, string]> = {
  live: ['Live SEC data', 'ok'],
  'disk cache': ['Cached SEC data (<12 h)', 'info'],
  'disk cache (stale)': ['Stale cache — refresh failed', 'warn'],
  'bundled snapshot': ['Bundled snapshot', 'warn'],
}

export function useCompany(symbol: string) {
  return useQuery({ queryKey: ['company', symbol], queryFn: () => api.company(symbol), staleTime: 15 * 60_000, retry: 1 })
}

export type CompanyCtx = { company: Company; fin: Financials; all: Year[]; shown: Year[] }

function Masthead({ company }: { company: Company }) {
  const e = company.entry!
  const fin = company.financials
  const last = fin?.years[fin.years.length - 1]
  const facts: [string, string][] = [
    ['Fiscal year-end', e.fiscal_year_end || '—'],
    ['Latest annual period', last?.period_end ?? '—'],
    ['Annual report', last ? `${last.form} · filed ${last.filed}` : '—'],
    ['Industry (SIC)', e.sic_description || '—'],
  ]
  const origin = fin ? ORIGIN[fin.origin] ?? [fin.origin, 'info'] : null
  return (
    <section className="company" aria-label="Company">
      <div className="company-id">
        <span className="ticker">{e.symbol}</span>
        <h2 className="company-name">{e.name}</h2>
        <div className="company-meta">
          {[e.exchange, e.instrument_type, e.cik ? `CIK ${e.cik}` : '', e.sector !== 'Unclassified' ? e.sector : '']
            .filter(Boolean).map((m, i) => <span key={i}>{m}</span>)}
        </div>
        {fin && origin && (
          <div className="tags">
            <Chip kind={origin[1]} dot>{origin[0]}</Chip>
            <Chip>{fin.basis} · {fin.currency}</Chip>
          </div>
        )}
      </div>
      <dl className="facts">
        {facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
    </section>
  )
}

/** Loads the selected company and renders the masthead plus every non-happy state; children get the data. */
export function CompanyGate({ children, masthead = true }: { children: (ctx: CompanyCtx) => ReactNode; masthead?: boolean }) {
  const { symbol, years } = useSettings()
  const q = useCompany(symbol)
  const client = useQueryClient()
  const [refreshing, setRefreshing] = useState(false)

  if (q.isPending) return <Skeleton />
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />
  const company = q.data

  if (company.status === 'not_listed' || !company.entry) {
    return (
      <EmptyState kicker="No match" title={company.error?.title ?? 'Symbol not found'}
        action={<Link className="btn" to={{ pathname: '/explorer' }}>Open Explorer</Link>}>
        {company.error?.message}
      </EmptyState>
    )
  }

  const refresh = async () => {
    setRefreshing(true)
    try {
      const fresh = await api.company(symbol, true)
      client.setQueryData(['company', symbol], fresh)
    } finally {
      setRefreshing(false)
    }
  }

  const head = masthead && <Masthead company={company} />
  if (company.status !== 'ok' || !company.financials) {
    const filings = company.profile?.annual_filings ?? []
    return (
      <>
        {head}
        <EmptyState kicker={company.status === 'not_company' ? 'Not applicable' : 'Data unavailable'}
          title={company.error?.title ?? 'Financial data unavailable'}
          action={company.error?.retryable && <button className="btn" onClick={refresh} disabled={refreshing}>{refreshing ? 'Retrying…' : 'Retry SEC request'}</button>}>
          <p>{company.error?.message}</p>
          {filings.length > 0 ? (
            <>
              <p>Annual filings on EDGAR for this registrant:</p>
              <ul>{filings.slice(0, 3).map(f => <li key={f.accession}><a href={f.url} target="_blank" rel="noopener noreferrer">{f.form} filed {f.filing_date}</a></li>)}</ul>
            </>
          ) : company.error?.edgar_url && company.error.kind !== 'config' ? (
            <p><a href={company.error.edgar_url} target="_blank" rel="noopener noreferrer">Open this registrant on SEC EDGAR</a></p>
          ) : null}
        </EmptyState>
      </>
    )
  }

  const fin = company.financials
  return (
    <>
      {head}
      {(company.notices ?? []).map((n, i) => <Notice key={i}>{n}</Notice>)}
      {company.newer_filing_note && <Notice kind="info">{company.newer_filing_note}</Notice>}
      {fin.excluded_note && <Notice kind="info">{fin.excluded_note}</Notice>}
      {children({ company, fin, all: fin.years, shown: fin.years.slice(-years) })}
      <div className="freshness">
        <p>Source: SEC XBRL Company Facts for CIK {fin.cik} · retrieved {fin.retrieved_at.slice(0, 16).replace('T', ' ')} UTC · {fin.years.length} annual periods available · amounts are reported values in {fin.currency}, scaled for display only. Not real-time market data.</p>
        <button className="btn ghost" onClick={refresh} disabled={refreshing}>{refreshing ? 'Checking SEC…' : 'Re-check SEC'}</button>
      </div>
    </>
  )
}
