// ILLUSTRATIVE output of the Pull pipeline (annual report + concall extraction -> structured JSON).
// Numbers are placeholders showing the shape; the live pipeline fills this per ticker from primary docs only.
export interface Research {
  t: string; snapshot: string; segments: { n: string; pct: number }[]
  fin: { k: string; v: string }[]
  trajectory: { k: string; dir: 'up'|'down'|'flat'; note: string }[]
  quality: { k: string; v: string; flag?: boolean }[]
  promises: { q: string; said: string; got: string; verdict: 'met'|'missed'|'beat' }[]
  bull: string[]; bear: string[]
}
export const research: Record<string, Research> = {
  INFY: { t:'INFY', snapshot:'Global IT services: consulting, application and infrastructure outsourcing, and AI-led platforms for large enterprises.',
    segments:[{n:'Financial services',pct:28},{n:'Retail',pct:14},{n:'Communication',pct:12},{n:'Energy & utilities',pct:12},{n:'Manufacturing',pct:12},{n:'Other',pct:22}],
    fin:[{k:'Revenue (TTM)',v:'₹1.62 lakh cr'},{k:'EBIT margin',v:'21.0%'},{k:'PAT',v:'₹25,900 cr'},{k:'ROCE',v:'38%'}],
    trajectory:[{k:'Revenue growth',dir:'flat',note:'High-single-digit INR growth, slower than FY22–23'},{k:'EBIT margin',dir:'up',note:'Recovering ~100 bps from FY24 trough'},{k:'Large-deal TCV',dir:'up',note:'Record TCV disclosed in two of last four quarters'}],
    quality:[{k:'CFO / PAT',v:'1.05×'},{k:'FCF / PAT',v:'0.98×'},{k:'Receivable days',v:'69 (↑3)',flag:true}],
    promises:[
      {q:'Q1 FY26',said:'Revenue growth 1–3% (CC) for the year',got:'Q1: 3.8% YoY CC',verdict:'beat'},
      {q:'Q2 FY26',said:'EBIT margin in 20–22% band',got:'20.8%',verdict:'met'},
      {q:'Q3 FY26',said:'"Discretionary spend to recover in H2"',got:'Retail & comms flat QoQ',verdict:'missed'},
      {q:'Q4 FY26',said:'Large-deal TCV > $3bn per quarter',got:'$4.1bn',verdict:'beat'}],
    bull:['Margin recovery with utilisation headroom','Large-deal pipeline gives multi-year visibility','Net cash balance sheet funds buybacks'],
    bear:['Discretionary-spend recovery repeatedly pushed out','Receivable days creeping up','AI deflation could shrink the renewal pricing base']},
  DEEPAKNTR: { t:'DEEPAKNTR', snapshot:'Phenol/acetone, nitrites and fuel-additive chemicals feeding paints, pharma and agro value chains.',
    segments:[{n:'Phenolics',pct:48},{n:'Advanced intermediates',pct:37},{n:'Other',pct:15}],
    fin:[{k:'Revenue (TTM)',v:'₹8,300 cr'},{k:'EBITDA margin',v:'16.4%'},{k:'PAT',v:'₹830 cr'},{k:'Net debt/EBITDA',v:'1.6×'}],
    trajectory:[{k:'Phenolics volumes',dir:'up',note:'New phenol plant ramping'},{k:'Margins',dir:'down',note:'Compressed ~400 bps from peak on spreads'}],
    quality:[{k:'CFO / PAT',v:'0.71×',flag:true},{k:'Capex / CFO',v:'1.9×',flag:true},{k:'Inventory days',v:'52'}],
    promises:[
      {q:'FY25 call',said:'Phenolics plant commissioned by Q2',got:'Commissioned Q3',verdict:'missed'},
      {q:'FY25 call',said:'EBITDA margin back to 18–20%',got:'16.4%',verdict:'missed'}],
    bull:['Integrated chain lowers input volatility','Operating leverage as new capacity fills'],
    bear:['Cash conversion weak while capex runs ahead of CFO','Guided margin recovery has slipped twice','New ₹2,400 cr expansion adds leverage']},
}
