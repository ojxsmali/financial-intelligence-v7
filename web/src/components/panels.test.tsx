import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { FilingEvent, Health } from '../lib/api'
import { FilingsList, HealthPanel, daysAgo, niceDate } from './Panels'
import { InsightList } from './ui'

const ev = (over: Partial<FilingEvent>): FilingEvent => ({
  form: '8-K', filing_date: '2026-11-02', report_date: '', accession: 'a', title: 'Earnings results released',
  detail: '8-K current report.', kind: 'event', importance: 'high', items: [], url: 'https://www.sec.gov/x', ...over,
})

describe('dates', () => {
  it('formats SEC calendar dates without time-zone drift', () => {
    expect(niceDate('2026-11-03')).toBe('3 Nov 2026')
    expect(daysAgo('2026-11-20', new Date(Date.UTC(2026, 10, 21)))).toBe('yesterday')
    expect(daysAgo('2026-11-11', new Date(Date.UTC(2026, 10, 21)))).toBe('10 days ago')
  })
})

describe('FilingsList', () => {
  it('marks filings newer than the last visit and flags alerts', () => {
    render(<FilingsList since="2026-11-01" events={[
      ev({ accession: 'n', filing_date: '2026-11-02' }),
      ev({ accession: 'o', filing_date: '2026-10-01', title: 'Earlier financial statements should no longer be relied on', importance: 'alert' }),
    ]} />)
    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('New')
    expect(items[1]).not.toHaveTextContent('New')
    expect(items[1]).toHaveTextContent('Important')
    expect(screen.getByRole('link', { name: 'Earnings results released' })).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

describe('HealthPanel', () => {
  const health: Health = {
    fiscal_year: 2026, prior_year: 2025, passed: 2, available: 3, verdict: 'Not enough data', summary: 'Only 3 of 9 tests could be run.',
    checks: [
      { key: 'a', group: 'Profitability', question: 'Did the company make a profit?', passed: true, detail: 'Yes', why: 'Because.' },
      { key: 'b', group: 'Profitability', question: 'Is profitability improving?', passed: false, detail: 'No', why: 'Because.' },
      { key: 'c', group: 'Efficiency', question: 'Is the gross margin improving?', passed: null, detail: 'Skipped', why: 'Because.' },
    ],
  }
  it('states the score in words and never relies on colour alone', () => {
    render(<HealthPanel health={health} />)
    expect(screen.getByRole('img', { name: '2 of 3 checks passed' })).toBeInTheDocument()
    expect(screen.getByText('Not available.')).toBeInTheDocument()
    expect(screen.getByText('Yes.')).toBeInTheDocument()
    expect(screen.getByText(/not AI/)).toBeInTheDocument()
  })
})

describe('InsightList', () => {
  it('leads with plain English and tucks the formula away', () => {
    render(<InsightList items={[{
      category: 'Calculation', tone: 'neutral', title: 'Net profit margin 27.60%', detail: 'Net income $132B on revenue $478B.',
      rule: 'net_income / revenue', evidence: 'FY2026 10-K filed 2026-11-03',
      how: 'Net income divided by revenue.', source: 'FY2026 annual report (10-K), filed 3 Nov 2026',
    }]} />)
    expect(screen.getByText("How it's worked out")).toBeInTheDocument()
    expect(screen.getByText('Worked out')).toBeInTheDocument()
    expect(screen.getByText('net_income / revenue').closest('details')).not.toHaveAttribute('open')
  })
})
