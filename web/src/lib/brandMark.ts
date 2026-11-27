/**
 * The Financial Intelligence mark: three audited years as isometric columns, rising left to right,
 * the newest one in cobalt. One source of truth for the SVG logo, the 3D logo, favicons and share cards.
 */

export const BRAND = {
  name: 'Financial Intelligence',
  short: 'FI',
  tagline: 'Audited fundamentals for every US-listed company',
  ink: '#0B0B0D',
  bone: '#F3F1EC',
  cobalt: '#2E4BFF',
  cobaltText: '#6F86FF', // cobalt tuned for text on ink (5.9:1)
  cobaltDeep: '#1A2BB8',
  signal: '#D7FF3A', // one-off highlight used only for the selected column top and focus rings on cobalt
  up: '#3DDC84',
  down: '#FF6B5E',
} as const

/** Ground-plane footprint (x, y) and height (z) of each column, in grid units. */
export const MARK_COLUMNS = [
  { x: 0, y: 0, h: 1.15, tone: 'bone' },
  { x: 1.25, y: 0, h: 1.95, tone: 'bone' },
  { x: 2.5, y: 0, h: 2.95, tone: 'cobalt' },
] as const

const C30 = Math.cos(Math.PI / 6)

type Tone = 'bone' | 'cobalt' | 'ink'
/** Face shades for a lit isometric prism: top, left (+y), right (+x). */
export const FACE: Record<Tone, [string, string, string]> = {
  bone: ['#F3F1EC', '#C8C5BD', '#8E8B84'],
  cobalt: ['#8C9EFF', '#2E4BFF', '#1A2BB8'],
  ink: ['#3A3A40', '#1C1C21', '#0B0B0D'],
}

export type Face = { points: string; fill: string }

/**
 * Polygons for the mark, back to front, fitted into a `size` box (centred).
 * `tones` can override the colour per column (e.g. all ink on a cobalt background).
 */
export function markFaces(size: number, tones?: Tone[]): Face[] {
  const u = size / 4.35
  const project = (x: number, y: number, z: number) => [(x - y) * C30 * u, (x + y) * 0.5 * u - z * u] as const
  // bounding box of the whole mark, for centring
  const pts = MARK_COLUMNS.flatMap(c => [
    project(c.x, c.y, c.h), project(c.x + 1, c.y, c.h), project(c.x, c.y + 1, 0), project(c.x + 1, c.y + 1, 0), project(c.x + 1, c.y, 0), project(c.x, c.y + 1, c.h),
  ])
  const minX = Math.min(...pts.map(p => p[0])), maxX = Math.max(...pts.map(p => p[0]))
  const minY = Math.min(...pts.map(p => p[1])), maxY = Math.max(...pts.map(p => p[1]))
  const ox = (size - (maxX - minX)) / 2 - minX
  const oy = (size - (maxY - minY)) / 2 - minY
  const P = (x: number, y: number, z: number) => {
    const [px, py] = project(x, y, z)
    return `${(px + ox).toFixed(2)},${(py + oy).toFixed(2)}`
  }
  const faces: Face[] = []
  MARK_COLUMNS.forEach((c, i) => {
    const [top, left, right] = FACE[tones?.[i] ?? c.tone]
    const { x, y, h } = c
    faces.push({ points: [P(x, y + 1, 0), P(x + 1, y + 1, 0), P(x + 1, y + 1, h), P(x, y + 1, h)].join(' '), fill: left })
    faces.push({ points: [P(x + 1, y, 0), P(x + 1, y + 1, 0), P(x + 1, y + 1, h), P(x + 1, y, h)].join(' '), fill: right })
    faces.push({ points: [P(x, y, h), P(x + 1, y, h), P(x + 1, y + 1, h), P(x, y + 1, h)].join(' '), fill: top })
  })
  return faces
}

/** Standalone SVG markup (favicons, share cards, the brand page download). */
export function markSvg({ size = 512, background = BRAND.ink, radius = 0.22, inset = 0.16, tones }: {
  size?: number; background?: string | null; radius?: number; inset?: number; tones?: Tone[]
} = {}) {
  const inner = size * (1 - inset * 2)
  const off = size * inset
  const faces = markFaces(inner, tones).map(f => `<polygon points="${f.points}" fill="${f.fill}"/>`).join('')
  const bg = background ? `<rect width="${size}" height="${size}" rx="${size * radius}" fill="${background}"/>` : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">${bg}<g transform="translate(${off} ${off})" stroke-linejoin="round">${faces}</g></svg>`
}
