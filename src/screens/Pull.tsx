import { useState } from 'react'
import { research } from '../data/research'
import { portfolio } from '../data/portfolio'
import { callList, affiliation, type NetView } from '../lib/network'
import Badge from '../components/Badge'
const sym = { up: '▲', down: '▼', flat: '▬' }
const API = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
const KEY = (t: string) => `finn.research.${t}`

/* ---- real research returned by POST /research/{ticker} ---- */
interface Cite { doc: string; page: number; quote: string; status?: string }
interface Claim { text: string; cites?: Cite[]; verified?: boolean }
interface Promise_ { topic: string; quarter_promised: string; promised: Claim; delivered: Claim; verdict: string }
interface RealView { business_snapshot?: Claim[]; financial_snapshot?: Claim[]; trajectory?: Claim[]; balance_sheet?: Claim[]; cash_quality?: Claim[]
  promised_vs_delivered?: Promise_[]; narrative_vs_numbers?: Claim[]; bull_case?: Claim[]; bear_case?: Claim[] }
interface RealResult { ticker: string; view: RealView; failed_claims?: unknown[]; savedAt?: string }

const loadReal = (t: string): RealResult | null => { try { const s = localStorage.getItem(KEY(t)); return s ? JSON.parse(s) : null } catch { return null } }
const savedTickers = (): string[] => { try { return Object.keys(localStorage).filter(k => k.startsWith('finn.research.')).map(k => k.slice(14)).sort() } catch { return [] } }
/** Remove wrapping quote marks so the renderer's own “ ” never doubles up. */
export const unquote = (s: string) => s.trim().replace(/^["'“”‘’]+|["'“”‘’]+$/g, '')
const verdictClass = (v: string) => v === 'delivered' ? 'met' : v === 'partly' ? 'partly' : v === 'missed' ? 'missed' : 'untested'

function Claims({ items }: { items?: Claim[] }) {
  return <>{(items ?? []).map((c, i) => <p key={i}>{c.text} {c.verified === false && <span className="cite unver">unverified</span>}
    {c.cites?.[0] && <span className="cite"> [{c.cites[0].doc.replace(/__/g, ' ')}, p{c.cites[0].page}]</span>}</p>)}</>
}

function RealResearch({ r }: { r: RealResult }) {
  const v = r.view
  const sec = (title: string, items?: Claim[]) => items?.length ? <section><h2>{title} <Badge kind="real" /></h2><Claims items={items} /></section> : null
  return <>
    {sec('Business', v.business_snapshot)}
    {sec('Financials', v.financial_snapshot)}
    {!!v.promised_vs_delivered?.length && <section><h2>Promised vs delivered <Badge kind="real" /></h2>{v.promised_vs_delivered.map((p, i) =>
      <div key={i} className={`prom ${verdictClass(p.verdict)}`}><small>{p.quarter_promised} · {p.topic}</small><div>“{unquote(p.promised.text)}”</div><div>→ {p.delivered.text}</div><span>{p.verdict.replace(/_/g, ' ')}</span></div>)}</section>}
    {sec('Trajectory', v.trajectory)}
    {sec('Balance sheet', v.balance_sheet)}
    {sec('Cash quality', v.cash_quality)}
    {sec('Narrative vs numbers', v.narrative_vs_numbers)}
    {(v.bull_case?.length || v.bear_case?.length) ? <section className="cols"><div><h2>Bull <Badge kind="real" /></h2>{v.bull_case?.map((b, i) => <p key={i}>+ {b.text}</p>)}</div><div><h2>Bear <Badge kind="real" /></h2>{v.bear_case?.map((b, i) => <p key={i}>− {b.text}</p>)}</div></section> : null}
    {!!r.failed_claims?.length && <p className="dim small">{r.failed_claims.length} claim(s) were dropped because their citations did not verify.</p>}
  </>
}

function DemoResearch({ t }: { t: string }) {
  const r = research[t]
  return <>
    <section><h2>Business <Badge kind="demo" /></h2><p>{r.snapshot}</p>
      <div className="bar">{r.segments.map(s => <i key={s.n} style={{ flex: s.pct }} title={s.n} />)}</div>
      <p className="dim small">{r.segments.map(s => `${s.n} ${s.pct}%`).join(' · ')}</p></section>
    <section><h2>Financials <Badge kind="demo" /></h2><div className="grid">{r.fin.map(f => <div key={f.k} className="kpi"><small>{f.k}</small><b>{f.v}</b></div>)}</div></section>
    <section><h2>Promised vs delivered <Badge kind="demo" /></h2>{r.promises.map((p, i) => <div key={i} className={`prom ${p.verdict}`}><small>{p.q}</small><div>“{unquote(p.said)}”</div><div>→ {p.got}</div><span>{p.verdict}</span></div>)}</section>
    <section><h2>Trajectory <Badge kind="demo" /></h2>{r.trajectory.map(x => <p key={x.k}><span className={`dir ${x.dir}`}>{sym[x.dir]}</span> <b>{x.k}</b> — {x.note}</p>)}</section>
    <section><h2>Cash quality <Badge kind="demo" /></h2>{r.quality.map(q => <p key={q.k} className={q.flag ? 'neg' : ''}><b>{q.k}</b> {q.v}</p>)}</section>
    <section className="cols"><div><h2>Bull <Badge kind="demo" /></h2>{r.bull.map(b => <p key={b}>+ {b}</p>)}</div><div><h2>Bear <Badge kind="demo" /></h2>{r.bear.map(b => <p key={b}>− {b}</p>)}</div></section>
    <p className="dim small">Sample extraction shown for illustration; figures are placeholders.</p>
  </>
}

type Run = { t: string; status: 'loading' | 'error'; msg?: string }

export default function Pull({ ticker, setTicker, openNet }: { ticker: string; setTicker: (t: string) => void; openNet: (v: NetView, arg?: string) => void }) {
  const [q, setQ] = useState('')
  const [saved, setSaved] = useState<string[]>(savedTickers)
  const [run, setRun] = useState<Run | null>(null)
  const qu = q.trim().toUpperCase()
  const sugg = qu ? portfolio.filter(c => c.t.includes(qu) || c.name.toUpperCase().includes(qu)).slice(0, 5) : []
  const validSymbol = /^[A-Z0-9&-]{1,20}$/.test(qu)
  const real = loadReal(ticker), demo = research[ticker], co = portfolio.find(c => c.t === ticker)
  const calls = callList(ticker)
  const pick = (t: string) => { setTicker(t); setQ(''); setRun(null) }

  async function analyse(t: string) {
    setRun({ t, status: 'loading' })
    try {
      const r = await fetch(`${API}/research/${encodeURIComponent(t)}`, { method: 'POST' })
      const text = await r.text()
      let body: any = null; try { body = JSON.parse(text) } catch { /* not JSON */ }
      if (!r.ok) throw new Error(body?.detail ?? `Backend returned HTTP ${r.status}${text && !body ? `: ${text.slice(0, 160)}` : ''}`)
      if (!body?.view) throw new Error('Backend response had no research view')
      try { localStorage.setItem(KEY(t), JSON.stringify({ ticker: t, view: body.view, failed_claims: body.failed_claims, savedAt: new Date().toISOString() })) } catch { /* storage unavailable */ }
      setSaved(savedTickers()); setRun(null)
    } catch (e) {
      const m = e instanceof TypeError ? 'Could not reach the backend. Is it running (uvicorn on :8000)?' : (e as Error).message
      setRun({ t, status: 'error', msg: m })
    }
  }
  const loading = run?.t === ticker && run.status === 'loading'
  const err = run?.t === ticker && run.status === 'error' ? run.msg : null
  const AnalyseBtn = ({ label }: { label: string }) => <button className="cta" disabled={loading} onClick={() => analyse(ticker)}>{loading ? <><span className="spin" />Analysing {ticker}… this can take a few minutes</> : label}</button>

  return (<>
    <div className="search"><input className="ask" placeholder="Analyse any NSE ticker — “INFY”, “Titan”…" value={q} autoCapitalize="characters" onChange={e => setQ(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && validSymbol) pick(sugg.find(c => c.t === qu)?.t ?? sugg[0]?.t ?? qu) }} />
      {qu && <div className="sugg">
        {sugg.map(c => <button key={c.t} onClick={() => pick(c.t)}><span>{c.name}</span><small>{c.t}{loadReal(c.t) ? ' · real research' : research[c.t] ? ' · sample' : ''}</small></button>)}
        {validSymbol && !sugg.some(c => c.t === qu) && <button onClick={() => pick(qu)}><span>Use NSE ticker “{qu}”</span><small>not in portfolio</small></button>}
        {!sugg.length && !validSymbol && <button disabled><span>Enter an NSE symbol (letters, digits, &amp; or -)</span></button>}</div>}
    </div>
    <section><h2>Research ready <Badge kind="real" /></h2>
      {saved.length ? <div className="chips">{saved.map(t => <button key={t} className="chip" onClick={() => pick(t)}>{t}</button>)}</div>
        : <p className="dim small">None yet — search a ticker above and press Analyse.</p>}
      <h2 style={{ marginTop: 14 }}>Samples <Badge kind="demo" /></h2>
      <div className="chips">{Object.keys(research).map(t => <button key={t} className="chip" onClick={() => pick(t)}>{t}</button>)}</div></section>

    <h2 style={{ marginTop: 22 }}>{co?.name ?? ticker} <small>{ticker}</small></h2>
    {real ? <>
        <div className="meta"><span className="dim small">Analysed {real.savedAt ? new Date(real.savedAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : ''}</span>
          <button className="ghost" style={{ marginLeft: 'auto' }} disabled={loading} onClick={() => analyse(ticker)}>{loading ? 'Re-analysing…' : 'Re-run'}</button></div>
        {err && <div className="errbox">{err}</div>}
        <RealResearch r={real} /></>
      : <>
        {demo && <>
          <section><p className="dim small">Showing a <b>demo sample</b> for {ticker} — not analysed from real documents.</p>
            <AnalyseBtn label="Run real analysis" />{err && <div className="errbox">{err}</div>}</section>
          <DemoResearch t={ticker} /></>}
        {!demo && <section><p><b>Not analysed yet.</b> <span className="dim">Analysing fetches the latest annual report and four concall transcripts from screener.in and extracts cited facts — primary sources only.</span></p>
          <AnalyseBtn label="Not analysed yet — Analyse" />{err && <div className="errbox">{err}</div>}</section>}</>}
    <section><h2>Who to call <Badge kind="demo" /> <small>synthetic network</small></h2>
      {calls.length ? calls.slice(0, 3).map(h => <div key={h.p.id} className="net"><div className="hit">◉ <b>{h.p.name}</b><span className={`rel ${h.rel.startsWith('worked') ? 'worked' : h.rel.startsWith('competitor') ? '' : 'supplier'}`}>{h.rel}</span>
        <br /><span className="dim">{affiliation(h.p)} · last spoke {h.p.lastTalkDays}d ago</span><br />{h.why}. <i>{h.know}.</i></div></div>)
        : <p className="dim small">No one in your network touches {co?.name ?? ticker} directly, or through a supplier, customer or competitor.</p>}
      <button className="more" style={{ marginTop: 8 }} onClick={() => openNet('call', ticker)}>{calls.length > 3 ? `All ${calls.length} contacts` : 'Open in Network'} →</button></section>
  </>)
}
