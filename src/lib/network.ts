import { network, filingPeople } from '../data/network'
import { portfolio } from '../data/portfolio'
import { supplies, rivals, sisters } from '../data/graph'
import { priority } from '../data/announcements'
import type { Announcement, Company, Person } from '../data/types'

export type NetView = 'call' | 'reach' | 'experts' | 'warm' | 'edges'
export type ReasonKind = 'employer' | 'overlap' | 'school' | 'name' | 'supplier' | 'customer' | 'competitor'
export interface Reason { kind: ReasonKind; text: string; weight: number }
type Stint = { company: string; role: string; yrs: string }

const NOW = 2026
export const nameOf = (t: string) => portfolio.find(c => c.t === t)?.name ?? t
const coOf = (t: string) => portfolio.find(c => c.t === t)
const sectorOf = (t: string) => coOf(t)?.sector
/** Does an employer string refer to this portfolio company (by name or former name)? */
export const isCo = (c: Company, employer: string) => c.name === employer || !!c.aka?.includes(employer)
export const tickersOfEmployer = (employer: string) => portfolio.filter(c => isCo(c, employer)).map(c => c.t)
const sameEmployer = (a: string, b: string) => a === b || tickersOfEmployer(a).some(t => tickersOfEmployer(b).includes(t))
/** "Tata Motors" is a former name: say so wherever the old name is shown. */
export const employerLabel = (employer: string) => {
  const c = portfolio.find(c => c.aka?.includes(employer))
  return c ? `${employer} (now ${portfolio.filter(x => x.aka?.includes(employer)).map(x => x.t).join('/')})` : employer
}

export function parseYrs(y: string): [number, number] {
  const m = y.match(/(\d{4})\D+(\d{4}|now|present)/i)
  if (!m) return [NOW, NOW]
  return [+m[1], /^\d/.test(m[2]) ? +m[2] : NOW]
}
export const overlapYears = (a: string, b: string) => { const [s1, e1] = parseYrs(a), [s2, e2] = parseYrs(b); return Math.max(0, Math.min(e1, e2) - Math.max(s1, s2)) }
const firstSentence = (s: string) => s.split(/(?<=[.;])\s/)[0].replace(/\.$/, '')
const lc = (s: string) => /^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s

/** All stints at an employer: former jobs plus the current one. */
export const stints = (p: Person): Stint[] => [...p.past, { company: p.company, role: p.role, yrs: 'now' }]

// ------------------------------------------------------------------ Who should I call?
export type Rel = 'worked there' | 'supplier side' | 'customer side' | 'competitor'
export interface CallHit { p: Person; rel: Rel; via: string; yrs: string; why: string; know: string; score: number }
const REL_BASE: Record<Rel, number> = { 'worked there': 10, 'supplier side': 6, 'customer side': 6, competitor: 4 }

/** Companies related to `ticker`: suppliers, customers, competitors (sector peers + rivals). */
export function relatedCompanies(ticker: string) {
  const sec = sectorOf(ticker)
  const sup = supplies.filter(e => e.to === ticker).map(e => ({ t: e.from, rel: 'supplier side' as Rel, note: e.note }))
  const cus = supplies.filter(e => e.from === ticker).map(e => ({ t: e.to, rel: 'customer side' as Rel, note: e.note }))
  const isSister = (t: string) => sisters.some(([a, b]) => (a === ticker && b === t) || (b === ticker && a === t))
  const peers = portfolio.filter(c => c.sector === sec && c.t !== ticker && !isSister(c.t)).map(c => c.t)
  const riv = rivals.flatMap(([a, b]) => a === ticker ? [b] : b === ticker ? [a] : [])
  const comp = [...new Set([...peers, ...riv])].map(t => ({ t, rel: 'competitor' as Rel, note: `${sectorOf(t)} peer` }))
  return [...sup, ...cus, ...comp]
}

export function callList(ticker: string): CallHit[] {
  const co = coOf(ticker); if (!co) return []
  const related = relatedCompanies(ticker)
  const out: CallHit[] = []
  for (const p of network) {
    let best: CallHit | null = null
    const consider = (rel: Rel, st: Stint, note?: string, peerName?: string) => {
      const [, end] = parseYrs(st.yrs)
      const score = REL_BASE[rel] + p.strength + (p.lastTalkDays < 60 ? 1 : 0) + (end >= 2022 ? 1 : 0)
      if (best && best.score >= score) return
      const where = employerLabel(st.company)
      const tenure = st.yrs === 'now' ? 'today' : st.yrs
      const first = firstSentence(p.knows)
      let why: string, know: string
      if (rel === 'worked there') { why = `${st.role} at ${where} (${tenure})`; know = `Knows ${co.name} from inside — ${lc(first)}` }
      else if (rel === 'competitor') { why = `${st.role} at ${where}, a ${note ?? 'peer'} (${tenure})`; know = `Can benchmark ${co.name} against ${peerName} — ${lc(first)}` }
      else if (rel === 'supplier side') { why = `${st.role} at ${where}, which supplies ${co.name} (${note}) (${tenure})`; know = `Sees ${co.name}'s ordering and pricing from the supply side — ${lc(first)}` }
      else { why = `${st.role} at ${where}, a customer of ${co.name} (${note}) (${tenure})`; know = `Sees demand for ${co.name}'s products from the buying side — ${lc(first)}` }
      best = { p, rel, via: where, yrs: tenure, why, know, score }
    }
    for (const st of stints(p)) {
      if (isCo(co, st.company)) consider('worked there', st)
      for (const r of related) { const c = coOf(r.t)!; if (isCo(c, st.company)) consider(r.rel, st, r.note, c.name) }
    }
    if (best) out.push(best)
  }
  return out.sort((a, b) => b.score - a.score)
}
/** Back-compat alias used by cards and the Pull screen. */
export const whoToCall = callList

// ------------------------------------------------------------------ links to a person in a filing (2nd degree)
export interface FilingPerson { name: string; headline: string; past: Stint[]; school: string; note: string }
export function linkReasons(p: Person, fp: FilingPerson): Reason[] {
  const out: Reason[] = []
  for (const mine of stints(p)) for (const theirs of fp.past) {
    if (!sameEmployer(mine.company, theirs.company)) continue
    const yrs = overlapYears(mine.yrs, theirs.yrs)
    const where = employerLabel(mine.company)
    if (yrs > 0) out.push({ kind: 'overlap', weight: 2 + Math.min(yrs, 4) / 2, text: `overlapped with ${fp.name} at ${where} for ~${yrs}y (${mine.role}, ${mine.yrs === 'now' ? 'now' : mine.yrs}; ${fp.name}: ${theirs.yrs})` })
    else out.push({ kind: 'employer', weight: 1, text: `both worked at ${where} (${mine.yrs} vs ${theirs.yrs}) — same firm, different years` })
  }
  if (p.school === fp.school) out.push({ kind: 'school', weight: 1.5, text: `same college as ${fp.name}: ${p.school}` })
  return out
}
export interface Reach { p: Person; reasons: Reason[]; link: 1 | 2 | 3 | 4 | 5 }
/** Contacts one hop from a filing person who is NOT in the network, with the strength of the link. */
export function secondDegree(name: string): { profile: FilingPerson; reach: Reach[]; isContact: boolean } | null {
  const profile = filingPeople[name]; if (!profile) return null
  const reach: Reach[] = []
  for (const p of network) {
    const reasons = linkReasons(p, profile); if (!reasons.length) continue
    const link = Math.max(1, Math.min(5, Math.round(reasons.reduce((s, r) => s + r.weight, 0)))) as Reach['link']
    reach.push({ p, reasons, link })
  }
  reach.sort((a, b) => b.link - a.link || b.p.strength - a.p.strength)
  return { profile, reach, isContact: network.some(p => p.name === name) }
}
export const overlapsFor = (name: string) => { const r = secondDegree(name); return r && { profile: r.profile, links: r.reach.map(x => ({ p: x.p, why: x.reasons.map(y => y.text).join(' · ') })) } }

// ------------------------------------------------------------------ Expertise map
export const allThemes = () => {
  const m = new Map<string, number>()
  for (const p of network) for (const t of p.themes) m.set(t, (m.get(t) ?? 0) + 1)
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}
export interface Expert { p: Person; score: number; angle: string }
export function expertise(theme: string): Expert[] {
  const t = theme.trim().toLowerCase(); if (!t) return []
  const out: Expert[] = []
  for (const p of network) {
    const exact = p.themes.some(x => x.toLowerCase() === t), partial = p.themes.some(x => x.toLowerCase().includes(t) || t.includes(x.toLowerCase()))
    const inKnows = p.knows.toLowerCase().includes(t) || stints(p).some(s => s.role.toLowerCase().includes(t))
    if (!exact && !partial && !inKnows) continue
    const score = (exact ? 6 : partial ? 4 : 2) + p.strength + (p.lastTalkDays < 60 ? 1 : 0) - (p.lastTalkDays > 200 ? 1 : 0)
    out.push({ p, score, angle: firstSentence(p.knows) })
  }
  return out.sort((a, b) => b.score - a.score)
}

// ------------------------------------------------------------------ Keep warm
export interface Warm { p: Person; a: Announcement; via: string; yrs: string; reason: string }
const REASON: Partial<Record<string, string>> = {
  results: 'ask how they read the numbers — they know the unit economics',
  management_change: 'ask what they know about the people involved and the reasons for the change',
  litigation: 'ask whether this is a one-off or a pattern they saw while there',
  capex: 'ask how credible the timeline and funding are, given what they saw of execution',
  'M&A': 'ask how the company has integrated deals before',
  fund_raise: 'ask how the balance sheet looked from the inside',
  credit_rating: 'ask what the agencies were pushing on',
  dividend: 'ask how the board thinks about capital allocation',
}
export function keepWarm(anns: Announcement[], minDays = 60): Warm[] {
  const out: Warm[] = []
  for (const p of network) {
    if (p.lastTalkDays <= minDays) continue
    let best: Warm | null = null
    for (const a of anns) {
      const c = coOf(a.t); if (!c) continue
      const st = stints(p).find(s => isCo(c, s.company)); if (!st) continue
      if (best && priority[best.a.cat].rank <= priority[a.cat].rank) continue
      const tenure = st.yrs === 'now' ? 'works there' : `${st.role}, ${st.yrs}`
      best = { p, a, via: employerLabel(st.company), yrs: tenure,
        reason: `${c.name} just filed “${a.title}”. ${p.name} was ${st.role} there — ${REASON[a.cat] ?? 'a natural, low-pressure reason to check in'}.` }
    }
    if (best) out.push(best)
  }
  return out.sort((x, y) => priority[x.a.cat].rank - priority[y.a.cat].rank || y.p.lastTalkDays * y.p.strength - x.p.lastTalkDays * x.p.strength)
}
export const reconnect = () => (anns: Announcement[]) => keepWarm(anns).map(w => ({ p: w.p, a: w.a }))

// ------------------------------------------------------------------ Quiet advantages
export interface Edge { title: string; body: string; kind: 'worked-with' | 'both-sides'; tickers: string[]; who: string[] }
export function quietAdvantages(): Edge[] {
  const out: Edge[] = []
  for (const name of Object.keys(filingPeople)) {
    const r = secondDegree(name)!
    const worked = r.reach.filter(x => x.reasons.some(y => y.kind === 'overlap'))
    if (worked.length >= 2) {
      const co = [...new Set(r.profile.past.map(s => tickersOfEmployer(s.company)[0]).filter(Boolean))]
      const school = r.reach.filter(x => x.reasons.some(y => y.kind === 'school') && !worked.includes(x))
      out.push({ kind: 'worked-with', tickers: co, who: worked.map(w => w.p.id),
        title: `${worked.length} of your contacts worked alongside ${name}`,
        body: `${worked.map(w => `${w.p.name} (${w.reasons.find(y => y.kind === 'overlap')!.text.replace(`overlapped with ${name} at `, '').split(' (')[0]})`).join('; ')}. ${name} (${r.profile.headline}) is not in your network, so these are your fastest read on how they work.${school.length ? ` ${school.map(s => s.p.name).join(', ')} also share${school.length === 1 ? 's' : ''} ${r.profile.school}.` : ''}` })
    }
  }
  for (const p of network) {            // contacts who sat on both sides of a supply relationship
    const cos = [...new Set(stints(p).flatMap(s => tickersOfEmployer(s.company)))]
    for (const e of supplies) if (cos.includes(e.from) && cos.includes(e.to))
      out.push({ kind: 'both-sides', tickers: [e.from, e.to], who: [p.id], title: `${p.name} has seen both ${nameOf(e.from)} and ${nameOf(e.to)}`,
        body: `Illustrative relationship (synthetic): ${nameOf(e.from)} supplies ${nameOf(e.to)} (${e.note}); ${p.name} worked at both — a rare view of the contract from each side. ${firstSentence(p.knows)}.` })
  }
  return out
}
export { network }
/** One clean "Role · Company" line; avoids repeating the company when the role already names it. */
export function affiliation(p: Person) {
  const co = p.company && p.company !== 'Independent' ? p.company : ''
  return !co || p.role.includes(co) ? p.role : `${p.role} · ${co}`
}
