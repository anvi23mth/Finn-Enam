import { useEffect, useState } from 'react'
export interface Bar { d: string; c: number; v: number }
export type Prices = Record<string, Bar[]>
export interface TickerMeta { status: 'live' | 'no_data' | 'demo'; lastDate: string | null; error?: string }
export interface PriceFile { prices: Prices; source: string; demo: boolean; meta: Record<string, TickerMeta> }
export function usePrices() {
  const [data, setData] = useState<PriceFile | null>(null)
  useEffect(() => { fetch('/prices.json').then(r => r.json()).then(setData).catch(() => setData({ prices: {}, source: 'unavailable', demo: false, meta: {} })) }, [])
  return data
}
export const fmtDate = (iso: string) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
/** Latest date any ticker has data for; tickers behind it are "stale". */
export function latestDate(meta: Record<string, TickerMeta>) {
  return Object.values(meta).map(m => m.lastDate).filter((d): d is string => !!d).sort().at(-1) ?? null
}
export interface Thresholds { movePct: number; volX: number }
export interface Alert { t: string; kind: 'price'|'volume'; text: string; sev: number }
export function evalAlerts(prices: Prices, th: Thresholds, meta: Record<string, TickerMeta> = {}): Alert[] {
  const out: Alert[] = []
  const newest = latestDate(meta)
  for (const [t, bars] of Object.entries(prices)) {
    if (bars.length < 12) continue
    const last = bars.at(-1)!, prev = bars.at(-2)!, base = bars.slice(-22, -1)
    const chg = (last.c / prev.c - 1) * 100
    const avg = base.reduce((s, b) => s + b.v, 0) / base.length
    const x = last.v / avg
    const asOf = newest && last.d < newest ? ` (as of ${fmtDate(last.d)})` : ''
    if (Math.abs(chg) >= th.movePct) out.push({ t, kind: 'price', sev: Math.abs(chg), text: `${chg > 0 ? '+' : ''}${chg.toFixed(1)}% on the day${asOf}` })
    if (x >= th.volX) out.push({ t, kind: 'volume', sev: x, text: `Volume ${x.toFixed(1)}× 20-day average${asOf}` })
  }
  return out.sort((a, b) => b.sev - a.sev)
}
