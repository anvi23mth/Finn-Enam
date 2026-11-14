import { network, filingPeople } from '../data/network'
import { portfolio } from '../data/portfolio'
import type { Announcement, Company, Person } from '../data/types'
const nameOf = (t: string) => portfolio.find(c => c.t === t)?.name ?? t
const sectorOf = (t: string) => portfolio.find(c => c.t === t)?.sector
/** Does an employer string refer to this portfolio company (by name or former name)? */
const isCo = (c: Company, employer: string) => c.name === employer || !!c.aka?.includes(employer)
const tickerOfEmployer = (employer: string) => portfolio.find(c => isCo(c, employer))?.t
export interface Hit { p: Person; why: string; score: number }
/** People in the network who touched this company (or its sector peers), ranked by relevance × relationship strength. */
export function whoToCall(ticker: string): Hit[] {
  const co = portfolio.find(c => c.t === ticker), nm = nameOf(ticker), sec = sectorOf(ticker)
  const peers = portfolio.filter(c => c.sector === sec && c.t !== ticker)
  const hits: Hit[] = []
  for (const p of network) {
    const direct = p.past.find(x => co && isCo(co, x.company)) || (co && isCo(co, p.company) ? { company: nm, role: p.role, yrs: 'now' } : undefined)
    const peer = p.past.find(x => peers.some(c => isCo(c, x.company)))
    if (direct) hits.push({ p, why: `${direct.role} at ${nm} (${direct.yrs})`, score: 10 + p.strength })
    else if (peer) hits.push({ p, why: `${peer.role} at ${peer.company}, a ${sec} peer`, score: 4 + p.strength })
  }
  return hits.sort((a, b) => b.score - a.score)
}
/** Link a person named in a filing to the network: shared employers & school. */
export function overlapsFor(name: string) {
  const fp = filingPeople[name]; if (!fp) return null
  const out: { p: Person; why: string }[] = []
  for (const p of network) {
    const shared = p.past.filter(a => fp.past.some(b => b.company === a.company)).map(a => a.company)
    const reasons = [...(shared.length ? [`both worked at ${shared.join(', ')}`] : []), ...(p.school === fp.school ? [`both ${fp.school}`] : [])]
    if (reasons.length) out.push({ p, why: reasons.join(' · ') })
  }
  return { profile: fp, links: out }
}
export const reconnect = () => {
  // warm-up nudges: stale contact (>60d) whose former employer is in today's feed
  return (anns: Announcement[]) => network.filter(p => p.lastTalkDays > 60).flatMap(p => {
    const a = anns.find(x => { const c = portfolio.find(c => c.t === x.t); return c && p.past.some(h => isCo(c, h.company)) })
    return a ? [{ p, a }] : []
  })
}
export const expertise = (theme: string) => network.filter(p => p.themes.some(t => t.toLowerCase().includes(theme.toLowerCase()))).sort((a, b) => b.strength - a.strength)

/** One clean "Role · Company" line; avoids repeating the company when the role already names it. */
export function affiliation(p: Person) {
  const co = p.company && !['Various', 'Retired', ''].includes(p.company) ? p.company : ''
  return !co || p.role.includes(co) ? p.role : `${p.role} · ${co}`
}
/** Holdings this person has a direct employer link to, plus sector-peer holdings. */
export function holdingsFor(p: Person) {
  const direct = [...portfolio.filter(c => isCo(c, p.company)), ...portfolio.filter(c => !isCo(c, p.company) && p.past.some(h => isCo(c, h.company)))].map(c => c.t) // current employer first
  const sectors = new Set(direct.map(t => sectorOf(t)))
  const peer = portfolio.filter(c => !direct.includes(c.t) && sectors.has(c.sector)).map(c => c.t)
  return { direct, peer }
}
/** One-line "why they matter", built from the person's employers (company data) and tagged themes. */
export function whyMatters(p: Person): string {
  const { direct, peer } = holdingsFor(p)
  const themes = p.themes.join(', ')
  const link = p.past.find(h => tickerOfEmployer(h.company))
  if (link) {
    const t = tickerOfEmployer(link.company)!
    const more = direct.filter(x => x !== t)
    return `Ex-${link.role}, ${link.company} (${link.yrs}) — covers ${themes}; use for ${[t, ...more].join(', ')}${peer.length ? ` and peers ${peer.slice(0, 3).join(', ')}` : ''}.`
  }
  if (isCo(portfolio.find(c => c.name === p.company) ?? { t: '', name: '', sector: '' }, p.company) && direct.length)
    return `Works at ${p.company} today — covers ${themes}; first call on ${direct.join(', ')}.`
  return `Covers ${themes}; no direct holding link — an outside view across the book.`
}
export { nameOf }
