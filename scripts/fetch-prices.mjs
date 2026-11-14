// EOD price/volume pipeline. Fetches Yahoo's chart endpoint per ticker (.NS).
// A ticker that fails is written as "no_data" (empty series) — never replaced with made-up prices.
// `--demo` is the only way to get synthetic data: it skips Yahoo, generates a deterministic series for
// every ticker, plants unusual last-day moves for alert demos, and flags the file demo:true.
import { writeFileSync } from 'node:fs'
const DEMO = process.argv.includes('--demo')
const tickers = ['RELIANCE','HDFCBANK','INFY','TCS','ICICIBANK','SBIN','TMPV','TMCV','SUNPHARMA','ITC','LT','BHARTIARTL','ASIANPAINT','PIDILITIND','DEEPAKNTR','POLYCAB','DIXON','CHOLAFIN','TITAN']
const prices = {}, meta = {}
const seed = s => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return () => ((h = Math.imul(h ^ (h >>> 15), 2246822507) >>> 0) / 4294967296) }

function synthetic(t) {
  const rnd = seed(t); let p = 300 + rnd() * 2500; const days = []
  const base = 8e5 + rnd() * 5e6
  for (let i = 60; i >= 0; i--) {
    const d = new Date(Date.now() - i * 864e5); if ([0, 6].includes(d.getDay())) continue
    p *= 1 + (rnd() - 0.48) * 0.025
    days.push({ d: d.toISOString().slice(0, 10), c: +p.toFixed(2), v: Math.round(base * (0.6 + rnd() * 0.8)) })
  }
  if (['DIXON', 'TMPV', 'DEEPAKNTR'].includes(t)) { // planted moves, demo only
    const l = days.at(-1); l.v = Math.round(base * 2.9); l.c = +(days.at(-2).c * (t === 'DEEPAKNTR' ? 0.94 : 1.055)).toFixed(2)
  }
  return days
}

async function live(t) {
  const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${t}.NS?range=3mo&interval=1d`, { headers: { 'User-Agent': 'Mozilla/5.0' } })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  const j = (await r.json()).chart.result?.[0]
  if (!j) throw new Error('empty chart result')
  const q = j.indicators.quote[0]
  const bars = j.timestamp.map((ts, i) => ({ d: new Date(ts * 1000).toISOString().slice(0, 10), c: +q.close[i]?.toFixed(2), v: q.volume[i] })).filter(x => x.c && x.v)
  if (!bars.length) throw new Error('no usable bars')
  return bars
}

const failed = {}
for (const t of tickers) {
  if (DEMO) { prices[t] = synthetic(t); meta[t] = { status: 'demo', lastDate: prices[t].at(-1).d }; continue }
  try { prices[t] = await live(t); meta[t] = { status: 'live', lastDate: prices[t].at(-1).d } }
  catch (e) { failed[t] = String(e.message ?? e); prices[t] = []; meta[t] = { status: 'no_data', lastDate: null, error: failed[t] } }
}
const nLive = tickers.filter(t => meta[t].status === 'live').length
const noData = Object.keys(failed)
const source = DEMO ? `DEMO DATA — synthetic, not real prices (${tickers.length}/${tickers.length})`
  : noData.length ? `yahoo (${nLive}/${tickers.length} live; no data: ${noData.join(', ')})`
  : `yahoo (${nLive}/${tickers.length} live)`
writeFileSync('public/prices.json', JSON.stringify({ generatedAt: new Date().toISOString(), source, demo: DEMO, prices, meta }))
console.log(`wrote public/prices.json — ${source}`)
for (const [t, e] of Object.entries(failed)) console.log(`  no data: ${t} (${e})`)
