# Backend Rules

## Framework

- FastAPI (Python 3.11.9) — do NOT switch frameworks
- ASGI server: `uvicorn`
- Docker deployment to Render

## LLM Provider — Z.AI ONLY

- **Only provider:** Z.ai via `httpx` to `https://api.zukijourney.com/v1`
- **Quality model:** `gpt-4o` (scoring agents, memo, deck structuring, OCR)
- **Bulk model:** `gpt-4o-mini` (enrichment summaries, website pages, news)
- **Auto-downgrade:** gpt-4o → gpt-4o-mini on HTTP 429
- **Singleton:** `from services.llm_provider import llm`

### FORBIDDEN
```python
import groq        # ❌ NEVER
import openai      # ❌ NEVER (use httpx directly)
import huggingface # ❌ NEVER
```

## Database Access

- ALL database access goes through `backend/db.py`
- Import pattern: `import db as database`
- Access tables via: `database.companies_collection()`, etc.
- Never import `supabase` directly in services or API routes
- Lazy initialization with retry logic — respect this pattern

## API Design

- All new endpoints go in `backend/api/v1/`
- Protected endpoints require `from api.v1.auth import verify_api_key`
- API key passed via `X-API-Key` header
- Multi-input upload endpoint at `POST /api/v1/ingestion/upload`

## Pipeline Architecture

Status progression: `processing → extracting → enriching → scoring → generating_memo → completed / failed`

Update **both** tables at every transition:
```python
companies_tbl.update({"id": company_id}, {"status": stage, "updated_at": now})
decks_tbl.update({"id": deck_id}, {"processing_status": stage})
```

## OCR Pipeline (`services/ocr_processor.py`)

Fallback chain: `pdfplumber → pypdf → gpt-4o vision → ValueError`
- Cap at 20 pages for OCR, 60,000 chars total
- Always return text with `--- Page N ---` headers
- Tables as pipe-separated rows

## Scoring Agents (100-point composite)

- All agents run in **parallel** via `asyncio.gather()`
- Founder Quality /30, Market Opp /20, Technical Moat /20, Traction /20, Business Model /10
- Supplemental: Website DD /10, Website Intel /10 (not in composite)
- Tier: ≥85 = Tier 1, 70–84 = Tier 2, 55–69 = Tier 3, <55 = Pass

## Citation Architecture

- Every agent call uses the citation system prompt (see CLAUDE.md §13)
- Every claim must end with `[SOURCE: url/page]`
- Missing data → `"not_mentioned"` — never fabricate

## Coding Patterns

```python
# ✅ Always .get() with defaults on LLM JSON
score = float(result.get("total_score", 10.0))

# ✅ Parallel enrichment — never sequential
results = await asyncio.gather(*[_safe(t) for t in tasks], return_exceptions=True)

# ✅ Cap LLM inputs
deck_text = extracted_text[:12_000]
enrichment_str = json.dumps(enrichment, default=str)[:4_000]

# ✅ Always logger, never print
logger.info(f"[{company_id}] Stage 3/5: Scoring agents starting")

# ❌ Never let one enrichment failure kill the pipeline
# Always use _safe() wrapper
```

## Business Logic

- All services in `backend/services/`
- Key services: `ocr_processor.py`, `deck_processor.py`, `enrichment_engine.py`, `agents.py`, `scorer.py`, `memo_generator.py`, `report_exporter.py`, `rag_extractor.py`
- 13-section investment memo generated in parallel
- Export formats: PDF (reportlab), PPTX (python-pptx), DOCX (python-docx), JSON
