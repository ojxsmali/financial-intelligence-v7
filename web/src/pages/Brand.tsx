import { motion } from 'motion/react'
import { useState, type CSSProperties } from 'react'
import { LogoMark, Wordmark } from '../components/Logo'
import { Mark3D } from '../components/three/Scene3D'
import { PageHeader, Section } from '../components/ui'
import { BRAND, markSvg } from '../lib/brandMark'
import { useSettings } from '../lib/settings'

const SWATCHES = [
  { name: 'Ink', hex: BRAND.ink, use: 'Page, type, column bodies', fg: BRAND.bone },
  { name: 'Bone', hex: BRAND.bone, use: 'Text on ink, the selected year', fg: BRAND.ink },
  { name: 'Cobalt', hex: BRAND.cobalt, use: 'Poster slabs, the newest column', fg: BRAND.bone },
  { name: 'Cobalt (text)', hex: BRAND.cobaltText, use: 'Links and accents on ink', fg: BRAND.ink },
  { name: 'Deep cobalt', hex: BRAND.cobaltDeep, use: 'Shaded faces, pressed states', fg: BRAND.bone },
  { name: 'Up', hex: BRAND.up, use: 'Increases only — always with ▲ and a sign', fg: BRAND.ink },
  { name: 'Down', hex: BRAND.down, use: 'Decreases only — always with ▼ and a sign', fg: BRAND.ink },
]

const TYPE = [
  { family: 'Geist', role: 'Display and text', sample: 'Apple Inc. $478.83B', style: { fontFamily: 'var(--sans)', fontWeight: 800, letterSpacing: '-0.06em' } },
  { family: 'Libre Caslon Condensed Italic', role: 'One editorial phrase per headline', sample: 'plainly told.', style: { fontFamily: 'var(--serif)', fontStyle: 'italic' } },
  { family: 'Geist Mono', role: 'Labels, tickers, dates, indices', sample: '10-K · FILED 2026-11-03', style: { fontFamily: 'var(--mono)', letterSpacing: '0.06em' } },
  { family: 'Doto', role: 'The fiscal-year readout', sample: 'FY2026', style: { fontFamily: 'var(--dots)', fontWeight: 700 } },
]

const RULES = [
  ['One scale per chart', 'Zero sits on the floor; losses hang below it. No truncated axes, ever.'],
  ['Direction is never colour alone', 'Every change carries ▲ or ▼ and a sign, so it reads in greyscale.'],
  ['Cobalt is the brand, not a result', 'Red and green are reserved for direction, so the brand colour never reads as a loss.'],
  ['Motion is physical', 'Springs, not fades: things are thrown, caught and settle. Reduced motion switches it all off.'],
  ['Drag is a mouse toy', 'On touch screens a drag always scrolls the page; tapping still selects.'],
]

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'image/svg+xml' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Share card artwork. Rendered at native pixel size (scripts/render-brand.mjs screenshots it for og-image.png and the GitHub preview). */
export function ShareCard({ w, h, id }: { w: number; h: number; id: string }) {
  return (
    <div id={id} className="share-card" style={{ width: w, height: h } as CSSProperties}>
      <div className="share-grid" aria-hidden="true" />
      <div className="share-top">
        <LogoMark size={64} />
        <Wordmark className="share-word" />
      </div>
      <p className="share-title">Audited fundamentals for every US-listed company<em>, plainly told.</em></p>
      <div className="share-foot">
        <span>SEC EDGAR · 13,000+ US-listed securities</span>
        <span>Designed &amp; built by Ojas Mali</span>
      </div>
      <svg className="share-mark" viewBox="0 0 512 512" aria-hidden="true" dangerouslySetInnerHTML={{ __html: markSvg({ size: 512, background: null, inset: 0, tones: ['ink', 'ink', 'bone'] }).replace(/^<svg[^>]*>|<\/svg>$/g, '') }} />
    </div>
  )
}

export function Brand() {
  const { notify } = useSettings()
  const [copied, setCopied] = useState('')
  const copy = async (hex: string) => {
    try { await navigator.clipboard.writeText(hex) } catch { /* clipboard blocked: the hex is on screen */ }
    setCopied(hex)
    notify(`Copied ${hex}`)
    setTimeout(() => setCopied(c => (c === hex ? '' : c)), 1400)
  }
  return (
    <>
      <PageHeader eyebrow="Brand kit" title="Three audited years," accent="one mark."
        sub="The logo is the product in miniature: annual figures as columns, rising, the newest in cobalt. Everything on this page is built from the same geometry as the favicon, the share cards and the 3D hero." />

      <section className="brand-hero" aria-label="The mark in 3D">
        <Mark3D className="brand-3d" fallback={<div className="brand-3d flat"><LogoMark size={220} plain /></div>} />
        <div className="brand-hero-copy">
          <Wordmark className="brand-hero-word" />
          <p>Flick it to spin. Tap it and the columns jump.</p>
        </div>
      </section>

      <Section title="Logo" sub="Isometric columns on an ink tile; keep clear space of one column width all round">
        <div className="logo-grid">
          {[
            { bg: 'ink', label: 'On ink', node: <LogoMark size={120} /> },
            { bg: 'bone', label: 'On bone', node: <LogoMark size={120} /> },
            { bg: 'cobalt', label: 'On cobalt (no tile)', node: <LogoMark size={120} plain tones={['ink', 'ink', 'bone']} /> },
            { bg: 'ink', label: 'Lockup', node: <span className="lockup"><LogoMark size={56} /><Wordmark /></span> },
          ].map((v, i) => (
            <motion.figure key={i} className={`logo-tile ${v.bg}`} whileHover={{ y: -6, rotate: i % 2 ? 1.2 : -1.2 }} whileTap={{ scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 380, damping: 18 }}>
              {v.node}
              <figcaption>{v.label}</figcaption>
            </motion.figure>
          ))}
        </div>
        <div className="sizes" aria-label="Favicon sizes">
          {[16, 24, 32, 48, 64].map(s => <span key={s}><LogoMark size={s} /><small>{s}px</small></span>)}
        </div>
        <div className="brand-actions">
          <button className="btn primary" type="button" onClick={() => download('financial-intelligence-mark.svg', markSvg())}>Download mark (SVG)</button>
          <button className="btn" type="button" onClick={() => download('financial-intelligence-mark-cobalt.svg', markSvg({ background: BRAND.cobalt, tones: ['ink', 'ink', 'bone'] }))}>Cobalt version (SVG)</button>
        </div>
      </Section>

      <Section title="Colour" sub="Click a swatch to copy its hex">
        <ul className="swatches">
          {SWATCHES.map((s, i) => (
            <motion.li key={s.hex} initial={{ y: 30, rotate: -2 }} whileInView={{ y: 0, rotate: 0 }} viewport={{ once: true }}
              transition={{ type: 'spring', stiffness: 260, damping: 18, delay: i * 0.04 }}>
              <motion.button type="button" className="swatch" style={{ background: s.hex, color: s.fg }} onClick={() => copy(s.hex)}
                whileHover={{ y: -8 }} whileTap={{ scale: 0.92, rotate: -3 }} transition={{ type: 'spring', stiffness: 500, damping: 16 }}
                aria-label={`Copy ${s.name} ${s.hex}`}>
                <b>{s.name}</b>
                <span className="mono">{copied === s.hex ? 'Copied ✓' : s.hex}</span>
              </motion.button>
              <p>{s.use}</p>
            </motion.li>
          ))}
        </ul>
      </Section>

      <Section title="Type" sub="Four faces, each with one job">
        <ul className="type-specimens">
          {TYPE.map(t => (
            <li key={t.family}>
              <span className="type-sample" style={t.style as CSSProperties}>{t.sample}</span>
              <span className="type-meta"><b>{t.family}</b>{t.role}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Rules" sub="What the design will not do">
        <ol className="rules-list">
          {RULES.map(([h, d]) => <li key={h}><b>{h}</b><span>{d}</span></li>)}
        </ol>
      </Section>

      <Section title="Share cards" sub="Open Graph (1200 × 630) and GitHub social preview (1280 × 640), generated from this page">
        <div className="share-previews">
          <div className="share-frame" style={{ '--w': 1200, '--h': 630 } as CSSProperties}><ShareCard w={1200} h={630} id="og-card" /></div>
          <div className="share-frame" style={{ '--w': 1280, '--h': 640 } as CSSProperties}><ShareCard w={1280} h={640} id="social-card" /></div>
        </div>
      </Section>
    </>
  )
}
