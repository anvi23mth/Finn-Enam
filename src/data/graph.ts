// SYNTHETIC company relationship graph between portfolio names (ticker → ticker). Used to rank contacts who
// sit at a supplier, customer or rival of the company you are looking at.
export interface Edge { from: string; to: string; note: string }   // `from` supplies `to`
export const supplies: Edge[] = [
  { from:'POLYCAB', to:'LT', note:'power and control cables for EPC projects' },
  { from:'RELIANCE', to:'POLYCAB', note:'PVC and polymer compounds' },
  { from:'DEEPAKNTR', to:'ASIANPAINT', note:'solvents and intermediates' },
  { from:'DEEPAKNTR', to:'PIDILITIND', note:'phenolic and adhesive intermediates' },
  { from:'DEEPAKNTR', to:'SUNPHARMA', note:'pharma intermediates' },
  { from:'RELIANCE', to:'DEEPAKNTR', note:'benzene and propylene feedstock' },
  { from:'DIXON', to:'BHARTIARTL', note:'customer-premises equipment' },
  { from:'TCS', to:'SBIN', note:'core-banking and digital programmes' },
  { from:'INFY', to:'ICICIBANK', note:'digital-banking platforms' },
  { from:'TCS', to:'HDFCBANK', note:'applications and infrastructure' },
  { from:'CHOLAFIN', to:'TMCV', note:'vehicle financing for commercial-vehicle buyers' },
  { from:'HDFCBANK', to:'TMPV', note:'dealer and retail vehicle finance' },
  { from:'TITAN', to:'ITC', note:'corporate gifting and lifestyle retail partnerships' },
  { from:'LT', to:'RELIANCE', note:'EPC for refinery and petchem projects' },
]
/** Cross-sector rivals (same-sector peers are derived from the portfolio sector tag). */
export const rivals: [string, string][] = [['RELIANCE', 'BHARTIARTL'], ['ASIANPAINT', 'PIDILITIND'], ['TMPV', 'TMCV']]
