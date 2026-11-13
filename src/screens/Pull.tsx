import { research } from '../data/research'
import { portfolio } from '../data/portfolio'
import { whoToCall } from '../lib/network'
const sym = { up: '▲', down: '▼', flat: '▬' }
export default function Pull({ ticker, setTicker }: { ticker: string; setTicker: (t: string) => void }) {
  const r = research[ticker], co = portfolio.find(c => c.t === ticker), calls = whoToCall(ticker).slice(0, 2)
  return (<>
    <select className="pick" value={ticker} onChange={e => setTicker(e.target.value)}>
      {portfolio.map(c => <option key={c.t} value={c.t}>{c.name}{research[c.t] ? '' : ' — not ingested'}</option>)}</select>
    {!r ? <section><p className="dim">{co?.name ?? ticker} hasn't been ingested yet. The pipeline fetches the latest annual report and four concall transcripts from screener.in, extracts structured facts with a small model, and fills this view — primary sources only.</p></section> : <>
      <section><h2>Business</h2><p>{r.snapshot}</p>
        <div className="bar">{r.segments.map(s => <i key={s.n} style={{ flex: s.pct }} title={s.n} />)}</div>
        <p className="dim small">{r.segments.map(s => `${s.n} ${s.pct}%`).join(' · ')}</p></section>
      <section className="grid">{r.fin.map(f => <div key={f.k} className="kpi"><small>{f.k}</small><b>{f.v}</b></div>)}</section>
      <section><h2>Promised vs delivered</h2>{r.promises.map((p, i) => <div key={i} className={`prom ${p.verdict}`}><small>{p.q}</small><div>“{p.said}”</div><div>→ {p.got}</div><span>{p.verdict}</span></div>)}</section>
      <section><h2>Trajectory</h2>{r.trajectory.map(t => <p key={t.k}><span className={`dir ${t.dir}`}>{sym[t.dir]}</span> <b>{t.k}</b> — {t.note}</p>)}</section>
      <section><h2>Cash quality</h2>{r.quality.map(q => <p key={q.k} className={q.flag ? 'neg' : ''}><b>{q.k}</b> {q.v}</p>)}</section>
      <section className="cols"><div><h2>Bull</h2>{r.bull.map(b => <p key={b}>+ {b}</p>)}</div><div><h2>Bear</h2>{r.bear.map(b => <p key={b}>− {b}</p>)}</div></section></>}
    {calls.length > 0 && <section><h2>Who to call</h2>{calls.map(h => <div key={h.p.id} className="net"><div className="hit">◉ <b>{h.p.name}</b> — {h.why}. {h.p.knows}</div></div>)}</section>}
    <p className="dim small">Sample extraction shown for illustration; figures are placeholders.</p>
  </>)
}
