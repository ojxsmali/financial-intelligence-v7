import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { ColumnChart } from '../components/Charts'
import { CompanyGate } from '../components/Company'
import { EmptyState, InsightList, KpiStrip, Notice, PageHeader, Section, Segmented, TabPanel, Tabs } from '../components/ui'
import { api, type Insight } from '../lib/api'
import { downloadCsv } from '../lib/csv'
import { CURRENCY_SYMBOLS, direction, formatMoney, formatPercent, isMissing } from '../lib/format'
import { fyLabels, moneySeries } from '../lib/series'
import { useSettings } from '../lib/settings'

type Filter = 'All' | 'Fact' | 'Calculation' | 'Flag'
const SAMPLE = 'fiscal_year,revenue,net_income,operating_income,operating_cash_flow,capex\n2022,100,12,15,18,6\n2023,115,14,17,21,7\n2024,130,18,22,26,8\n2025,142,21,25,29,9\n'
const MAX_BYTES = 1_000_000

function Filtered({ items }: { items: Insight[] }) {
  const [filter, setFilter] = useState<Filter>('All')
  const shown = items.filter(i => filter === 'All' || i.category === filter)
  return (
    <>
      <Segmented label="Show" value={filter} onChange={setFilter} options={[
        { id: 'All', label: 'All' }, { id: 'Fact', label: 'Reported figures' }, { id: 'Calculation', label: 'Worked out' }, { id: 'Flag', label: 'Worth a look' },
      ] as { id: Filter; label: string }[]} />
      {shown.length ? <div className="cols-2"><InsightList items={shown} /></div>
        : <EmptyState kicker="Filtered out" title="No observations in this category">Choose another filter above.</EmptyState>}
    </>
  )
}

function Upload() {
  const { unit } = useSettings()
  const [scale, setScale] = useState('M')
  const [currency, setCurrency] = useState('USD')
  const [name, setName] = useState('Uploaded company')
  const [fileError, setFileError] = useState('')
  const run = useMutation({ mutationFn: api.upload })

  const onFile = async (file: File | undefined) => {
    setFileError('')
    run.reset()
    if (!file) return
    if (file.size > MAX_BYTES) return setFileError('The file is larger than 1 MB.')
    const text = await file.text()
    run.mutate({ csv_text: text, scale, currency, name: name.trim() || 'Uploaded company' })
  }
  const blob = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([SAMPLE], { type: 'text/csv' })); a.download = 'fip_sample_financials.csv'; a.click(); URL.revokeObjectURL(a.href) }
  const data = run.data
  const last = data?.years[data.years.length - 1]

  return (
    <Section title="Analyze your own CSV" sub="Same calculations as SEC data. The file is processed in memory on the server and not stored.">
      <form className="upload" onSubmit={e => e.preventDefault()}>
        <div className="field"><label htmlFor="up-file">CSV file (max 1 MB)</label><input id="up-file" type="file" accept=".csv,text/csv" onChange={e => onFile(e.target.files?.[0])} /></div>
        <div className="field"><label htmlFor="up-scale">Values in the file are in</label>
          <select id="up-scale" value={scale} onChange={e => setScale(e.target.value)}>
            <option value="M">Millions</option><option value="K">Thousands</option><option value="B">Billions</option><option value="units">Full units</option>
          </select></div>
        <div className="field"><label htmlFor="up-cur">Currency</label>
          <select id="up-cur" value={currency} onChange={e => setCurrency(e.target.value)}>{Object.keys(CURRENCY_SYMBOLS).map(c => <option key={c}>{c}</option>)}</select></div>
        <div className="field"><label htmlFor="up-name">Label</label><input id="up-name" value={name} maxLength={60} onChange={e => setName(e.target.value)} /></div>
      </form>
      <p className="caption">Required columns: fiscal_year (or year), revenue, net_income. Optional: operating_income, gross_profit, operating_cash_flow, capex, total_assets, total_liabilities, total_equity. Change the options before choosing the file.</p>
      <button className="btn ghost" type="button" onClick={blob}>Download sample CSV template</button>
      {fileError && <Notice kind="bad">{fileError}</Notice>}
      {run.isPending && <p className="loading" role="status">Analyzing…</p>}
      {run.isError && <Notice kind="bad">{run.error.message}</Notice>}
      {data && last && (
        <div className="upload-result">
          {data.warnings.map((w, i) => <Notice key={i} kind="info">{w}</Notice>)}
          <KpiStrip label={`${data.name}, FY${last.fiscal_year}`} items={[
            { label: 'Revenue', value: formatMoney(last.values.revenue, data.currency, unit), delta: isMissing(last.ratios.revenue_growth) ? '' : `${formatPercent(last.ratios.revenue_growth, 2, true)} YoY`, direction: direction(last.ratios.revenue_growth), foot: `FY${last.fiscal_year}` },
            { label: 'Net income', value: formatMoney(last.values.net_income, data.currency, unit) },
            { label: 'Net margin', value: formatPercent(last.ratios.net_margin) },
          ]} />
          <ColumnChart title={`${data.name}: revenue and net income`} categories={fyLabels(data.years)}
            {...moneySeries(data.years, [['revenue', 'Revenue'], ['net_income', 'Net income']], data.currency, unit)} />
          <Filtered items={data.insights} />
          <button className="btn" onClick={() => {
            const keys = Object.keys(data.years[0].values).concat(Object.keys(data.years[0].ratios))
            downloadCsv('fip_uploaded_analysis.csv', [['fiscal_year', 'period_end', ...keys, 'currency', 'unit'],
              ...data.years.map(y => [y.fiscal_year, y.period_end, ...keys.map(k => y.values[k] ?? y.ratios[k] ?? ''), data.currency, 'full units'])])
          }}>Download prepared data with ratios (CSV)</button>
        </div>
      )}
    </Section>
  )
}

export function Insights() {
  const [tab, setTab] = useState<'company' | 'upload'>('company')
  return (
    <>
      <PageHeader eyebrow="Insights" title="Rule-based" accent="observations."
        sub="Every observation is computed by a fixed rule from reported figures, and states that rule and its evidence. No AI is involved on this page." />
      <Tabs label="Insight source" value={tab} onChange={setTab} tabs={[{ id: 'company', label: 'Selected company' }, { id: 'upload', label: 'Upload your own CSV' }]} />
      <TabPanel id={tab}>
        {tab === 'company' ? (
          <CompanyGate>
            {({ fin }) => (
              <>
                <p className="caption">“Reported” figures come straight from the annual report. “Worked out” figures are simple calculations, explained in plain words. “Worth a look” points to patterns or data caveats to check in the filing. No forecasts or recommendations.</p>
                <Filtered items={fin.insights} />
              </>
            )}
          </CompanyGate>
        ) : <Upload />}
      </TabPanel>
    </>
  )
}
