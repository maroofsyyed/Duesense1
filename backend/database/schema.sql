-- DueSense Production Schema for Supabase PostgreSQL

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Companies table
CREATE TABLE companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  tagline TEXT,
  website TEXT,
  website_source TEXT,
  stage TEXT CHECK (stage IN ('pre-seed', 'seed', 'series-a', 'series-b', 'series-c+')),
  founded_year TEXT,
  hq_location TEXT,
  industry TEXT,
  status TEXT DEFAULT 'processing' CHECK (status IN ('processing', 'extracting', 'enriching', 'scoring', 'generating_memo', 'completed', 'failed')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pitch decks table
CREATE TABLE pitch_decks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  file_path TEXT,
  file_name TEXT NOT NULL,
  file_size INTEGER,
  website_source TEXT,
  processing_status TEXT DEFAULT 'uploading' CHECK (processing_status IN ('uploading', 'extracting', 'extracted', 'enriching', 'scoring', 'generating_memo', 'completed', 'failed')),
  extracted_data JSONB,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Founders table
CREATE TABLE founders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  role TEXT,
  linkedin_url TEXT,
  github_url TEXT,
  previous_companies TEXT[],
  years_in_industry INTEGER,
  education TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enrichment sources table
CREATE TABLE enrichment_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL CHECK (source_type IN ('github', 'news', 'competitors', 'market_research', 'website', 'website_intelligence', 'website_due_diligence')),
  source_url TEXT,
  data JSONB NOT NULL DEFAULT '{}'::jsonb,
  citations JSONB DEFAULT '[]'::jsonb,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  is_valid BOOLEAN DEFAULT TRUE
);

-- Competitors table
CREATE TABLE competitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  name TEXT,
  url TEXT,
  description TEXT,
  source_query TEXT,
  discovered_at TIMESTAMPTZ DEFAULT NOW()
);

-- Investment scores table
CREATE TABLE investment_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID UNIQUE NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  total_score NUMERIC(5,2) CHECK (total_score >= 0 AND total_score <= 100),
  tier TEXT CHECK (tier IN ('TIER_1', 'TIER_2', 'TIER_3', 'PASS')),
  tier_label TEXT,
  confidence_level TEXT CHECK (confidence_level IN ('HIGH', 'MEDIUM', 'LOW')),
  founder_score NUMERIC(5,2),
  market_score NUMERIC(5,2),
  moat_score NUMERIC(5,2),
  traction_score NUMERIC(5,2),
  model_score NUMERIC(5,2),
  website_score NUMERIC(5,2),
  website_dd_score NUMERIC(5,2),
  scoring_weights JSONB,
  agent_details JSONB,
  recommendation TEXT,
  investment_thesis TEXT,
  top_reasons TEXT[],
  top_risks TEXT[],
  expected_return TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Investment memos table
CREATE TABLE investment_memos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id UUID UNIQUE NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  title TEXT,
  date TEXT,
  sections JSONB,
  score_summary JSONB,
  status TEXT DEFAULT 'completed',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_companies_status ON companies(status);
CREATE INDEX idx_companies_created_at ON companies(created_at DESC);
CREATE INDEX idx_pitch_decks_company ON pitch_decks(company_id);
CREATE INDEX idx_pitch_decks_status ON pitch_decks(processing_status);
CREATE INDEX idx_founders_company ON founders(company_id);
CREATE INDEX idx_enrichment_company_type ON enrichment_sources(company_id, source_type);
CREATE INDEX idx_enrichment_fetched ON enrichment_sources(fetched_at DESC);
CREATE INDEX idx_competitors_company ON competitors(company_id);
CREATE INDEX idx_scores_company ON investment_scores(company_id);
CREATE INDEX idx_scores_tier ON investment_scores(tier);
CREATE INDEX idx_memos_company ON investment_memos(company_id);

-- Update trigger for companies.updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_companies_updated_at
  BEFORE UPDATE ON companies
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pitch_decks_updated_at
  BEFORE UPDATE ON pitch_decks
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
