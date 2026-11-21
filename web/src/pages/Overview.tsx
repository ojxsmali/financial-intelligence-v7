import { Link } from 'react-router-dom'
import { ColumnChart } from '../components/Charts'
import { CompanyGate } from '../components/Company'
import { FilingsList, HealthPanel } from '../components/Panels'
import { InsightList, KpiStrip, PageHeader, Section, type Kpi } from '../components/ui'
import { direction, formatMoney, formatPerShare, formatPercent, formatPp, isMissing } from '../lib/format'
import { fyLabels, moneySeries, ratioSeries } from '../lib/series'
import { useSettings } from '../lib/settings'

export function Overview() {
  const { unit, symbol } = useSettings()
  return (
    <>
      <PageHeader eyebrow="Overview" title="Annual performance"
        sub="Audited annual results from SEC filings: revenue, profitability, cash generation and balance sheet." />
      <CompanyGate>
        {({ company, fin, all, shown }) => {
          const cur = fin.currency
          const last = all[all.length - 1]
          const v = last.values
          const r = last.ratios
          const fy = `FY${last.fiscal_year}`
          const prevFy = all.length > 1 ? `FY${all[all.length - 2].fiscal_year}` : 'the prior year'
          const foot = `${fy} · ${last.form}`
          const money = (x: number | null) => formatMoney(x, cur, unit)
          const cagr = fin.revenue_cagr
          const kpis: Kpi[] = [
            { label: 'Revenue', value: money(v.revenue), delta: isMissing(r.revenue_growth) ? 'YoY n/a' : `${formatPercent(r.revenue_growth, 2, true)} YoY`,
              direction: direction(r.revenue_growth), foot, tip: `Reported total revenue for the fiscal year ended ${last.period_end}. Growth vs ${prevFy}.`, available: !isMissing(v.revenue) },
            { label: 'Net income', value: money(v.net_income), delta: isMissing(r.net_income_growth) ? '' : `${formatPercent(r.net_income_growth, 2, true)} YoY`,
              direction: direction(r.net_income_growth), foot, tip: 'Net income attributable to the parent company (reported).', available: !isMissing(v.net_income) },
            { label: 'Net profit margin', value: formatPercent(r.net_margin), delta: isMissing(r.net_margin_change) ? '' : formatPp(r.net_margin_change),
              direction: direction(r.net_margin_change), foot, tip: 'Net income ÷ revenue. Change in percentage points.', available: !isMissing(r.net_margin) },
            { label: 'Operating margin', value: isMissing(r.operating_margin) ? 'Not reported' : formatPercent(r.operating_margin),
              delta: isMissing(r.operating_margin_change) ? '' : formatPp(r.operating_margin_change), direction: direction(r.operating_margin_change), foot,
              tip: 'Operating income ÷ revenue. Banks and insurers often do not report operating income.', available: !isMissing(r.operating_margin) },
            { label: 'Free cash flow', value: isMissing(v.free_cash_flow) ? 'Not available' : money(v.free_cash_flow),
              delta: isMissing(r.fcf_margin) ? '' : `${formatPercent(r.fcf_margin)} of revenue`, direction: 'flat', foot: 'derived: OCF − capex',
              tip: 'Derived: operating cash flow − capital expenditure (purchases of PP&E).', available: !isMissing(v.free_cash_flow) },
            { label: cagr.years ? `${cagr.years}-yr revenue CAGR` : 'Revenue CAGR', value: isMissing(cagr.value) ? 'n/a' : formatPercent(cagr.value, 2, true),
              foot: cagr.years ? `FY${all[all.length - 1 - cagr.years].fiscal_year}–${fy}` : '',
              tip: 'Compound annual growth over the longest unbroken run of fiscal years (max 5).', available: !isMissing(cagr.value) },
          ]
          const labels = fyLabels(shown)
          const rev = moneySeries(shown, [['revenue', 'Revenue'], ['operating_income', 'Operating income'], ['net_income', 'Net income']], cur, unit)
          const cash = moneySeries(shown, [['operating_cash_flow', 'Operating cash flow'], ['capex', 'Capex'], ['free_cash_flow', 'Free cash flow']], cur, unit)
          const margins = ratioSeries(shown, [['gross_margin', 'Gross'], ['operating_margin', 'Operating'], ['net_margin', 'Net'], ['fcf_margin', 'Free cash flow']])
          const observations = fin.insights.filter(i => i.category !== 'Fact').slice(0, 4)
          return (
            <>
              <KpiStrip items={kpis} label={`Key figures, ${fy}`} />
              {(company.share_classes ?? []).length > 0 && (
                <p className="caption">Same SEC registrant also trades as {company.share_classes!.join(', ')}. Statements cover the whole company, not one share class.</p>
              )}
              <div className="grid-2">
                <Section title="Revenue and profit" sub="Reported annual figures; one scale for all bars">
                  <ColumnChart title="Revenue and profit" categories={labels} {...rev} />
                </Section>
                <Section title="Margin profile" sub="Share of revenue by fiscal year">
                  <ColumnChart title="Margin profile" categories={labels} series={margins} kind="line" unitText="Percent of revenue" suffix="%" height={240} />
                </Section>
                <Section title="Cash generation" sub="Operating cash flow, capital expenditure and derived free cash flow">
                  <ColumnChart title="Cash generation" categories={labels} {...cash} />
                </Section>
                <Section title="Key observations" sub="Rule-based calculations and flags — not AI-generated">
                  <InsightList items={observations} />
                  <Link className="more" to={{ pathname: '/insights', search: `?t=${symbol}` }}>All insights and their rules →</Link>
                </Section>
              </div>
              <div className="grid-2">
                <Section title="Financial health check" sub="Nine plain yes/no tests on the latest two annual reports">
                  {company.health ? <HealthPanel health={company.health} /> : <p className="caption">Not available.</p>}
                </Section>
                <Section title="Latest from SEC" sub={company.events_checked_at
                  ? `Live filing feed — checked ${company.events_checked_at.slice(0, 16).replace('T', ' ')} UTC, refreshed hourly`
                  : 'Live filing feed'}>
                  {company.events_error && !(company.events ?? []).length
                    ? <p className="caption">The filing feed is unavailable right now: {company.events_error}</p>
                    : <FilingsList events={(company.events ?? []).slice(0, 8)} />}
                  <Link className="more" to={{ pathname: '/watchlist', search: `?t=${symbol}` }}>Follow companies on your watchlist →</Link>
                </Section>
              </div>
              <Section title="Balance sheet" sub={`As of ${last.period_end} (${fy} ${last.form})`}>
                <KpiStrip label="Balance sheet" items={[
                  { label: 'Total assets', value: money(v.total_assets), available: !isMissing(v.total_assets) },
                  { label: 'Total liabilities', value: money(v.total_liabilities), foot: isMissing(r.liabilities_to_assets) ? '' : `${formatPercent(r.liabilities_to_assets)} of assets`, available: !isMissing(v.total_liabilities) },
                  { label: "Shareholders' equity", value: money(v.total_equity), available: !isMissing(v.total_equity) },
                  { label: 'Cash', value: money(v.cash), available: !isMissing(v.cash) },
                  { label: 'Diluted EPS', value: formatPerShare(v.eps_diluted, cur), foot: 'per share, reported', available: !isMissing(v.eps_diluted) },
                  { label: 'Return on equity', value: formatPercent(r.return_on_equity), foot: 'net income / year-end equity', available: !isMissing(r.return_on_equity) },
                ]} />
              </Section>
              {fin.warnings.length > 0 && (
                <details className="disclosure">
                  <summary>Data notes ({fin.warnings.length})</summary>
                  <ul>{fin.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                </details>
              )}
            </>
          )
        }}
      </CompanyGate>
    </>
  )
}
