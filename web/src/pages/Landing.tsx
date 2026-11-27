import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useCompany } from '../components/Company'
import { LogoMark, Wordmark } from '../components/Logo'
import { Skyline3D } from '../components/three/Scene3D'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatMoney } from '../lib/format'

const SHOWCASE = 'AAPL'
const SPRING = { type: 'spring', stiffness: 260, damping: 20 } as const

/** Only same-site paths are followed after entering, never an absolute URL from the query string. */
export function safeNext(search: string) {
  const next = new URLSearchParams(search).get('next') ?? ''
  return next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\') && next !== '/' ? next : '/overview'
}

/** The three ways in. Rendered in the hero and again under "How it works". */
export function EntryActions({ variant, next }: { variant: 'hero' | 'cards'; next: string }) {
  const { mode, enterGuest } = useAuth()
  const navigate = useNavigate()
  const q = next === '/overview' ? '' : `?next=${encodeURIComponent(next)}`
  const guest = () => { enterGuest(); navigate(next) }

  if (mode === 'user') {
    return (
      <div className={`entry ${variant}`}>
        <Link className="btn entry-btn primary-bone" to={next}>Open your workspace <span aria-hidden="true">→</span></Link>
      </div>
    )
  }
  if (variant === 'hero') {
    return (
      <div className="entry hero">
        <Link className="btn entry-btn primary-bone" to={`/signup${q}`}>Create account</Link>
        <Link className="btn entry-btn ghost-bone" to={`/login${q}`}>Log in</Link>
        <button type="button" className="btn entry-btn ink" onClick={guest}>
          Continue as guest <span aria-hidden="true">→</span>
        </button>
      </div>
    )
  }
  const cards = [
    { k: 'Create account', d: 'E-mail and password. Your watchlist, comparisons and display settings follow you to any device.', to: `/signup${q}`, cls: 'cobalt' },
    { k: 'Log in', d: 'Pick up where you left off: the same companies, the same filings marked as read.', to: `/login${q}`, cls: 'bone' },
    { k: 'Continue as guest', d: 'One click, no form. Opens the full app with a sample watchlist and comparison. Nothing is saved.', to: '', cls: 'ink' },
  ]
  return (
    <ul className="entry cards">
      {cards.map((c, i) => (
        <motion.li key={c.k} initial={{ y: 40, rotate: i === 1 ? 0 : i === 0 ? -2 : 2 }} whileInView={{ y: 0, rotate: 0 }} viewport={{ once: true }}
          transition={{ ...SPRING, delay: i * 0.06 }}>
          {c.to ? (
            <motion.div whileHover={{ y: -8 }} whileTap={{ scale: 0.96 }} transition={{ type: 'spring', stiffness: 420, damping: 18 }}>
              <Link className={`entry-card ${c.cls}`} to={c.to}><b>{c.k}</b><span>{c.d}</span><i aria-hidden="true">→</i></Link>
            </motion.div>
          ) : (
            <motion.div whileHover={{ y: -8 }} whileTap={{ scale: 0.96 }} transition={{ type: 'spring', stiffness: 420, damping: 18 }}>
              <button type="button" className={`entry-card ${c.cls}`} onClick={guest}><b>{c.k}</b><span>{c.d}</span><i aria-hidden="true">→</i></button>
            </motion.div>
          )}
        </motion.li>
      ))}
    </ul>
  )
}

function Showcase() {
  const q = useCompany(SHOWCASE)
  const fin = q.data?.status === 'ok' ? q.data.financials : null
  const years = fin?.years.slice(-6) ?? []
  const [picked, setPicked] = useState<number | null>(null)
  const idx = picked ?? years.length - 1
  const values = years.map(y => y.values.revenue ?? null)
  const y = years[idx]
  const money = (v: number | null) => formatMoney(v, fin?.currency ?? 'USD', 'auto')
  const label = years.length ? `Apple Inc. revenue by fiscal year: ${years.map((yy, i) => `FY${yy.fiscal_year} ${money(values[i])}`).join('; ')}` : ''

  return (
    <div className="land-show">
      <div className="sky land-sky">
        {years.length ? (
          <Skyline3D values={values} selected={idx} onPick={setPicked} label={label}
            fallback={<div className="land-flat" aria-hidden="true">{values.map((v, i) => <i key={i} className={i === idx ? 'on' : ''} style={{ height: `${v && Math.max(...values.map(x => x ?? 0)) ? (v / Math.max(...values.map(x => x ?? 0))) * 100 : 4}%` }} />)}</div>} />
        ) : q.isError ? <div className="land-flat-mark"><LogoMark size={200} plain /></div>
          : <div className="land-loading" role="status"><span className="loader" aria-hidden="true">{[0, 1, 2, 3, 4].map(i => <i key={i} style={{ ['--i' as string]: i }} />)}</span><span>Loading Apple’s 10-K figures…</span></div>}
      </div>
      {y && (
        <motion.div className="land-readout" key={y.fiscal_year} initial={{ y: 10, opacity: 0.4 }} animate={{ y: 0, opacity: 1 }} transition={SPRING} aria-live="polite">
          <span className="ticker">AAPL</span>
          <span className="land-ro-name">Apple Inc. · revenue · FY{y.fiscal_year}</span>
          <b>{money(values[idx])}</b>
          <small>{y.form} filed {y.filed} · tap a column</small>
        </motion.div>
      )}
    </div>
  )
}

export function Landing() {
  const { ready, mode } = useAuth()
  const loc = useLocation()
  const next = safeNext(loc.search)
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 10 * 60_000 })
  const listed = meta.data ? meta.data.universe.total.toLocaleString('en-US') : '13,000+'
  const companies = meta.data ? meta.data.universe.companies.toLocaleString('en-US') : '5,500+'

  // Signed-in visitors go straight to the app — unless they clicked the logo to come back here.
  if (ready && mode === 'user' && !(loc.state as { home?: boolean } | null)?.home) return <Navigate to={next} replace />

  const words = ['Every', 'US-listed', 'company’s', 'audited', 'books,']
  return (
    <div className="landing">
      <a className="skip" href="#land-main">Skip to content</a>
      <header className="land-bar">
        <div className="bar-inner land-bar-inner">
          <Link to="/" state={{ home: true }} className="brand" aria-label="Financial Intelligence — home page"><LogoMark /><Wordmark className="brand-name" /></Link>
          <nav className="land-nav" aria-label="Account">
            {mode === 'user' ? <Link className="btn sm bone" to={next}>Open workspace</Link> : <>
              <Link className="btn sm ghost" to="/login">Log in</Link>
              <Link className="btn sm primary" to="/signup">Create account</Link>
            </>}
          </nav>
        </div>
      </header>

      <main id="land-main" tabIndex={-1}>
        <section className="slab land-hero" aria-labelledby="land-title">
          <div className="slab-inner land-hero-inner">
            <div className="land-copy">
              <p className="ledger-tag"><span className="ticker">SEC EDGAR</span><span>{listed} listed securities</span><span>10-K · 20-F · 40-F</span></p>
              <h1 id="land-title" className="land-title">
                {words.map((w, i) => (
                  <motion.span key={i} className="w" initial={{ opacity: 0, y: '0.7em', rotate: 5 }} animate={{ opacity: 1, y: 0, rotate: 0 }}
                    transition={{ ...SPRING, delay: i * 0.06 }}>{w}{' '}</motion.span>
                ))}
                <motion.em initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} transition={{ ...SPRING, delay: 0.4 }}>in 3D.</motion.em>
              </h1>
              <p className="land-dek">Statements, a verified screener, a filings watchlist and a plain-English health check — straight from SEC filings, with every number traced to its source.</p>
              <EntryActions variant="hero" next={next} />
              <p className="land-fine">Guest mode needs no sign-up and saves nothing. Not investment advice.</p>
            </div>
            <Showcase />
          </div>
        </section>

        <section className="land-stats" aria-label="In numbers">
          <div className="bar-inner land-stats-inner">
            {[[listed, 'US-listed securities, rebuilt daily'], [companies, 'operating companies with SEC filings'], ['10', 'fiscal years of audited statements'], ['9', 'yes/no tests in the health check']].map(([n, t]) => (
              <div key={t}><b>{n}</b><span>{t}</span></div>
            ))}
          </div>
        </section>

        <section className="bar-inner land-how" aria-labelledby="how-title">
          <div className="page-tag"><span className="page-no">→</span><span className="eyebrow">How it works</span></div>
          <h2 id="how-title" className="land-h2">Three steps, <em>one source of truth.</em></h2>
          <ol className="steps">
            {[
              ['Choose how to start', 'Create an account to keep your work, log in, or look around as a guest with sample companies.'],
              ['Open any company', 'Search 13,000+ listings. Each one opens on its audited history: drag the 3D skyline, switch the figure, read the year.'],
              ['Rank, compare, follow', 'Screen thousands of filers, line companies up side by side, and follow new SEC filings explained in plain English.'],
            ].map(([h, d], i) => (
              <motion.li key={h} initial={{ y: 30 }} whileInView={{ y: 0 }} viewport={{ once: true }} transition={{ ...SPRING, delay: i * 0.06 }}>
                <span className="step-no">0{i + 1}</span><b>{h}</b><span>{d}</span>
              </motion.li>
            ))}
          </ol>
          <EntryActions variant="cards" next={next} />
        </section>

        <section className="bar-inner land-inside" aria-labelledby="inside-title">
          <h2 id="inside-title" className="land-h2">What’s <em>inside.</em></h2>
          <ul className="inside-grid">
            {[
              ['Overview', 'Ten years of revenue, profit and cash flow on one scale, with the filing behind each figure.'],
              ['Screener', 'Rank every SEC filer by margin, growth or size; the leaders are re-checked against their annual reports.'],
              ['Watchlist', 'New 8-Ks, 10-Qs and 10-Ks for the companies you follow, translated into plain English.'],
              ['Health check', 'Nine yes/no tests on the latest two annual reports — the Piotroski method, explained.'],
              ['Compare', 'Up to six companies side by side, with fiscal-year and currency checks.'],
              ['Assistant', 'A Gemini research assistant that only sees the reported figures, and says so.'],
            ].map(([h, d]) => <li key={h}><b>{h}</b><span>{d}</span></li>)}
          </ul>
        </section>
      </main>

      <footer className="land-foot">
        <div className="tape" aria-hidden="true">
          <div className="tape-track">{[0, 1].map(k => <span key={k}>Audited figures <em>plainly told</em> ✦ Straight from SEC EDGAR ✦ Every number has a source ✦&nbsp;</span>)}</div>
        </div>
        <div className="bar-inner land-foot-inner">
          <p className="credit">Designed &amp; built by <a href="https://github.com/ojxsmali" target="_blank" rel="noopener noreferrer">Ojas Mali</a></p>
          <p>Data: SEC EDGAR XBRL Company Facts and the Nasdaq Trader symbol directory. Reported annual statements — not real-time market data and not investment advice.</p>
          <p className="footer-links"><Link to="/brand">Brand kit</Link><a href="https://github.com/ojxsmali/financial-intelligence-v7" target="_blank" rel="noopener noreferrer">Source on GitHub</a></p>
        </div>
      </footer>
    </div>
  )
}
