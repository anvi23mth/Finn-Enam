import { useEffect, useRef, useState } from 'react'
import { portfolio } from '../data/portfolio'
import { callList, affiliation, type NetView } from '../lib/network'
import Badge from '../components/Badge'
const API = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
const KEY = (t: string) => `finn.research.${t}`
const CODE_KEY = 'finn.accessCode'
const JOB_KEY = 'finn.job'   // {id, ticker} — only ever used to RESUME POLLING a job; never to start or replay one
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
const loadJob = (): { id: string; ticker: string } | null => { try { const j = JSON.parse(localStorage.getItem(JOB_KEY) ?? 'null'); return j?.id && j?.ticker ? j : null } catch { return null } }
const saveJob = (id: string, ticker: string) => { try { localStorage.setItem(JOB_KEY, JSON.stringify({ id, ticker })) } catch { /* storage unavailable */ } }
const clearJob = () => { try { localStorage.removeItem(JOB_KEY) } catch { /* storage unavailable */ } }
const getCode = () => { try { return sessionStorage.getItem(CODE_KEY) ?? '' } catch { return '' } }
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))
/** Remove wrapping quote marks so the renderer's own “ ” never doubles up. */
const unquote = (s: string) => s.trim().replace(/^["'“”‘’]+|["'“”‘’]+$/g, '')
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

type Run = { t: string; status: 'loading' | 'error' | 'interrupted'; msg?: string }
const INTERRUPTED = 'The analysis was interrupted — retry.'

export default function Pull({ ticker, setTicker, openNet }: { ticker: string; setTicker: (t: string) => void; openNet: (v: NetView, arg?: string) => void }) {
  const [q, setQ] = useState('')
  const [ready, setReady] = useState<ReadyItem[] | null>(null)   // null until the list has loaded
  const [real, setReal] = useState<RealResult | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [code, setCode] = useState(getCode)
  const [codeRequired, setCodeRequired] = useState(false)   // server says new analyses need a code
  const [showCode, setShowCode] = useState(false)
  const tok = useRef(0)                                      // invalidates older polling loops
  const qu = q.trim().toUpperCase()
  const sugg = qu ? portfolio.filter(c => c.t.includes(qu) || c.name.toUpperCase().includes(qu)).slice(0, 5) : []
  const validSymbol = /^[A-Z0-9&-]{1,20}$/.test(qu)
  const co = portfolio.find(c => c.t === ticker)
  const calls = callList(ticker)
  const readyMap = Object.fromEntries((ready ?? []).map(i => [i.ticker, i]))
  const pick = (t: string) => { setTicker(t); setQ(''); setRun(null) }

  const refreshList = async () => {
    const j = await getJson(`${API}/research`)
    if (j?.items) { setReady(j.items); setCodeRequired(!!j.access_code_required) }
    else setReady(SEEDS.map(t => ({ ticker: t, source: 'seed' })))   // backend unreachable: static seeds still work
  }
  useEffect(() => { refreshList() }, [])
  // Only ask for a result the server says exists (no 404 probes for tickers that were never analysed).
  useEffect(() => {
    let on = true; setReal(null)
    if (ready?.some(i => i.ticker === ticker)) fetchResult(ticker).then(r => { if (on) setReal(r) })
    return () => { on = false }
  }, [ticker, ready])

  /** GET-only: follow a job to its end. Starts nothing. A missing/lost job is reported as interrupted, never as a raw 404. */
  async function poll(id: string, t: string) {
    const my = ++tok.current
    for (let i = 0; i < 450 && tok.current === my; i++) {          // every 2s, up to 15 minutes
      let jr: Response, j: any = null
      try { jr = await fetch(`${API}/research/jobs/${id}`); j = await jr.json().catch(() => null) }
      catch { if (tok.current === my) setRun({ t, status: 'loading', msg: 'reconnecting to the backend…' }); await sleep(3000); continue }
      if (tok.current !== my) return
      if (jr.status === 404 || j?.status === 'interrupted') { clearJob(); setRun({ t, status: 'interrupted', msg: INTERRUPTED }); return }
      if (!jr.ok) { clearJob(); setRun({ t, status: 'error', msg: j?.message ?? `Job status failed (HTTP ${jr.status})` }); return }
      if (j.status === 'failed') { clearJob(); setRun({ t, status: 'error', msg: j.error ?? 'Analysis failed' }); return }
      if (j.status === 'done') {
        clearJob()
        const res = await fetchResult(t)
        if (tok.current !== my) return
        if (res) { if (t === ticker) setReal(res); setRun(null); refreshList() }
        else setRun({ t, status: 'error', msg: 'Analysis finished but the result could not be loaded' })
        return
      }
      setRun({ t, status: 'loading', msg: j.message })
      await sleep(2000)
    }
  }
  // Resume polling a job that was in flight when the page was closed. GET requests only.
  useEffect(() => { const j = loadJob(); if (j) { setTicker(j.ticker); setRun({ t: j.ticker, status: 'loading', msg: 'resuming…' }); poll(j.id, j.ticker) } return () => { tok.current++ } }, [])

  /** The ONLY place a job is started, and only from a deliberate click (see `onClick` guards below). */
  async function analyse(t: string, refresh = false) {
    setRun({ t, status: 'loading', msg: 'starting…' })
    try {
      try { sessionStorage.setItem(CODE_KEY, code) } catch { /* storage unavailable */ }
      const r = await fetch(`${API}/research/${encodeURIComponent(t)}${refresh ? '?refresh=true' : ''}`, { method: 'POST', headers: code ? { 'X-Access-Code': code } : {} })
      const body = await r.json().catch(() => null)
      if (r.status === 401) { setCodeRequired(true); setShowCode(true) }
      if (!r.ok) throw new Error(body?.message ?? body?.detail ?? `Backend returned HTTP ${r.status}`)
      if (r.status === 202) { saveJob(body.job_id, t); await poll(body.job_id, t); return }
      const res = await fetchResult(t)     // 200 "ready": an existing result; nothing was started
      if (res) { if (t === ticker) setReal(res); setRun(null); refreshList() } else throw new Error('Result could not be loaded')
    } catch (e) {
      const m = e instanceof TypeError ? 'Could not reach the backend. Is it running (uvicorn on :8000)?' : (e as Error).message
      setRun({ t, status: 'error', msg: m })
    }
  }
  /** Programmatic/synthetic clicks (e.isTrusted === false) never start an analysis. */
  const onClick = (fn: () => void) => (e: React.MouseEvent) => { if (e.isTrusted) fn() }

  const loading = run?.t === ticker && run.status === 'loading'
  const msg = run?.t === ticker && run.status !== 'loading' ? run.msg : null
  const interrupted = run?.t === ticker && run.status === 'interrupted'
  const canRerun = !!real && !!code.trim()                  // re-runs need the access code; hidden otherwise
  const AnalyseBtn = ({ label }: { label: string }) => <button className="cta" disabled={loading} onClick={onClick(() => analyse(ticker))}>{loading ? <><span className="spin" />{run?.msg ?? 'Analysing'} · {ticker} · a few minutes</> : label}</button>
  const CodeBox = () => (showCode || (codeRequired && !real)) ? <input className="ask" type="password" placeholder="Access code" value={code} autoComplete="off" onChange={e => setCode(e.target.value)} style={{ marginTop: 10 }} /> : null
  const Status = () => msg ? <div className="errbox">{msg}{interrupted && <><br /><button className="ghost" style={{ marginTop: 8 }} onClick={onClick(() => analyse(ticker, !!real))}>Retry</button></>}</div> : null
  const meta = real?.models ? `${real.models.strong_used ?? ''}${real.models.used_fallback ? ' (fallback model)' : ''}` : ''

  return (<>
    <div className="search"><input className="ask" placeholder="Analyse any NSE ticker — “INFY”, “Titan”…" value={q} autoCapitalize="characters" onChange={e => setQ(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && validSymbol) pick(sugg.find(c => c.t === qu)?.t ?? sugg[0]?.t ?? qu) }} />
      {qu && <div className="sugg">
        {sugg.map(c => <button key={c.t} onClick={() => pick(c.t)}><span>{c.name}</span><small>{c.t}{readyMap[c.t] ? ' · real research' : ''}</small></button>)}
        {validSymbol && !sugg.some(c => c.t === qu) && <button onClick={() => pick(qu)}><span>Use NSE ticker “{qu}”</span><small>{readyMap[qu] ? 'real research' : 'not in portfolio'}</small></button>}
        {!sugg.length && !validSymbol && <button disabled><span>Enter an NSE symbol (letters, digits, &amp; or -)</span></button>}</div>}
    </div>
    <section><h2>Research ready <Badge kind="real" /></h2>
      {ready?.length ? <div className="chips">{ready.map(i => <button key={i.ticker} className={`chip${i.ticker === ticker ? ' on' : ''}`} onClick={() => pick(i.ticker)} title={i.company ?? ''}>{i.ticker}</button>)}</div>
        : <p className="dim small">{ready ? 'None yet — search a ticker above and press Analyse.' : 'Loading…'}</p>}</section>

    <h2 style={{ marginTop: 22 }}>{co?.name ?? real?.company ?? ticker} <small>{ticker}</small></h2>
    {real ? <>
        <div className="meta"><span className="dim small">Analysed {real.generated_at ? new Date(real.generated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : ''}{meta && ` · ${meta}`}</span>
          {canRerun ? <button className="ghost" style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }} disabled={loading} onClick={onClick(() => analyse(ticker, true))}>{loading ? (run?.msg ?? 'Re-analysing…') : 'Re-run'}</button>
            : <button className="ghost" style={{ marginLeft: 'auto', whiteSpace: 'nowrap' }} onClick={() => setShowCode(s => !s)}>Access code</button>}</div>
        <CodeBox />{loading && <p className="dim small"><span className="spin" /> {run?.msg}</p>}<Status />
        <RealResearch r={real} /></>
      : <section><p><b>Not analysed yet.</b> <span className="dim">Analysing fetches the latest annual report and four concall transcripts from screener.in and extracts cited facts — primary sources only.</span></p>
          <AnalyseBtn label="Analyse" /><CodeBox /><Status /></section>}
    <section><h2>Who to call <Badge kind="demo" /> <small>synthetic network · links are illustrative</small></h2>
      {calls.length ? calls.slice(0, 3).map(h => <div key={h.p.id} className="net"><div className="hit">◉ <b>{h.p.name}</b><span className={`rel ${h.rel.startsWith('worked') ? 'worked' : h.rel.startsWith('competitor') ? '' : 'supplier'}`}>{h.rel}</span>
        <br /><span className="dim">{affiliation(h.p)} · last spoke {h.p.lastTalkDays}d ago</span><br />{h.why}. <i>{h.know}.</i></div></div>)
        : <p className="dim small">No one in your network touches {co?.name ?? ticker} directly, or through a supplier, customer or competitor.</p>}
      <button className="more" style={{ marginTop: 8 }} onClick={() => openNet('call', ticker)}>{calls.length > 3 ? `All ${calls.length} contacts` : 'Open in Network'} →</button></section>
  </>)
}
