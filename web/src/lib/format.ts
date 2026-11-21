// One formatting system for every number on screen — a direct port of fip/formatting.py.
// Values arrive in full currency units exactly as filed; scaling happens only here, at display time.

export const MINUS = '−'

export type ScaleKey = 'units' | 'K' | 'M' | 'B' | 'T'
export type Unit = 'auto' | ScaleKey

export const SCALES: Record<ScaleKey, { divisor: number; suffix: string; word: string }> = {
  units: { divisor: 1, suffix: '', word: 'units' },
  K: { divisor: 1e3, suffix: 'K', word: 'thousands' },
  M: { divisor: 1e6, suffix: 'M', word: 'millions' },
  B: { divisor: 1e9, suffix: 'B', word: 'billions' },
  T: { divisor: 1e12, suffix: 'T', word: 'trillions' },
}

export const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$', EUR: '€', GBP: '£', JPY: '¥', CNY: 'CN¥', TWD: 'NT$', CAD: 'C$', AUD: 'A$', HKD: 'HK$', INR: '₹',
  KRW: '₩', BRL: 'R$', MXN: 'MX$', CHF: 'CHF ', DKK: 'DKK ', SEK: 'SEK ', NOK: 'NOK ', ILS: '₪', ZAR: 'R ', SGD: 'S$',
}

export type Num = number | null | undefined

export function isMissing(v: Num): v is null | undefined {
  return v === null || v === undefined || Number.isNaN(v) || !Number.isFinite(v)
}

export function currencySymbol(currency: string): string {
  const c = (currency || '').toUpperCase()
  return CURRENCY_SYMBOLS[c] ?? (currency ? `${currency} ` : '')
}

export function autoScale(value: number): ScaleKey {
  const m = Math.abs(value)
  if (m >= 1e12) return 'T'
  if (m >= 1e9) return 'B'
  if (m >= 1e6) return 'M'
  if (m >= 1e3) return 'K'
  return 'units'
}

function fixed(value: number, places: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: places, maximumFractionDigits: places })
}

export function formatMoney(value: Num, currency = 'USD', unit: Unit = 'auto', decimals = 2, missing = '—'): string {
  if (isMissing(value)) return missing
  const scale = unit === 'auto' ? autoScale(value) : unit
  const { divisor, suffix } = SCALES[scale]
  const places = scale === 'units' && Number.isInteger(value) ? 0 : decimals
  const scaled = Math.abs(value) / divisor
  const body = `${fixed(scaled, places)}${suffix}`
  const sign = value < 0 && Number(scaled.toFixed(places)) !== 0 ? MINUS : ''
  return `${sign}${currencySymbol(currency)}${body}`
}

export function formatPercent(ratio: Num, decimals = 2, signed = false, missing = '—'): string {
  if (isMissing(ratio)) return missing
  const pct = ratio * 100
  const text = `${fixed(Math.abs(pct), decimals)}%`
  if (pct < 0 && Number(Math.abs(pct).toFixed(decimals)) !== 0) return MINUS + text
  if (signed && Number(pct.toFixed(decimals)) > 0) return '+' + text
  return text
}

export function formatPp(delta: Num, decimals = 1, missing = '—'): string {
  if (isMissing(delta)) return missing
  const pp = delta * 100
  if (Number(pp.toFixed(decimals)) === 0) return `${(0).toFixed(decimals)} pp`
  return `${pp > 0 ? '+' : MINUS}${fixed(Math.abs(pp), decimals)} pp`
}

export function formatPerShare(value: Num, currency = 'USD', missing = '—'): string {
  if (isMissing(value)) return missing
  return `${value < 0 ? MINUS : ''}${currencySymbol(currency)}${fixed(Math.abs(value), 2)}`
}

export function formatMultiple(value: Num, decimals = 2, missing = '—'): string {
  return isMissing(value) ? missing : `${fixed(value, decimals)}×`
}

/** Concrete scale for a group of values that must share one scale (a table or a chart). */
export function resolveUnit(values: Num[], unit: Unit = 'auto'): ScaleKey {
  if (unit !== 'auto') return unit
  const finite = values.filter((v): v is number => !isMissing(v)).map(Math.abs)
  return finite.length ? autoScale(Math.max(...finite)) : 'units'
}

export function scaleLabel(currency: string, scale: ScaleKey): string {
  return scale === 'units' ? currency : `${currency} ${SCALES[scale].word}`
}

export function direction(v: Num): 'up' | 'down' | 'flat' {
  if (isMissing(v) || v === 0) return 'flat'
  return v > 0 ? 'up' : 'down'
}

export function fy(year: number): string {
  return `FY${year}`
}
