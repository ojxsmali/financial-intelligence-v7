import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Unit } from './format'

// App-wide view settings. The selected company lives in the URL (?t=AAPL) so links are shareable;
// everything else is a per-browser preference kept in localStorage (wrapped: storage can be unavailable).

export const MAX_COMPARE = 6
export const DEFAULT_COMPARE = ['AAPL', 'MSFT', 'GOOGL', 'NVDA']
export const DEFAULT_SYMBOL = 'AAPL'
export const YEAR_OPTIONS = [3, 4, 5, 6, 7, 8, 10]
export const MAX_WATCH = 15
export const DEFAULT_WATCH = ['AAPL', 'MSFT', 'NVDA']

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}
function write(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode etc. */ }
}

type Settings = {
  symbol: string
  setSymbol: (s: string) => void
  unit: Unit
  setUnit: (u: Unit) => void
  years: number
  setYears: (n: number) => void
  compare: string[]
  setCompare: (list: string[]) => void
  addToCompare: (s: string) => 'added' | 'exists'
  toast: string
  notify: (message: string) => void
  watchlist: string[]
  toggleWatch: (s: string) => 'added' | 'removed' | 'full'
  lastSeen: Record<string, string>      // symbol -> newest filing date the visitor has seen
  markSeen: (entries: Record<string, string>) => void
}

const Ctx = createContext<Settings | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams()
  const urlSymbol = (params.get('t') ?? '').toUpperCase().slice(0, 12)
  const [storedSymbol, setStoredSymbol] = useState<string>(() => read('fip.symbol', DEFAULT_SYMBOL))
  const symbol = urlSymbol || storedSymbol
  const [unit, setUnitState] = useState<Unit>(() => read('fip.unit', 'auto'))
  const [years, setYearsState] = useState<number>(() => read('fip.years', 5))
  const [compare, setCompareState] = useState<string[]>(() => read('fip.compare', DEFAULT_COMPARE))
  const [toast, setToast] = useState('')
  const [watchlist, setWatchlist] = useState<string[]>(() => read('fip.watchlist', DEFAULT_WATCH))
  const [lastSeen, setLastSeen] = useState<Record<string, string>>(() => read('fip.lastSeen', {}))

  useEffect(() => { if (urlSymbol) { setStoredSymbol(urlSymbol); write('fip.symbol', urlSymbol) } }, [urlSymbol])
  useEffect(() => {
    if (!toast) return
    const id = window.setTimeout(() => setToast(''), 3200)
    return () => window.clearTimeout(id)
  }, [toast])

  const setSymbol = useCallback((s: string) => {
    const next = s.toUpperCase()
    setStoredSymbol(next)
    write('fip.symbol', next)
    setParams(prev => { const p = new URLSearchParams(prev); p.set('t', next); return p })
  }, [setParams])

  const setUnit = useCallback((u: Unit) => { setUnitState(u); write('fip.unit', u) }, [])
  const setYears = useCallback((n: number) => { setYearsState(n); write('fip.years', n) }, [])
  const setCompare = useCallback((list: string[]) => {
    const unique = [...new Set(list.map(s => s.toUpperCase()))].slice(-MAX_COMPARE)
    setCompareState(unique)
    write('fip.compare', unique)
  }, [])
  const addToCompare = useCallback((s: string) => {
    const sym = s.toUpperCase()
    if (compare.includes(sym)) return 'exists' as const
    setCompare([...compare, sym])
    return 'added' as const
  }, [compare, setCompare])

  const toggleWatch = useCallback((s: string) => {
    const sym = s.toUpperCase()
    if (watchlist.includes(sym)) {
      const next = watchlist.filter(x => x !== sym)
      setWatchlist(next); write('fip.watchlist', next)
      return 'removed' as const
    }
    if (watchlist.length >= MAX_WATCH) return 'full' as const
    const next = [...watchlist, sym]
    setWatchlist(next); write('fip.watchlist', next)
    return 'added' as const
  }, [watchlist])
  const markSeen = useCallback((entries: Record<string, string>) => {
    setLastSeen(prev => {
      const next = { ...prev, ...entries }
      write('fip.lastSeen', next)
      return next
    })
  }, [])

  const value = useMemo(() => ({
    symbol, setSymbol, unit, setUnit, years, setYears, compare, setCompare, addToCompare, toast, notify: setToast,
    watchlist, toggleWatch, lastSeen, markSeen,
  }), [symbol, setSymbol, unit, setUnit, years, setYears, compare, setCompare, addToCompare, toast,
    watchlist, toggleWatch, lastSeen, markSeen])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSettings(): Settings {
  const v = useContext(Ctx)
  if (!v) throw new Error('useSettings must be used inside SettingsProvider')
  return v
}
