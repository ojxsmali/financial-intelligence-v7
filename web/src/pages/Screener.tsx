import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { HBars, SERIES } from '../components/Charts'
import { Chip, EmptyState, ErrorState, Notice, PageHeader, Section, Segmented, Skeleton } from '../components/ui'
import { api, type ScreenerRow } from '../lib/api'
import { formatMoney, formatPercent, resolveUnit, scaleLabel, SCALES } from '../lib/format'
import { useSettings } from '../lib/settings'

type Metric = 'revenue' | 'net_income' | 'net_margin' | 'revenue_growth' | 'return_on_assets' | 'total_assets'
const METRICS: { id: Metric; label: string; kind: 'money' | 'ratio'; plain: string }[] = [
  { id: 'revenue', label: 'Revenue', kind: 'money', plain: 'Total sales for the year.' },
  { id: 'net_income', label: 'Net income', kind: 'money', plain: 'Profit left after all costs and taxes.' },
  { id: 'net_margin', label: 'Net margin', kind: 'ratio', plain: 'Profit kept from each dollar of sales.' },
  { id: 'revenue_growth', label: 'Revenue growth', kind: 'ratio', plain: 'Change in sales versus the year before.' },
  { id: 'return_on_assets', label: 'Return on assets', kind: 'ratio', plain: 'Profit for each dollar the company owns.' },
  { id: 'total_assets', label: 'Total assets', kind: 'money', plain: 'Everything the company owns at year-end.' },
]
const SIZES = [
  { id: '0', label: 'Any size' }, { id: '100000000', label: 'Sales ≥ $100M' }, { id: '1000000000', label: 'Sales ≥ $1B' },
  { id: '10000000000', label: 'Sales ≥ $10B' }, { id: '100000000000', label: 'Sales ≥ $100B' },
]

export function Screener() {
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 10 * 60_000 })
  const { unit, setSymbol } = useSettings()
  const navigate = useNavigate()
  const [metric, setMetric] = useState<Metric>('net_margin')
  const [order, setOrder] = useState<'desc' | 'asc'>('desc')
  const [sector, setSector] = useState('')
  const [minRevenue, setMinRevenue] = useState('1000000000')
  const q = useQuery({
    queryKey: ['screener', metric, order, sector, minRevenue],
    queryFn: () => api.screener({ sort: metric, order, sector: sector ? [sector] : [], min_revenue: Number(minRevenue), limit: 25 }),
    placeholderData: keepPreviousData, staleTime: 30 * 60_000, retry: 1,
  })
  const def = METRICS.find(m => m.id === metric)!
  const fmt = (r: ScreenerRow, k: Metric) => {
    const v = r[k]
    return METRICS.find(m => m.id === k)!.kind === 'money' ? formatMoney(v, 'USD', unit) : formatPercent(v, 1)
  }
  const open = (s: string) => { setSymbol(s); navigate({ pathname: '/overview', search: `?t=${s}` }) }

  return (
    <>
      <PageHeader eyebrow="Screener" title="Rank every US‑listed" accent="company."
        sub="Find the most profitable, fastest-growing or largest companies across thousands of SEC filers at once — straight from audited annual reports, refreshed daily." />
      <div className="screener-controls">
        <div>
          <span className="field-label" id="rank-by">Rank by</span>
          <Segmented label="Rank by" value={metric} onChange={setMetric} options={METRICS.map(m => ({ id: m.id, label: m.label }))} />
        </div>
        <div className="screener-row">
          <Segmented label="Order" value={order} onChange={setOrder} options={[{ id: 'desc', label: 'Highest first' }, { id: 'asc', label: 'Lowest first' }]} />
          <label className="inline-field">
            <span>Size</span>
            <select value={minRevenue} onChange={e => setMinRevenue(e.target.value)}>{SIZES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>
          </label>
          <label className="inline-field">
            <span>Sector</span>
            <select value={sector} onChange={e => setSector(e.target.value)}>
              <option value="">All sectors</option>
              {(meta.data?.sectors ?? []).map(s => <option key={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <p className="caption"><b>{def.label}:</b> {def.plain}</p>
      </div>

      {q.isPending ? <Skeleton message="Ranking thousands of companies and double-checking the leaders against their annual reports… (the first load can take up to 20 seconds)" />
        : q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : (() => {
          const d = q.data
          if (!d.rows.length) return <EmptyState kicker="No match" title="No companies match these filters">Try a smaller size or another sector.</EmptyState>
          const top = d.rows.slice(0, 10)
          const scale = def.kind === 'money' ? resolveUnit(top.map(r => r[metric]), unit) : null
          return (
            <>
              <div className="tags" aria-live="polite">
                <Chip kind="info">{d.total.toLocaleString('en-US')} companies ranked</Chip>
                <Chip>Calendar year {d.year}</Chip>
                <Chip>{d.universe_size.toLocaleString('en-US')} SEC filers scanned</Chip>
                <Chip kind="ok">{d.verified} of {d.rows.length} verified against annual reports</Chip>
                {q.isFetching && <Chip>Updating…</Chip>}
              </div>
              {d.corrected > 0 && <Notice kind="info">{d.corrected} {d.corrected === 1 ? 'figure was' : 'figures were'} corrected: SEC's bulk data disagreed with the company's own annual report, so the annual report's numbers are used.</Notice>}
              {d.excluded > 0 && <Notice kind="info">{d.excluded} {d.excluded === 1 ? 'company was' : 'companies were'} left out because the filed figures give an impossible {def.label.toLowerCase()} (usually a unit mistake in the company's tagging).</Notice>}
              <Section title={`Top 10 by ${def.label.toLowerCase()}`} sub="Bars show the exact value; open any company for its full annual history">
                <HBars title={def.label} unitText={def.kind === 'money' ? `${def.label}, ${scaleLabel('USD', scale!)}` : `${def.label}, %`}
                  items={top.map(r => ({
                    key: r.symbol, label: r.symbol, sub: r.name.slice(0, 22),
                    value: r[metric] === null ? null : def.kind === 'money' ? (r[metric] as number) / SCALES[scale!].divisor : (r[metric] as number) * 100,
                    text: fmt(r, metric), color: SERIES[0],
                  }))} />
              </Section>
              <div className="table-wrap" role="region" aria-label="Screener results" tabIndex={0}>
                <table className="table results">
                  <caption>Top {d.rows.length} of {d.total.toLocaleString('en-US')} by {def.label.toLowerCase()}, calendar year {d.year}, USD</caption>
                  <thead><tr>
                    <th scope="col">#</th><th scope="col">Company</th><th scope="col">Sector</th>
                    {METRICS.filter(m => m.id !== 'total_assets').map(m => <th key={m.id} scope="col" className={m.id === metric ? 'sorted num' : 'num'} aria-sort={m.id === metric ? (order === 'desc' ? 'descending' : 'ascending') : undefined}>{m.label}</th>)}
                    <th scope="col"><span className="sr-only">Actions</span></th>
                  </tr></thead>
                  <tbody>
                    {d.rows.map((r, i) => (
                      <tr key={r.cik}>
                        <td className="num muted">{i + 1}</td>
                        <th scope="row" className="name"><span className="mono">{r.symbol}</span> {r.name}
                          {r.verified
                            ? <span className="verified" title={`Checked against the FY${r.fiscal_year} annual report`}> ✓<span className="sr-only"> verified against the FY{r.fiscal_year} annual report</span></span>
                            : <span className="unverified" title="Could not be checked against the annual report"> ?<span className="sr-only"> not verified</span></span>}
                        </th>
                        <td>{r.sector === 'Unclassified' ? '—' : r.sector}</td>
                        {METRICS.filter(m => m.id !== 'total_assets').map(m => (
                          <td key={m.id} className={`num ${m.id === metric ? 'sorted' : ''} ${(r[m.id] ?? 0) < 0 ? 'neg' : ''}`}>{fmt(r, m.id)}</td>
                        ))}
                        <td className="actions"><button className="btn sm" onClick={() => open(r.symbol)} aria-label={`Open ${r.symbol}`}>Open</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="caption">✓ = figures confirmed against the company's own annual report (FY shown on its page); ? = could not be checked. Source: SEC XBRL “frames” — one audited figure per company for calendar year {d.year}, then cross-checked. SEC lines each company's fiscal year up with the nearest calendar year, so figures can differ slightly from the company's own fiscal-year pages. Revenue uses the largest total-revenue figure the company reports; ratios use positive denominators only. Rule-based ranking, not advice.</p>
            </>
          )
        })()}
    </>
  )
}
