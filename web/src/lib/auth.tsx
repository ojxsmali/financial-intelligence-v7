import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { accountsEnabled, getSupabase } from './supabase'

/**
 * How the visitor entered: not yet ('none' → the landing page), as a guest (sample data, kept only for this
 * tab in sessionStorage, never sent anywhere) or signed in with a Supabase account (settings sync to their row).
 */
export type Mode = 'none' | 'guest' | 'user'
export type AuthUser = { id: string; email: string }

type Auth = {
  ready: boolean
  mode: Mode
  user: AuthUser | null
  accountsEnabled: boolean
  enterGuest: () => void
  leaveGuest: () => void
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<'signed-in' | 'confirm-email'>
  signOut: () => Promise<void>
}

const GUEST_KEY = 'fip.guest'
const Ctx = createContext<Auth | null>(null)

const isGuest = () => { try { return sessionStorage.getItem(GUEST_KEY) === '1' } catch { return false } }

/** Visitor-safe wording for Supabase auth errors. */
export function authMessage(error: unknown): string {
  const raw = (error as { message?: string } | null)?.message ?? ''
  if (/invalid login credentials/i.test(raw)) return 'That e-mail and password don’t match an account.'
  if (/already registered|already exists/i.test(raw)) return 'An account with this e-mail already exists — log in instead.'
  if (/email not confirmed/i.test(raw)) return 'Please confirm your e-mail first — check your inbox for the link.'
  if (/password/i.test(raw) && /(6|8) characters|weak/i.test(raw)) return 'Choose a longer password (at least 8 characters).'
  if (/rate limit|too many/i.test(raw)) return 'Too many attempts. Wait a minute and try again.'
  if (/fetch|network/i.test(raw)) return 'Couldn’t reach the account service. Check your connection and try again.'
  return 'Something went wrong. Please try again.'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [guest, setGuest] = useState(isGuest)
  const [ready, setReady] = useState(!accountsEnabled)

  useEffect(() => {
    const p = getSupabase()
    if (!p) return
    let unsub: (() => void) | undefined
    let alive = true
    p.then(async sb => {
      const { data } = await sb.auth.getSession()
      if (!alive) return
      const u = data.session?.user
      setUser(u ? { id: u.id, email: u.email ?? '' } : null)
      setReady(true)
      const sub = sb.auth.onAuthStateChange((_e, session) => {
        const su = session?.user
        setUser(su ? { id: su.id, email: su.email ?? '' } : null)
      })
      unsub = () => sub.data.subscription.unsubscribe()
    }).catch(() => setReady(true))
    return () => { alive = false; unsub?.() }
  }, [])

  const enterGuest = useCallback(() => {
    try { sessionStorage.setItem(GUEST_KEY, '1') } catch { /* storage blocked: guest lasts until reload */ }
    setGuest(true)
  }, [])
  const leaveGuest = useCallback(() => {
    try { sessionStorage.removeItem(GUEST_KEY) } catch { /* nothing to clear */ }
    setGuest(false)
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const sb = await getSupabase()
    if (!sb) throw new Error('Accounts are not enabled')
    const { error } = await sb.auth.signInWithPassword({ email, password })
    if (error) throw error
  }, [])

  const signUp = useCallback(async (email: string, password: string) => {
    const sb = await getSupabase()
    if (!sb) throw new Error('Accounts are not enabled')
    const { data, error } = await sb.auth.signUp({ email, password, options: { emailRedirectTo: `${location.origin}/overview` } })
    if (error) throw error
    return data.session ? 'signed-in' as const : 'confirm-email' as const
  }, [])

  const signOut = useCallback(async () => {
    const sb = await getSupabase()
    await sb?.auth.signOut()
    setUser(null)
  }, [])

  const mode: Mode = user ? 'user' : guest ? 'guest' : 'none'
  const value = useMemo(() => ({ ready, mode, user, accountsEnabled, enterGuest, leaveGuest, signIn, signUp, signOut }),
    [ready, mode, user, enterGuest, leaveGuest, signIn, signUp, signOut])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): Auth {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth must be used inside AuthProvider')
  return v
}
