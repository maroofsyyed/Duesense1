-- ================================================================
-- DueSense v2.0 Schema Additions
-- Run in Supabase SQL Editor to upgrade from v1.x to v2.0
-- ================================================================

-- 1. New columns for companies table
ALTER TABLE companies ADD COLUMN IF NOT EXISTS employee_count INTEGER;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS total_funding_usd BIGINT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_funding_date TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_funding_round TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS monthly_web_visits INTEGER;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS linkedin_followers INTEGER;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS social_presence_score NUMERIC(5,2);

-- 2. New columns for founders table
ALTER TABLE founders ADD COLUMN IF NOT EXISTS linkedin_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE founders ADD COLUMN IF NOT EXISTS prior_exits BOOLEAN DEFAULT FALSE;
ALTER TABLE founders ADD COLUMN IF NOT EXISTS education_top_tier BOOLEAN DEFAULT FALSE;
ALTER TABLE founders ADD COLUMN IF NOT EXISTS previous_companies_enriched JSONB;
ALTER TABLE founders ADD COLUMN IF NOT EXISTS total_experience_years INTEGER;

-- 3. New columns for investment_scores table
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS linkedin_score NUMERIC(5,2);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS funding_quality_score NUMERIC(5,2);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS web_growth_score NUMERIC(5,2);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS social_presence_score NUMERIC(5,2);

-- 4. Update enrichment_sources CHECK constraint (v2.0 source types)
ALTER TABLE enrichment_sources DROP CONSTRAINT IF EXISTS enrichment_sources_source_type_check;
ALTER TABLE enrichment_sources ADD CONSTRAINT enrichment_sources_source_type_check
  CHECK (source_type IN (
    'github', 'news', 'competitors', 'market_research', 'website',
    'website_intelligence', 'website_due_diligence',
    'linkedin_enrichment', 'funding_history', 'web_traffic',
    'social_signals', 'market_analysis', 'gtm_analysis',
    'competitive_landscape', 'milestones', 'kruncher_insights',
    'glassdoor', 'founder_profiles', 'enrichlayer'
  ));

-- 5. Update companies status CHECK (add generating_insights)
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_status_check;
ALTER TABLE companies ADD CONSTRAINT companies_status_check
  CHECK (status IN (
    'processing', 'extracting', 'enriching', 'analyzing', 'scoring',
    'generating_memo', 'generating_insights', 'completed', 'failed'
  ));

-- 6. New table: kruncher_insights
CREATE TABLE IF NOT EXISTS kruncher_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID UNIQUE NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  strengths JSONB DEFAULT '[]',
  risks JSONB DEFAULT '[]',
  investment_questions JSONB DEFAULT '[]',
  ice_breakers JSONB DEFAULT '[]',
  confidence_level TEXT,
  data_completeness_score NUMERIC(5,2),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. New table: pipeline_events (for observability)
CREATE TABLE IF NOT EXISTS pipeline_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  stage INTEGER,
  status TEXT CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
  duration_ms INTEGER,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Indexes
CREATE INDEX IF NOT EXISTS idx_kruncher_company ON kruncher_insights(company_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_company ON pipeline_events(company_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_agent ON pipeline_events(agent_name);
