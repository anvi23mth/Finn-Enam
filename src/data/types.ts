export type Category = 'results'|'M&A'|'fund_raise'|'management_change'|'litigation'|'insider_trading'|'earnings_call'|'investor_meetings'|'credit_rating'|'dividend'|'bonus_split'|'capex'|'press_release'|'postal_ballot'|'agm_egm'|'pledging'|'unclassified'
export interface Company { t: string; name: string; sector: string; aka?: string[] }
export interface Announcement { id: string; t: string; hoursAgo: number; cat: Category; title: string; summary?: string; person?: string; results?: ResultRow[] }
export interface ResultRow { k: 'Revenue'|'EBITDA'|'PBT'|'PAT'; cur: number; qoq: number; yoy: number } // ₹ cr; qoq/yoy as % change
export interface Person { id: string; name: string; role: string; company: string; past: { company: string; role: string; yrs: string }[]; school: string; strength: 1|2|3|4|5; lastTalkDays: number; knows: string; themes: string[] }
