import { useEffect, useState } from 'react'
import { Building2, X } from 'lucide-react'
import type { Supplier } from '../api'
import { useApp } from '../context'

export default function Suppliers() {
  const { suppliers, alerts, loadData } = useApp()
  const [selected, setSelected] = useState<Supplier | null>(null)
  useEffect(() => { loadData() }, [loadData])

  const atRiskIds = new Set(alerts.flatMap(a => (a.Affected_Supplier_IDs ?? '').split(';').map(x => x.trim()).filter(Boolean)))
  const isAtRisk = (s: Supplier) => atRiskIds.has(s.Supplier_ID) || atRiskIds.has(s.Supplier_Name)

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-gray-800">Suppliers</h1>
        <p className="text-xs text-gray-400 mt-0.5">{suppliers.length} suppliers in database</p>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              {['ID', 'Name', 'Country', 'Material', 'Spend', 'Single Src', 'Criticality', 'Inv.', 'Status'].map(h => (
                <th key={h} className="text-left px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {suppliers.map(s => {
              const risk = isAtRisk(s)
              return (
                <tr key={s.Supplier_ID} onClick={() => setSelected(s)} className="cursor-pointer hover:bg-blue-50/30 transition-colors border-b border-gray-50">
                  <td className="px-3 py-2.5 text-gray-400 text-xs">{s.Supplier_ID}</td>
                  <td className="px-3 py-2.5 font-medium text-gray-800 text-xs">{s.Supplier_Name}</td>
                  <td className="px-3 py-2.5 text-gray-500 text-xs">{s.Country}</td>
                  <td className="px-3 py-2.5 text-gray-500 text-xs max-w-28 truncate">{s.Material_Supplied}</td>
                  <td className="px-3 py-2.5 text-gray-500 text-xs">{(s.Annual_Spend_EUR / 1e6).toFixed(1)}M</td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${s.Single_Source === 'Yes' ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-600'}`}>{s.Single_Source}</span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${s.Criticality === 'Critical' ? 'bg-red-50 text-red-500' : s.Criticality === 'High' ? 'bg-orange-50 text-orange-500' : 'bg-gray-50 text-gray-400'}`}>{s.Criticality}</span>
                  </td>
                  <td className={`px-3 py-2.5 text-xs ${s.Inventory_Cover_Days < 30 ? 'text-orange-500 font-medium' : 'text-gray-500'}`}>{s.Inventory_Cover_Days}d</td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${risk ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-600'}`}>{risk ? 'AT RISK' : 'OK'}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/10" onClick={() => setSelected(null)}>
          <div className="w-80 h-full overflow-y-auto p-5 bg-white border-l border-gray-200 shadow-lg" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Building2 size={16} className="text-blue-500" />
                <div>
                  <p className="font-semibold text-gray-800 text-sm">{selected.Supplier_Name}</p>
                  <p className="text-[11px] text-gray-400">{selected.Supplier_ID}</p>
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
            </div>
            {[
              ['Category', selected.Category],
              ['Material', selected.Material_Supplied],
              ['Country', `${selected.Country}, ${selected.City}`],
              ['Annual Spend', `${(selected.Annual_Spend_EUR / 1e6).toFixed(1)}M EUR`],
              ['Single Source', selected.Single_Source],
              ['Alternate', selected.Approved_Alternate_ID ?? 'None'],
              ['Inventory', `${selected.Inventory_Cover_Days} days`],
              ['Criticality', selected.Criticality],
              ['Quality Score', selected.Quality_Score],
            ].map(([l, v]) => (
              <div key={l as string} className="flex justify-between py-2.5 border-b border-gray-50 text-xs">
                <span className="text-gray-400">{l}</span>
                <span className="font-medium text-gray-700">{v ?? '—'}</span>
              </div>
            ))}
            <div className={`mt-4 p-3 rounded-lg text-sm font-medium ${isAtRisk(selected) ? 'bg-red-50 text-red-500' : 'bg-green-50 text-green-600'}`}>
              {isAtRisk(selected) ? 'AT RISK — active alerts' : 'No active alerts'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
