// Axis maths shared by the charts (port of fip/ui/charts.py).

export function niceStep(span: number, target = 5): number {
  if (!(span > 0) || !Number.isFinite(span)) return 1
  const raw = span / Math.max(target, 1)
  const mag = 10 ** Math.floor(Math.log10(raw))
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag
  return 10 * mag
}

/** Round tick values covering [lo, hi] and always including zero. */
export function niceTicks(lo: number, hi: number, target = 5): number[] {
  let a = Math.min(lo, 0)
  let b = Math.max(hi, 0)
  if (a === b) b = a + 1
  const step = niceStep(b - a, target)
  const start = Math.floor(a / step + 1e-9) * step
  const end = Math.ceil(b / step - 1e-9) * step
  const count = Math.round((end - start) / step)
  return Array.from({ length: count + 1 }, (_, i) => Number((start + i * step).toFixed(10)))
}

export function tickText(value: number, step: number, prefix = '', suffix = ''): string {
  let decimals = step > 0 ? Math.max(0, -Math.floor(Math.log10(step))) : 0
  while (decimals < 4 && Math.abs(Number(step.toFixed(decimals)) - step) > 1e-9) decimals++
  const sign = value < 0 ? '−' : ''
  const body = Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
  return `${sign}${prefix}${body}${suffix}`
}
