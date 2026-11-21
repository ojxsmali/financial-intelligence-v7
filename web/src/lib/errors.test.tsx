import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ErrorBoundary, ErrorState } from '../components/ui'
import { MESSAGES, RequestError, toVisitorError } from './api'

describe('visitor-safe errors', () => {
  it('keeps curated server messages for the visitor and attaches the reference', () => {
    const e = toVisitorError(400, { error: { kind: 'bad_csv', message: 'Could not use this file: the revenue column is missing.', ref: 'FI-ABC234' } })
    expect(e.message).toMatch(/revenue column/)
    expect(e.ref).toBe('FI-ABC234')
    expect(toVisitorError(403, { error: { kind: 'access_code', message: 'Incorrect access code.' } }).message).toBe('Incorrect access code.')
  })
  it('never shows platform pages, unknown kinds or stack text', () => {
    expect(toVisitorError(504, '<html>FUNCTION_INVOCATION_TIMEOUT</html>').message).toBe(MESSAGES.timeout)
    expect(toVisitorError(502, null).message).toBe(MESSAGES.service)
    expect(toVisitorError(500, { detail: 'Traceback (most recent call last) …' }).message).toBe(MESSAGES.internal)
    expect(toVisitorError(500, { error: { kind: 'weird', message: 'KeyError: x at api.py:12' } }).message).toBe(MESSAGES.internal)
    expect(toVisitorError(503, null, 'FI-HDR999').ref).toBe('FI-HDR999')
  })
})

describe('ErrorState and ErrorBoundary', () => {
  afterEach(() => vi.restoreAllMocks())
  it('shows only the safe message and reference', () => {
    render(<ErrorState error={new RequestError(503, 'upstream', MESSAGES.data, 'FI-XYZ789')} />)
    expect(screen.getByText(MESSAGES.data)).toBeInTheDocument()
    expect(screen.getByText('FI-XYZ789')).toBeInTheDocument()
    expect(screen.getByText('Temporarily unavailable')).toBeInTheDocument()
  })
  it('replaces a raw JavaScript error with the generic message', () => {
    render(<ErrorState error={new TypeError("Cannot read properties of undefined (reading 'x')")} />)
    expect(screen.queryByText(/Cannot read/)).toBeNull()
    expect(screen.getByText(MESSAGES.internal)).toBeInTheDocument()
  })
  it('catches render crashes, reports privately and shows a calm fallback', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}'))
    const Boom = () => { throw new Error('secret internal detail') }
    render(<ErrorBoundary><Boom /></ErrorBoundary>)
    expect(screen.getByText('This page couldn’t be displayed')).toBeInTheDocument()
    expect(screen.queryByText(/secret internal detail/)).toBeNull()
    expect(fetchSpy).toHaveBeenCalledWith('/api/client-error', expect.objectContaining({ method: 'POST' }))
  })
})
