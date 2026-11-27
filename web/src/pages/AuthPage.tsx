import { motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LogoMark, Wordmark } from '../components/Logo'
import { authMessage, useAuth } from '../lib/auth'
import { safeNext } from './Landing'

const EMAIL = /^[^\s@<>()]+@[^\s@<>()]+\.[A-Za-z]{2,}$/

/** Log in / create account (Supabase e-mail + password), always with a one-click guest way in. */
export function AuthPage({ kind }: { kind: 'login' | 'signup' }) {
  const { ready, mode, accountsEnabled, signIn, signUp, enterGuest } = useAuth()
  const loc = useLocation()
  const navigate = useNavigate()
  const next = safeNext(loc.search)
  const q = next === '/overview' ? '' : `?next=${encodeURIComponent(next)}`
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const signup = kind === 'signup'

  if (ready && mode === 'user') return <Navigate to={next} replace />

  const valid = EMAIL.test(email.trim()) && password.length >= 8
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valid || busy) return
    setBusy(true); setError('')
    try {
      if (signup) {
        const r = await signUp(email.trim(), password)
        if (r === 'confirm-email') setSent(true)
        else navigate(next, { replace: true })
      } else {
        await signIn(email.trim(), password)
        navigate(next, { replace: true })
      }
    } catch (err) {
      setError(authMessage(err))
    } finally {
      setBusy(false)
    }
  }
  const guest = () => { enterGuest(); navigate(next) }

  return (
    <div className="auth">
      <Link to="/" state={{ home: true }} className="brand auth-brand" aria-label="Financial Intelligence — home page"><LogoMark /><Wordmark className="brand-name" /></Link>
      <motion.main className="auth-card" initial={{ y: 30, rotate: -1.5, opacity: 0 }} animate={{ y: 0, rotate: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 240, damping: 20 }}>
        <p className="eyebrow">{signup ? 'Create account' : 'Log in'}</p>
        <h1>{signup ? <>Keep your <em>research.</em></> : <>Welcome <em>back.</em></>}</h1>
        <p className="auth-sub">{signup
          ? 'Your watchlist, comparisons and display settings are saved to your account and follow you to any device.'
          : 'Your watchlist and comparisons are waiting where you left them.'}</p>

        {!accountsEnabled && (
          <div className="notice info" role="status"><b>Note:</b> Accounts aren’t switched on for this deployment yet. Everything works as a guest in the meantime.</div>
        )}

        {sent ? (
          <div className="auth-sent" role="status">
            <b>Check your inbox.</b>
            <p>We sent a confirmation link to <span className="mono">{email.trim()}</span>. Open it on this device to finish creating your account.</p>
            <Link className="btn" to={`/login${q}`}>Back to log in</Link>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            <label className="field-label" htmlFor="auth-email">E-mail</label>
            <input id="auth-email" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} disabled={!accountsEnabled}
              placeholder="you@example.com" aria-invalid={email.length > 3 && !EMAIL.test(email.trim())} />
            <label className="field-label" htmlFor="auth-pass">Password</label>
            <div className="pass">
              <input id="auth-pass" type={show ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} value={password}
                onChange={e => setPassword(e.target.value)} disabled={!accountsEnabled} placeholder={signup ? 'At least 8 characters' : ''} />
              <button type="button" className="pass-toggle" onClick={() => setShow(s => !s)} aria-pressed={show} disabled={!accountsEnabled}>{show ? 'Hide' : 'Show'}</button>
            </div>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="btn primary auth-submit" disabled={!accountsEnabled || !valid || busy}>
              {busy ? (signup ? 'Creating account…' : 'Logging in…') : signup ? 'Create account' : 'Log in'}
            </button>
          </form>
        )}

        <div className="auth-or"><span>or</span></div>
        <motion.button type="button" className="btn auth-guest" onClick={guest} whileTap={{ scale: 0.95 }}>
          Continue as guest <span aria-hidden="true">→</span>
        </motion.button>
        <p className="auth-fine">Guest mode opens the full app with sample companies. Nothing is saved.</p>

        <p className="auth-switch">{signup
          ? <>Already have an account? <Link to={`/login${q}`}>Log in</Link></>
          : <>New here? <Link to={`/signup${q}`}>Create an account</Link></>}</p>
      </motion.main>
    </div>
  )
}
