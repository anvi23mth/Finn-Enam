import { network, filingPeople } from '../data/network'
import { portfolio } from '../data/portfolio'
import type { Announcement, Person } from '../data/types'
import { callList, linkReasons, employerLabel, nameOf, type Reason, type FilingPerson } from './network'

export interface Entity { type: 'company' | 'person'; label: string; detail: string }
export interface Match { p: Person; reasons: Reason[]; score: number }
export interface MatchResult { entities: Entity[]; matches: Match[]; companies: string[]; people: string[] }

const has = (text: string, needle: string) => new RegExp(`(^|[^\\w])${needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}($|[^\\w])`, 'i').test(text)

/**
 * The visible matching step: (1) find the companies and people a filing/card mentions,
 * (2) match each to people in the network by employer history, name and college, keeping the reason.
 */
export function matchAnnouncement(a: Announcement): MatchResult {
  const text = `${a.title}. ${a.summary ?? ''}`
  const entities: Entity[] = []
  const companies: string[] = [a.t]
  const primary = portfolio.find(c => c.t === a.t)
  entities.push({ type: 'company', label: nameOf(a.t), detail: `${a.t}${primary?.aka ? ` · formerly ${primary.aka.join(', ')}` : ''}` })
  for (const c of portfolio) {
    if (c.t === a.t) continue
    const hit = [c.name, ...(c.aka ?? [])].find(n => has(text, n))
    if (hit) { companies.push(c.t); entities.push({ type: 'company', label: c.name, detail: `${c.t} · mentioned in text${hit !== c.name ? ` as “${hit}”` : ''}` }) }
  }
  const people: string[] = []
  const profiles: FilingPerson[] = []
  const addPerson = (name: string) => {
    if (people.includes(name)) return
    people.push(name)
    const fp = filingPeople[name]
    const contact = network.find(p => p.name === name)
    if (fp) profiles.push(fp)
    entities.push({ type: 'person', label: name, detail: contact ? 'already in your network' : fp ? `${fp.headline} · not in your network` : 'name only — no profile' })
  }
  if (a.person) addPerson(a.person)
  for (const name of Object.keys(filingPeople)) if (has(text, name)) addPerson(name)
  for (const p of network) if (has(text, p.name)) addPerson(p.name)

  const by = new Map<string, Match>()
  const add = (p: Person, r: Reason) => { const m = by.get(p.id) ?? { p, reasons: [], score: 0 }; if (!m.reasons.some(x => x.text === r.text)) { m.reasons.push(r); m.score += r.weight } by.set(p.id, m) }
  for (const t of companies) for (const h of callList(t)) {
    const kind = h.rel === 'worked there' ? 'employer' : h.rel === 'supplier side' ? 'supplier' : h.rel === 'customer side' ? 'customer' : 'competitor'
    add(h.p, { kind, weight: kind === 'employer' ? 3 : kind === 'competitor' ? 0.75 : 1, text: kind === 'employer' ? `worked at ${employerLabel(h.via)} ${h.yrs === 'today' ? '(works there now)' : h.yrs}` : h.why })
  }
  for (const fp of profiles) for (const p of network) for (const r of linkReasons(p, fp)) add(p, r)
  for (const name of people) { const p = network.find(x => x.name === name); if (p) add(p, { kind: 'name', weight: 4, text: 'named in this filing' }) }
  for (const m of by.values()) { m.score += m.p.strength * 0.3; m.reasons.sort((a, b) => b.weight - a.weight) } // strongest evidence first
  return { entities, companies, people, matches: [...by.values()].sort((x, y) => y.score - x.score) }
}
