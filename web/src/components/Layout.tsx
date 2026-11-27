import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { api, getContact, setContact } from '../lib/api'
import type { Unit } from '../lib/format'
import { useSettings, YEAR_OPTIONS } from '../lib/settings'
import { NAV } from '../lib/nav'
import { CompanyPicker } from './CompanyPicker'
import { LogoMark, Wordmark } from './Logo'
import { Segmented } from './ui'

const MAIN_NAV = NAV.filter(n => n.to !== '/brand')

export const AUTHOR = { name: 'Ojas Mali', url: 'https://github.com/ojxsmali' }

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
  const [palette, setPalette] = useState(false)
  const [menu, setMenu] = useState(false)
  useEffect(() => { setMenu(false) }, [pathname])
  useEffect(() => {
    document.documentElement.classList.toggle('menu-open', menu)
  }, [menu])
  const navigate = useNavigate()

  // ⌘K / Ctrl+K (or "/" outside a field) opens the command palette.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) {
        e.preventDefault()
        setPalette(p => !p)
      } else if (e.key === 'Escape') { setPalette(false); setMenu(false) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="masthead-bar">
        <div className="bar-inner">
          <NavLink to={{ pathname: '/', search }} className="brand" aria-label="Financial Intelligence — home">
            <LogoMark />
            <Wordmark className="brand-name" />
          </NavLink>
          <nav aria-label="Pages" className="nav">
            {MAIN_NAV.map(n => (
              <NavLink key={n.to} to={{ pathname: n.to, search }} end={n.to === '/'}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="fi-nav-pill" className="nav-pill" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
                    {n.label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <button type="button" className="cmdk-hint" onClick={() => setPalette(true)} aria-label="Search companies and pages" aria-keyshortcuts="Control+K Meta+K">
            <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" /><path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
            <span className="cmdk-text">Search</span><kbd>⌘K</kbd>
          </button>
          <ThemeToggle />
          <button type="button" className="menu-btn" aria-expanded={menu} aria-controls="menu-sheet" onClick={() => setMenu(m => !m)}>
            <span className="menu-icon" aria-hidden="true"><i /><i /></span>
            <span>{menu ? 'Close' : 'Menu'}</span>
          </button>
        </div>
      </header>

      <AnimatePresence>
        {menu && (
          <motion.nav id="menu-sheet" className="menu-sheet" aria-label="All pages"
            initial={{ clipPath: 'inset(0 0 100% 0)' }} animate={{ clipPath: 'inset(0 0 0% 0)' }} exit={{ clipPath: 'inset(0 0 100% 0)' }}
            transition={{ type: 'spring', stiffness: 260, damping: 32 }}>
            <ol>
              {NAV.map((n, i) => (
                <motion.li key={n.to} initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', stiffness: 320, damping: 24, delay: 0.06 + i * 0.035 }}>
                  <NavLink to={{ pathname: n.to, search }} end={n.to === '/'} onClick={() => setMenu(false)}>
                    <span className="menu-no">{String(i + 1).padStart(2, '0')}</span>{n.label}
                  </NavLink>
                </motion.li>
              ))}
            </ol>
            <p className="menu-foot">Designed &amp; built by {AUTHOR.name} · SEC EDGAR data, not advice</p>
          </motion.nav>
        )}
      </AnimatePresence>

      <div className="toolbar" role="region" aria-label="Company and display settings">
        <div className="bar-inner toolbar-inner">
          <div className="tool-company">
            <CompanyPicker label="Change company" compact onPick={setSymbol} placeholder={`${symbol} — search another company`} />
            <button className="btn ghost" type="button" aria-label={`Add ${symbol} to compare`} onClick={() => {
              const r = addToCompare(symbol)
              notify(r === 'added' ? `${symbol} added to the comparison` : `${symbol} is already in the comparison`)
            }}><span aria-hidden="true">+</span> Compare</button>
            <button className={following ? 'btn ghost on' : 'btn ghost'} type="button" aria-pressed={following} onClick={() => {
              const r = toggleWatch(symbol)
              notify(r === 'added' ? `Following ${symbol}: new SEC filings will show on your watchlist`
                : r === 'removed' ? `Stopped following ${symbol}` : 'Your watchlist is full (15 companies)')
            }}><span aria-hidden="true">{following ? '★' : '☆'}</span> {following ? 'Following' : 'Follow'}<span className="sr-only"> {symbol}</span></button>
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

      <main id="main" className="main" tabIndex={-1}><div key={pathname} className="page-settle">{children}</div></main>

      <footer className="footer">
        <div className="tape" aria-hidden="true">
          <div className="tape-track">
            {Array.from({ length: 2 }, (_, k) => (
              <span key={k}>Audited figures <em>plainly told</em> ✦ Straight from SEC EDGAR ✦ {meta.data ? meta.data.universe.total.toLocaleString('en-US') : '13,000+'} listed securities ✦ Every number has a source ✦&nbsp;</span>
            ))}
          </div>
        </div>
        <div className="bar-inner footer-inner">
          <div className="footer-brand">
            <LogoMark size={56} />
            <p className="credit">Designed &amp; built by <a href={AUTHOR.url} target="_blank" rel="noopener noreferrer">{AUTHOR.name}</a></p>
            <p>Data: SEC EDGAR XBRL Company Facts and the Nasdaq Trader symbol directory. Reported annual statements — not real-time market data and not investment advice.</p>
            <p className="footer-links"><NavLink to={{ pathname: '/brand', search }}>Brand kit</NavLink><a href="https://github.com/ojxsmali/financial-intelligence-v7" target="_blank" rel="noopener noreferrer">Source on GitHub</a><NavLink to={{ pathname: '/sources', search }}>Methodology</NavLink></p>
          </div>
          {meta.data && (
            <dl className="status">
              <div><dt>Listed securities</dt><dd>{meta.data.universe.total.toLocaleString('en-US')}</dd></div>
              <div><dt>Operating companies</dt><dd>{meta.data.universe.companies.toLocaleString('en-US')}</dd></div>
              <div><dt>Listings built</dt><dd>{meta.data.universe.built_at.slice(0, 10) || '—'}</dd></div>
              <div><dt>AI assistant</dt><dd>{meta.data.gemini_configured ? 'Gemini, on' : 'off on this deploy'}</dd></div>
              <div><dt>Version</dt><dd>{meta.data.version}</dd></div>
            </dl>
          )}
        </div>
      </footer>
      <div className="toast" role="status" aria-live="polite">{toast}</div>

      <AnimatePresence>
        {palette && (
          <>
            <motion.div key="bd" className="cmdk-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setPalette(false)} />
            <motion.div key="cmdk" className="cmdk" role="dialog" aria-modal="true" aria-label="Search companies and pages"
              initial={{ opacity: 0, y: -16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -10, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 420, damping: 32 }}>
              <CompanyPicker label="Open a company" autoFocus placeholder="Type a ticker or company name — 13,000+ listed" onPick={s => { setSymbol(s); setPalette(false) }} />
              <p className="cmdk-label">Go to</p>
              <nav className="cmdk-pages" aria-label="Pages">
                {NAV.map(n => (
                  <a key={n.to} href={n.to + search} onClick={e => { e.preventDefault(); navigate({ pathname: n.to, search }); setPalette(false) }}>
                    <span aria-hidden="true">→</span>{n.label}
                  </a>
                ))}
              </nav>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

type Theme = 'light' | 'dark'

/** Light "paper" or dark "ink". The choice is remembered; the first visit follows the OS. */
function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'))
  const next: Theme = theme === 'dark' ? 'light' : 'dark'
  const apply = () => {
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('fip.theme', next) } catch { /* private mode: the choice lasts this visit */ }
    setTheme(next)
  }
  return (
    <button type="button" className="theme-toggle" onClick={apply} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}>
      {theme === 'dark' ? (
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" /></svg>
      )}
      <span className="theme-label">{theme === 'dark' ? 'Ink' : 'Paper'}</span>
    </button>
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
