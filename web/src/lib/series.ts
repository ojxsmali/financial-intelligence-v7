import type { ChartSeries } from '../components/Charts'
import { SERIES } from '../components/Charts'
import { currencySymbol, formatMoney, formatPercent, resolveUnit, scaleLabel, SCALES, type Unit } from './format'

type Row = { fiscal_year: number; values?: Record<string, number | null>; ratios?: Record<string, number | null> }

const pick = (r: Row, key: string) => r.values?.[key] ?? r.ratios?.[key] ?? null

/** Monetary series on ONE shared scale. Colour slots are assigned in the order given, never by rank. */
export function moneySeries(rows: Row[], keys: [string, string][], currency: string, unit: Unit) {
  const present = keys.filter(([k]) => rows.some(r => pick(r, k) !== null))
  const scale = resolveUnit(present.flatMap(([k]) => rows.map(r => pick(r, k))), unit)
  const { divisor, suffix } = SCALES[scale]
  const sym = currencySymbol(currency).trim()
  const series: ChartSeries[] = present.map(([k, label], i) => ({
    label, color: SERIES[i % SERIES.length],
    values: rows.map(r => { const v = pick(r, k); return v === null ? null : v / divisor }),
    texts: rows.map(r => formatMoney(pick(r, k), currency, unit, 2, 'Not reported')),
  }))
  return { series, unitText: scaleLabel(currency, scale), prefix: sym.length <= 3 ? sym : '', suffix }
}

export function ratioSeries(rows: Row[], keys: [string, string][]) {
  const present = keys.filter(([k]) => rows.some(r => pick(r, k) !== null))
  return present.map(([k, label], i): ChartSeries => ({
    label, color: SERIES[i % SERIES.length],
    values: rows.map(r => { const v = pick(r, k); return v === null ? null : v * 100 }),
    texts: rows.map(r => formatPercent(pick(r, k), 2, false, 'n/a')),
  }))
}

export const fyLabels = (rows: { fiscal_year: number }[]) => rows.map(r => `FY${r.fiscal_year}`)
