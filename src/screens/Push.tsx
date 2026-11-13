import { useMemo, useState } from 'react'
import { announcements, priority } from '../data/announcements'
import { usePrices, evalAlerts } from '../lib/market'
import { overlapsFor, whoToCall, reconnect, nameOf } from '../lib/network'
import type { Announcement } from '../data/types'

const WINDOWS = [{ l: '24h', h: 24 }, { l: '3d', h: 72 }, { l: '7d', h: 168 }]
const pct = (n: number) => <span className={n >= 0 ? 'pos' : 'neg'}>{n >= 0 ? '+' : ''}{n.toFixed(1)}%</span>

function Card({ a, open }: { a: Announcement; open: (t: string) => void }) {
  const link = a.person ? overlapsFor(a.person) : null
  const calls = ['M&A', 'litigation', 'capex', 'fund_raise'].includes(a.cat) ? whoToCall(a.t).slice(0, 1) : []
  return (
    <article className={`card r${priority[a.cat].rank}`}>
      <div className="meta"><span className="tag">{priority[a.cat].label}</span><button className="lnk" onClick={() => open(a.t)}>{a.t}</button><span className="ago">{a.hoursAgo}h</span></div>
      <h3>{a.title}</h3>
      {a.summary && <p>{a.summary}</p>}
      {a.results && <table className="res"><thead><tr><th>₹ cr</th><th></th><th>QoQ</th><th>YoY</th></tr></thead><tbody>
        {a.results.map(r => <tr key={r.k}><td>{r.k}</td><td>{r.cur.toLocaleString('en-IN')}</td><td>{pct(r.qoq)}</td><td>{pct(r.yoy)}</td></tr>)}</tbody></table>}
      {link && <div className="net"><div className="who"><b>{link.profile.name}</b> · {link.profile.headline}<br/>
        {link.profile.past.map(p => `${p.role}, ${p.company}`).join(' → ')} · {link.profile.school}</div>
        <p className="note">{link.profile.note}</p>
        {link.links.length ? link.links.map(l => <div key={l.p.id} className="hit">◉ <b>{l.p.name}</b> — {l.why}</div>) : <div className="hit dim">No overlap in your network</div>}</div>}
      {calls.map(h => <div key={h.p.id} className="net"><div className="hit">◉ Call <b>{h.p.name}</b> — {h.why}. {h.p.knows}</div></div>)}
    </article>
  )
}

export default function Push({ openCompany }: { openCompany: (t: string) => void }) {
  const [win, setWin] = useState(24)
  const [th, setTh] = useState({ movePct: 4, volX: 2 })
  const [showRoutine, setShowRoutine] = useState(false)
  const [cfg, setCfg] = useState(false)
  const px = usePrices()
  const alerts = useMemo(() => px ? evalAlerts(px.prices, th) : [], [px, th])
  const inWin = announcements.filter(a => a.hoursAgo <= win)
  const main = inWin.filter(a => priority[a.cat].rank < 2).sort((a, b) => priority[a.cat].rank - priority[b.cat].rank || a.hoursAgo - b.hoursAgo)
  const routine = inWin.filter(a => priority[a.cat].rank === 2)
  const nudges = reconnect()(main).slice(0, 2)
  return (<>
    <div className="seg">{WINDOWS.map(w => <button key={w.h} className={win === w.h ? 'on' : ''} onClick={() => setWin(w.h)}>{w.l}</button>)}
      <button className="gear" onClick={() => setCfg(!cfg)}>⚙ alerts</button></div>
    {cfg && <div className="cfg">
      <label>Price move ≥ <b>{th.movePct}%</b><input type="range" min={1} max={10} step={0.5} value={th.movePct} onChange={e => setTh({ ...th, movePct: +e.target.value })} /></label>
      <label>Volume ≥ <b>{th.volX}×</b> avg<input type="range" min={1.2} max={5} step={0.1} value={th.volX} onChange={e => setTh({ ...th, volX: +e.target.value })} /></label></div>}
    <section><h2>Unusual moves <small>{px?.source}</small></h2>
      {alerts.length ? alerts.slice(0, 6).map((a, i) => <button key={i} className="alert" onClick={() => openCompany(a.t)}><b>{a.t}</b><span>{a.text}</span></button>) : <p className="dim">Nothing crosses your thresholds.</p>}</section>
    {nudges.length > 0 && <section><h2>Worth a call</h2>{nudges.map(n => <div key={n.p.id} className="net"><div className="hit">◉ <b>{n.p.name}</b> — silent {n.p.lastTalkDays}d. Their old firm {nameOf(n.a.t)} just filed: “{n.a.title}”. A natural reason to reconnect.</div></div>)}</section>}
    <section><h2>What matters <small>{main.length} of {inWin.length} filings</small></h2>
      {main.map(a => <Card key={a.id} a={a} open={openCompany} />)}
      {routine.length > 0 && <button className="more" onClick={() => setShowRoutine(!showRoutine)}>{showRoutine ? 'Hide' : 'Show'} {routine.length} routine filings</button>}
      {showRoutine && routine.map(a => <div key={a.id} className="routine"><b>{a.t}</b> {a.title}</div>)}</section>
  </>)
}
