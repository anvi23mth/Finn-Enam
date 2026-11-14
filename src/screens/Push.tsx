import { useMemo, useState } from 'react'
import { announcements, priority } from '../data/announcements'
import { usePrices, evalAlerts, latestDate, fmtDate } from '../lib/market'
import { keepWarm, type NetView } from '../lib/network'
import { toAnnouncement, ago, useResults, type Feed, type RealAnn } from '../lib/feed'
import MatchPanel from '../components/MatchPanel'
import Badge from '../components/Badge'
import type { Announcement } from '../data/types'

const WINDOWS = [{ l: '24h', h: 24 }, { l: '3d', h: 72 }, { l: '7d', h: 168 }, { l: '30d', h: 720 }]
const pct = (n: number | null) => n == null ? <span className="dim">—</span> : <span className={n >= 0 ? 'pos' : 'neg'}>{n >= 0 ? '+' : ''}{n.toFixed(1)}%</span>
type OpenNet = (v: NetView, arg?: string) => void
const cr = (n: number | null) => n == null ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: 1 })

/* ------------------------------------------------------------------ real results table (extracted + verified from the filing PDF) */
function RealResults({ id, ticker }: { id: string; ticker: string }) {
  const r = useResults(ticker, true)
  if (!r || r.filing.id !== id) return null
  if (r.status === 'not_found' || r.status === 'failed' || !r.table_crore) return <p className="dim small">Results numbers not extracted: {r.error ?? 'not found in the filing'}.</p>
  const rows: [string, keyof NonNullable<typeof r.table_crore>][] = [['Revenue', 'revenue'], ['EBITDA', 'ebitda'], ['PBT', 'pbt'], ['PAT', 'pat']]
  return <div>
    <table className="res"><thead><tr><th>₹ cr · {r.basis}</th><th>Qtr</th><th>Prev</th><th>QoQ</th><th>YoY</th></tr></thead><tbody>
      {rows.map(([lab, k]) => { const m = r.table_crore![k]; return <tr key={k}><td>{lab}{m.derived ? '*' : ''}</td><td>{cr(m.current)}</td><td>{cr(m.previous)}</td><td>{pct(m.qoq_pct)}</td><td>{m.yoy_pct == null && m.year_ago != null ? <span className="dim" title={m.verified ? 'base is zero or negative' : 'year-ago figure not verified'}>n/a</span> : pct(m.yoy_pct)}</td></tr> })}</tbody></table>
    <p className="dim small">Extracted from the filing PDF; each figure's page and quote checked against the page text. * EBITDA derived, not stated.{r.not_found_or_unverified?.length ? ` Unverified: ${r.not_found_or_unverified.join(', ')}.` : ''}</p>
    {r.flags?.map((f, i) => <p key={i} className="warnbox" style={{ marginTop: 4 }}>⚠ {f}</p>)}</div>
}

function RealCard({ a, asOf, open, openNet, expanded }: { a: RealAnn; asOf: Date; open: (t: string) => void; openNet: OpenNet; expanded: boolean }) {
  const ann = toAnnouncement(a, asOf)
  const p = priority[a.category]
  return (
    <article className={`card r${a.priority === 'high' ? 0 : 1}`}>
      <div className="meta"><span className="tag">{p?.label ?? a.category}</span><Badge kind="real" /><button className="lnk" onClick={() => open(a.ticker)}>{a.ticker}</button>
        <span className="ago" title={new Date(a.datetime).toLocaleString()}>{ago(ann.hoursAgo)}</span></div>
      <h3>{a.subject}</h3>
      {a.summary && <p>{a.summary}</p>}
      {a.category === 'results' && a.priority === 'high' && <RealResults id={a.id} ticker={a.ticker} />}
      {a.attachment && <a className="pdf" href={a.attachment} target="_blank" rel="noopener noreferrer">PDF ↗</a>}
      {expanded && <MatchPanel a={ann} openNet={openNet} />}
    </article>
  )
}

function Card({ a, open, openNet }: { a: Announcement; open: (t: string) => void; openNet: OpenNet }) {
  return (
    <article className={`card r${priority[a.cat].rank}`}>
      <div className="meta"><span className="tag">{priority[a.cat].label}</span><Badge kind="demo" /><button className="lnk" onClick={() => open(a.t)}>{a.t}</button><span className="ago">{a.hoursAgo}h</span></div>
      <h3>{a.title}</h3>
      {a.summary && <p>{a.summary}</p>}
      {a.results && <table className="res"><thead><tr><th>₹ cr</th><th></th><th>QoQ</th><th>YoY</th></tr></thead><tbody>
        {a.results.map(r => <tr key={r.k}><td>{r.k}</td><td>{r.cur.toLocaleString('en-IN')}</td><td>{pct(r.qoq)}</td><td>{pct(r.yoy)}</td></tr>)}</tbody></table>}
      <MatchPanel a={a} openNet={openNet} />
    </article>
  )
}

function Unusual({ openCompany, th }: { openCompany: (t: string) => void; th: { movePct: number; volX: number } }) {
  const px = usePrices()
  const alerts = useMemo(() => px ? evalAlerts(px.prices, th, px.meta) : [], [px, th])
  const newest = px ? latestDate(px.meta) : null
  const noData = px ? Object.entries(px.meta).filter(([, m]) => m.status === 'no_data').map(([t]) => t) : []
  const stale = px && newest ? Object.entries(px.meta).filter(([, m]) => m.lastDate && m.lastDate < newest).map(([t, m]) => [t, m.lastDate!] as [string, string]) : []
  return <section><h2>Unusual moves <Badge kind={px && !px.demo ? 'real' : 'demo'} /> <small>{px?.source}</small></h2>
    {px?.demo && <p className="warnbox">⚠ DEMO DATA — synthetic prices for demonstrating alerts. Not real market data.</p>}
    {px && !px.demo && noData.length > 0 && <p className="warnbox">No price data: {noData.join(', ')}</p>}
    {px && !px.demo && stale.length > 0 && <p className="dim small">Behind the latest session: {stale.map(([t, d]) => `${t} (as of ${fmtDate(d)})`).join(', ')}</p>}
    {alerts.length ? alerts.slice(0, 6).map((a, i) => <button key={i} className="alert" onClick={() => openCompany(a.t)}><b>{a.t}</b><span>{a.text}</span></button>) : <p className="dim">Nothing crosses your thresholds.</p>}</section>
}

function LiveFeed({ feed, error, win, openCompany, openNet }: { feed: Feed | null; error: string | null; win: number; openCompany: (t: string) => void; openNet: OpenNet }) {
  const [showRoutine, setShowRoutine] = useState(false)
  const [showMed, setShowMed] = useState(true)
  const items = useMemo(() => feed ? feed.items.filter(a => (feed.asOf.getTime() - new Date(a.datetime).getTime()) / 36e5 <= win) : [], [feed, win])
  const high = items.filter(a => a.priority === 'high'), med = items.filter(a => a.priority === 'medium'), low = items.filter(a => a.priority === 'low')
  const warm = useMemo(() => feed ? keepWarm([...high, ...med].map(a => toAnnouncement(a, feed.asOf))).slice(0, 2) : [], [feed, high, med])
  if (error) return <p className="warnbox">Could not load the classified announcements ({error}). Run backend/scripts/classify_announcements.py.</p>
  if (!feed) return <p className="dim">Loading announcements…</p>
  return <>
    <p className="dim small">{feed.items.length} real filings from screener.in, classified by {Object.keys(feed.models).join(', ')} · as of {feed.asOf.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}. Screener exposes only the latest 5 per company, so older windows are incomplete.</p>
    {warm.length > 0 && <section><h2>Worth a call <Badge kind="demo" /> <small>real filings · synthetic contacts</small></h2>{warm.map(n => <div key={n.p.id} className="net"><div className="hit">◉ <b>{n.p.name}</b> — silent {n.p.lastTalkDays}d. {n.reason}</div></div>)}<button className="more" onClick={() => openNet('warm')}>All keep-warm contacts →</button></section>}
    <section><h2>High priority <Badge kind="real" /> <small>{high.length}</small></h2>
      {high.length ? high.map(a => <RealCard key={a.id} a={a} asOf={feed.asOf} open={openCompany} openNet={openNet} expanded />) : <p className="dim">Nothing high-priority in this window.</p>}</section>
    <section><h2>Medium <Badge kind="real" /> <small>{med.length}</small></h2>
      {med.length > 0 && <button className="more" onClick={() => setShowMed(!showMed)}>{showMed ? 'Hide' : 'Show'} {med.length} medium-priority filings</button>}
      {showMed && med.map(a => <RealCard key={a.id} a={a} asOf={feed.asOf} open={openCompany} openNet={openNet} expanded />)}</section>
    {low.length > 0 && <section><h2>Routine <Badge kind="real" /> <small>{low.length}</small></h2>
      <button className="more" onClick={() => setShowRoutine(!showRoutine)}>{showRoutine ? 'Hide' : 'Show'} {low.length} routine filings</button>
      {showRoutine && low.map(a => <div key={a.id} className="routine"><b>{a.ticker}</b> {a.subject} <span className="dim">· {ago((feed.asOf.getTime() - new Date(a.datetime).getTime()) / 36e5)}</span>{a.attachment && <> <a className="pdf" href={a.attachment} target="_blank" rel="noopener noreferrer">PDF ↗</a></>}</div>)}</section>}
  </>
}

function DemoScenarios({ win, openCompany, openNet }: { win: number; openCompany: (t: string) => void; openNet: OpenNet }) {
  const [showRoutine, setShowRoutine] = useState(false)
  const inWin = announcements.filter(a => a.hoursAgo <= win)
  const main = inWin.filter(a => priority[a.cat].rank < 2).sort((a, b) => priority[a.cat].rank - priority[b.cat].rank || a.hoursAgo - b.hoursAgo)
  const routine = inWin.filter(a => priority[a.cat].rank === 2)
  const nudges = keepWarm(main).slice(0, 2)
  return <>
    <p className="warnbox">Demo scenarios — invented filings, built to showcase the network matching (e.g. a CFO moving between two holdings). Not real announcements.</p>
    {nudges.length > 0 && <section><h2>Worth a call <Badge kind="demo" /></h2>{nudges.map(n => <div key={n.p.id} className="net"><div className="hit">◉ <b>{n.p.name}</b> — silent {n.p.lastTalkDays}d. {n.reason}</div></div>)}<button className="more" onClick={() => openNet('warm')}>All keep-warm contacts →</button></section>}
    <section><h2>What matters <Badge kind="demo" /> <small>{main.length} of {inWin.length} scenario filings</small></h2>
      {main.map(a => <Card key={a.id} a={a} open={openCompany} openNet={openNet} />)}
      {routine.length > 0 && <button className="more" onClick={() => setShowRoutine(!showRoutine)}>{showRoutine ? 'Hide' : 'Show'} {routine.length} routine filings</button>}
      {showRoutine && routine.map(a => <div key={a.id} className="routine"><b>{a.t}</b> {a.title}</div>)}</section>
  </>
}

export default function Push({ openCompany, openNet, feed, feedError }: { openCompany: (t: string) => void; openNet: OpenNet; feed: Feed | null; feedError: string | null }) {
  const [mode, setMode] = useState<'live' | 'demo'>('live')
  const [win, setWin] = useState(168)
  const [th, setTh] = useState({ movePct: 4, volX: 2 })
  const [cfg, setCfg] = useState(false)
  return (<>
    <div className="seg"><button className={mode === 'live' ? 'on' : ''} onClick={() => setMode('live')}>Live feed</button><button className={mode === 'demo' ? 'on' : ''} onClick={() => setMode('demo')}>Demo scenarios</button></div>
    <div className="seg" style={{ marginTop: 0 }}>{WINDOWS.map(w => <button key={w.h} className={win === w.h ? 'on' : ''} onClick={() => setWin(w.h)}>{w.l}</button>)}
      <button className="gear" onClick={() => setCfg(!cfg)}>⚙ alerts</button></div>
    {cfg && <div className="cfg">
      <label>Price move ≥ <b>{th.movePct}%</b><input type="range" min={1} max={10} step={0.5} value={th.movePct} onChange={e => setTh({ ...th, movePct: +e.target.value })} /></label>
      <label>Volume ≥ <b>{th.volX}×</b> avg<input type="range" min={1.2} max={5} step={0.1} value={th.volX} onChange={e => setTh({ ...th, volX: +e.target.value })} /></label></div>}
    {mode === 'live' && <Unusual openCompany={openCompany} th={th} />}
    {mode === 'live' ? <LiveFeed feed={feed} error={feedError} win={win} openCompany={openCompany} openNet={openNet} /> : <DemoScenarios win={win} openCompany={openCompany} openNet={openNet} />}
  </>)
}
