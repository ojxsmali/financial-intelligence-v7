import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ColumnChart, HBars, SERIES, type ChartSeries } from '../components/Charts'
import { CompanyPicker } from '../components/CompanyPicker'
import { EmptyState, ErrorState, Notice, PageHeader, Section, Segmented, Skeleton, StatTable, type Row } from '../components/ui'
import { api, exportUrls, type CompareRow } from '../lib/api'
import { currencySymbol, formatMoney, formatPercent, isMissing, resolveUnit, scaleLabel, SCALES } from '../lib/format'
import { MAX_COMPARE, useSettings } from '../lib/settings'

const RATIO = { net_margin: 'Net profit margin', operating_margin: 'Operating margin', gross_margin: 'Gross margin', fcf_margin: 'Free-cash-flow margin', revenue_growth: 'Revenue growth (YoY)', revenue_cagr: 'Revenue CAGR', return_on_equity: 'Return on equity', liabilities_to_assets: 'Liabilities / assets' }
const MONEY = { revenue: 'Revenue', net_income: 'Net income', operating_income: 'Operating income', free_cash_flow: 'Free cash flow', total_assets: 'Total assets' }
const TREND = { revenue: 'Revenue', net_margin: 'Net margin', operating_margin: 'Operating margin', revenue_growth: 'Revenue growth' }
type RatioKey = keyof typeof RATIO
type MoneyKey = keyof typeof MONEY
type TrendKey = keyof typeof TREND

const num = (r: CompareRow, k: string) => (typeof r[k] === 'number' ? (r[k] as number) : null)

export function Compare() {
  const { compare, setCompare, unit, years, notify } = useSettings()
  const [ratio, setRatio] = useState<RatioKey>('net_margin')
  const [amount, setAmount] = useState<MoneyKey>('revenue')
  const [trend, setTrend] = useState<TrendKey>('revenue')
  const enough = compare.length >= 2
  const q = useQuery({ queryKey: ['compare', compare.join(',')], queryFn: () => api.compare(compare), enabled: enough, staleTime: 15 * 60_000 })

  const add = (s: string) => {
    if (compare.includes(s)) return notify(`${s} is already in the comparison`)
    if (compare.length >= MAX_COMPARE) notify(`Comparison holds ${MAX_COMPARE} companies; ${compare[0]} was removed`)
    setCompare([...compare, s])
  }

  return (
    <>
      <PageHeader eyebrow="Compare" title="Side-by-side fundamentals"
        sub="Latest audited fiscal year for each company, with currency, period and accounting-basis checks." />
      <div className="compare-pick">
        <ul className="pills-list" aria-label="Companies in the comparison">
          {compare.map(s => (
            <li key={s}><span>{s}</span><button type="button" aria-label={`Remove ${s}`} onClick={() => setCompare(compare.filter(x => x !== s))}>×</button></li>
          ))}
        </ul>
        <CompanyPicker label={`Add a company (up to ${MAX_COMPARE})`} onPick={add} exclude={compare} />
      </div>

      {!enough ? (
        <EmptyState kicker="Comparison" title="Pick at least two companies">Use the search above, or “Add to compare” in the toolbar on any company page.</EmptyState>
      ) : q.isPending ? <Skeleton message="Loading annual filings for each company…" /> : q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : (() => {
        const data = q.data
        const rows = data.rows
        const colors = Object.fromEntries(data.companies.filter(c => c.ok).map((c, i) => [c.symbol, SERIES[i % SERIES.length]]))
        const currencies = [...new Set(rows.map(r => r.currency))]
        const single = currencies.length === 1
        const cur = currencies[0] ?? 'USD'
        const moneyCells = (k: string) => rows.map(r => formatMoney(num(r, k), r.currency, unit))
        const negs = (k: string) => [false, ...rows.map(r => (num(r, k) ?? 0) < 0)]
        const table: Row[] = [
          { cells: ['Company', ...rows.map(r => r.company)] },
          { cells: ['Fiscal year · form', ...rows.map(r => `FY${r.fiscal_year} · ${r.form}`)] },
          { cells: ['Period end', ...rows.map(r => r.period_end)] },
          { cells: ['Currency · basis', ...rows.map(r => `${r.currency} · ${r.basis}`)] },
          ...(['revenue', 'operating_income', 'net_income', 'free_cash_flow'] as const).map(k => ({
            cells: [k === 'free_cash_flow' ? 'Free cash flow (derived)' : MONEY[k], ...moneyCells(k)], neg: negs(k) })),
          { cells: ['Revenue growth (YoY)', ...rows.map(r => formatPercent(num(r, 'revenue_growth'), 2, true))], cls: 'ratio', neg: negs('revenue_growth') },
          { cells: ['Revenue CAGR', ...rows.map(r => isMissing(num(r, 'revenue_cagr')) ? '—' : `${formatPercent(num(r, 'revenue_cagr'), 2, true)} (${r.cagr_years}y)`)], cls: 'ratio' },
          ...(['gross_margin', 'operating_margin', 'net_margin', 'fcf_margin', 'return_on_equity', 'liabilities_to_assets'] as const).map(k => ({
            cells: [RATIO[k], ...rows.map(r => formatPercent(num(r, k)))], cls: 'ratio', neg: negs(k) })),
        ]

        let trendBody
        if (trend === 'revenue' && !single) {
          trendBody = <EmptyState kicker="Not comparable" title="Different reporting currencies">Revenue trends need a common currency; choose a ratio.</EmptyState>
        } else {
          const syms = Object.keys(data.series)
          const allYears = [...new Set(syms.flatMap(s => data.series[s].slice(-years).map(p => p.fiscal_year)))].sort()
          const isMoney = trend === 'revenue'
          const scale = resolveUnit(syms.flatMap(s => data.series[s].map(p => p.revenue as number | null)), unit)
          const series: ChartSeries[] = syms.map(s => {
            const by = new Map(data.series[s].slice(-years).map(p => [p.fiscal_year, p[trend] as number | null]))
            const raw = allYears.map(y => by.get(y) ?? null)
            return {
              label: s, color: colors[s] ?? SERIES[0],
              values: raw.map(v => v === null ? null : isMoney ? v / SCALES[scale].divisor : v * 100),
              texts: raw.map(v => isMoney ? formatMoney(v, cur, unit) : formatPercent(v)),
            }
          })
          const sym = currencySymbol(cur).trim()
          trendBody = <ColumnChart title={TREND[trend]} categories={allYears.map(y => `FY${y}`)} series={series} kind="line"
            unitText={isMoney ? `${TREND[trend]}, ${scaleLabel(cur, scale)}` : `${TREND[trend]}, %`}
            prefix={isMoney && sym.length <= 3 ? sym : ''} suffix={isMoney ? SCALES[scale].suffix : '%'} />
        }

        const moneyScale = resolveUnit(rows.map(r => num(r, amount)), unit)
        return (
          <>
            {data.companies.filter(c => !c.ok).map(c => <Notice key={c.symbol} kind="bad">{c.symbol}: excluded — {c.error}</Notice>)}
            {data.companies.filter(c => c.ok).flatMap(c => (c.notices ?? []).map((n, i) => <Notice key={`${c.symbol}${i}`}>{c.symbol}: {n}</Notice>))}
            {rows.length < 2 ? (
              <EmptyState kicker="Comparison" title="Not enough comparable data">At least two companies need annual SEC financial statements.</EmptyState>
            ) : (
              <>
                {data.warnings.map((w, i) => <Notice key={i} kind="info">{w}</Notice>)}
                <StatTable caption="Latest fiscal year per company" header={['Metric', ...rows.map(r => r.symbol)]} rows={table} />
                <p className="caption">“—” means the company does not report that line item in its XBRL data (e.g. banks have no gross margin); it is never estimated. Ratios are currency-neutral.</p>
                <div className="grid-2">
                  <Section title="Ratios" sub="Currency-neutral; latest fiscal year">
                    <Segmented label="Ratio" value={ratio} onChange={setRatio} options={Object.entries(RATIO).map(([id, label]) => ({ id: id as RatioKey, label }))} />
                    <HBars title={RATIO[ratio]} unitText={`${RATIO[ratio]}, %`} items={rows.map(r => ({
                      key: r.symbol, label: r.symbol, sub: `FY${r.fiscal_year}`, value: num(r, ratio) === null ? null : (num(r, ratio) as number) * 100,
                      text: formatPercent(num(r, ratio)), color: colors[r.symbol] ?? SERIES[0] }))} />
                  </Section>
                  <Section title="Amounts" sub="Only charted when every company reports in the same currency">
                    <Segmented label="Amount" value={amount} onChange={setAmount} options={Object.entries(MONEY).map(([id, label]) => ({ id: id as MoneyKey, label }))} />
                    {single ? (
                      <HBars title={MONEY[amount]} unitText={`${MONEY[amount]}, ${scaleLabel(cur, moneyScale)}`} items={rows.map(r => ({
                        key: r.symbol, label: r.symbol, sub: `FY${r.fiscal_year}`, value: num(r, amount) === null ? null : (num(r, amount) as number) / SCALES[moneyScale].divisor,
                        text: formatMoney(num(r, amount), r.currency, unit), color: colors[r.symbol] ?? SERIES[0] }))} />
                    ) : (
                      <EmptyState kicker="Not comparable" title="Different reporting currencies">
                        Absolute amounts are not charted together because the companies report in {currencies.join(', ')}. Compare the ratio chart instead.
                      </EmptyState>
                    )}
                  </Section>
                </div>
                <Section title="Trend" sub={`Last ${years} fiscal years per company (each on its own fiscal calendar)`}>
                  <Segmented label="Trend series" value={trend} onChange={setTrend} options={Object.entries(TREND).map(([id, label]) => ({ id: id as TrendKey, label }))} />
                  {trendBody}
                </Section>
                <p><a className="btn" href={exportUrls.compare(compare)} download>Download comparison (CSV, full provenance)</a></p>
                <p className="caption">CSV values are in full reporting-currency units, one row per company × fiscal year × metric, with XBRL concept, form, filing date and accession number.</p>
              </>
            )}
          </>
        )
      })()}
    </>
  )
}
