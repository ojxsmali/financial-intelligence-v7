// Regenerates the brand assets from the one geometry in src/lib/brandMark.ts:
//   public/favicon.svg, icon-192/512, icon-maskable-512, apple-touch-icon, og-image.png
//   ../docs/social-preview.png (GitHub social preview, 1280×640)
// The share cards are screenshotted from the live /brand page, so start `npm run dev` first.
//
// Usage: node scripts/render-brand.mjs [baseUrl]
// Needs puppeteer-core and a Chromium-based browser:
//   PUPPETEER_CORE=<path to puppeteer-core>  BROWSER=<path to chrome/msedge>
import { writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { markSvg } from '../src/lib/brandMark.ts'

const require = createRequire(import.meta.url)
const puppeteer = require(process.env.PUPPETEER_CORE ?? 'puppeteer-core')
const browserPath = process.env.BROWSER ?? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const base = process.argv[2] ?? 'http://localhost:5190'
const pub = p => fileURLToPath(new URL(`../public/${p}`, import.meta.url))

const browser = await puppeteer.launch({ executablePath: browserPath, headless: 'new', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage()

// 1. icons, straight from the SVG
await writeFile(pub('favicon.svg'), markSvg({ size: 64 }))
const icons = [
  ['icon-192.png', 192, markSvg({ size: 192 })],
  ['icon-512.png', 512, markSvg({ size: 512 })],
  ['apple-touch-icon.png', 180, markSvg({ size: 180, radius: 0 })],
  ['icon-maskable-512.png', 512, markSvg({ size: 512, radius: 0, inset: 0.24 })],
]
for (const [name, size, svg] of icons) {
  await page.setViewport({ width: size, height: size, deviceScaleFactor: 1 })
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`)
  await page.screenshot({ path: pub(name), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } })
  console.log('wrote', name)
}

// 2. share cards, from the brand page (same fonts and layout the site uses)
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }])
await page.goto(`${base}/brand`, { waitUntil: 'networkidle0' })
await page.evaluate(() => document.fonts.ready)
for (const [id, file] of [['og-card', pub('og-image.png')], ['social-card', fileURLToPath(new URL('../../docs/social-preview.png', import.meta.url))]]) {
  const handle = await page.evaluateHandle(cardId => {
    const card = document.getElementById(cardId).cloneNode(true)
    card.id = `${cardId}-capture`
    Object.assign(card.style, { position: 'fixed', left: '0', top: '0', transform: 'none', zIndex: '9999' })
    document.body.appendChild(card)
    return card
  }, id)
  await new Promise(r => setTimeout(r, 300))
  await handle.asElement().screenshot({ path: file })
  await page.evaluate(el => el.remove(), handle)
  console.log('wrote', file)
}

await browser.close()
