import { useState } from 'react'
import { ChevronDown, ChevronUp, ArrowRight } from 'lucide-react'
import type { AlertResult } from '../api'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context'

const P_C: Record<string, string> = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308', LOW: '#22c55e' }

function parseIds(s: string | undefined): string[] {
  if (!s) return []; return s.split(';').map(x => x.trim()).filter(Boolean)
}
function fmtEur(x: number): string {
  if (x >= 1e6) return `${(x / 1e6).toFixed(1)}M EUR`
  if (x >= 1e3) return `${(x / 1e3).toFixed(0)}k EUR`
  return `${x} EUR`
}

export default function AlertCard({ alert }: { alert: AlertResult }) {
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const { setFocusedSupplierId } = useApp()
  const c = P_C[alert.Priority?.toUpperCase()] ?? '#9ca3af'
  const ids = parseIds(alert.Affected_Supplier_IDs)

  return (
    <div className="card mb-2 overflow-hidden" style={{ borderLeft: `3px solid ${c}` }}>
      <div className="flex items-center justify-between px-4 py-3 cursor-pointer" onClick={() => setOpen(v => !v)}>
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0" style={{ background: `${c}10`, color: c, border: `1px solid ${c}25` }}>
            {alert.Priority}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-800 truncate">{alert.Headline}</p>
            <p className="text-[11px] text-gray-400">{alert.News_ID} &bull; {alert.Event_Type}</p>
          </div>
        </div>
        <div className="shrink-0 ml-2 text-gray-300">{open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}</div>
      </div>

      {open && (
        <div className="px-4 pb-4 border-t border-gray-50">
          <p className="text-sm mt-3 mb-3 text-gray-600 leading-relaxed">{alert.Reasoning}</p>

          <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
            <div className="p-2 rounded-lg bg-gray-50"><p className="text-gray-400">Risk</p><p className={alert.Is_Risk === 'Y' ? 'text-red-500 font-semibold' : 'text-green-500'}>{alert.Is_Risk === 'Y' ? 'YES' : 'NO'}</p></div>
            <div className="p-2 rounded-lg bg-gray-50"><p className="text-gray-400">Urgent</p><p className={alert.Urgent === 'Y' ? 'text-orange-500 font-semibold' : 'text-green-500'}>{alert.Urgent === 'Y' ? 'YES' : 'NO'}</p></div>
            <div className="p-2 rounded-lg bg-gray-50"><p className="text-gray-400">Spend at Risk</p><p className="text-gray-700 font-medium">{fmtEur(alert.Spend_At_Risk_EUR ?? 0)}</p></div>
            <div className="p-2 rounded-lg bg-gray-50"><p className="text-gray-400">Inventory</p><p className="text-gray-700 font-medium">{alert.Min_Inventory_Days != null ? `${alert.Min_Inventory_Days}d` : 'N/A'}</p></div>
          </div>

          {ids.length > 0 && (
            <div className="mb-3">
              <p className="text-[11px] text-gray-400 mb-1.5">Affected Suppliers</p>
              <div className="flex flex-wrap gap-1.5">{ids.map(s => <span key={s} className="text-[11px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100">{s}</span>)}</div>
            </div>
          )}

          {alert.Products_At_Risk && <p className="mb-3 text-xs text-gray-500"><span className="font-medium text-gray-700">Products at risk:</span> {alert.Products_At_Risk}</p>}

          {alert.Action && (
            <div className="mb-3 p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs">
              <p className="font-semibold text-blue-600 mb-1">Recommended Action</p>
              <p className="text-gray-600">{alert.Action}</p>
            </div>
          )}

          {ids.length > 0 && (
            <button onClick={() => { setFocusedSupplierId(ids[0]); nav('/alternatives') }}
              className="flex items-center gap-1 text-xs font-semibold py-1.5 px-3 rounded-lg text-blue-600 bg-blue-50 border border-blue-100 hover:bg-blue-100 transition-colors">
              View Alternatives <ArrowRight size={11} />
            </button>
          )}
        </div>
      )}
    </div>
  )
}
