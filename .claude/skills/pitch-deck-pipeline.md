# Skill: Pitch Deck Pipeline (End-to-End)

## Overview

The core product flow: any combination of inputs → 300+ data points → 100-point score → 13-section memo.
Target: 10–15 minutes end-to-end, 1000+ deals/year throughput.

## Accepted Inputs (Any Combination)

| Input | Form Field | Processing |
|-------|-----------|-----------|
| PDF/PPTX deck | `file` (UploadFile) | OCR: pdfplumber → pypdf → gpt-4o vision |
| Company website | `company_website` (str) | 25-page deep crawl |
| Founder LinkedIn | `linkedin_url` (str) | SerpAPI scrape |
| Raw pasted text | `raw_text` (str) | Direct to LLM structuring |
| Company name | `company_name` (str) | Override if no deck |

At least one of: file, website, or text is required.

## Pipeline Stages

### Stage 1: Extraction (parallel)
- PDF/PPTX → OCR pipeline (`services/ocr_processor.py`)
- Website → 25-page crawl (`services/website_due_diligence.py`)
- LinkedIn → SerpAPI parse
- Raw text → direct to LLM structuring (`services/deck_processor.py`)
- All merged into `extracted{}` dict

### Stage 2: Enrichment (13 sources, all parallel)
- GitHub, HackerNews, Reddit, Wayback Machine
- Product Hunt, App Stores, News API
- Crunchbase, WHOIS, Open Corporates
- SEC EDGAR, Glassdoor, Competitors
- Uses `asyncio.gather()` with `_safe()` wrappers — one failure never kills pipeline

### Stage 3: AI Scoring (8+ agents, all parallel via Z.ai gpt-4o)
- Founder Quality /30 (4 sub-scores)
- Market Opportunity /20 (4 sub-scores)
- Technical Moat /20 (4 sub-scores)
- Traction /20 (4 sub-scores)
- Business Model /10 (3 sub-scores)
- Website DD /10* (supplemental)
- Website Intel /10* (supplemental)
- Competitive Intelligence (matrix, no numeric score in composite)
- Market Timing (advisory)

### Stage 4: Synthesis
- 100-point composite score → Tier classification
- Bull / Base / Bear thesis generation
- Comparable companies identification
- Expected return estimate

### Stage 5: Output Generation (parallel)
- 13-section investment memo (5–7 pages, 3,500–5,000 words)
- IC PPTX deck (10–15 slides)
- JSON export for CRM
- Dashboard update

## Status Progression

```
processing → extracting → enriching → scoring → generating_memo → completed / failed
```

Both `companies` and `pitch_decks` tables updated at each stage.

## Tier Classification

| Tier | Score | Action |
|------|-------|--------|
| TIER_1 | ≥ 85 | Term sheet immediately |
| TIER_2 | 70–84 | Deeper diligence |
| TIER_3 | 55–69 | Monitor 6 months |
| PASS | < 55 | Pass |

## API Endpoints

```bash
# Upload (multi-input)
curl -X POST \
  -H "X-API-Key: KEY" \
  -F "file=@pitch.pdf" \
  -F "company_website=https://startup.com" \
  -F "linkedin_url=https://linkedin.com/in/founder" \
  https://BACKEND/api/v1/ingestion/upload

# Check status
curl -H "X-API-Key: KEY" https://BACKEND/api/v1/ingestion/status/{deck_id}

# View results
curl -H "X-API-Key: KEY" https://BACKEND/api/v1/deals/{company_id}
```

## Debugging

- Check `/health` for LLM and DB status
- Server logs: `logger.info(f"[{company_id}] Stage X/5: ...")`
- Verify Z_API_KEY is valid and has quota
- Check `MAX_FILE_SIZE_MB` if upload fails
- OCR failures: ensure `poppler-utils` in Dockerfile
