import { useMemo, useState } from 'react'
import { network } from '../data/network'
import { portfolio } from '../data/portfolio'
import { whoToCall, affiliation, whyMatters, holdingsFor } from '../lib/network'
import Badge from '../components/Badge'
import type { Person } from '../data/types'

type Mode = 'theme' | 'company'
interface Group { key: string; label: string; sub?: string; people: { p: Person; why: string }[] }

function PersonRow({ p, why }: { p: Person; why: string }) {
  return <div className="pn"><div className="top"><b>{p.name}</b><span className="dots" title={`relationship strength ${p.strength}/5`}>{'●'.repeat(p.strength)}{'○'.repeat(5 - p.strength)}</span></div>
    <div className="aff">{affiliation(p)} · <span className={p.lastTalkDays > 90 ? 'neg' : ''}>last spoke {p.lastTalkDays}d ago</span></div>
    <div className="why">{why}</div></div>
}

export default function Network({ openCompany }: { openCompany: (t: string) => void }) {
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<Mode>('theme')
  const ql = q.trim().toLowerCase()

  const matches = (p: Person) => !ql || [p.name, p.role, p.company, p.knows, p.school, ...p.themes, ...p.past.flatMap(h => [h.company, h.role])].some(s => s.toLowerCase().includes(ql))
  const people = useMemo(() => network.filter(matches).sort((a, b) => b.strength - a.strength || a.lastTalkDays - b.lastTalkDays), [ql]) // eslint-disable-line react-hooks/exhaustive-deps

  const groups: Group[] = useMemo(() => {
    if (mode === 'theme') {
      // group by the sector of the holdings a person is linked to; theme tags become the subtitle. One row per person.
      const m = new Map<string, Group>()
      for (const p of people) {
        const t = holdingsFor(p).direct[0]
        const sector = (t && portfolio.find(c => c.t === t)?.sector) || 'Cross-portfolio'
        if (!m.has(sector)) m.set(sector, { key: sector, label: sector, sub: '', people: [] })
        const g = m.get(sector)!; g.people.push({ p, why: whyMatters(p) })
        g.sub = [...new Set([...(g.sub ? g.sub.split(' · ') : []), ...p.themes])].join(' · ')
      }
      return [...m.values()].sort((a, b) => (a.key === 'Cross-portfolio' ? 1 : b.key === 'Cross-portfolio' ? -1 : 0) || b.people.length - a.people.length || a.label.localeCompare(b.label))
    }
    const out: Group[] = []
    const used = new Set<string>()
    for (const c of portfolio) {
      let hits = whoToCall(c.t).filter(h => people.some(p => p.id === h.p.id))
      if (hits.some(h => h.score >= 10)) hits = hits.filter(h => h.score >= 10) // peers only when nobody knows the company itself
      if (!hits.length) continue
      hits.forEach(h => used.add(h.p.id))
      out.push({ key: c.t, label: c.name, sub: c.t, people: hits.map(h => ({ p: h.p, why: h.why + ` — ${h.p.knows}` })) })
    }
    const rest = people.filter(p => !used.has(p.id))
    if (rest.length) out.push({ key: '_other', label: 'No holding link', sub: 'cross-portfolio', people: rest.map(p => ({ p, why: whyMatters(p) })) })
    return out.sort((a, b) => (a.key === '_other' ? 1 : b.key === '_other' ? -1 : 0) || b.people.length - a.people.length)
  }, [mode, people])

  return (<>
    <input className="ask" placeholder="Search people, companies, themes — “Tata Motors”, “chemicals”…" value={q} onChange={e => setQ(e.target.value)} />
    <div className="seg" style={{ marginTop: 10 }}>
      <button className={mode === 'theme' ? 'on' : ''} onClick={() => setMode('theme')}>By theme</button>
      <button className={mode === 'company' ? 'on' : ''} onClick={() => setMode('company')}>By company</button></div>
    <section><h2>Your network <Badge kind="demo" /> <small>{people.length} of {network.length} people · ranked by relationship strength</small></h2>
      {!groups.length && <p className="dim">No one matches “{q}”.</p>}
      {groups.map(g => <div key={g.key}>
        <div className="grp"><span>{g.label}</span><small>{mode === 'company' && g.key !== '_other' ? <button className="lnk" onClick={() => openCompany(g.key)} style={{ fontWeight: 400, color: 'var(--dim)' }}>{g.sub} →</button> : g.sub}</small></div>
        {g.people.map(({ p, why }) => <PersonRow key={p.id} p={p} why={why} />)}</div>)}
    </section>
  </>)
}
