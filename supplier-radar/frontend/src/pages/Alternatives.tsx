import { useEffect, useState } from 'react'
import { ArrowRight, AlertCircle } from 'lucide-react'
import { fetchAlternatives } from '../api'
import type { Supplier, Alternative } from '../api'
import { useApp } from '../context'

function Card({ supplier, variant }: { supplier: Supplier; variant: 'risk' | 'safe' }) {
  const r = variant === 'risk'
  return (
    <div className={`p-4 rounded-lg flex-1 border ${r ? 'border-red-200 bg-red-50/30' : 'border-green-200 bg-green-50/30'}`}>
      <p className={`text-[10px] font-semibold mb-1 ${r ? 'text-red-500' : 'text-green-600'}`}>{r ? 'AT RISK' : 'ALTERNATE'}</p>
      <p className="font-semibold text-gray-800 text-sm">{supplier.Supplier_Name}</p>
      <p className="text-[11px] text-gray-400 mb-2">{supplier.Country}, {supplier.City}</p>
      <div className="space-y-1 text-[11px]">
        <div className="flex justify-between"><span className="text-gray-400">Material</span><span className="text-gray-600 max-w-28 truncate text-right">{supplier.Material_Supplied}</span></div>
        <div className="flex justify-between"><span className="text-gray-400">Quality</span><span className="text-gray-600">{supplier.Quality_Score}</span></div>
        <div className="flex justify-between"><span className="text-gray-400">Inventory</span><span className={supplier.Inventory_Cover_Days < 30 ? 'text-orange-500' : 'text-gray-600'}>{supplier.Inventory_Cover_Days}d</span></div>
      </div>
    </div>
  )
}

function AltRow({ supplier }: { supplier: Supplier }) {
  const [alts, setAlts] = useState<Alternative[]>([])
  const [loading, setLoading] = useState(false)
  useEffect(() => { setLoading(true); fetchAlternatives(supplier.Supplier_ID).then(setAlts).catch(() => {}).finally(() => setLoading(false)) }, [supplier.Supplier_ID])
  if (loading) return <div className="card p-4 mb-3 animate-pulse h-24" />
  const wd = alts.filter(a => a.alternate_supplier_id && a.alternate_supplier_details)
  if (!wd.length) return null

  return (
    <div className="card p-4 mb-3">
      <p className="text-[11px] font-medium text-gray-400 mb-3">Materials: {alts.map(a => a.material).join(', ')}</p>
      <div className="flex items-center gap-3">
        <Card supplier={supplier} variant="risk" />
        <ArrowRight size={18} className="shrink-0 text-blue-400" />
        <div className="flex-1 flex gap-2">{wd.slice(0, 2).map(a => <Card key={a.alternate_supplier_id} supplier={a.alternate_supplier_details as Supplier} variant="safe" />)}</div>
      </div>
    </div>
  )
}

export default function Alternatives() {
  const { suppliers, alerts, loadData, focusedSupplierId } = useApp()
  useEffect(() => { loadData() }, [loadData])

  const ids = new Set(alerts.flatMap(a => (a.Affected_Supplier_IDs ?? '').split(';').map(x => x.trim()).filter(Boolean)))
  const atRisk = suppliers.filter(s => ids.has(s.Supplier_ID) && s.Approved_Alternate_ID)
  const focused = focusedSupplierId ? suppliers.filter(s => s.Supplier_ID === focusedSupplierId) : null
  const display = focused?.length ? focused : atRisk

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-lg font-bold text-gray-800">Alternatives</h1>
        <p className="text-xs text-gray-400 mt-0.5">{display.length} at-risk supplier{display.length !== 1 ? 's' : ''} with alternates{focused?.length ? ' (filtered)' : ''}</p>
      </div>

      {display.length === 0 ? (
        <div className="text-center py-20 text-gray-300">
          <AlertCircle size={36} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">No at-risk suppliers with alternates.</p>
        </div>
      ) : display.map(s => <AltRow key={s.Supplier_ID} supplier={s} />)}
    </div>
  )
}
