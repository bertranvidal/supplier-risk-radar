import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div style={{ marginLeft: 192 }} className="min-h-screen overflow-x-hidden">
        <Outlet />
      </div>
    </div>
  )
}
