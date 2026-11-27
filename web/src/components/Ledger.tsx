import { animate, motion, useDragControls, useMotionValue } from 'motion/react'
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react'
import type { Company, Financials, Year } from '../lib/api'
import { formatMoney, formatPercent, type Unit } from '../lib/format'
import { Skyline3D } from './three/Scene3D'
import { Chip } from './ui'

const METRICS = [
  { id: 'revenue', label: 'Revenue' },
  { id: 'net_income', label: 'Net income' },
  { id: 'operating_cash_flow', label: 'Operating cash' },
  { id: 'free_cash_flow', label: 'Free cash flow' },
] as const
type MetricId = (typeof METRICS)[number]['id']

const ORIGIN: Record<string, [string, string]> = {
  live: ['Live SEC data', 'ok'],
  'disk cache': ['Cached SEC data (<12 h)', 'info'],
  'disk cache (stale)': ['Stale cache — refresh failed', 'warn'],
  'bundled snapshot': ['Bundled snapshot', 'warn'],
}

const SPRING = { type: 'spring', stiffness: 520, damping: 34 } as const

const reduced = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** A figure that rolls from whatever it currently shows to the new value (never restarting from zero).
 *  The text is owned by the animation, not by React, so a re-render can never make it jump. */
function Rolling({ value, format }: { value: number; format: (v: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const shown = useRef(0)
  const fmt = useRef(format)
  fmt.current = format
  const target = format(value)
  useLayoutEffect(() => {
    if (ref.current && !ref.current.textContent) ref.current.textContent = reduced() ? target : fmt.current(0)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (reduced()) { shown.current = value; el.textContent = target; return }
    const c = animate(shown.current, value, {
      duration: 0.5, ease: [0.2, 0.8, 0.2, 1],
      onUpdate: v => { shown.current = v; el.textContent = fmt.current(v) },
      onComplete: () => { shown.current = value; el.textContent = target },
    })
    return () => c.stop()
  }, [value, target])
  return <span ref={ref} />
}

/** Flat fallback for browsers without WebGL: the same years as bars you can scrub by dragging. */
function FlatBars({ values, labels, idx, setIdx }: { values: (number | null)[]; labels: string[]; idx: number; setIdx: (i: number) => void }) {
  const track = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [dragging, setDragging] = useState(false)
  const x = useMotionValue(0)
  const controls = useDragControls()
  const n = values.length

  useLayoutEffect(() => {
    const el = track.current
    if (!el) return
    const measure = () => setWidth(el.clientWidth)
    measure()
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [])

  const slot = n > 0 ? width / n : 0
  useEffect(() => {
    if (dragging || !width) return
    const c = animate(x, slot * idx + slot / 2, SPRING)
    return () => c.stop()
  }, [idx, width, dragging]) // eslint-disable-line react-hooks/exhaustive-deps

  const nearest = (px: number) => Math.max(0, Math.min(n - 1, Math.floor(px / (slot || 1))))
  const present = values.filter((v): v is number => v !== null)
  const top = Math.max(0, ...present)
  const bottom = Math.min(0, ...present)
  const range = top - bottom || 1
  const base = (top / range) * 100

  const grab = (ev: PointerEvent<HTMLDivElement>) => {
    const r = track.current?.getBoundingClientRect()
    if (!r) return
    const px = ev.clientX - r.left
    x.set(Math.max(0, Math.min(width, px)))
    setIdx(nearest(px))
    controls.start(ev, { snapToCursor: false })
  }

  return (
    <div ref={track} className={dragging ? 'ledger-bars dragging' : 'ledger-bars'} onPointerDown={grab} aria-hidden="true">
      <div className="ledger-base" style={{ top: `${base}%` }} />
      {values.map((v, i) => {
        const h = v === null ? 0 : (Math.abs(v) / range) * 100
        const neg = v !== null && v < 0
        return (
          <div key={labels[i]} className="ledger-col">
            <motion.div className={['ledger-bar', i === idx ? 'on' : '', neg ? 'neg' : '', v === null ? 'missing' : ''].join(' ')}
              style={neg ? { top: `${base}%` } : { bottom: `${100 - base}%` }}
              initial={{ height: 0 }} animate={{ height: `${v === null ? 0 : Math.max(h, 0.6)}%` }}
              transition={{ type: 'spring', stiffness: 160, damping: 17, delay: i * 0.035 }} />
          </div>
        )
      })}
      <motion.div className="ledger-handle" style={{ x }} drag="x" dragControls={controls} dragListener={false}
        dragConstraints={{ left: 0, right: width }} dragElastic={0.18} dragMomentum={false}
        onDragStart={() => setDragging(true)} onDrag={() => setIdx(nearest(x.get()))}
        onDragEnd={() => { setIdx(nearest(x.get())); setDragging(false) }} whileDrag={{ scale: 1.15 }}>
        <span className="ledger-grip" />
      </motion.div>
    </div>
  )
}

/**
 * The Overview hero: a full-bleed cobalt poster. The company's name at billboard size, and its reported
 * history as a 3D skyline — one column per fiscal year, one scale, zero at the floor. Drag to turn it,
 * tap a column (or use the year rail / arrow keys) to read that year. Every figure is a reported value.
 */
export function Ledger({ company, fin, years, unit }: { company: Company; fin: Financials; years: Year[]; unit: Unit }) {
  const e = company.entry!
  const [metric, setMetric] = useState<MetricId>('revenue')
  const [idx, setIdx] = useState(years.length - 1)

  useEffect(() => { setIdx(years.length - 1) }, [years.length, fin.cik])

  const n = years.length
  const values = years.map(y => y.values[metric] ?? null)
  const labels = years.map(y => String(y.fiscal_year))
  const year = years[idx]
  const value = values[idx]
  const prev = idx > 0 ? values[idx - 1] : null
  const growth = value !== null && prev !== null && prev !== 0 ? (value - prev) / Math.abs(prev) : null
  const money = (v: number | null) => formatMoney(v, fin.currency, unit)
  const label = METRICS.find(m => m.id === metric)!.label
  const origin = ORIGIN[fin.origin] ?? [fin.origin, 'info']
  const pick = (i: number) => setIdx(Math.max(0, Math.min(n - 1, i)))

  const onKey = (ev: KeyboardEvent) => {
    const next = ev.key === 'ArrowRight' || ev.key === 'ArrowUp' ? idx + 1 : ev.key === 'ArrowLeft' || ev.key === 'ArrowDown' ? idx - 1
      : ev.key === 'Home' ? 0 : ev.key === 'End' ? n - 1 : null
    if (next === null) return
    ev.preventDefault()
    pick(next)
  }

  const sceneLabel = `${label} by fiscal year, FY${labels[0]}–FY${labels[n - 1]}: ` +
    values.map((v, i) => `FY${labels[i]} ${v === null ? 'not reported' : money(v)}`).join('; ')

  return (
    <section className="ledger" aria-labelledby="ledger-name">
      <div className="slab">
        <div className="slab-inner">
          <div className="ledger-id">
            <p className="ledger-tag">
              <span className="ticker">{e.symbol}</span>
              {[e.exchange, e.instrument_type, e.cik ? `CIK ${e.cik}` : '', e.sector !== 'Unclassified' ? e.sector : ''].filter(Boolean).map((m, i) => <span key={i}>{m}</span>)}
            </p>
            <motion.h2 id="ledger-name" className="ledger-name" style={{ '--len': Math.max(8, e.name.length) } as CSSProperties}
              initial={{ opacity: 0, y: 40, rotateX: -35 }} animate={{ opacity: 1, y: 0, rotateX: 0 }}
              transition={{ type: 'spring', stiffness: 160, damping: 18 }}>{e.name}</motion.h2>
            <p className="ledger-dek">
              <span>{n} fiscal year{n === 1 ? '' : 's'} of <em>audited</em> results, FY{years[0]?.fiscal_year}–FY{years[n - 1]?.fiscal_year}.</span>
              <span className="ledger-chips"><Chip kind={origin[1]} dot>{origin[0]}</Chip><Chip>{fin.basis} · {fin.currency}</Chip></span>
            </p>
          </div>

          <div className="ledger-body">
            <div className="ledger-readout">
              <div className="metric-tabs" role="radiogroup" aria-label="Figure shown">
                {METRICS.map(m => (
                  <button key={m.id} type="button" role="radio" aria-checked={metric === m.id} onClick={() => setMetric(m.id)}>
                    {metric === m.id && <motion.span layoutId="ledger-metric" className="metric-pill" transition={SPRING} />}
                    <span>{m.label}</span>
                  </button>
                ))}
              </div>
              <p className="ledger-year" aria-hidden="true">FY{year?.fiscal_year}</p>
              <p className="ledger-figure" aria-live="polite">
                <span className="sr-only">{label}, FY{year?.fiscal_year}: </span>
                {value === null ? <span className="na">Not reported</span> : <Rolling value={value} format={money} />}
              </p>
              <p className="ledger-delta">
                {growth === null ? <span className="flat">No prior-year comparison</span> : (
                  <span className={growth > 0 ? 'up' : growth < 0 ? 'down' : 'flat'}>
                    <span aria-hidden="true">{growth > 0 ? '▲ ' : growth < 0 ? '▼ ' : ''}</span>
                    {formatPercent(growth, 1, true)} vs FY{years[idx - 1].fiscal_year}
                  </span>
                )}
              </p>
              {year && <p className="ledger-src">{year.form} filed {year.filed} · period ended {year.period_end}</p>}
            </div>

            <div className="ledger-stage">
              <div className="sky">
                <Skyline3D values={values} selected={idx} onPick={pick} label={sceneLabel}
                  fallback={<FlatBars values={values} labels={labels} idx={idx} setIdx={pick} />} />
                <span className="sky-axis" aria-hidden="true">{label} · one scale · zero at the floor</span>
              </div>
              <div className="year-rail" role="slider" tabIndex={0} aria-label={`${label}: fiscal year — use the arrow keys`}
                aria-valuemin={0} aria-valuemax={Math.max(0, n - 1)} aria-valuenow={idx}
                aria-valuetext={`FY${year?.fiscal_year}: ${value === null ? 'not reported' : money(value)}`} onKeyDown={onKey}>
                {labels.map((l, i) => (
                  <button key={l} type="button" tabIndex={-1} className={i === idx ? 'on' : ''} onClick={() => pick(i)}>
                    {i === idx && <motion.span layoutId="year-pill" className="year-pill" transition={SPRING} />}
                    <span>’{l.slice(-2)}</span>
                  </button>
                ))}
              </div>
              <p className="ledger-hint" aria-hidden="true"><span className="hint-3d">Drag to turn · tap a column</span><span className="hint-flat">Drag across the years</span> · ← → keys</p>
            </div>
          </div>
        </div>
      </div>

      <dl className="facts ledger-facts">
        <div><dt>Fiscal year-end</dt><dd>{e.fiscal_year_end || '—'}</dd></div>
        <div><dt>Latest annual period</dt><dd>{years[n - 1]?.period_end ?? '—'}</dd></div>
        <div><dt>Annual report</dt><dd>{years[n - 1] ? `${years[n - 1].form} · filed ${years[n - 1].filed}` : '—'}</dd></div>
        <div><dt>Industry (SIC)</dt><dd>{e.sic_description || '—'}</dd></div>
      </dl>
    </section>
  )
}
