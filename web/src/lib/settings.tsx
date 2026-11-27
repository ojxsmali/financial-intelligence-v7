import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from './auth'
import type { Unit } from './format'
import { loadRemoteSettings, saveRemoteSettings, type RemoteSettings } from './supabase'

// App-wide view settings. The selected company lives in the URL (?t=AAPL) so links are shareable.
// Where the rest is kept depends on how the visitor entered:
//  - guest: sessionStorage only (this tab), starting from sample values; nothing leaves the browser.
//  - signed in: a per-user localStorage cache, synced to the user's own row in Supabase (RLS: owner only).
// Storage access is wrapped: it can be unavailable (private mode, blocked cookies).

export const MAX_COMPARE = 6
export const DEFAULT_COMPARE = ['AAPL', 'MSFT', 'GOOGL', 'NVDA']
export const DEFAULT_SYMBOL = 'AAPL'
export const YEAR_OPTIONS = [3, 4, 5, 6, 7, 8, 10]
export const MAX_WATCH = 15
export const DEFAULT_WATCH = ['AAPL', 'MSFT', 'NVDA']

type Store = { area: 'local' | 'session'; prefix: string }
let store: Store = { area: 'local', prefix: 'fip.' }
const area = () => (store.area === 'session' ? sessionStorage : localStorage)

function read<T>(key: string, fallback: T): T {
  try {
    const raw = area().getItem(store.prefix + key.replace(/^fip\./, ''))
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}
function write(key: string, value: unknown) {
  try { area().setItem(store.prefix + key.replace(/^fip\./, ''), JSON.stringify(value)) } catch { /* private mode etc. */ }
}

/** The guest's current values, if this tab has a guest session — used to seed a brand-new account. */
function guestSnapshot(): RemoteSettings | null {
  try {
    const get = (k: string) => { const v = sessionStorage.getItem('fip.g.' + k); return v === null ? undefined : JSON.parse(v) }
    const snap: RemoteSettings = { watchlist: get('watchlist'), compare: get('compare'), unit: get('unit'), years: get('years'), symbol: get('symbol') }
    return Object.values(snap).some(v => v !== undefined) ? snap : null
  } catch { return null }
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

/** Picks the storage for the current entry mode and remounts the settings when it changes (sign in / out). */
export function SettingsProvider({ children }: { children: ReactNode }) {
  const { mode, user } = useAuth()
  const ns = mode === 'user' && user ? `u:${user.id}` : mode === 'guest' ? 'guest' : 'none'
  store = mode === 'user' && user ? { area: 'local', prefix: `fip.u.${user.id}.` } : mode === 'guest' ? { area: 'session', prefix: 'fip.g.' } : { area: 'local', prefix: 'fip.' }
  return <SettingsState key={ns} userId={mode === 'user' ? user?.id : undefined}>{children}</SettingsState>
}

function SettingsState({ children, userId }: { children: ReactNode; userId?: string }) {
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

  // Signed in: pull the user's row once, then push changes (debounced). A new account starts from the guest's values.
  const synced = useRef(false)
  useEffect(() => {
    if (!userId) return
    let alive = true
    loadRemoteSettings(userId).then(remote => {
      if (!alive) return
      const seed = remote ?? guestSnapshot()
      if (seed) {
        if (seed.watchlist) { setWatchlist(seed.watchlist); write('fip.watchlist', seed.watchlist) }
        if (seed.compare) { setCompareState(seed.compare); write('fip.compare', seed.compare) }
        if (seed.unit) { setUnitState(seed.unit as Unit); write('fip.unit', seed.unit) }
        if (seed.years) { setYearsState(seed.years); write('fip.years', seed.years) }
        if (seed.lastSeen) { setLastSeen(seed.lastSeen); write('fip.lastSeen', seed.lastSeen) }
      }
      synced.current = true
    }).catch(() => { synced.current = true })
    return () => { alive = false }
  }, [userId])
  useEffect(() => {
    if (!userId || !synced.current) return
    const id = window.setTimeout(() => {
      saveRemoteSettings(userId, { watchlist, compare, unit, years, lastSeen, symbol }).catch(() => setToast('Couldn’t save to your account just now — your changes are kept in this browser'))
    }, 800)
    return () => window.clearTimeout(id)
  }, [userId, watchlist, compare, unit, years, lastSeen, symbol])

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
