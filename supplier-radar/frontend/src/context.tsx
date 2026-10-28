import React, { createContext, useContext, useState, useCallback } from 'react'
import type { AlertResult, KPIs, Supplier } from './api'
import { fetchKPIs, fetchResults, fetchSuppliers, runAnalysis } from './api'

interface AppState {
  alerts: AlertResult[]
  kpis: KPIs | null
  suppliers: Supplier[]
  loading: boolean
  analyzing: boolean
  source: string
  mode: string
  setSource: (s: string) => void
  setMode: (m: string) => void
  analyse: () => Promise<void>
  loadData: () => Promise<void>
  focusedSupplierId: string | null
  setFocusedSupplierId: (id: string | null) => void
}

const Ctx = createContext<AppState>({} as AppState)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<AlertResult[]>([])
  const [kpis, setKpis] = useState<KPIs | null>(null)
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [source, setSource] = useState('test')
  const [mode, setMode] = useState('rules')
  const [focusedSupplierId, setFocusedSupplierId] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [k, s, r] = await Promise.allSettled([fetchKPIs(), fetchSuppliers(), fetchResults()])
      if (k.status === 'fulfilled') setKpis(k.value)
      if (s.status === 'fulfilled') setSuppliers(s.value)
      if (r.status === 'fulfilled' && Array.isArray(r.value)) setAlerts(r.value)
    } finally {
      setLoading(false)
    }
  }, [])

  const analyse = useCallback(async () => {
    setAnalyzing(true)
    try {
      const results = await runAnalysis(source, mode)
      if (Array.isArray(results)) setAlerts(results)
      const k = await fetchKPIs()
      setKpis(k)
    } finally {
      setAnalyzing(false)
    }
  }, [source, mode])

  return (
    <Ctx.Provider value={{ alerts, kpis, suppliers, loading, analyzing, source, mode, setSource, setMode, analyse, loadData, focusedSupplierId, setFocusedSupplierId }}>
      {children}
    </Ctx.Provider>
  )
}

export function useApp() {
  return useContext(Ctx)
}
