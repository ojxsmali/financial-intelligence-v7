import '@fontsource-variable/source-serif-4'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import './styles.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React, { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { EmptyState, ErrorBoundary } from './components/ui'
import { reportClientError } from './lib/api'
import { SettingsProvider } from './lib/settings'
import { Assistant } from './pages/Assistant'
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
  '/': 'Overview', '/explorer': 'Explorer', '/compare': 'Compare', '/statements': 'Statements',
  '/insights': 'Insights', '/assistant': 'Assistant', '/sources': 'Sources', '/screener': 'Screener', '/watchlist': 'Watchlist',
}

/** Per-page document title, and focus moved to <main> on navigation so screen readers announce the new page. */
function RouteEffects() {
  const { pathname } = useLocation()
  useEffect(() => {
    document.title = `${TITLES[pathname] ?? 'Not found'} · Financial Intelligence`
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

// Uncaught errors and promise rejections are reported privately; the page keeps working.
window.addEventListener('error', e => reportClientError(String(e.message || 'Script error'), 'window'))
window.addEventListener('unhandledrejection', e => {
  const r = e.reason as { message?: string } | undefined
  reportClientError(String(r?.message ?? r ?? 'Unhandled rejection'), 'promise')
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <SettingsProvider>
          <RouteEffects />
          <Layout>
            <RoutedBoundary>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/watchlist" element={<Watchlist />} />
              <Route path="/screener" element={<Screener />} />
              <Route path="/explorer" element={<Explorer />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/statements" element={<Statements />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="*" element={<EmptyState kicker="404" title="Page not found">Use the navigation above.</EmptyState>} />
            </Routes>
            </RoutedBoundary>
          </Layout>
        </SettingsProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
