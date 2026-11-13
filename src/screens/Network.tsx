import { useState } from 'react'
import { network } from '../data/network'
import { whoToCall, expertise, nameOf } from '../lib/network'
import { portfolio } from '../data/portfolio'
export default function Network({ openCompany }: { openCompany: (t: string) => void }) {
  const [q, setQ] = useState('')
  const ql = q.trim().toLowerCase()
  const co = portfolio.find(c => ql && (c.t.toLowerCase() === ql || c.name.toLowerCase().includes(ql)))
  const byCo = co ? whoToCall(co.t) : []
  const byTheme = !co && ql ? expertise(ql) : []
  return (<>
    <input className="ask" placeholder="Company or theme — “Tata Motors”, “chemicals”…" value={q} onChange={e => setQ(e.target.value)} />
    {co && <section><h2>Who knows {nameOf(co.t)}</h2>{byCo.length ? byCo.map(h => <div key={h.p.id} className="net"><div className="hit">◉ <b>{h.p.name}</b> <small>· {'●'.repeat(h.p.strength)}</small><br/>{h.why}<br/><i>{h.p.knows}</i></div></div>) : <p className="dim">No direct or peer connection. Try a second-degree ask.</p>}
      <button className="more" onClick={() => openCompany(co.t)}>Open research →</button></section>}
    {ql && !co && <section><h2>Go-to people: {q}</h2>{byTheme.length ? byTheme.map(p => <div key={p.id} className="net"><div className="hit">◉ <b>{p.name}</b> — {p.role}<br/><i>{p.knows}</i></div></div>) : <p className="dim">No one tagged for that theme.</p>}</section>}
    {!ql && <section><h2>Your network <small>{network.length} people</small></h2>{[...network].sort((a, b) => b.lastTalkDays - a.lastTalkDays).map(p => <div key={p.id} className="person"><b>{p.name}</b><span>{p.role}</span><small className={p.lastTalkDays > 90 ? 'neg' : 'dim'}>last spoke {p.lastTalkDays}d ago</small></div>)}</section>}
  </>)
}
