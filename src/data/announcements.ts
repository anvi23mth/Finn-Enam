import type { Announcement } from './types'
// Mock feed shaped like the NSE corporate-announcements API. Production: poll NSE/BSE every few minutes and classify.
export const announcements: Announcement[] = [
  { id:'a1', t:'TMPV', hoursAgo:2, cat:'management_change', title:'Appointment of Chief Financial Officer', person:'Sameer Kulkarni', summary:'Board approves Sameer Kulkarni as CFO effective 1 Dec; current CFO moves to advisory role.' },
  { id:'a2', t:'INFY', hoursAgo:5, cat:'results', title:'Unaudited Consolidated Results for the quarter ended 30 Sep 2026',
    results:[{k:'Revenue',cur:41890,qoq:2.9,yoy:7.1},{k:'EBITDA',cur:9320,qoq:3.4,yoy:8.9},{k:'PBT',cur:8610,qoq:1.8,yoy:9.5},{k:'PAT',cur:6470,qoq:1.2,yoy:8.2}] },
  { id:'a3', t:'DEEPAKNTR', hoursAgo:7, cat:'capex', title:'Board approves ₹2,400 cr expansion of phenolics complex', summary:'Brownfield capacity addition; commissioning guided for FY28. Funded by internal accruals plus debt.' },
  { id:'a4', t:'DIXON', hoursAgo:9, cat:'litigation', title:'Receipt of show-cause notice from Directorate of Revenue Intelligence', summary:'Customs-classification dispute on imported components; company says no material impact expected.' },
  { id:'a5', t:'SUNPHARMA', hoursAgo:13, cat:'M&A', title:'Acquisition of 100% stake in a US specialty dermatology business', summary:'All-cash deal; closing subject to HSR clearance.' },
  { id:'a6', t:'RELIANCE', hoursAgo:15, cat:'earnings_call', title:'Intimation of analyst/investor conference call' },
  { id:'a7', t:'HDFCBANK', hoursAgo:19, cat:'credit_rating', title:'CRISIL reaffirms AAA/Stable on the bank’s infrastructure bonds' },
  { id:'a8', t:'ITC', hoursAgo:21, cat:'dividend', title:'Interim dividend ₹7.50/share; record date 22 Nov' },
  { id:'a9', t:'POLYCAB', hoursAgo:22, cat:'unclassified', title:'Allotment of equity shares under ESOP scheme' },
  { id:'a10', t:'LT', hoursAgo:28, cat:'press_release', title:'Wins "large" order (₹2,500–5,000 cr) for power transmission in Middle East' },
  { id:'a11', t:'TCS', hoursAgo:30, cat:'unclassified', title:'Compliance certificate under Reg 74(5) of SEBI DP Regulations' },
  { id:'a12', t:'CHOLAFIN', hoursAgo:36, cat:'management_change', title:'Resignation of Chief Financial Officer', summary:'Sameer Kulkarni resigned effective 30 Nov to pursue another opportunity.' , person:'Sameer Kulkarni' },
  { id:'a13', t:'BHARTIARTL', hoursAgo:50, cat:'fund_raise', title:'Raises ₹5,000 cr via non-convertible debentures' },
  { id:'a14', t:'SBIN', hoursAgo:70, cat:'agm_egm', title:'Notice of Extraordinary General Meeting' },
  { id:'a15', t:'TITAN', hoursAgo:100, cat:'investor_meetings', title:'Schedule of meetings with institutional investors' },
]
export const priority: Record<string, { rank: 0|1|2; label: string }> = {
  results:{rank:0,label:'Results'}, 'M&A':{rank:0,label:'M&A'}, management_change:{rank:0,label:'Mgmt change'}, litigation:{rank:0,label:'Litigation'}, fund_raise:{rank:0,label:'Fund raise'}, pledging:{rank:0,label:'Pledging'}, capex:{rank:0,label:'Capex'},
  insider_trading:{rank:1,label:'Insider'}, credit_rating:{rank:1,label:'Rating'}, dividend:{rank:1,label:'Dividend'}, bonus_split:{rank:1,label:'Bonus/split'}, press_release:{rank:1,label:'Press'}, earnings_call:{rank:1,label:'Call'},
  investor_meetings:{rank:2,label:'Meetings'}, postal_ballot:{rank:2,label:'Ballot'}, agm_egm:{rank:2,label:'AGM/EGM'}, unclassified:{rank:2,label:'Routine'},
}
