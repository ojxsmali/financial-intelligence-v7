import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Chip, ErrorState, Notice, PageHeader, Section, Skeleton } from '../components/ui'
import { api } from '../lib/api'
import { Markdown } from '../lib/markdown'
import { useSettings } from '../lib/settings'

export function Assistant() {
  const { symbol, compare } = useSettings()
  const client = useQueryClient()
  const status = useQuery({ queryKey: ['assistant-status'], queryFn: api.assistantStatus, staleTime: 30_000 })
  const pool = [...new Set([symbol, ...compare])]
  const [chosen, setChosen] = useState<string[]>([symbol])
  const [question, setQuestion] = useState('')
  const [code, setCode] = useState('')
  const ask = useMutation({ mutationFn: api.ask, onSettled: () => client.invalidateQueries({ queryKey: ['assistant-status'] }) })

  if (status.isPending) return <Skeleton message="Checking assistant status…" />
  if (status.isError) return <ErrorState error={status.error} retry={() => status.refetch()} />
  const s = status.data
  const q = question || s.presets.Performance
  const selected = chosen.filter(c => pool.includes(c))
  const canAsk = s.configured && s.enabled && selected.length > 0 && q.trim().length > 0 && !ask.isPending

  return (
    <>
      <PageHeader eyebrow="Assistant" title="Ask Google Gemini about the reported figures"
        sub="This is the only AI feature in the app. Gemini receives just the structured SEC figures shown elsewhere, and must keep facts, calculations and hypotheses apart and cite each fiscal year." />
      <div className="tags">
        <Chip kind={s.configured ? 'ok' : 'warn'} dot>{s.configured ? 'Gemini configured' : 'Gemini not configured'}</Chip>
        <Chip kind="info">Free-tier models only</Chip>
        <Chip>Your remaining questions (24 h): {s.client_remaining}/{s.client_limit}</Chip>
        <Chip>Site budget left: {s.global_remaining}/{s.global_limit}</Chip>
        {!s.enabled && <Chip kind="bad">Disabled by owner</Chip>}
      </div>
      {!s.configured && (
        <Notice kind="info">The research assistant isn’t available on this site right now. All dashboards, statements, the screener and the rule-based insights work as usual.</Notice>
      )}

      <form className="ask" onSubmit={e => { e.preventDefault(); if (canAsk) ask.mutate({ symbols: selected, question: q, access_code: code }) }}>
        <fieldset>
          <legend>Companies to analyze (max {s.max_companies})</legend>
          <p className="caption">From the selected company and your comparison list.</p>
          <div className="checks">
            {pool.map(p => (
              <label key={p} className="check">
                <input type="checkbox" checked={selected.includes(p)} disabled={!selected.includes(p) && selected.length >= s.max_companies}
                  onChange={e => setChosen(e.target.checked ? [...selected, p] : selected.filter(x => x !== p))} />
                {p}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="presets" role="group" aria-label="Template questions">
          <span className="caption">Start from a template:</span>
          {Object.entries(s.presets).map(([name, text]) => <button key={name} type="button" className="btn ghost sm" onClick={() => setQuestion(text)}>{name}</button>)}
        </div>
        <label htmlFor="ai-q" className="field-label">Research question</label>
        <textarea id="ai-q" rows={4} maxLength={s.max_question_chars} value={q} onChange={e => setQuestion(e.target.value)} aria-describedby="ai-q-count" />
        <p id="ai-q-count" className="caption">{q.length}/{s.max_question_chars} characters</p>
        {s.access_code_required && (
          <div className="field"><label htmlFor="ai-code">Access code</label>
            <input id="ai-code" type="password" autoComplete="off" value={code} maxLength={128} onChange={e => setCode(e.target.value)} />
            <p className="caption">The site owner limits AI usage to invited visitors.</p></div>
        )}
        <button className="btn primary" disabled={!canAsk}>{ask.isPending ? 'Asking Gemini…' : 'Generate analysis'}</button>
      </form>

      {ask.isPending && <p className="loading" role="status">Loading SEC data and asking Gemini (free tier)… this can take up to a minute.</p>}
      {ask.isError && <Notice kind="bad">{ask.error.message}</Notice>}
      {ask.data && (
        <Section title="Gemini's answer" sub="AI-generated text — check every figure against the cited filing (Sources page). Not investment advice.">
          {ask.data.skipped.length > 0 && <Notice>Skipped (no annual SEC financial data): {ask.data.skipped.join(', ')}</Notice>}
          <div className="tags">
            <Chip kind="info">{ask.data.model}</Chip><Chip>{ask.data.at}</Chip><Chip kind="sym">{ask.data.symbols.join(', ')}</Chip>
            {ask.data.from_cache && <Chip kind="ok">Cached answer · no quota used</Chip>}
          </div>
          <article className="answer"><Markdown text={ask.data.text} /></article>
          <details className="disclosure">
            <summary>Exactly what was sent to Gemini (fact pack)</summary>
            <p className="caption">Structured SEC figures in millions of the reporting currency, plus your question. No API key, personal data or browsing history is sent.</p>
            <pre className="code">{JSON.stringify(ask.data.fact_pack, null, 1).slice(0, 20000)}</pre>
          </details>
        </Section>
      )}

      <details className="disclosure">
        <summary>How the assistant is protected</summary>
        <ul>
          <li>The Gemini key is kept on the server; this page never receives it.</li>
          <li>Models are restricted to Google's free-tier allowlist ({s.models.join(', ')}). There is no paid fallback; quota errors simply pause the assistant.</li>
          <li>Server-side limits: {s.client_limit} questions per visitor per 24 h, {s.global_limit} per site per 24 h, {s.per_minute} per minute, {s.cooldown_seconds} s cooldown.</li>
          <li>Identical questions about identical data are answered from a 24 h cache without using quota.</li>
          <li>Questions are limited to {s.max_question_chars} characters and {s.max_companies} companies; the model is instructed to treat them as data, not instructions.</li>
        </ul>
      </details>
    </>
  )
}
