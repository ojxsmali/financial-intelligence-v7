// Client-side CSV for the per-statement tables. Same protections as fip/exports.py:
// UTF-8 BOM for Excel, RFC 4180 quoting, and spreadsheet formula injection neutralised.

export function sanitizeCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return /^[=+\-@\t\r]/.test(text) && !/^-?\d+(\.\d+)?(e[+-]?\d+)?$/i.test(text) ? `'${text}` : text
}

export function toCsv(rows: unknown[][]): string {
  const esc = (v: unknown) => {
    const s = sanitizeCell(v)
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return '﻿' + rows.map(r => r.map(esc).join(',')).join('\r\n') + '\r\n'
}

export function downloadCsv(filename: string, rows: unknown[][]) {
  const blob = new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
