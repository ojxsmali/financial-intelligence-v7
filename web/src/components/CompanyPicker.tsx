import { useQuery } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../lib/api'

// WAI-ARIA combobox (list autocomplete). Type a ticker or name; ↑/↓ to move, Enter to pick, Esc to close.
export function CompanyPicker({ label, onPick, placeholder = 'Search ticker or company', exclude = [], compact = false, autoFocus = false }: {
  label: string; onPick: (symbol: string) => void; placeholder?: string; exclude?: string[]; compact?: boolean; autoFocus?: boolean
}) {
  const id = useId()
  const [text, setText] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(text.trim()), 160)
    return () => window.clearTimeout(t)
  }, [text])

  const { data, isFetching, isError } = useQuery({
    queryKey: ['symbols', debounced],
    queryFn: () => api.symbols(debounced),
    enabled: debounced.length > 0,
    staleTime: 10 * 60_000,
  })
  const results = (data?.results ?? []).filter(r => !exclude.includes(r.symbol))

  useEffect(() => setActive(0), [debounced])
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const pick = (symbol: string) => {
    onPick(symbol)
    setText('')
    setOpen(false)
  }

  const showList = open && debounced.length > 0
  const status = !debounced ? '' : isError ? 'Search failed' : isFetching && !data ? 'Searching…'
    : results.length ? `${results.length} result${results.length === 1 ? '' : 's'}` : 'No matching companies'

  return (
    <div className={compact ? 'picker compact' : 'picker'} ref={wrap}>
      <label htmlFor={`${id}-in`} className={compact ? 'sr-only' : 'field-label'}>{label}</label>
      <input
        id={`${id}-in`} autoFocus={autoFocus} type="text" role="combobox" autoComplete="off" spellCheck={false} value={text} placeholder={placeholder}
        aria-expanded={showList} aria-controls={`${id}-list`} aria-autocomplete="list"
        aria-activedescendant={showList && results[active] ? `${id}-opt-${active}` : undefined}
        onChange={e => { setText(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive(a => Math.min(a + 1, Math.max(results.length - 1, 0))) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter') { if (showList && results[active]) { e.preventDefault(); pick(results[active].symbol) } }
          else if (e.key === 'Escape') { setOpen(false) }
        }}
      />
      <span className="sr-only" aria-live="polite">{showList ? status : ''}</span>
      {showList && (
        <ul id={`${id}-list`} role="listbox" className="listbox" aria-label={`${label} suggestions`}>
          {results.map((r, i) => (
            <li key={r.symbol} id={`${id}-opt-${i}`} role="option" aria-selected={i === active}
              onMouseDown={e => { e.preventDefault(); pick(r.symbol) }} onMouseEnter={() => setActive(i)}>
              <span className="opt-sym">{r.symbol}</span><span className="opt-name">{r.name}</span><span className="opt-ex">{r.exchange}</span>
            </li>
          ))}
          {!results.length && <li className="listbox-empty" role="presentation">{status}</li>}
        </ul>
      )}
    </div>
  )
}
