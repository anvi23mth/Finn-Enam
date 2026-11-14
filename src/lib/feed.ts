import { useEffect, useState } from 'react'
import type { Announcement, Category } from '../data/types'

export type Prio = 'high' | 'medium' | 'low'
export interface RealAnn { id: string; ticker: string; datetime: string; subject: string; details?: string; attachment?: string; category: Category; priority: Prio; summary: string | null; source: string }
export interface Feed { asOf: Date; items: RealAnn[]; counts: { category: Record<string, number>; priority: Record<string, number> }; models: Record<string, number> }

/** Real, classified announcements (data/announcements/classified.json, published to /announcements/). */
export function useFeed() {
  const [feed, setFeed] = useState<Feed | null>(null), [error, setError] = useState<string | null>(null)
  useEffect(() => {
    fetch('/announcements/classified.json').then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(j => setFeed({ asOf: new Date(j.generated_at), items: j.items, counts: j.counts, models: j.models }))
      .catch(e => setError(String(e.message ?? e)))
  }, [])
  return { feed, error }
}

/** Adapter so the network-matching code (which works on Announcement) runs on real items. */
export const toAnnouncement = (r: RealAnn, asOf: Date): Announcement => ({
  id: r.id, t: r.ticker, cat: r.category, title: r.subject, summary: r.summary ?? r.details ?? undefined,
  hoursAgo: Math.max(0, (asOf.getTime() - new Date(r.datetime).getTime()) / 36e5),
})
export const ago = (h: number) => h < 1 ? `${Math.max(1, Math.round(h * 60))}m` : h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)}d`

export interface MetricRow { current: number | null; previous: number | null; year_ago: number | null; qoq_pct: number | null; yoy_pct: number | null; verified: boolean; derived: boolean }
export interface ResultsFile { ticker: string; status: 'ok' | 'partial' | 'not_found' | 'failed'; error?: string; filing: { id: string; subject: string; datetime: string }; basis?: string; unit?: string
  quarter_labels?: Record<string, string>; table_crore?: Record<'revenue' | 'ebitda' | 'pbt' | 'pat', MetricRow>; flags?: string[]; not_found_or_unverified?: string[]; metrics?: Record<string, Record<string, { verified?: boolean } | null>> }

const resultsCache = new Map<string, Promise<ResultsFile | null>>()
/** One fetch per ticker per session, shared between cards. */
function loadResults(ticker: string) {
  let p = resultsCache.get(ticker)
  if (!p) {
    p = fetch(`/results/${ticker}.json`).then(x => x.ok && (x.headers.get('content-type') ?? '').includes('json') ? x.json() as Promise<ResultsFile> : null).catch(() => null)
    resultsCache.set(ticker, p)
  }
  return p
}
/** undefined while loading, null when there is no results file. */
export function useResults(ticker: string, enabled: boolean) {
  const [r, setR] = useState<ResultsFile | null | undefined>(undefined)
  useEffect(() => {
    if (!enabled) return
    let live = true
    loadResults(ticker).then(x => { if (live) setR(x) })
    return () => { live = false }
  }, [ticker, enabled])
  return r
}
