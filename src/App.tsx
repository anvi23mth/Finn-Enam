import { useState } from 'react'
import Push from './screens/Push'
import Pull from './screens/Pull'
import Network from './screens/Network'
type Tab = 'push'|'pull'|'network'
export default function App() {
  const [tab, setTab] = useState<Tab>('push')
  const [ticker, setTicker] = useState('INFY')
  const open = (t: string) => { setTicker(t); setTab('pull') }
  return (
    <div className="app">
      <header><b>FINN</b><span className="demo">demo data</span></header>
      <main>
        {tab === 'push' && <Push openCompany={open} />}
        {tab === 'pull' && <Pull ticker={ticker} setTicker={setTicker} />}
        {tab === 'network' && <Network openCompany={open} />}
      </main>
      <nav>{(['push','pull','network'] as Tab[]).map(t => <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t === 'push' ? 'Today' : t === 'pull' ? 'Research' : 'Network'}</button>)}</nav>
    </div>
  )
}
