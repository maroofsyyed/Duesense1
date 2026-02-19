-- DueSense Schema Migration: Add missing scoring columns & expand enrichment types
-- Run this in the Supabase SQL Editor

-- ============================================================
-- 1. Add missing columns to investment_scores
-- ============================================================

ALTER TABLE investment_scores
  ADD COLUMN IF NOT EXISTS linkedin_score NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS funding_quality_score NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS web_growth_score NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS social_presence_score NUMERIC(5,2);


-- ============================================================
-- 2. Expand enrichment_sources.source_type CHECK constraint
--    to allow all enrichment types used by the pipeline
-- ============================================================

-- Drop the old constraint
ALTER TABLE enrichment_sources
  DROP CONSTRAINT IF EXISTS enrichment_sources_source_type_check;

-- Add updated constraint with all enrichment types
ALTER TABLE enrichment_sources
  ADD CONSTRAINT enrichment_sources_source_type_check
  CHECK (source_type IN (
    -- Original types
    'github',
    'news',
    'competitors',
    'market_research',
    'website',
    'website_intelligence',
    'website_due_diligence',
    -- Enrichment engine types
    'linkedin',
    'social_signals',
    'glassdoor',
    'founder_profiles',
    -- New API integrations
    'email_intel',
    'company_validation',
    -- Agent-generated types
    'funding_history',
    'web_traffic',
    'market_sizing',
    'competitive_landscape'
  ));


-- ============================================================
-- 3. Expand companies.status CHECK to include 'scored'
-- ============================================================

ALTER TABLE companies
  DROP CONSTRAINT IF EXISTS companies_status_check;

ALTER TABLE companies
  ADD CONSTRAINT companies_status_check
  CHECK (status IN (
    'processing', 'extracting', 'enriching', 'scoring',
    'generating_memo', 'completed', 'failed', 'scored', 'complete'
  ));


-- ============================================================
-- 4. Verify the changes
-- ============================================================

-- Check investment_scores columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'investment_scores'
ORDER BY ordinal_position;
