const BASE = '/api'

export interface Supplier {
  Supplier_ID: string
  Supplier_Name: string
  Category: string
  Material_Supplied: string
  Country: string
  City: string
  Annual_Spend_EUR: number
  'Share_of_Category_Spend_%': number
  Single_Source: string
  Approved_Alternate_ID: string | null
  Lead_Time_Days: number
  Inventory_Cover_Days: number
  Criticality: string
  Quality_Score: number
}

export interface KPIs {
  total_alerts: number
  critical_alerts: number
  suppliers_at_risk: number
  countries_affected: number
  most_exposed_supplier: { id: string; name: string; country: string; alert_count: number }
  spend_at_risk: number
  total_spend: number
  single_source_pct: number
  alt_coverage_pct: number
  stockout_countdown: number | null
  category_risk: Record<string, number>
  event_counts: Record<string, number>
  urgent_count: number
}

export interface AlertResult {
  News_ID: string
  Headline: string
  Is_Risk: string
  Urgent: string
  Affected_Supplier_IDs: string
  Event_Type: string
  Supply_Impact: string
  Duration: string
  Confidence: string
  Reasoning: string
  Spend_At_Risk_EUR: number
  Duration_Days: number | null
  Min_Inventory_Days: number | null
  Stockout_Risk: string
  Single_Source_Affected: string
  Alternates: string
  Products_At_Risk: string
  Priority: string
  Action: string
}

export interface Alternative {
  material_id: string
  material: string
  alternate_supplier_id: string | null
  alternate_supplier_name: string
  alternate_supplier_details: Supplier | null
}

export async function fetchSuppliers(): Promise<Supplier[]> {
  const r = await fetch(`${BASE}/suppliers`)
  return r.json()
}

export async function fetchMaterials(): Promise<Record<string, unknown>[]> {
  const r = await fetch(`${BASE}/materials`)
  return r.json()
}

export async function fetchKPIs(): Promise<KPIs> {
  const r = await fetch(`${BASE}/kpis`)
  return r.json()
}

export async function fetchResults(): Promise<AlertResult[]> {
  const r = await fetch(`${BASE}/results`)
  return r.json()
}

export async function runAnalysis(source: string, mode: string): Promise<AlertResult[]> {
  const r = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, mode }),
  })
  return r.json()
}

export async function fetchAlternatives(supplierId: string): Promise<Alternative[]> {
  const r = await fetch(`${BASE}/alternatives/${supplierId}`)
  return r.json()
}

export function exportExcel() {
  window.open(`${BASE}/export`, '_blank')
}
