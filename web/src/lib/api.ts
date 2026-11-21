// Typed client for the FastAPI layer (fip/api.py). All requests are same-origin /api/*.

export type Insight = {
  category: 'Fact' | 'Calculation' | 'Flag'; tone: string; title: string; detail: string; rule: string; evidence: string
  how?: string; source?: string
}

export type FilingEvent = {
  form: string; filing_date: string; report_date: string; accession: string; title: string; detail: string
  kind: string; importance: 'alert' | 'high' | 'normal' | 'low'; items: string[]; url: string
}

export type HealthCheck = { key: string; group: string; question: string; passed: boolean | null; detail: string; why: string }
export type Health = {
  fiscal_year: number | null; prior_year: number | null; checks: HealthCheck[]; passed: number; available: number
  verdict: 'Strong' | 'Average' | 'Weak' | 'Not enough data'; summary: string
}

export type WatchItem = { symbol: string; ok: boolean; name: string; exchange?: string; events: FilingEvent[]; checked_at?: string; error?: string }

export type ScreenerRow = {
  cik: number; symbol: string; name: string; exchange: string; sector: string
  revenue: number | null; net_income: number | null; total_assets: number | null
  net_margin: number | null; revenue_growth: number | null; return_on_assets: number | null
  verified: boolean; corrected: boolean; fiscal_year: number | null
}
export type Screener = {
  year: number; sort: string; order: 'asc' | 'desc'; total: number; excluded: number; universe_size: number
  verified: number; corrected: number
  rows: ScreenerRow[]; metrics: Record<string, { label: string; kind: 'money' | 'ratio' }>
}

export type FactMeta = {
  concept: string; derived: boolean; formula: string; restated: boolean; original_value: number | null
  form: string; filed: string; accession: string
}

export type Year = {
  fiscal_year: number; period_start: string; period_end: string; form: string; filed: string; accession: string
  filing_index_url: string; consecutive: boolean
  values: Record<string, number | null>; ratios: Record<string, number | null>; facts: Record<string, FactMeta>
}

export type Financials = {
  cik: number; entity_name: string; taxonomy: string; basis: string; currency: string; origin: string
  retrieved_at: string; source_url: string; warnings: string[]; excluded_note: string; years: Year[]
  revenue_cagr: { value: number | null; years: number }; insights: Insight[]
}

export type Entry = {
  symbol: string; name: string; exchange: string; instrument_type: string; is_company: boolean; cik: number | null
  sector: string; sic_description: string; country: string; fiscal_year_end: string; financial_status: string
}

export type Filing = { form: string; filing_date: string; report_date: string; accession: string; url: string; index_url?: string }

export type Profile = {
  name: string; sic_description: string; sector: string; fiscal_year_end: string; location: string; edgar_url: string
  annual_filings: Filing[]
}

export type ApiError = { kind: string; title?: string; message: string; edgar_url?: string; ref?: string; retryable?: boolean }

export type Company = {
  symbol: string; status: 'ok' | 'not_listed' | 'not_company' | 'error'; entry?: Entry; profile?: Profile | null
  profile_error?: string; share_classes?: string[]; error?: ApiError; financials?: Financials; notices?: string[]
  newer_filing_note?: string
  events?: FilingEvent[]; events_checked_at?: string; events_error?: string; health?: Health
}

export type Meta = {
  app: string; version: string
  universe: {
    total: number; companies: number; with_cik: number; origin: string; built_at: string; warning: string
    nasdaq_file_created: string; other_file_created: string; exchanges: string[]
    by_exchange: Record<string, number>; by_type: Record<string, number>
  }
  instrument_types: string[]; company_types: string[]; sectors: string[]; gemini_configured: boolean
  sec_contact_configured: boolean; default_compare: string[]; max_compare: number; currencies: string[]; models: string[]
}

export type SearchResult = { total: number; page: number; pages: number; page_size: number; by_exchange: Record<string, number>; rows: Entry[] }

export type CompareRow = {
  symbol: string; company: string; currency: string; taxonomy: string; basis: string; fiscal_year: number
  period_end: string; form: string; cagr_years: number
  [metric: string]: string | number | null
}

export type Compare = {
  symbols: string[]; companies: { symbol: string; name: string; ok: boolean; error?: string; notices?: string[] }[]
  rows: CompareRow[]; warnings: string[]
  series: Record<string, { fiscal_year: number; period_end: string; [k: string]: number | string | null }[]>
}

export type Methodology = {
  metrics: { key: string; label: string; statement: string; kind: string; us_gaap: string[]; ifrs: string[]; description: string }[]
  ratios: { key: string; label: string; formula: string }[]
  forms: Record<string, string>; free_tier_models: string[]; default_models: string[]
  sources: { nasdaq_listed: string; other_listed: string; sec_tickers: string }
  universe: { built_at: string; origin: string; nasdaq_file_created: string; other_file_created: string }
}

export type AssistantStatus = {
  configured: boolean; enabled: boolean; access_code_required: boolean; client_remaining: number; client_limit: number
  global_remaining: number; global_limit: number; per_minute: number; cooldown_seconds: number; retry_after: number
  models: string[]; rejected_models: string[]; max_question_chars: number; max_companies: number
  presets: Record<string, string>
}

export type Answer = {
  text: string; model: string; symbols: string[]; question: string; fact_pack: unknown; at: string
  from_cache: boolean; skipped: string[]
}

export type UploadResult = {
  name: string; currency: string; warnings: string[]; insights: Insight[]
  years: { fiscal_year: number; period_end: string; values: Record<string, number | null>; ratios: Record<string, number | null> }[]
}

export class RequestError extends Error {
  status: number
  kind: string
  ref: string
  constructor(status: number, kind: string, message: string, ref = '') {
    super(message)
    this.status = status
    this.kind = kind
    this.ref = ref
  }
}

// Visitor-facing wording for failures that are not the visitor's doing. Technical detail never reaches
// the page: the server logs it privately under the reference ID shown with the message.
export const MESSAGES = {
  internal: 'Something went wrong. Please try again shortly.',
  data: 'Financial data is temporarily unavailable. Please try again later.',
  service: 'This service is temporarily unavailable. We are working to restore it.',
  network: 'We couldn’t reach the server. Check your connection and try again.',
  timeout: 'This is taking longer than usual. Please try again shortly.',
}

/** Error kinds whose server-written message is meant for the visitor (validation, limits, explanations). */
const VISITOR_KINDS = new Set(['bad_request', 'bad_csv', 'access_code', 'limit', 'no_data', 'not_found', 'quota',
  'blocked', 'empty', 'not_configured', 'unavailable', 'upstream', 'internal'])

export function toVisitorError(status: number, body: unknown, headerRef = ''): RequestError {
  const err = (body && typeof body === 'object' && 'error' in body ? (body as { error?: ApiError & { ref?: string } }).error : undefined)
  const ref = err?.ref || headerRef
  if (err && typeof err.message === 'string' && VISITOR_KINDS.has(err.kind)) return new RequestError(status, err.kind, err.message, ref)
  // Anything else (platform error pages, gateway timeouts, unexpected shapes) gets a generic message.
  if (status === 504) return new RequestError(status, 'timeout', MESSAGES.timeout, ref)
  if (status === 502 || status === 503) return new RequestError(status, 'unavailable', MESSAGES.service, ref)
  if (status === 404) return new RequestError(status, 'not_found', 'We couldn’t find what you were looking for.', ref)
  return new RequestError(status, 'internal', MESSAGES.internal, ref)
}

const CONTACT_KEY = 'fip.secContact'

/** Optional visitor-supplied SEC contact (only used when the server has none configured). */
export function getContact(): string {
  try { return localStorage.getItem(CONTACT_KEY) ?? '' } catch { return '' }
}
export function setContact(value: string) {
  try { if (value) localStorage.setItem(CONTACT_KEY, value); else localStorage.removeItem(CONTACT_KEY) } catch { /* ignore */ }
}

const DEFAULT_TIMEOUT_MS = 30_000

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const headers = new Headers(init?.headers)
  const contact = getContact()
  if (contact) headers.set('X-SEC-Contact', contact)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), init?.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(path, { ...init, headers, signal: controller.signal })
  } catch (e) {
    clearTimeout(timer)
    if (controller.signal.aborted) throw new RequestError(0, 'timeout', MESSAGES.timeout)
    void e
    throw new RequestError(0, 'network', MESSAGES.network)
  }
  let body: unknown = null
  try { body = await res.json() } catch { /* non-JSON (e.g. a platform error page) */ } finally { clearTimeout(timer) }
  const ref = res.headers.get('X-Request-ID') ?? ''
  // 404 for an unknown company still carries a useful, visitor-safe payload.
  if (res.status === 404 && body && typeof body === 'object' && 'status' in body) return body as T
  if (!res.ok) throw toVisitorError(res.status, body, ref)
  if (body === null || typeof body !== 'object') throw new RequestError(res.status, 'internal', MESSAGES.internal, ref)
  return body as T
}

/** Fire-and-forget crash report (message and page only). Never throws, never blocks the UI. */
export function reportClientError(message: string, kind = 'render', ref = '') {
  try {
    const key = `${kind}:${message.slice(0, 80)}`
    const w = window as unknown as { __fipReported?: Set<string> }
    w.__fipReported ??= new Set()
    if (w.__fipReported.has(key) || w.__fipReported.size > 10) return
    w.__fipReported.add(key)
    void fetch('/api/client-error', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
      body: JSON.stringify({ message: message.slice(0, 500), page: location.pathname, kind, ref }),
    }).catch(() => {})
  } catch { /* reporting must never break the page */ }
}

const q = (params: Record<string, string | number | boolean | string[] | undefined>) => {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === '') continue
    if (Array.isArray(v)) v.forEach(x => sp.append(k, x))
    else sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const api = {
  meta: () => request<Meta>('/api/meta'),
  symbols: (query: string) => request<{ results: { symbol: string; name: string; exchange: string }[] }>(`/api/symbols${q({ q: query })}`),
  search: (p: { q: string; exchange: string[]; type: string[]; sector: string[]; filers: boolean; page: number }) =>
    request<SearchResult>(`/api/search${q(p)}`),
  company: (symbol: string, refresh = false) =>
    request<Company>(`/api/company/${encodeURIComponent(symbol)}${refresh ? '?refresh=true' : ''}`),
  compare: (symbols: string[]) => request<Compare>(`/api/compare${q({ symbols: symbols.join(',') })}`, { timeoutMs: 60_000 }),
  methodology: () => request<Methodology>('/api/methodology'),
  assistantStatus: () => request<AssistantStatus>('/api/assistant/status'),
  ask: (body: { symbols: string[]; question: string; access_code: string }) =>
    request<Answer>('/api/assistant/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), timeoutMs: 70_000 }),
  events: (symbol: string, all = false) =>
    request<{ symbol: string; name: string; events: FilingEvent[]; checked_at: string; error: string }>(
      `/api/events/${encodeURIComponent(symbol)}${all ? '?all=true' : ''}`),
  watchlist: (symbols: string[]) => request<{ items: WatchItem[] }>(`/api/watchlist${q({ symbols: symbols.join(',') })}`),
  screener: (p: { sort: string; order: string; sector: string[]; min_revenue: number; limit: number }) =>
    request<Screener>(`/api/screener${q({ ...p, min_revenue: p.min_revenue || undefined })}`, { timeoutMs: 70_000 }),
  upload: (body: { csv_text: string; scale: string; currency: string; name: string }) =>
    request<UploadResult>('/api/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
}

export const exportUrls = {
  company: (symbol: string) => `/api/export/company/${encodeURIComponent(symbol)}.csv`,
  compare: (symbols: string[]) => `/api/export/compare.csv?symbols=${encodeURIComponent(symbols.join(','))}`,
}
