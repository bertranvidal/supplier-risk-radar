import type { LucideIcon } from 'lucide-react'

interface Props {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  accent?: string
}

export default function KPICard({ title, value, subtitle, icon: Icon, accent = '#3b82f6' }: Props) {
  return (
    <div className="card px-5 py-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={15} style={{ color: accent }} />
        <span className="text-xs font-medium text-gray-400">{title}</span>
      </div>
      <p className="text-[22px] font-bold text-gray-800">{value}</p>
      {subtitle && <p className="text-[11px] text-gray-400 mt-0.5">{subtitle}</p>}
    </div>
  )
}
