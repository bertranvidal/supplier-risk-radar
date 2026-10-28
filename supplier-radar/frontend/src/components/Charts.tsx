import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import type { AlertResult, Supplier, KPIs } from '../api'

function parseIds(s: string | undefined): string[] {
  if (!s) return []
  return s.split(';').map(x => x.trim()).filter(Boolean)
}

const P_COLORS: Record<string, string> = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e' }

function Tip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm text-xs">
      <p className="text-gray-400">{label}</p>
      <p className="font-semibold text-gray-800">{payload[0].value}</p>
    </div>
  )
}

export function AlertsByPriorityChart({ alerts }: { alerts: AlertResult[] }) {
  const c: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }
  alerts.forEach(a => { const p = a.Priority?.toUpperCase(); if (p && c[p] !== undefined) c[p]++ })
  const data = Object.entries(c).map(([name, value]) => ({ name, value }))

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold text-gray-800">Alerts by Priority</p>
      <p className="text-[11px] text-gray-400 mb-4">Severity distribution</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} layout="vertical" margin={{ left: 5, right: 15 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
          <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={70} />
          <Tooltip content={<Tip />} cursor={{ fill: 'rgba(0,0,0,0.02)' }} />
          <Bar dataKey="value" radius={[0, 5, 5, 0]} barSize={18}>
            {data.map(e => <Cell key={e.name} fill={P_COLORS[e.name] ?? '#9ca3af'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function SuppliersByCountryChart({ alerts, suppliers }: { alerts: AlertResult[]; suppliers: Supplier[] }) {
  const ids = new Set(alerts.flatMap(a => parseIds(a.Affected_Supplier_IDs)))
  const cc: Record<string, number> = {}
  suppliers.filter(s => ids.has(s.Supplier_ID) || ids.has(s.Supplier_Name)).forEach(s => { cc[s.Country] = (cc[s.Country] ?? 0) + 1 })
  const data = Object.entries(cc).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, value]) => ({ name, value }))

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold text-gray-800">Geographic Exposure</p>
      <p className="text-[11px] text-gray-400 mb-4">Suppliers at risk by country</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ left: 0, right: 15, bottom: 25 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 10 }} axisLine={false} tickLine={false} angle={-30} textAnchor="end" />
          <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<Tip />} cursor={{ fill: 'rgba(0,0,0,0.02)' }} />
          <Bar dataKey="value" fill="#60a5fa" radius={[4, 4, 0, 0]} barSize={24} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function TopSuppliersChart({ alerts, suppliers }: { alerts: AlertResult[]; suppliers: Supplier[] }) {
  const ac: Record<string, number> = {}
  alerts.forEach(a => { parseIds(a.Affected_Supplier_IDs).forEach(sid => { ac[sid] = (ac[sid] ?? 0) + 1 }) })
  const data = Object.entries(ac).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([id, value]) => {
    const s = suppliers.find(s => s.Supplier_ID === id || s.Supplier_Name === id)
    return { name: s?.Supplier_Name ?? id, value }
  })

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold text-gray-800">Most Exposed Suppliers</p>
      <p className="text-[11px] text-gray-400 mb-4">Top 5 by alert count</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ left: 0, right: 15, bottom: 35 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 9 }} axisLine={false} tickLine={false} angle={-30} textAnchor="end" />
          <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<Tip />} cursor={{ fill: 'rgba(0,0,0,0.02)' }} />
          <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={24} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function CategoryRiskChart({ kpis }: { kpis: KPIs | null }) {
  if (!kpis?.category_risk) return null
  const data = Object.entries(kpis.category_risk).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name, value }))
  if (!data.length) return null
  const C = ['#3b82f6', '#60a5fa', '#93c5fd', '#f97316', '#ef4444', '#22c55e', '#14b8a6', '#eab308']

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold text-gray-800">Category Risk</p>
      <p className="text-[11px] text-gray-400 mb-3">Spend at risk by category</p>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3} dataKey="value" nameKey="name" stroke="none">
            {data.map((_, i) => <Cell key={i} fill={C[i % C.length]} />)}
          </Pie>
          <Tooltip formatter={(v: number) => [`${(v / 1e6).toFixed(1)}M EUR`]} contentStyle={{ background: '#fff', border: '1px solid #eaedf3', borderRadius: 8, fontSize: 11 }} />
          <Legend wrapperStyle={{ fontSize: 10 }} formatter={(v: string) => <span className="text-gray-600">{v}</span>} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export function EventTypeChart({ kpis }: { kpis: KPIs | null }) {
  if (!kpis?.event_counts) return null
  const data = Object.entries(kpis.event_counts).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name, value]) => ({ name: name.length > 16 ? name.slice(0, 14) + '..' : name, value }))
  if (!data.length) return null

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold text-gray-800">Events by Type</p>
      <p className="text-[11px] text-gray-400 mb-3">Classification breakdown</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ left: 0, right: 15, bottom: 45 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 9 }} axisLine={false} tickLine={false} angle={-35} textAnchor="end" />
          <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<Tip />} cursor={{ fill: 'rgba(0,0,0,0.02)' }} />
          <Bar dataKey="value" fill="#60a5fa" radius={[4, 4, 0, 0]} barSize={22} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ExposureRadar({ kpis, suppliers }: { kpis: KPIs | null; suppliers: Supplier[] }) {
  if (!kpis) return null
  const t = suppliers.length || 1
  const data = [
    { m: 'Single Source', v: kpis.single_source_pct },
    { m: 'No Alternate', v: 100 - kpis.alt_coverage_pct },
    { m: 'Spend Conc.', v: kpis.total_spend > 0 ? Math.min(100, kpis.spend_at_risk / kpis.total_spend * 100) : 0 },
    { m: 'At Risk', v: Math.min(100, kpis.suppliers_at_risk / t * 100) },
    { m: 'Critical', v: kpis.total_alerts > 0 ? Math.min(100, kpis.critical_alerts / kpis.total_alerts * 100) : 0 },
  ]

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold text-gray-800">Risk Exposure</p>
      <p className="text-[11px] text-gray-400 mb-3">Multi-dimensional profile</p>
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart data={data}>
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis dataKey="m" tick={{ fill: '#6b7280', fontSize: 10 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar dataKey="v" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.1} strokeWidth={1.5} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
