import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { safeNext } from '../pages/Landing'
import { AuthProvider, authMessage, useAuth } from './auth'
import { SettingsProvider, useSettings } from './settings'

describe('safeNext', () => {
  it('follows same-site paths only', () => {
    expect(safeNext('?next=%2Fscreener%3Ft%3DNVDA')).toBe('/screener?t=NVDA')
    expect(safeNext('?next=https%3A%2F%2Fevil.example')).toBe('/overview')
    expect(safeNext('?next=%2F%2Fevil.example')).toBe('/overview')
    expect(safeNext('')).toBe('/overview')
  })
})

describe('authMessage', () => {
  it('turns Supabase errors into visitor-safe text', () => {
    expect(authMessage({ message: 'Invalid login credentials' })).toMatch(/don’t match/)
    expect(authMessage({ message: 'User already registered' })).toMatch(/already exists/)
    expect(authMessage(new Error('weird internal thing'))).toBe('Something went wrong. Please try again.')
  })
})

function GuestProbe() {
  const { mode, enterGuest } = useAuth()
  const { watchlist, toggleWatch } = useSettings()
  return (
    <>
      <p data-testid="mode">{mode}</p>
      <p data-testid="watch">{watchlist.join(',')}</p>
      <button onClick={enterGuest}>guest</button>
      <button onClick={() => toggleWatch('TSLA')}>watch</button>
    </>
  )
}

describe('guest mode', () => {
  afterEach(() => { sessionStorage.clear(); localStorage.clear() })
  it('starts with sample companies and never writes to localStorage', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><AuthProvider><SettingsProvider><Routes><Route path="*" element={<GuestProbe />} /></Routes></SettingsProvider></AuthProvider></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.getByTestId('mode').textContent).toBe('none')
    act(() => screen.getByText('guest').click())
    expect(screen.getByTestId('mode').textContent).toBe('guest')
    expect(screen.getByTestId('watch').textContent).toBe('AAPL,MSFT,NVDA')
    act(() => screen.getByText('watch').click())
    expect(screen.getByTestId('watch').textContent).toContain('TSLA')
    expect(sessionStorage.getItem('fip.g.watchlist')).toContain('TSLA')
    expect(Object.keys(localStorage)).toEqual([])
  })
})
