import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Figure, parseFigure } from './ui'

describe('parseFigure', () => {
  it('splits currency figures with a unit suffix', () => {
    expect(parseFigure('$478.83B')).toEqual({ prefix: '$', value: 478.83, decimals: 2, grouped: false, suffix: 'B' })
  })
  it('keeps the sign of growth figures', () => {
    expect(parseFigure('+5.53%')).toMatchObject({ value: 5.53, suffix: '%' })
    expect(parseFigure('−12.4%')).toMatchObject({ value: -12.4 })
  })
  it('recognises grouped thousands', () => {
    expect(parseFigure('13,214')).toMatchObject({ value: 13214, grouped: true, decimals: 0 })
  })
  it('returns null for text that is not a figure', () => {
    expect(parseFigure('Not reported')).toBeNull()
    expect(parseFigure('n/a')).toBeNull()
  })
})

describe('Figure', () => {
  it('renders the exact reported text (no animation without matchMedia)', () => {
    render(<Figure text="$132.18B" />)
    expect(screen.getByText('$132.18B')).toBeInTheDocument()
  })
})
