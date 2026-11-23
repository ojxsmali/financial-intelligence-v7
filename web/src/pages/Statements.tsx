import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { CompanyGate } from '../components/Company'
import { PageHeader, StatTable, TabPanel, Tabs, type Row } from '../components/ui'
import { api, exportUrls, type Financials, type Year } from '../lib/api'
import { downloadCsv } from '../lib/csv'
import { formatMoney, formatMultiple, formatPerShare, formatPercent, isMissing, resolveUnit, SCALES } from '../lib/format'
import { useSettings } from '../lib/settings'

type Tab = 'income' | 'balance' | 'cashflow' | 'ratios' | 'concepts'

const STATEMENTS: Record<'income' | 'balance' | 'cashflow', [string, string][]> = {
  income: [['revenue', ''], ['cost_of_revenue', 'sub'], ['gross_profit', ''], ['operating_income', ''], ['net_income', ''], ['eps_diluted', 'sub']],
  balance: [['total_assets', ''], ['total_liabilities', ''], ['total_equity', ''], ['cash', 'sub']],
  cashflow: [['operating_cash_flow', ''], ['capex', 'sub'], ['free_cash_flow', '']],
}
const NAMES = { income: 'Income statement', balance: 'Balance sheet', cashflow: 'Cash flow' }
const RATIOS = ['revenue_growth', 'gross_margin', 'operating_margin', 'net_margin', 'fcf_margin', 'cash_conversion', 'liabilities_to_assets', 'return_on_equity']

function Statement({ fin, years, keys, labels, name, symbol }: { fin: Financials; years: Year[]; keys: [string, string][]; labels: Record<string, string>; name: string; symbol: string }) {
  const { unit } = useSettings()
  const money = keys.filter(([k]) => k !== 'eps_diluted').flatMap(([k]) => years.map(y => y.values[k]))
  const scale = resolveUnit(money, unit)
  const rows: Row[] = keys.map(([k, cls]) => {
    const cells = [labels[k] ?? k]
    const neg = [false]
    const marks = ['']
    for (const y of years) {
      const v = y.values[k]
      const fact = y.facts[k]
      if (isMissing(v) || !fact) { cells.push('—'); neg.push(false); marks.push(''); continue }
      cells.push(k === 'eps_diluted' ? formatPerShare(v, fin.currency) : formatMoney(v, fin.currency, scale))
      neg.push(v < 0)
      const notes = []
      if (fact.derived) notes.push(`Derived: ${fact.formula}`)
      if (fact.restated) notes.push(`Revised in a later filing (originally ${formatMoney(fact.original_value, fin.currency)})`)
      marks.push(notes.join('; '))
    }
    return { cells, cls, neg, marks }
  })
  const header = [`${fin.currency} · ${SCALES[scale].word}`, ...years.map(y => `FY${y.fiscal_year}`)]
  const csv = () => downloadCsv(`${symbol}_${name.toLowerCase().replace(/ /g, '_')}.csv`, [
    ['metric', 'unit', ...years.map(y => `FY${y.fiscal_year} (${y.period_end})`)],
    ...keys.map(([k]) => [labels[k] ?? k, k === 'eps_diluted' ? `${fin.currency}/share` : `${fin.currency} (full units)`, ...years.map(y => y.values[k] ?? '')]),
  ])
  return (
    <>
      <StatTable header={header} rows={rows} caption={`${name}, ${fin.currency} ${SCALES[scale].word}, one scale for the whole table`} />
      <p className="caption">● marks derived or later-revised values (hover or focus for details). “—” = not reported in XBRL; never estimated.</p>
      <button className="btn" onClick={csv}>Download {name.toLowerCase()} (CSV)</button>
    </>
  )
}

export function Statements() {
  const { symbol } = useSettings()
  const [tab, setTab] = useState<Tab>('income')
  const method = useQuery({ queryKey: ['methodology'], queryFn: api.methodology, staleTime: Infinity })
  const labels = Object.fromEntries((method.data?.metrics ?? []).map(m => [m.key, m.label]))
  const ratioDefs = Object.fromEntries((method.data?.ratios ?? []).map(r => [r.key, r]))
  return (
    <>
      <PageHeader eyebrow="Statements" title="Income, balance sheet" accent="& cash flow."
        sub="Annual figures from 10-K / 20-F / 40-F XBRL data. Each column is the company's own fiscal year." />
      <CompanyGate>
        {({ fin, shown }) => (
          <>
            <Tabs label="Statement" value={tab} onChange={setTab} tabs={[
              { id: 'income', label: 'Income statement' }, { id: 'balance', label: 'Balance sheet' }, { id: 'cashflow', label: 'Cash flow' },
              { id: 'ratios', label: 'Ratios' }, { id: 'concepts', label: 'XBRL concept map' },
            ]} />
            <TabPanel id={tab}>
              {(tab === 'income' || tab === 'balance' || tab === 'cashflow') && (
                <Statement fin={fin} years={shown} keys={STATEMENTS[tab]} labels={labels} name={NAMES[tab]} symbol={symbol} />
              )}
              {tab === 'ratios' && (
                <>
                  <StatTable caption="Ratios by fiscal year" header={['Ratio', ...shown.map(y => `FY${y.fiscal_year}`)]} rows={RATIOS.map(k => ({
                    cells: [ratioDefs[k]?.label ?? k, ...shown.map(y => k === 'cash_conversion' ? formatMultiple(y.ratios[k]) : formatPercent(y.ratios[k], 2, k.endsWith('growth')))],
                    cls: 'ratio', neg: [false, ...shown.map(y => !isMissing(y.ratios[k]) && (y.ratios[k] as number) < 0)],
                  }))} />
                  <details className="disclosure"><summary>Formulas</summary>
                    <ul>{RATIOS.map(k => ratioDefs[k] && <li key={k}><b>{ratioDefs[k].label}</b> — <code>{ratioDefs[k].formula}</code></li>)}</ul>
                  </details>
                </>
              )}
              {tab === 'concepts' && (
                <>
                  <StatTable caption="Every value maps to an XBRL concept in a specific filing"
                    header={['Fiscal year · metric', 'Concept / formula', 'Form', 'Filed', 'Accession', 'Flags']}
                    rows={shown.flatMap(y => Object.entries(y.facts).map(([k, f]) => ({
                      cells: [`FY${y.fiscal_year} · ${labels[k] ?? k}`, f.concept, f.form, f.filed, f.accession, [f.derived ? 'derived' : '', f.restated ? 'revised' : ''].filter(Boolean).join(', ') || '—'],
                    })))} />
                  <p className="caption">When a later filing revises a prior year (restatement or recast), the latest filed value is shown and flagged.</p>
                </>
              )}
            </TabPanel>
            <p><a className="btn" href={exportUrls.company(symbol)} download>Download all statements, long format with provenance (CSV)</a></p>
          </>
        )}
      </CompanyGate>
    </>
  )
}
