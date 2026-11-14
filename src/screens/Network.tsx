import { useState } from 'react'
import { network, filingPeople } from '../data/network'
import { portfolio } from '../data/portfolio'
import { announcements } from '../data/announcements'
import { callList, secondDegree, allThemes, expertise, keepWarm, quietAdvantages, affiliation, type NetView, type CallHit } from '../lib/network'
import { LABEL } from '../data/graph'
import Badge from '../components/Badge'

const TABS: { v: NetView; l: string }[] = [{ v: 'call', l: 'Who to call' }, { v: 'reach', l: '2nd degree' }, { v: 'experts', l: 'Experts' }, { v: 'warm', l: 'Keep warm' }, { v: 'edges', l: 'Edges' }]
export const Dots = ({ n }: { n: number }) => <span className="dots" title={`${n}/5`}>{'●'.repeat(n)}{'○'.repeat(5 - n)}</span>
const relClass = (r: string) => r.startsWith('worked') ? 'worked' : r.startsWith('supplier') ? 'supplier' : r.startsWith('customer') ? 'customer' : ''
const spoke = (d: number) => <span className={d > 90 ? 'neg' : ''}>last spoke {d}d ago</span>

export function CallRow({ h }: { h: CallHit }) {
  return <div className="pn"><div className="top"><span><b>{h.p.name}</b><span className={`rel ${relClass(h.rel)}`}>{h.rel}</span></span><Dots n={h.p.strength} /></div>
    <div className="aff">{affiliation(h.p)} · {spoke(h.p.lastTalkDays)}</div>
    <div className="why">{h.why}</div><div className="why dim">{h.know}.</div></div>
}

function CallView({ ticker, setTicker, openCompany }: { ticker: string; setTicker: (t: string) => void; openCompany: (t: string) => void }) {
  const hits = callList(ticker)
  return <section><h2>Who should I call about…</h2>
    <select className="pick" style={{ margin: '0 0 8px' }} value={ticker} onChange={e => setTicker(e.target.value)}>{portfolio.map(c => <option key={c.t} value={c.t}>{c.name} ({c.t})</option>)}</select>
    <p className="dim small">Ranked: worked there, then supplier or customer side, then competitor — weighted by your relationship and how recent their tenure is. Supplier, customer and rival links are {LABEL}.</p>
    {hits.length ? hits.map(h => <CallRow key={h.p.id} h={h} />) : <p className="dim">No direct, supplier, customer or competitor connection. Try a second-degree ask.</p>}
    <button className="more" style={{ marginTop: 10 }} onClick={() => openCompany(ticker)}>Open research →</button></section>
}

function ReachView({ name, setName }: { name: string; setName: (n: string) => void }) {
  const r = secondDegree(name)
  return <section><h2>Second-degree reach</h2>
    <select className="pick" style={{ margin: '0 0 8px' }} value={name} onChange={e => setName(e.target.value)}>{Object.keys(filingPeople).map(n => <option key={n}>{n}</option>)}</select>
    {r && <><div className="net"><b>{r.profile.name}</b> · {r.profile.headline}<br /><span className="dim">{r.profile.past.map(s => `${s.role}, ${s.company} (${s.yrs})`).join(' → ')} · {r.profile.school}</span>
      <p className="note">{r.isContact ? 'In your network.' : 'Not in your network — reach them through someone who is:'} {r.profile.note}</p></div>
      {r.reach.length ? r.reach.map(x => <div key={x.p.id} className="pn"><div className="top"><b>{x.p.name}</b><span className="dim small">link <Dots n={x.link} /></span></div>
        <div className="aff">{affiliation(x.p)} · your tie <Dots n={x.p.strength} /> · {spoke(x.p.lastTalkDays)}</div>
        <ul className="why" style={{ paddingLeft: 16, margin: '4px 0 0' }}>{x.reasons.map((y, i) => <li key={i}>{y.text}</li>)}</ul></div>)
        : <p className="dim">Nobody in your network is one hop away.</p>}</>}</section>
}

function ExpertView({ theme, setTheme }: { theme: string; setTheme: (t: string) => void }) {
  const themes = allThemes(), res = expertise(theme)
  return <section><h2>Expertise map</h2>
    <input className="ask" style={{ margin: 0 }} placeholder="Theme — “specialty chemicals”, “rural lending”…" value={theme} onChange={e => setTheme(e.target.value)} />
    <div className="chips">{themes.slice(0, 18).map(([t, n]) => <button key={t} className={`chip ${theme.toLowerCase() === t.toLowerCase() ? 'on' : ''}`} onClick={() => setTheme(t)}>{t} <small className="dim">{n}</small></button>)}</div>
    {theme && <h2 style={{ marginTop: 16 }}>Go-to people: {theme} <small>{res.length}</small></h2>}
    {res.map((e, i) => <div key={e.p.id} className="pn"><div className="top"><span><b>{e.p.name}</b>{i === 0 && <span className="rel worked">go-to</span>}</span><Dots n={e.p.strength} /></div>
      <div className="aff">{affiliation(e.p)} · {spoke(e.p.lastTalkDays)}</div><div className="why">{e.angle}.</div></div>)}
    {theme && !res.length && <p className="dim">No one tagged for “{theme}”. Try a broader term.</p>}</section>
}

function WarmView({ openCompany, focus }: { openCompany: (t: string) => void; focus?: string }) {
  const list = keepWarm(announcements)
  return <section><h2>Keep warm <small>contacts you haven’t spoken to in 60+ days whose old employer just filed</small></h2>
    {list.length ? list.map(w => <div key={w.p.id} className={`pn ${focus === w.a.t ? 'hl' : ''}`}><div className="top"><b>{w.p.name}</b><Dots n={w.p.strength} /></div>
      <div className="aff">{affiliation(w.p)} · {spoke(w.p.lastTalkDays)}</div>
      <div className="why">{w.reason}</div>
      <button className="lnk dim small" onClick={() => openCompany(w.a.t)}>{w.a.t} · {w.via} →</button></div>) : <p className="dim">Nothing to reconnect on today.</p>}</section>
}

function EdgesView({ openCompany }: { openCompany: (t: string) => void }) {
  const items = quietAdvantages()
  return <section><h2>Quiet advantages <small>patterns hidden in your network</small></h2>
    {items.map((e, i) => <div key={i} className="insight"><b>{e.title}</b>{e.body}
      <div className="chips">{e.tickers.map(t => <button key={t} className="chip" onClick={() => openCompany(t)}>{t}</button>)}</div></div>)}</section>
}

export default function Network({ openCompany, nav, setNav }: { openCompany: (t: string) => void; nav: { view: NetView; arg?: string }; setNav: (n: { view: NetView; arg?: string }) => void }) {
  const [call, setCall] = useState('TMPV'), [who, setWho] = useState('Sameer Kulkarni'), [theme, setTheme] = useState('specialty chemicals')
  // arriving from a card: use its argument once as the selection for that view
  const [seen, setSeen] = useState<typeof nav | null>(null)
  if (nav !== seen) {
    setSeen(nav)
    if (nav.view === 'call' && nav.arg) setCall(nav.arg)
    if (nav.view === 'reach' && nav.arg) setWho(nav.arg)
    if (nav.view === 'experts' && nav.arg) setTheme(nav.arg)
  }
  return (<>
    <div className="synth">Synthetic data — {network.length} invented people and a made-up company graph. Real use needs your consented CRM, email and calendar import.</div>
    <div className="seg wrap small">{TABS.map(t => <button key={t.v} className={nav.view === t.v ? 'on' : ''} onClick={() => setNav({ view: t.v })}>{t.l}</button>)}</div>
    <h2 style={{ margin: '0 0 6px' }}><Badge kind="demo" /> <small>{network.length} people · {portfolio.length} holdings</small></h2>
    {nav.view === 'call' && <CallView ticker={call} setTicker={setCall} openCompany={openCompany} />}
    {nav.view === 'reach' && <ReachView name={who} setName={setWho} />}
    {nav.view === 'experts' && <ExpertView theme={theme} setTheme={setTheme} />}
    {nav.view === 'warm' && <WarmView openCompany={openCompany} focus={nav.arg} />}
    {nav.view === 'edges' && <EdgesView openCompany={openCompany} />}
  </>)
}
