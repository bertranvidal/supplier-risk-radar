import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppProvider } from './context'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Alerts from './pages/Alerts'
import Suppliers from './pages/Suppliers'
import Alternatives from './pages/Alternatives'
import KPIsPage from './pages/KPIsPage'

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="suppliers" element={<Suppliers />} />
            <Route path="alternatives" element={<Alternatives />} />
            <Route path="kpis" element={<KPIsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  )
}
