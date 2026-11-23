import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { CompanyGate } from '../components/Company'
import { ErrorState, PageHeader, Section, Skeleton, StatTable, TabPanel, Tabs } from '../components/ui'
import { api } from '../lib/api'

type Tab = 'company' | 'method' | 'platform'

const ext = { target: '_blank', rel: 'noopener noreferrer' }

export function Sources() {
  const [tab, setTab] = useState<Tab>('company')
  const m = useQuery({ queryKey: ['methodology'], queryFn: api.methodology, staleTime: Infinity })
  return (
    <>
      <PageHeader eyebrow="Sources" title="Where every number" accent="comes from." sub="Filing links, fiscal periods, XBRL concepts, formulas, timestamps and limitations." />
      <Tabs label="Sources" value={tab} onChange={setTab} tabs={[{ id: 'company', label: 'Selected company' }, { id: 'method', label: 'Methodology' }, { id: 'platform', label: 'Platform data sources' }]} />
      <TabPanel id={tab}>
        {tab === 'company' && (
          <CompanyGate>
            {({ company, fin }) => {
              const filings = company.profile?.annual_filings ?? []
              return (
                <>
                  <Section title="Primary data for this company">
                    <ul className="plain">
                      <li><b>SEC XBRL Company Facts</b> (all structured financial facts): <a href={fin.source_url} {...ext}>{fin.source_url}</a></li>
                      <li><b>SEC submissions metadata</b> (profile, SIC, filing list): <a href={`https://data.sec.gov/submissions/CIK${String(fin.cik).padStart(10, '0')}.json`} {...ext}>data.sec.gov/submissions/CIK{String(fin.cik).padStart(10, '0')}.json</a></li>
                      {company.profile && <li><b>EDGAR filing index</b>: <a href={company.profile.edgar_url} {...ext}>{company.profile.name} on EDGAR</a></li>}
                      <li>Retrieved <b>{fin.retrieved_at.slice(0, 16).replace('T', ' ')} UTC</b> · origin <b>{fin.origin}</b> · basis <b>{fin.basis}</b> · currency <b>{fin.currency}</b></li>
                    </ul>
                  </Section>
                  <Section title="Fiscal periods used" sub="Each row is one annual report; its fiscal-year label comes from the filing.">
                    <div className="table-wrap" role="region" aria-label="Fiscal periods used" tabIndex={0}>
                      <table className="table">
                        <thead><tr><th scope="col">Fiscal year</th><th scope="col">Period</th><th scope="col">Form</th><th scope="col">Filed</th><th scope="col">Documents</th></tr></thead>
                        <tbody>{[...fin.years].reverse().map(y => {
                          const doc = filings.find(f => f.accession === y.accession)
                          return (
                            <tr key={y.fiscal_year}>
                              <th scope="row">FY{y.fiscal_year}</th><td>{y.period_start} → {y.period_end}</td>
                              <td>{y.form} <span className="muted">· {m.data?.forms[y.form] ?? ''}</span></td><td>{y.filed}</td>
                              <td className="links">{doc && <a href={doc.url} {...ext}>Filing<span className="sr-only"> FY{y.fiscal_year}</span></a>}{y.filing_index_url && <a href={y.filing_index_url} {...ext}>Index<span className="sr-only"> FY{y.fiscal_year}</span></a>}</td>
                            </tr>
                          )
                        })}</tbody>
                      </table>
                    </div>
                  </Section>
                </>
              )
            }}
          </CompanyGate>
        )}
        {tab !== 'company' && (m.isPending ? <Skeleton message="Loading methodology…" /> : m.isError ? <ErrorState error={m.error} retry={() => m.refetch()} /> : tab === 'method' ? (
          <>
            <Section title="Metric definitions and XBRL concepts" sub="Concepts are tried in the order listed (revenue: largest total).">
              <StatTable header={['Metric', 'Statement', 'US GAAP concepts', 'IFRS concepts', 'Notes']} rows={m.data.metrics.map(x => ({
                cells: [x.label, x.statement, x.us_gaap.join(', ') || 'derived', x.ifrs.join(', ') || 'derived', x.description || '—'], cls: 'wrap' }))} />
            </Section>
            <Section title="Ratio formulas">
              <StatTable header={['Ratio', 'Formula']} rows={m.data.ratios.map(r => ({ cells: [r.label, r.formula], cls: 'wrap' }))} />
            </Section>
            <Section title="How annual figures are selected">
              <ol className="plain numbered">
                <li>Only facts from annual reports (10-K, 10-K/A, 10-KT, 20-F, 40-F and amendments) are used. Flow items must cover 350–380 days, so quarterly and year-to-date values can never leak in.</li>
                <li>A fiscal year is included only if it is the primary period of an annual report, labelled as the company labels it — Walmart's year ending 31 Jan 2026 is FY2026.</li>
                <li>When a later filing revises a prior year, the latest filed value is shown and marked; the original is kept for reference.</li>
                <li>One accounting basis (US GAAP or IFRS) and one reporting currency per company. Amounts are never converted between currencies.</li>
                <li>Values are stored in full currency units exactly as filed and scaled only for display, with the unit printed on every figure, axis and table.</li>
                <li>Growth rates are computed only between consecutive fiscal years and only from a positive base.</li>
                <li>Missing line items are shown as “—”; nothing is estimated, interpolated or borrowed from another registrant.</li>
              </ol>
            </Section>
            <Section title="Limitations">
              <ul className="plain">
                <li>XBRL Company Facts contains only consolidated facts: no segment or geographic detail.</li>
                <li>Some annual reports appear on EDGAR before their statements reach Company Facts; the app flags this.</li>
                <li>SIC-based sectors are approximate. No stock prices, market capitalisation or real-time data. Not investment advice.</li>
              </ul>
            </Section>
          </>
        ) : (
          <>
            <Section title="Listing universe">
              <ul className="plain">
                <li><a href={m.data.sources.nasdaq_listed} {...ext}>Nasdaq Trader — nasdaqlisted.txt</a> · file created {m.data.universe.nasdaq_file_created || '?'}</li>
                <li><a href={m.data.sources.other_listed} {...ext}>Nasdaq Trader — otherlisted.txt</a> (NYSE, NYSE American, NYSE Arca, Cboe BZX, IEX) · file created {m.data.universe.other_file_created || '?'}</li>
                <li><a href={m.data.sources.sec_tickers} {...ext}>SEC company_tickers_exchange.json</a> — ticker → CIK mapping</li>
                <li>SEC submissions metadata — SIC industry, country and fiscal-year end per registrant</li>
                <li>Built <b>{m.data.universe.built_at || '?'}</b>, origin <b>{m.data.universe.origin}</b>.</li>
              </ul>
            </Section>
            <Section title="AI assistant">
              <p>Google Gemini API, free-tier models only: {m.data.free_tier_models.join(', ')}. The model receives only the structured figures shown in this app.</p>
            </Section>
            <Section title="SEC fair access">
              <p>Requests identify the operator with a contact e-mail in the User-Agent, are rate-limited to 5 per second (SEC allows 10), retried with exponential backoff on 429/5xx, and cached (financials 12 h, profiles 24 h). See <a href="https://www.sec.gov/os/accessing-edgar-data" {...ext}>SEC: Accessing EDGAR data</a>.</p>
            </Section>
          </>
        ))}
      </TabPanel>
    </>
  )
}
