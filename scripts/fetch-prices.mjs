// EOD price/volume pipeline. Tries Yahoo's chart endpoint per ticker (.NS);
// falls back to a deterministic synthetic series so the demo never breaks.
import { writeFileSync } from 'node:fs'
const tickers = ['RELIANCE','HDFCBANK','INFY','TCS','ICICIBANK','SBIN','TATAMOTORS','SUNPHARMA','ITC','LT','BHARTIARTL','ASIANPAINT','PIDILITIND','DEEPAKNTR','POLYCAB','DIXON','CHOLAFIN','TITAN']
const out = {}
let live = 0
const seed = s => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return () => ((h = Math.imul(h ^ (h >>> 15), 2246822507) >>> 0) / 4294967296) }
for (const t of tickers) {
  try {
    const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${t}.NS?range=3mo&interval=1d`, { headers: { 'User-Agent': 'Mozilla/5.0' } })
    if (!r.ok) throw new Error(r.status)
    const j = (await r.json()).chart.result[0]
    const q = j.indicators.quote[0]
    out[t] = j.timestamp.map((ts, i) => ({ d: new Date(ts * 1000).toISOString().slice(0, 10), c: +q.close[i]?.toFixed(2), v: q.volume[i] })).filter(x => x.c && x.v)
    live++
  } catch {
    const rnd = seed(t); let p = 300 + rnd() * 2500; const days = []
    const base = 8e5 + rnd() * 5e6
    for (let i = 60; i >= 0; i--) {
      const d = new Date(Date.now() - i * 864e5); if ([0, 6].includes(d.getDay())) continue
      p *= 1 + (rnd() - 0.48) * 0.025
      days.push({ d: d.toISOString().slice(0, 10), c: +p.toFixed(2), v: Math.round(base * (0.6 + rnd() * 0.8)) })
    }
    // plant unusual last-day moves on a few names so alerts are demoable
    if (['DIXON','TATAMOTORS','DEEPAKNTR'].includes(t)) { const l = days.at(-1); l.v = Math.round(base * 2.9); l.c = +(days.at(-2).c * (t === 'DEEPAKNTR' ? 0.94 : 1.055)).toFixed(2) }
    out[t] = days
  }
}
writeFileSync('public/prices.json', JSON.stringify({ generatedAt: new Date().toISOString(), source: live ? `yahoo(${live}/${tickers.length}) + synthetic fallback` : 'synthetic', prices: out }))
console.log('wrote public/prices.json —', live, 'live,', tickers.length - live, 'synthetic')
