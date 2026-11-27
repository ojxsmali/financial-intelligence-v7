/** Site map: the masthead, the mobile menu, the ⌘K palette and the page headers' "03 / 10" index all read this. */
export const NAV = [
  { to: '/overview', label: 'Overview' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/screener', label: 'Screener' },
  { to: '/explorer', label: 'Explorer' },
  { to: '/compare', label: 'Compare' },
  { to: '/statements', label: 'Statements' },
  { to: '/insights', label: 'Insights' },
  { to: '/assistant', label: 'Assistant' },
  { to: '/sources', label: 'Sources' },
  { to: '/brand', label: 'Brand' },
] as const

export const pageIndex = (pathname: string) => {
  const i = NAV.findIndex(n => n.to === pathname)
  return i < 0 ? null : { n: String(i + 1).padStart(2, '0'), of: String(NAV.length).padStart(2, '0') }
}
