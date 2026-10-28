import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Bell, Building2, GitCompare, BarChart3 } from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/suppliers', label: 'Suppliers', icon: Building2 },
  { to: '/alternatives', label: 'Alternatives', icon: GitCompare },
  { to: '/kpis', label: 'KPIs', icon: BarChart3 },
]

export default function Sidebar() {
  return (
    <aside
      style={{ width: 192 }}
      className="fixed left-0 top-0 bottom-0 z-40 bg-white border-r border-gray-200 flex flex-col"
    >
      <div className="px-5 py-5 border-b border-gray-100">
        <p className="text-sm font-bold text-gray-800">Supplier Radar</p>
        <p className="text-[11px] text-gray-400">Helixa Pharma</p>
      </div>

      <nav className="flex-1 px-3 py-3 overflow-y-auto">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to} to={to} end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-lg mb-0.5 text-[13px] font-medium transition-colors ${
                isActive ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
              }`
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
