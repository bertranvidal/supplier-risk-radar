-- Esquema de tablas para Supabase

CREATE TABLE IF NOT EXISTS scraped_news (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT,
    source TEXT,
    published_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT now(),
    title_hash TEXT UNIQUE NOT NULL,
    is_labeled BOOLEAN DEFAULT FALSE,
    is_risk BOOLEAN,
    urgent BOOLEAN,
    event_type TEXT,
    affected_supplier_ids TEXT,
    predicted_risk REAL,
    predicted_urgent REAL,
    predicted_event_type TEXT,
    predicted_supplier_ids TEXT,
    confidence REAL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scraped_news_hash ON scraped_news (title_hash);
CREATE INDEX IF NOT EXISTS idx_scraped_news_scraped ON scraped_news (scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_news_labeled ON scraped_news (is_labeled);

CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    supplier_id TEXT UNIQUE NOT NULL,
    supplier_name TEXT NOT NULL,
    category TEXT,
    material_supplied TEXT,
    country TEXT,
    city TEXT,
    annual_spend_eur REAL,
    share_of_category_spend REAL,
    single_source TEXT,
    approved_alternate_id TEXT,
    lead_time_days INTEGER,
    inventory_cover_days INTEGER,
    criticality TEXT,
    quality_score REAL
);

CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    material_id TEXT UNIQUE NOT NULL,
    material TEXT,
    primary_supplier_id TEXT,
    alternate_supplier_id TEXT,
    alternate_supplier_name TEXT,
    used_in_products TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id BIGSERIAL PRIMARY KEY,
    news_id TEXT,
    scraped_news_id BIGINT REFERENCES scraped_news(id),
    headline TEXT,
    is_risk TEXT,
    urgent TEXT,
    affected_supplier_ids TEXT,
    event_type TEXT,
    supply_impact TEXT,
    duration TEXT,
    confidence TEXT,
    reasoning TEXT,
    spend_at_risk_eur REAL,
    priority TEXT,
    action TEXT,
    analysis_mode TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_results_analyzed ON analysis_results (analyzed_at DESC);
