import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { api, getContact, setContact } from '../lib/api'
import type { Unit } from '../lib/format'
import { useSettings, YEAR_OPTIONS } from '../lib/settings'
import { CompanyPicker } from './CompanyPicker'
import { Segmented } from './ui'

/** Mark: three rising bars on an ink tile — audited figures, year after year. */
export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false" className="brand-mark">
      <rect width="32" height="32" rx="6" fill="#16181B" />
      <path d="M7.5 25.5h17" stroke="#F5F3EE" strokeWidth="1.6" strokeLinecap="round" opacity=".55" />
      <rect x="8" y="16" width="4" height="7" rx="1" fill="#F5F3EE" />
      <rect x="14" y="12" width="4" height="11" rx="1" fill="#F5F3EE" />
      <rect x="20" y="7" width="4" height="16" rx="1" fill="#8FB8E3" />
    </svg>
  )
}

export const AUTHOR = { name: 'Ojas Mali', url: 'https://github.com/ojxsmali' }

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/screener', label: 'Screener' },
  { to: '/explorer', label: 'Explorer' },
  { to: '/compare', label: 'Compare' },
  { to: '/statements', label: 'Statements' },
  { to: '/insights', label: 'Insights' },
  { to: '/assistant', label: 'Assistant' },
  { to: '/sources', label: 'Sources' },
]

const UNITS: { id: Unit; label: string }[] = [
  { id: 'auto', label: 'Auto' }, { id: 'M', label: 'M' }, { id: 'B', label: 'B' }, { id: 'T', label: 'T' },
]

export function Layout({ children }: { children: ReactNode }) {
  const { symbol, setSymbol, unit, setUnit, years, setYears, addToCompare, toast, notify, watchlist, toggleWatch } = useSettings()
  const following = watchlist.includes(symbol)
  const { pathname } = useLocation()
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 10 * 60_000 })
  const search = `?t=${encodeURIComponent(symbol)}`
  const companyPage = ['/', '/statements', '/insights', '/sources'].includes(pathname)

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="masthead-bar">
        <div className="bar-inner">
          <NavLink to={{ pathname: '/', search }} className="brand" aria-label="Financial Intelligence — home">
            <LogoMark />
            <span className="brand-text">
              <span className="brand-name">Financial Intelligence</span>
              <span className="brand-sub">SEC fundamentals</span>
            </span>
          </NavLink>
          <nav aria-label="Pages" className="nav">
            {NAV.map(n => (
              <NavLink key={n.to} to={{ pathname: n.to, search }} end={n.to === '/'}>{n.label}</NavLink>
            ))}
          </nav>
        </div>
      </header>

      <div className="toolbar" role="region" aria-label="Company and display settings">
        <div className="bar-inner toolbar-inner">
          <div className="tool-company">
            <CompanyPicker label="Change company" compact onPick={setSymbol} placeholder={`${symbol} — search another company`} />
            <button className="btn ghost" type="button" onClick={() => {
              const r = addToCompare(symbol)
              notify(r === 'added' ? `${symbol} added to the comparison` : `${symbol} is already in the comparison`)
            }}>Add {symbol} to compare</button>
            <button className={following ? 'btn ghost on' : 'btn ghost'} type="button" aria-pressed={following} onClick={() => {
              const r = toggleWatch(symbol)
              notify(r === 'added' ? `Following ${symbol}: new SEC filings will show on your watchlist`
                : r === 'removed' ? `Stopped following ${symbol}` : 'Your watchlist is full (15 companies)')
            }}>{following ? `Following ${symbol}` : `Follow ${symbol}`}</button>
          </div>
          <div className="tool-display">
            <Segmented label="Display units" options={UNITS} value={unit} onChange={setUnit} size="sm" />
            <label className="years">
              <span>Years</span>
              <select value={years} onChange={e => setYears(Number(e.target.value))} aria-label="Fiscal years shown">
                {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
          </div>
        </div>
      </div>

      {meta.data && !meta.data.sec_contact_configured && companyPage && <ContactNotice />}

      <main id="main" className="main" tabIndex={-1}>{children}</main>

      <footer className="footer">
        <div className="bar-inner footer-inner">
          <div>
            <p className="credit">Designed &amp; built by <a href={AUTHOR.url} target="_blank" rel="noopener noreferrer">{AUTHOR.name}</a></p>
            <p>Data: SEC EDGAR XBRL Company Facts and the Nasdaq Trader symbol directory. Reported annual statements — not real-time market data and not investment advice.</p>
          </div>
          {meta.data && (
            <dl className="status">
              <div><dt>Listed securities</dt><dd>{meta.data.universe.total.toLocaleString('en-US')}</dd></div>
              <div><dt>Operating companies</dt><dd>{meta.data.universe.companies.toLocaleString('en-US')}</dd></div>
              <div><dt>Listings built</dt><dd>{meta.data.universe.built_at.slice(0, 10) || '—'}</dd></div>
              <div><dt>Gemini assistant</dt><dd>{meta.data.gemini_configured ? 'configured' : 'off'}</dd></div>
              <div><dt>Version</dt><dd>{meta.data.version}</dd></div>
            </dl>
          )}
        </div>
      </footer>
      <div className="toast" role="status" aria-live="polite">{toast}</div>
    </>
  )
}

function ContactNotice() {
  const [value, setValue] = useState(getContact())
  const [saved, setSaved] = useState(Boolean(getContact()))
  const valid = /^[^\s@<>()]+@[^\s@<>()]+\.[A-Za-z]{2,}$/.test(value.trim())
  return (
    <div className="bar-inner">
      <details className="contact" open={!saved}>
        <summary>Live SEC data needs a contact e-mail {saved ? '(set for this browser)' : '(not set — showing cached or bundled data)'}</summary>
        <form onSubmit={e => { e.preventDefault(); if (valid) { setContact(value.trim()); setSaved(true); location.reload() } }}>
          <p>The SEC asks automated clients to identify a contact e-mail. Yours is sent only to sec.gov as the request's User-Agent, kept in this browser, and never stored on the server.</p>
          <label htmlFor="sec-contact">Contact e-mail</label>
          <div className="row">
            <input id="sec-contact" type="email" value={value} onChange={e => setValue(e.target.value)} placeholder="you@example.com" />
            <button className="btn" disabled={!valid}>Save</button>
            {saved && <button type="button" className="btn ghost" onClick={() => { setContact(''); setValue(''); setSaved(false) }}>Clear</button>}
          </div>
        </form>
      </details>
    </div>
  )
}
