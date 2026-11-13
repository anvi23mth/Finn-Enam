import { useEffect, useState } from 'react'
export interface Bar { d: string; c: number; v: number }
export type Prices = Record<string, Bar[]>
export function usePrices() {
  const [data, setData] = useState<{ prices: Prices; source: string } | null>(null)
  useEffect(() => { fetch('/prices.json').then(r => r.json()).then(setData).catch(() => setData({ prices: {}, source: 'unavailable' })) }, [])
  return data
}
export interface Thresholds { movePct: number; volX: number }
export interface Alert { t: string; kind: 'price'|'volume'; text: string; sev: number }
export function evalAlerts(prices: Prices, th: Thresholds): Alert[] {
  const out: Alert[] = []
  for (const [t, bars] of Object.entries(prices)) {
    if (bars.length < 12) continue
    const last = bars.at(-1)!, prev = bars.at(-2)!, base = bars.slice(-22, -1)
    const chg = (last.c / prev.c - 1) * 100
    const avg = base.reduce((s, b) => s + b.v, 0) / base.length
    const x = last.v / avg
    if (Math.abs(chg) >= th.movePct) out.push({ t, kind: 'price', sev: Math.abs(chg), text: `${chg > 0 ? '+' : ''}${chg.toFixed(1)}% on the day` })
    if (x >= th.volX) out.push({ t, kind: 'volume', sev: x, text: `Volume ${x.toFixed(1)}× 20-day average` })
  }
  return out.sort((a, b) => b.sev - a.sev)
}
