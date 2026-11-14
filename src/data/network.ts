import type { Person } from './types'
// SYNTHETIC profiles. In production: investor-consented CRM/email/calendar import + licensed profile API.
export const network: Person[] = [
  { id:'p1', name:'Meera Iyer', role:'Partner, Aster Capital', company:'Aster Capital', school:'IIT Kanpur',
    past:[{company:'Infosys',role:'VP Finance',yrs:'2012–2018'},{company:'Tata Consultancy',role:'Finance Controller',yrs:'2008–2012'}], strength:5, lastTalkDays:14, knows:'Deep on IT-services margins and deal pricing.', themes:['IT services','offshoring'] },
  { id:'p2', name:'Rohan Malhotra', role:'CFO, Nimbus Agro', company:'Nimbus Agro', school:'IIM Ahmedabad',
    past:[{company:'Tata Motors',role:'Head Treasury',yrs:'2015–2020'},{company:'Cholamandalam Fin',role:'AVP Credit',yrs:'2011–2015'}], strength:4, lastTalkDays:96, knows:'Auto-finance cycles, Tata Motors treasury and EV capex discipline.', themes:['auto','vehicle finance'] },
  { id:'p3', name:'Dr. Anjali Rao', role:'Independent Director (ex-Sun Pharma)', company:'Independent', school:'AIIMS Delhi',
    past:[{company:'Sun Pharma',role:'Head, Regulatory Affairs',yrs:'2010–2019'}], strength:3, lastTalkDays:41, knows:'US FDA inspections, specialty-generics pipeline.', themes:['pharma','FDA'] },
  { id:'p4', name:'Vikram Sethi', role:'MD, Kestrel Specialty', company:'Kestrel Specialty', school:'ICT Mumbai',
    past:[{company:'Deepak Nitrite',role:'Plant Head',yrs:'2009–2017'},{company:'Pidilite',role:'Manager, Supply Chain',yrs:'2005–2009'}], strength:4, lastTalkDays:210, knows:'Phenol/acetone chain, capex-to-revenue lags in specialty chemicals.', themes:['specialty chemicals','capex'] },
  { id:'p5', name:'Sana Qureshi', role:'Principal, Lakeview PE', company:'Lakeview PE', school:'IIT Kanpur',
    past:[{company:'Dixon Technologies',role:'Strategy',yrs:'2016–2019'}], strength:5, lastTalkDays:9, knows:'EMS/PLI economics, customer concentration in electronics manufacturing.', themes:['electronics','PLI'] },
  { id:'p6', name:'Arjun Menon', role:'Former Head of Retail', company:'HDFC Bank (retired)', school:'IIM Calcutta',
    past:[{company:'HDFC Bank',role:'Head, Retail Liabilities',yrs:'2006–2021'}], strength:3, lastTalkDays:150, knows:'Deposit franchise, CASA dynamics post-merger.', themes:['banks','deposits'] },
  { id:'p7', name:'Priya Nambiar', role:'Director, Ledger Advisory', company:'Ledger Advisory', school:'IIM Ahmedabad',
    past:[{company:'Deloitte',role:'Partner, Audit',yrs:'2004–2020'}], strength:4, lastTalkDays:33, knows:'Forensic read of auditor notes, RPTs and contingent liabilities.', themes:['accounting','governance'] },
  { id:'p8', name:'Kabir Anand', role:'Founder, Cable Co.', company:'Cable Co.', school:'IIT Bombay',
    past:[{company:'Polycab',role:'Sales Head, North',yrs:'2011–2018'}], strength:2, lastTalkDays:320, knows:'Copper pass-through, dealer channel inventory.', themes:['electricals','channel'] },
  { id:'p9', name:'Neha Bhatt', role:'VP Network Strategy', company:'Bharti Airtel', school:'IIT Kanpur',
    past:[{company:'Reliance Industries',role:'Strategy (Jio)',yrs:'2015–2020'}], strength:3, lastTalkDays:75, knows:'Telecom tariff repair, 5G capex phasing, Jio vs Airtel ARPU.', themes:['telecom'] },
]
// Public-profile data about people who appear in filings (synthetic).
export const filingPeople: Record<string, { name: string; headline: string; past: { company: string; role: string; yrs: string }[]; school: string; note: string }> = {
  'Sameer Kulkarni': { name:'Sameer Kulkarni', headline:'Incoming CFO, Tata Motors', school:'IIM Ahmedabad',
    past:[{company:'Cholamandalam Fin',role:'Chief Financial Officer',yrs:'2019–2024'},{company:'Mahindra Finance',role:'Head, Treasury',yrs:'2012–2019'}],
    note:'First CFO hire from a lender, not an OEM — worth asking about his view on captive-finance and balance-sheet leverage.' },
}
