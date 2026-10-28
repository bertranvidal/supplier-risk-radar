import { useEffect } from 'react'
import {
  Bell, AlertTriangle, Building2, Globe,
  DollarSign, Shield, Clock, RefreshCw, TrendingUp,
  Play, Download, Loader2,
} from 'lucide-react'
import KPICard from '../components/KPICard'
import {
  AlertsByPriorityChart, SuppliersByCountryChart, TopSuppliersChart,
  CategoryRiskChart, EventTypeChart, ExposureRadar,
} from '../components/Charts'
import { useApp } from '../context'
import { exportExcel } from '../api'

function fmtEur(x: number): string {
  if (x >= 1e6) return `${(x / 1e6).toFixed(1)}M`
  if (x >= 1e3) return `${(x / 1e3).toFixed(0)}k`
  return `${x}`
}

export default function Dashboard() {
  const { kpis, alerts, suppliers, loadData, loading, source, setSource, mode, setMode, analyse, analyzing } = useApp()
  useEffect(() => { loadData() }, [loadData])

  return (
    <div className="p-8">
      {/* Header with controls */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-lg font-bold text-gray-800">Dashboard</h1>
          <p className="text-xs text-gray-400 mt-0.5">Supply chain risk overview{kpis ? ` — ${alerts.length} articles scanned` : ''}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={source} onChange={e => setSource(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-lg bg-gray-50 text-gray-600 border border-gray-200 outline-none">
            <option value="test">Test</option>
            <option value="validation">Validation</option>
          </select>
          <select value={mode} onChange={e => setMode(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-lg bg-gray-50 text-gray-600 border border-gray-200 outline-none">
            <option value="rules">Rules</option>
            <option value="models">Models</option>
          </select>
          <button onClick={analyse} disabled={analyzing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-colors"
            style={{ background: analyzing ? '#9ca3af' : '#3b82f6' }}>
            {analyzing ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {analyzing ? 'Running...' : 'Analyse'}
          </button>
          <button onClick={exportExcel}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-500 bg-gray-50 border border-gray-200 hover:bg-gray-100">
            <Download size={12} /> Export
          </button>
        </div>
      </div>

      {loading && (
        <div className="text-center py-20 text-gray-400">
          <div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-2" />
          <p className="text-sm">Analysing...</p>
        </div>
      )}

      {/* Row 1: Main KPIs */}
      <div className="grid grid-cols-4 gap-3 mb-3">
        <KPICard title="Total Alerts" value={kpis?.total_alerts ?? '—'} subtitle="Risk events detected" icon={Bell} accent="#3b82f6" />
        <KPICard title="Critical" value={kpis?.critical_alerts ?? '—'} subtitle="Immediate action" icon={AlertTriangle} accent="#ef4444" />
        <KPICard title="Suppliers at Risk" value={kpis?.suppliers_at_risk ?? '—'} subtitle={`of ${suppliers.length} total`} icon={Building2} accent="#f97316" />
        <KPICard title="Countries" value={kpis?.countries_affected ?? '—'} subtitle="Geographic spread" icon={Globe} accent="#3b82f6" />
      </div>

      {/* Row 2: Financial KPIs */}
      <div className="grid grid-cols-5 gap-3 mb-5">
        <KPICard title="Spend at Risk" value={kpis ? `${fmtEur(kpis.spend_at_risk)}` : '—'} subtitle={kpis ? `of ${fmtEur(kpis.total_spend)} EUR total` : ''} icon={DollarSign} accent="#ef4444" />
        <KPICard title="Single Source" value={kpis ? `${kpis.single_source_pct}%` : '—'} subtitle="Without backup" icon={Shield} accent="#f97316" />
        <KPICard title="Alt. Coverage" value={kpis ? `${kpis.alt_coverage_pct}%` : '—'} subtitle="Have alternate" icon={RefreshCw} accent="#22c55e" />
        <KPICard title="Stockout Risk" value={kpis?.stockout_countdown != null ? `${kpis.stockout_countdown}d` : '—'} subtitle="Min inventory days" icon={Clock} accent="#eab308" />
        <KPICard title="Urgent" value={kpis?.urgent_count ?? '—'} subtitle="Immediate response" icon={TrendingUp} accent="#f97316" />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <AlertsByPriorityChart alerts={alerts} />
        <SuppliersByCountryChart alerts={alerts} suppliers={suppliers} />
        <TopSuppliersChart alerts={alerts} suppliers={suppliers} />
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <CategoryRiskChart kpis={kpis} />
        <EventTypeChart kpis={kpis} />
        <ExposureRadar kpis={kpis} suppliers={suppliers} />
      </div>

      {/* Most Exposed */}
      {kpis?.most_exposed_supplier?.name && (
        <div className="card px-5 py-4 flex items-center justify-between">
          <div>
            <p className="text-[11px] text-gray-400 uppercase tracking-wider font-medium">Most Exposed Supplier</p>
            <p className="text-base font-bold text-gray-800 mt-1">{kpis.most_exposed_supplier.name}</p>
            <p className="text-xs text-gray-400">{kpis.most_exposed_supplier.country}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-red-500">{kpis.most_exposed_supplier.alert_count}</p>
            <p className="text-[11px] text-gray-400">active alerts</p>
          </div>
        </div>
      )}
    </div>
  )
}
