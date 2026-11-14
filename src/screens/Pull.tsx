import { useEffect, useRef, useState } from 'react'
import { research } from '../data/research'
import { portfolio } from '../data/portfolio'
import { callList, affiliation, type NetView } from '../lib/network'
import Badge from '../components/Badge'
const sym = { up: '▲', down: '▼', flat: '▬' }
const API = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
const KEY = (t: string) => `finn.research.${t}`
const CODE_KEY = 'finn.accessCode'
const SEEDS = ['INFY', 'DEEPAKNTR']   // static fallback list when the backend is unreachable (files in /seed/research)

/* ---- real research served by the FINN backend (GET /research/{ticker}); seeds also ship as static files ---- */
interface Cite { doc: string; page: number; quote: string; status?: string }
interface Claim { text: string; cites?: Cite[]; verified?: boolean }
interface Pair { id: string; metric: string; covers: string; quarter_said: string; reiterated_in?: string[]
  promised: { quote: string; doc: string; page: number }; actual?: { quote: string; doc: string; page: number } | null
  verdict: string | null; detail: string; explanation?: string | null }
interface RealView { business_snapshot?: Claim[]; financial_snapshot?: Claim[]; trajectory?: Claim[]; balance_sheet?: Claim[]; cash_quality?: Claim[]; reconciliation?: Claim[]
  promised_vs_delivered?: Pair[]; narrative_vs_numbers?: Claim[]; bull_case?: Claim[]; bear_case?: Claim[] }
interface RealResult { ticker: string; company?: string | null; generated_at?: string; source?: 'seed' | 'live'; view: RealView
  models?: { strong_used?: string; strong_requested?: string; used_fallback?: boolean }; failed_claims?: unknown[]; consistency_flags?: unknown[] }
interface ReadyItem { ticker: string; company?: string | null; generated_at?: string; model_used?: string; used_fallback?: boolean; source?: string }

const loadLocal = (t: string): RealResult | null => { try { const s = localStorage.getItem(KEY(t)); return s ? JSON.parse(s) : null } catch { return null } }
async function getJson(url: string): Promise<any | null> {
  try { const r = await fetch(url); return r.ok && (r.headers.get('content-type') ?? '').includes('json') ? await r.json() : null } catch { return null }
}
/** Backend first, then the static seed shipped with the app, then the last copy cached in this browser. */
async function fetchResult(t: string): Promise<RealResult | null> {
  for (const url of [`${API}/research/${encodeURIComponent(t)}`, `/seed/research/${encodeURIComponent(t)}.json`]) {
    const j = await getJson(url)
    if (j?.view) { try { localStorage.setItem(KEY(t), JSON.stringify(j)) } catch { /* storage unavailable */ } return j }
  }
  return loadLocal(t)
}
const getCode = () => { try { return sessionStorage.getItem(CODE_KEY) ?? '' } catch { return '' } }
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
/** Remove wrapping quote marks so the renderer's own “ ” never doubles up. */
export const unquote = (s: string) => s.trim().replace(/^["'“”‘’]+|["'“”‘’]+$/g, '')
const verdictClass = (v: string | null) => v === 'delivered' ? 'met' : v === 'partly' ? 'partly' : v === 'missed' ? 'missed' : 'untested'
const verdictLabel = (v: string | null) => v ? v.replace(/_/g, ' ') : 'unscored'
const docName = (d: string) => d.replace(/__/g, ' ')
const metricName = (m: string) => m.replace(/_/g, ' ')

function Claims({ items }: { items?: Claim[] }) {
  return <>{(items ?? []).map((c, i) => <p key={i}>{c.text} {c.verified === false && <span className="cite unver">unverified</span>}
    {c.cites?.[0] && <span className="cite"> [{docName(c.cites[0].doc)}, p{c.cites[0].page}]</span>}</p>)}</>
}

function RealResearch({ r }: { r: RealResult }) {
  const v = r.view
  const sec = (title: string, items?: Claim[], note?: string) => items?.length ? <section><h2>{title} <Badge kind="real" /></h2>{note && <p className="dim small">{note}</p>}<Claims items={items} /></section> : null
  const dropped = (r.failed_claims?.length ?? 0) + (r.consistency_flags?.length ?? 0)
  return <>
    {sec('Business', v.business_snapshot)}
    {sec('Financials', v.financial_snapshot)}
    {!!v.promised_vs_delivered?.length && <section><h2>Promised vs delivered <Badge kind="real" /></h2>
      <p className="dim small">Verdicts are computed from reported figures, never from comparing two guidance statements.</p>
      {v.promised_vs_delivered.map(p => <div key={p.id} className={`prom ${verdictClass(p.verdict)}`}>
        <small>{p.quarter_said} · {metricName(p.metric)} for {p.covers}{p.reiterated_in?.length ? ` · reiterated ${p.reiterated_in.join(', ')}` : ''}</small>
        <div>“{unquote(p.promised.quote)}” <em className="cite">[{docName(p.promised.doc)}, p{p.promised.page}]</em></div>
        <div>→ {p.detail}</div>
        {p.actual && <div className="dim small">“{unquote(p.actual.quote)}” <em className="cite">[{docName(p.actual.doc)}, p{p.actual.page}]</em></div>}
        {p.explanation && <div className="dim small">{p.explanation}</div>}
        <span>{verdictLabel(p.verdict)}</span></div>)}</section>}
    {sec('Trajectory', v.trajectory)}
    {sec('Balance sheet', v.balance_sheet)}
    {sec('Cash quality', v.cash_quality)}
    {sec('Scope & definition differences', v.reconciliation, 'Figures that look inconsistent but differ in scope, period or definition — shown side by side, never merged.')}
    {sec('Narrative vs numbers', v.narrative_vs_numbers)}
    {(v.bull_case?.length || v.bear_case?.length) ? <section className="cols"><div><h2>Bull <Badge kind="real" /></h2>{v.bull_case?.map((b, i) => <p key={i}>+ {b.text}</p>)}</div><div><h2>Bear <Badge kind="real" /></h2>{v.bear_case?.map((b, i) => <p key={i}>− {b.text}</p>)}</div></section> : null}
    {dropped > 0 && <p className="dim small">{dropped} claim(s) were dropped because their citations did not verify or they mixed scopes/periods.</p>}
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
  const [ready, setReady] = useState<ReadyItem[]>([])
  const [real, setReal] = useState<RealResult | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [code, setCode] = useState(getCode)
  const [needCode, setNeedCode] = useState(false)
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  const qu = q.trim().toUpperCase()
  const sugg = qu ? portfolio.filter(c => c.t.includes(qu) || c.name.toUpperCase().includes(qu)).slice(0, 5) : []
  const validSymbol = /^[A-Z0-9&-]{1,20}$/.test(qu)
  const demo = research[ticker], co = portfolio.find(c => c.t === ticker)
  const calls = callList(ticker)
  const readyMap = Object.fromEntries(ready.map(i => [i.ticker, i]))
  const pick = (t: string) => { setTicker(t); setQ(''); setRun(null) }

  const refreshList = async () => {
    const j = await getJson(`${API}/research`)
    if (j?.items) { setReady(j.items); if (j.access_code_required) setNeedCode(n => n || !getCode()) }
    else setReady(SEEDS.map(t => ({ ticker: t, source: 'seed' })))   // backend unreachable: static seeds still work
  }
  useEffect(() => { refreshList() }, [])
  useEffect(() => { let on = true; setReal(null); fetchResult(ticker).then(r => { if (on) setReal(r) }); return () => { on = false } }, [ticker])

  async function analyse(t: string, refresh = false) {
    setRun({ t, status: 'loading', msg: 'starting…' })
    try {
      try { sessionStorage.setItem(CODE_KEY, code) } catch { /* storage unavailable */ }
      const r = await fetch(`${API}/research/${encodeURIComponent(t)}${refresh ? '?refresh=true' : ''}`, { method: 'POST', headers: code ? { 'X-Access-Code': code } : {} })
      const body = await r.json().catch(() => null)
      if (r.status === 401) setNeedCode(true)
      if (!r.ok) throw new Error(body?.message ?? body?.detail ?? `Backend returned HTTP ${r.status}`)
      if (r.status === 202) {
        const id = body.job_id as string
        for (let i = 0; i < 450 && alive.current; i++) {          // poll every 2s, up to 15 minutes
          await sleep(2000)
          const jr = await fetch(`${API}/research/jobs/${id}`)
          const j = await jr.json().catch(() => null)
          if (!jr.ok) throw new Error(j?.message ?? `Job status failed (HTTP ${jr.status})`)
          if (j.status === 'failed') throw new Error(j.error ?? 'Analysis failed')
          if (j.status === 'done') break
          setRun({ t, status: 'loading', msg: j.message })
        }
      }
      const res = await fetchResult(t)
      if (!res) throw new Error('Analysis finished but the result could not be loaded')
      if (alive.current) { if (t === ticker) setReal(res); setRun(null); refreshList() }
    } catch (e) {
      const m = e instanceof TypeError ? 'Could not reach the backend. Is it running (uvicorn on :8000)?' : (e as Error).message
      if (alive.current) setRun({ t, status: 'error', msg: m })
    }
  }
  const loading = run?.t === ticker && run.status === 'loading'
  const err = run?.t === ticker && run.status === 'error' ? run.msg : null
  const AnalyseBtn = ({ label }: { label: string }) => <button className="cta" disabled={loading} onClick={() => analyse(ticker)}>{loading ? <><span className="spin" />{run?.msg ?? 'Analysing'} · {ticker} · a few minutes</> : label}</button>
  const CodeBox = () => needCode ? <input className="ask" type="password" placeholder="Access code (needed to analyse a new ticker)" value={code} autoComplete="off" onChange={e => setCode(e.target.value)} style={{ marginTop: 10 }} /> : null
  const meta = real?.models ? `${real.models.strong_used ?? ''}${real.models.used_fallback ? ' (fallback model)' : ''}` : ''

  return (<>
    <div className="search"><input className="ask" placeholder="Analyse any NSE ticker — “INFY”, “Titan”…" value={q} autoCapitalize="characters" onChange={e => setQ(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && validSymbol) pick(sugg.find(c => c.t === qu)?.t ?? sugg[0]?.t ?? qu) }} />
      {qu && <div className="sugg">
        {sugg.map(c => <button key={c.t} onClick={() => pick(c.t)}><span>{c.name}</span><small>{c.t}{readyMap[c.t] ? ' · real research' : research[c.t] ? ' · sample' : ''}</small></button>)}
        {validSymbol && !sugg.some(c => c.t === qu) && <button onClick={() => pick(qu)}><span>Use NSE ticker “{qu}”</span><small>{readyMap[qu] ? 'real research' : 'not in portfolio'}</small></button>}
        {!sugg.length && !validSymbol && <button disabled><span>Enter an NSE symbol (letters, digits, &amp; or -)</span></button>}</div>}
    </div>
    <section><h2>Research ready <Badge kind="real" /></h2>
      {ready.length ? <div className="chips">{ready.map(i => <button key={i.ticker} className="chip" onClick={() => pick(i.ticker)} title={i.company ?? ''}>{i.ticker}</button>)}</div>
        : <p className="dim small">None yet — search a ticker above and press Analyse.</p>}
      <h2 style={{ marginTop: 14 }}>Samples <Badge kind="demo" /></h2>
      <div className="chips">{Object.keys(research).map(t => <button key={t} className="chip" onClick={() => pick(t)}>{t}</button>)}</div></section>

    <h2 style={{ marginTop: 22 }}>{co?.name ?? real?.company ?? ticker} <small>{ticker}</small></h2>
    {real ? <>
        <div className="meta"><span className="dim small">Analysed {real.generated_at ? new Date(real.generated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : ''}{meta && ` · ${meta}`}</span>
          <button className="ghost" style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }} disabled={loading} onClick={() => analyse(ticker, true)}>{loading ? (run?.msg ?? 'Re-analysing…') : 'Re-run'}</button></div>
        <CodeBox />{err && <div className="errbox">{err}</div>}
        <RealResearch r={real} /></>
      : <>
        {demo && <>
          <section><p className="dim small">Showing a <b>demo sample</b> for {ticker} — not analysed from real documents.</p>
            <AnalyseBtn label="Run real analysis" /><CodeBox />{err && <div className="errbox">{err}</div>}</section>
          <DemoResearch t={ticker} /></>}
        {!demo && <section><p><b>Not analysed yet.</b> <span className="dim">Analysing fetches the latest annual report and four concall transcripts from screener.in and extracts cited facts — primary sources only.</span></p>
          <AnalyseBtn label="Not analysed yet — Analyse" /><CodeBox />{err && <div className="errbox">{err}</div>}</section>}</>}
    <section><h2>Who to call <Badge kind="demo" /> <small>synthetic network · links are illustrative</small></h2>
      {calls.length ? calls.slice(0, 3).map(h => <div key={h.p.id} className="net"><div className="hit">◉ <b>{h.p.name}</b><span className={`rel ${h.rel.startsWith('worked') ? 'worked' : h.rel.startsWith('competitor') ? '' : 'supplier'}`}>{h.rel}</span>
        <br /><span className="dim">{affiliation(h.p)} · last spoke {h.p.lastTalkDays}d ago</span><br />{h.why}. <i>{h.know}.</i></div></div>)
        : <p className="dim small">No one in your network touches {co?.name ?? ticker} directly, or through a supplier, customer or competitor.</p>}
      <button className="more" style={{ marginTop: 8 }} onClick={() => openNet('call', ticker)}>{calls.length > 3 ? `All ${calls.length} contacts` : 'Open in Network'} →</button></section>
  </>)
}
