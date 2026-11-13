import { network, filingPeople } from '../data/network'
import { portfolio } from '../data/portfolio'
import type { Announcement, Person } from '../data/types'
const nameOf = (t: string) => portfolio.find(c => c.t === t)?.name ?? t
const sectorOf = (t: string) => portfolio.find(c => c.t === t)?.sector
export interface Hit { p: Person; why: string; score: number }
/** People in the network who touched this company (or its sector peers), ranked by relevance × relationship strength. */
export function whoToCall(ticker: string): Hit[] {
  const nm = nameOf(ticker), sec = sectorOf(ticker)
  const peers = portfolio.filter(c => c.sector === sec && c.t !== ticker).map(c => c.name)
  const hits: Hit[] = []
  for (const p of network) {
    const direct = p.past.find(x => x.company === nm) || (p.company === nm ? { company: nm, role: p.role, yrs: 'now' } : undefined)
    const peer = p.past.find(x => peers.includes(x.company))
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
    const a = anns.find(x => p.past.some(h => h.company === nameOf(x.t)))
    return a ? [{ p, a }] : []
  })
}
export const expertise = (theme: string) => network.filter(p => p.themes.some(t => t.toLowerCase().includes(theme.toLowerCase()))).sort((a, b) => b.strength - a.strength)
export { nameOf }
