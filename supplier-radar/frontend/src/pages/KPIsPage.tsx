import { useEffect } from 'react'
import {
  Bell, AlertTriangle, Building2, Globe,
  DollarSign, Shield, Clock, RefreshCw, TrendingUp, Star,
} from 'lucide-react'
import {
  AlertsByPriorityChart, SuppliersByCountryChart, TopSuppliersChart,
  CategoryRiskChart, EventTypeChart, ExposureRadar,
} from '../components/Charts'
import { useApp } from '../context'

function fmtEur(x: number): string {
  if (x >= 1e6) return `${(x / 1e6).toFixed(1)}M`
  if (x >= 1e3) return `${(x / 1e3).toFixed(0)}k`
  return `${x}`
}

function BigKPI({ title, value, sub, icon: Icon }: { title: string; value: string | number; sub: string; icon: React.ComponentType<{ size: number; className?: string }> }) {
  return (
    <div className="card px-5 py-5">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className="text-blue-500" />
        <p className="text-xs font-medium text-gray-400">{title}</p>
      </div>
      <p className="text-3xl font-bold text-gray-800">{value}</p>
      <p className="text-[11px] text-gray-400 mt-1">{sub}</p>
    </div>
  )
}

export default function KPIsPage() {
  const { kpis, alerts, suppliers, loadData } = useApp()
  useEffect(() => { loadData() }, [loadData])

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-gray-800">Key Performance Indicators</h1>
        <p className="text-xs text-gray-400 mt-0.5">Live risk metrics — Helixa Pharmaceuticals</p>
      </div>

      <div className="grid grid-cols-4 gap-3 mb-3">
        <BigKPI title="Total Alerts" value={kpis?.total_alerts ?? '—'} sub="All risk events" icon={Bell} />
        <BigKPI title="Critical" value={kpis?.critical_alerts ?? '—'} sub="Immediate action" icon={AlertTriangle} />
        <BigKPI title="Suppliers at Risk" value={kpis?.suppliers_at_risk ?? '—'} sub={`Affected of ${suppliers.length}`} icon={Building2} />
        <BigKPI title="Countries" value={kpis?.countries_affected ?? '—'} sub="Geographic spread" icon={Globe} />
      </div>

      <div className="grid grid-cols-5 gap-3 mb-5">
        <BigKPI title="Spend at Risk" value={kpis ? fmtEur(kpis.spend_at_risk) : '—'} sub={kpis ? `of ${fmtEur(kpis.total_spend)} EUR` : ''} icon={DollarSign} />
        <BigKPI title="Single Source" value={kpis ? `${kpis.single_source_pct}%` : '—'} sub="Without backup" icon={Shield} />
        <BigKPI title="Alt. Coverage" value={kpis ? `${kpis.alt_coverage_pct}%` : '—'} sub="Have alternate" icon={RefreshCw} />
        <BigKPI title="Stockout Risk" value={kpis?.stockout_countdown != null ? `${kpis.stockout_countdown}d` : '—'} sub="Min days to stockout" icon={Clock} />
        <BigKPI title="Urgent" value={kpis?.urgent_count ?? '—'} sub="Immediate response" icon={TrendingUp} />
      </div>

      {kpis?.most_exposed_supplier?.name && (
        <div className="card px-5 py-4 flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <Star size={18} className="text-red-400" />
            <div>
              <p className="text-[11px] text-gray-400">Most Exposed Supplier</p>
              <p className="text-base font-bold text-gray-800">{kpis.most_exposed_supplier.name}</p>
              <p className="text-xs text-gray-400">{kpis.most_exposed_supplier.country}</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-4xl font-bold text-red-500">{kpis.most_exposed_supplier.alert_count}</p>
            <p className="text-[11px] text-gray-400">alerts</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 mb-3">
        <AlertsByPriorityChart alerts={alerts} />
        <SuppliersByCountryChart alerts={alerts} suppliers={suppliers} />
        <TopSuppliersChart alerts={alerts} suppliers={suppliers} />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <CategoryRiskChart kpis={kpis} />
        <EventTypeChart kpis={kpis} />
        <ExposureRadar kpis={kpis} suppliers={suppliers} />
      </div>
    </div>
  )
}
