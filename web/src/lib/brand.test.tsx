import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { KpiStrip } from '../components/ui'
import { markFaces, markSvg, MARK_COLUMNS } from './brandMark'
import { NAV, pageIndex } from './nav'

describe('brand mark', () => {
  it('draws three faces per column, all inside the box', () => {
    const faces = markFaces(32)
    expect(faces).toHaveLength(MARK_COLUMNS.length * 3)
    for (const f of faces) {
      for (const pt of f.points.split(' ')) {
        const [x, y] = pt.split(',').map(Number)
        expect(x).toBeGreaterThanOrEqual(-0.01)
        expect(x).toBeLessThanOrEqual(32.01)
        expect(y).toBeGreaterThanOrEqual(-0.01)
        expect(y).toBeLessThanOrEqual(32.01)
      }
    }
  })
  it('makes a standalone SVG with and without the tile', () => {
    expect(markSvg({ size: 64 })).toMatch(/^<svg[^>]+viewBox="0 0 64 64".*<rect/)
    expect(markSvg({ background: null })).not.toContain('<rect')
  })
})

describe('site map', () => {
  it('numbers pages for the header index', () => {
    expect(pageIndex('/')).toEqual({ n: '01', of: String(NAV.length).padStart(2, '0') })
    expect(pageIndex('/brand')?.n).toBe(String(NAV.length).padStart(2, '0'))
    expect(pageIndex('/nope')).toBeNull()
  })
})

describe('KPI tiles', () => {
  it('render the figures and ignore touch drags (only a mouse can pull a tile)', () => {
    render(<MemoryRouter><KpiStrip label="Key figures" items={[{ label: 'Revenue', value: '$1.00B' }]} /></MemoryRouter>)
    const tile = screen.getByText('Revenue').closest('.kpi') as HTMLElement
    expect(tile).toBeInTheDocument()
    fireEvent.pointerDown(tile, { pointerType: 'touch', clientX: 10, clientY: 10 })
    fireEvent.pointerMove(tile, { pointerType: 'touch', clientX: 120, clientY: 10 })
    expect(tile.style.transform).not.toMatch(/translateX/)
  })
})
