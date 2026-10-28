import { useEffect, useState } from 'react'
import { Search, Filter, Bell } from 'lucide-react'
import AlertCard from '../components/AlertCard'
import { useApp } from '../context'

const PRIORITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
const P_COLORS: Record<string, string> = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e' }

export default function Alerts() {
  const { alerts, loadData } = useApp()
  const [search, setSearch] = useState('')
  const [sel, setSel] = useState<string[]>([])

  useEffect(() => { loadData() }, [loadData])

  const toggle = (p: string) => setSel(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p])

  const filtered = alerts.filter(a => {
    const mp = sel.length === 0 || sel.includes(a.Priority?.toUpperCase())
    const ms = !search || a.Headline?.toLowerCase().includes(search.toLowerCase()) || a.Event_Type?.toLowerCase().includes(search.toLowerCase())
    return mp && ms
  })

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-gray-800">Alerts</h1>
        <p className="text-xs text-gray-400 mt-0.5">{filtered.length} alert{filtered.length !== 1 ? 's' : ''} matching filters</p>
      </div>

      <div className="card p-4 mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" placeholder="Search alerts..." value={search} onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-gray-50 text-gray-700 border border-gray-200 outline-none focus:border-blue-300" />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={13} className="text-gray-400" />
          {PRIORITIES.map(p => (
            <button key={p} onClick={() => toggle(p)}
              className="text-[11px] px-2 py-1 rounded-full font-semibold transition-colors"
              style={{
                color: P_COLORS[p],
                background: sel.includes(p) ? `${P_COLORS[p]}12` : '#f9fafb',
                border: `1px solid ${sel.includes(p) ? P_COLORS[p] + '40' : '#e5e7eb'}`,
              }}>{p}</button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-20 text-gray-300">
          <Bell size={36} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">No alerts found.</p>
        </div>
      ) : filtered.map((a, i) => <AlertCard key={a.News_ID ?? i} alert={a} />)}
    </div>
  )
}
