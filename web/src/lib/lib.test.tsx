import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ColumnChart, HBars, SERIES } from '../components/Charts'
import { sanitizeCell, toCsv } from './csv'
import { formatMoney, formatPerShare, formatPercent, formatPp, resolveUnit } from './format'
import { Markdown } from './markdown'
import { niceTicks, tickText } from './scale'

describe('format (parity with fip/formatting.py)', () => {
  it('scales money from full units', () => {
    expect(formatMoney(416_161_000_000, 'USD')).toBe('$416.16B')
    expect(formatMoney(1_250_000_000_000, 'USD')).toBe('$1.25T')
    expect(formatMoney(845_000_000, 'USD')).toBe('$845.00M')
    expect(formatMoney(-5_000_000_000, 'USD')).toBe('−$5.00B')
    expect(formatMoney(48_040_000_000_000, 'JPY')).toBe('¥48.04T')
    expect(formatMoney(416_161_000_000, 'USD', 'M')).toBe('$416,161.00M')
    expect(formatMoney(null)).toBe('—')
  })
  it('formats ratios, percentage points and per-share values', () => {
    expect(formatPercent(0.4031)).toBe('40.31%')
    expect(formatPercent(0.1586, 2, true)).toBe('+15.86%')
    expect(formatPercent(-0.0364, 2, true)).toBe('−3.64%')
    expect(formatPp(0.012)).toBe('+1.2 pp')
    expect(formatPp(-0.019)).toBe('−1.9 pp')
    expect(formatPerShare(8.98)).toBe('$8.98')
    expect(formatPerShare(-1.5)).toBe('−$1.50')
  })
  it('resolves one shared unit for a group', () => {
    expect(resolveUnit([1e9, 4e11, null])).toBe('B')
    expect(resolveUnit([1e9], 'M')).toBe('M')
    expect(resolveUnit([])).toBe('units')
  })
})

describe('axis scale', () => {
  it('covers the range and includes zero', () => {
    const t = niceTicks(12, 478.8)
    expect(t[0]).toBe(0)
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(478.8)
    const n = niceTicks(-5, 2)
    expect(n[0]).toBeLessThanOrEqual(-5)
    expect(n).toContain(0)
  })
  it('labels ticks with matching decimals', () => {
    expect(tickText(100, 50, '$', 'B')).toBe('$100B')
    expect(tickText(0.25, 0.25, '', '%')).toBe('0.25%')
    expect(tickText(-50, 25, '$', 'B')).toBe('−$50B')
  })
})

describe('csv', () => {
  it('neutralises formula injection but keeps numbers', () => {
    expect(sanitizeCell('=HYPERLINK("x")')).toBe(`'=HYPERLINK("x")`)
    expect(sanitizeCell('@SUM(A1)')).toBe(`'@SUM(A1)`)
    expect(sanitizeCell('-5.2')).toBe('-5.2')
    expect(sanitizeCell(null)).toBe('')
  })
  it('quotes and adds a BOM', () => {
    const out = toCsv([['a', 'b,c'], ['say "hi"', 1]])
    expect(out.startsWith('﻿')).toBe(true)
    expect(out).toContain('a,"b,c"')
    expect(out).toContain('"say ""hi""",1')
  })
})

describe('markdown', () => {
  it('renders structure without injecting HTML', () => {
    const { container } = render(<Markdown text={'### Key facts\n- Revenue **$416B** [AAPL FY2025 10-K]\n- <img src=x onerror=alert(1)>\n\nPlain `code`.'} />)
    expect(container.querySelector('h4')?.textContent).toBe('Key facts')
    expect(container.querySelectorAll('li')).toHaveLength(2)
    expect(container.querySelector('strong')?.textContent).toBe('$416B')
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>')
  })
})

describe('charts', () => {
  const series = [
    { label: 'Revenue', color: SERIES[0], values: [383.3, 391.0, 416.2], texts: ['$383.29B', '$391.04B', '$416.16B'] },
    { label: 'Net income', color: SERIES[1], values: [97.0, null, 112.0], texts: ['$97.00B', 'Not reported', '$112.01B'] },
  ]
  it('gives every fiscal year one keyboard stop with a full label, a legend and a data table', () => {
    render(<ColumnChart title="Revenue and profit" categories={['FY2023', 'FY2024', 'FY2025']} series={series} unitText="USD billions" prefix="$" suffix="B" />)
    const cols = screen.getAllByRole('img')
    expect(cols).toHaveLength(3)
    expect(cols[1]).toHaveAttribute('tabindex', '0')
    expect(cols[1]).toHaveAccessibleName('FY2024: Revenue $391.04B; Net income Not reported')
    expect(screen.getByRole('list', { name: 'Legend' })).toBeInTheDocument()
    expect(screen.getByRole('rowheader', { name: 'FY2025' })).toBeInTheDocument()
    expect(screen.getByText('USD billions')).toBeInTheDocument()
  })
  it('breaks lines at missing values instead of bridging them', () => {
    const { container } = render(<ColumnChart title="m" kind="line" categories={['A', 'B', 'C']} series={series} />)
    expect(container.querySelectorAll('polyline')).toHaveLength(1)   // only the complete series draws a line
  })
  it('explains an empty chart', () => {
    render(<ColumnChart title="x" categories={['A']} series={[{ label: 'R', color: SERIES[0], values: [null], texts: ['—'] }]} />)
    expect(screen.getByRole('note')).toHaveTextContent('No reported values')
  })
  it('sorts horizontal bars and lists missing companies', () => {
    render(<HBars title="Gross margin" unitText="%" items={[
      { key: 'AAPL', label: 'AAPL', value: 47, text: '47.00%', color: SERIES[0] },
      { key: 'MSFT', label: 'MSFT', value: 69, text: '69.00%', color: SERIES[1] },
      { key: 'JPM', label: 'JPM', value: null, text: '—', color: SERIES[2] },
    ]} />)
    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('MSFT')
    expect(screen.getByText('Not reported: JPM')).toBeInTheDocument()
  })
})
