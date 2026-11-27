import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '@fontsource/libre-caslon-condensed/latin-400-italic.css'
import '@fontsource-variable/doto/wght.css'
import './styles.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import React, { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { EmptyState, ErrorBoundary } from './components/ui'
import { reportClientError } from './lib/api'
import { AuthProvider, useAuth } from './lib/auth'
import { SettingsProvider } from './lib/settings'
import { Assistant } from './pages/Assistant'
import { AuthPage } from './pages/AuthPage'
import { Landing } from './pages/Landing'
import { Brand } from './pages/Brand'
import { Compare } from './pages/Compare'
import { Explorer } from './pages/Explorer'
import { Insights } from './pages/Insights'
import { Overview } from './pages/Overview'
import { Screener } from './pages/Screener'
import { Sources } from './pages/Sources'
import { Statements } from './pages/Statements'
import { Watchlist } from './pages/Watchlist'

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })

const TITLES: Record<string, string> = {
  '/overview': 'Overview', '/explorer': 'Explorer', '/compare': 'Compare', '/statements': 'Statements',
  '/insights': 'Insights', '/assistant': 'Assistant', '/sources': 'Sources', '/screener': 'Screener', '/watchlist': 'Watchlist', '/brand': 'Brand kit',
}

/** Per-page document title, and focus moved to <main> on navigation so screen readers announce the new page. */
function RouteEffects() {
  const { pathname } = useLocation()
  useEffect(() => {
    document.title = pathname === '/' ? 'Financial Intelligence — audited fundamentals for every US-listed company'
      : pathname === '/login' ? 'Log in · Financial Intelligence' : pathname === '/signup' ? 'Create account · Financial Intelligence'
      : `${TITLES[pathname] ?? 'Not found'} · Financial Intelligence`
    const main = document.getElementById('main')
    if (main && document.activeElement !== document.body) main.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function RoutedBoundary({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  return <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
}

/** The app itself: open to guests and signed-in users. Anyone else starts on the landing page, then comes back here. */
function AppShell() {
  const { ready, mode } = useAuth()
  const { pathname, search } = useLocation()
  if (!ready) return <div className="entry-wait" role="status"><span className="loader" aria-hidden="true">{[0, 1, 2, 3, 4].map(i => <i key={i} style={{ ['--i' as string]: i }} />)}</span><span className="sr-only">Loading…</span></div>
  if (mode === 'none' && pathname !== '/brand') return <Navigate to={`/?next=${encodeURIComponent(pathname + search)}`} replace />
  return <Layout><RoutedBoundary><Outlet /></RoutedBoundary></Layout>
}

// Press feedback: every button-like control gets a ripple from the exact point it was pressed.
document.addEventListener('pointerdown', e => {
  const el = (e.target as HTMLElement | null)?.closest<HTMLElement>('.btn, .segmented button, .tabs button, .theme-toggle, .cmdk-hint, .metric-tabs button, .menu-btn, .year-rail button, .swatch')
  if (!el || (el as HTMLButtonElement).disabled) return
  const r = el.getBoundingClientRect()
  el.style.setProperty('--rx', `${e.clientX - r.left}px`)
  el.style.setProperty('--ry', `${e.clientY - r.top}px`)
  el.classList.remove('rippling')
  void el.offsetWidth // restart the animation on repeated presses
  el.classList.add('rippling')
}, { passive: true })
document.addEventListener('animationend', e => {
  if (e.animationName === 'fi-ripple') (e.target as HTMLElement).closest('.rippling')?.classList.remove('rippling')
})

// Uncaught errors and promise rejections are reported privately; the page keeps working.
window.addEventListener('error', e => reportClientError(String(e.message || 'Script error'), 'window'))
window.addEventListener('unhandledrejection', e => {
  const r = e.reason as { message?: string } | undefined
  reportClientError(String(r?.message ?? r ?? 'Unhandled rejection'), 'promise')
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
        <SettingsProvider>
          <RouteEffects />
          <Routes>
            <Route path="/" element={<RoutedBoundary><Landing /></RoutedBoundary>} />
            <Route path="/login" element={<RoutedBoundary><AuthPage kind="login" /></RoutedBoundary>} />
            <Route path="/signup" element={<RoutedBoundary><AuthPage kind="signup" /></RoutedBoundary>} />
            <Route element={<AppShell />}>
              <Route path="/overview" element={<Overview />} />
              <Route path="/watchlist" element={<Watchlist />} />
              <Route path="/screener" element={<Screener />} />
              <Route path="/explorer" element={<Explorer />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/statements" element={<Statements />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/brand" element={<Brand />} />
              <Route path="*" element={<EmptyState kicker="404 · no such page" title="This page isn’t in the filing."
                action={<><Link className="btn primary" to="/overview">Back to the overview</Link><Link className="btn" to="/screener">Open the screener</Link></>}>
                The address may be mistyped, or the page has moved. Every company is one search away: press <kbd>/</kbd>.</EmptyState>} />
            </Route>
          </Routes>
        </SettingsProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
    </MotionConfig>
  </StrictMode>,
)
