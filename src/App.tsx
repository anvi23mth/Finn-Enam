import { useState } from 'react'
import Push from './screens/Push'
import Pull from './screens/Pull'
import Network from './screens/Network'
import type { NetView } from './lib/network'
type Tab = 'push'|'pull'|'network'
export default function App() {
  const [tab, setTab] = useState<Tab>('push')
  const [ticker, setTicker] = useState('INFY')
  const [net, setNet] = useState<{ view: NetView; arg?: string }>({ view: 'call' })
  const openNet = (view: NetView, arg?: string) => { setNet({ view, arg }); setTab('network') }
  const open = (t: string) => { setTicker(t); setTab('pull') }
  return (
    <div className="app">
      <header><b>FINN</b><span className="demo">demo data</span></header>
      <main>
        {tab === 'push' && <Push openCompany={open} openNet={openNet} />}
        {tab === 'pull' && <Pull ticker={ticker} setTicker={setTicker} openNet={openNet} />}
        {tab === 'network' && <Network openCompany={open} nav={net} setNav={setNet} />}
      </main>
      <nav>{(['push','pull','network'] as Tab[]).map(t => <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t === 'push' ? 'Today' : t === 'pull' ? 'Research' : 'Network'}</button>)}</nav>
    </div>
  )
}
