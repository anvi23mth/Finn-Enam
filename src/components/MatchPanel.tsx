import { useState } from 'react'
import { matchAnnouncement } from '../lib/match'
import { keepWarm, type NetView } from '../lib/network'
import type { Announcement } from '../data/types'
const ICON: Record<string, string> = { employer: '💼', overlap: '🤝', school: '🎓', name: '🔎', supplier: '⛓', customer: '🛒', competitor: '⚔' }
const Dots = ({ n }: { n: number }) => <span className="dots" title={`your relationship ${n}/5`}>{'●'.repeat(n)}{'○'.repeat(5 - n)}</span>

/** Visible entity-matching step for a filing card: what was recognised, who it matched, and why. */
export default function MatchPanel({ a, openNet }: { a: Announcement; openNet: (v: NetView, arg?: string) => void }) {
  const [open, setOpen] = useState(false), [all, setAll] = useState(false)
  const r = matchAnnouncement(a)
  const warm = keepWarm([a]).length > 0
  if (!r.matches.length && r.people.length === 0) return null
  const shown = all ? r.matches : r.matches.slice(0, 3)
  return <div className="match">
    <button className="mhead" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span>Network match <small>{r.entities.length} entities → {r.matches.length} contacts</small></span><span>{open ? '▾' : '▸'}</span></button>
    {open && <>
      <div className="step"><b>1 · Recognised</b><div className="chips">{r.entities.map(e => <span key={e.label} className={`ent ${e.type}`} title={e.detail}>{e.type === 'company' ? '🏢' : '👤'} {e.label}<small>{e.detail}</small></span>)}</div></div>
      <div className="step"><b>2 · Matched to your network</b>
        {shown.map(m => <div key={m.p.id} className="mrow"><div className="top"><b>{m.p.name}</b><Dots n={m.p.strength} /></div>
          <div className="aff">{m.p.role} · {m.p.company}</div>
          <ul>{m.reasons.slice(0, 4).map((x, i) => <li key={i}><span>{ICON[x.kind]}</span> {x.text}</li>)}</ul></div>)}
        {r.matches.length > 3 && <button className="ghost" onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${r.matches.length}`}</button>}
        {!r.matches.length && <p className="dim small">No contact links found.</p>}</div>
      <div className="acts">
        <button className="ghost" onClick={() => openNet('call', a.t)}>Who to call</button>
        {a.person && <button className="ghost" onClick={() => openNet('reach', a.person)}>2nd-degree</button>}
        {warm && <button className="ghost" onClick={() => openNet('warm', a.t)}>Keep warm</button>}</div></>}
  </div>
}
