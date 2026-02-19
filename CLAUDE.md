# CLAUDE.md — SenseAI / DueSense VC Deal Intelligence Platform
## Master Agent Memory & Coding Standards

> **READ THIS FIRST — every session, every task.**
> This is the canonical source of truth. Goal: Kruncher-class deal intelligence —
> 300+ data points per company, zero hallucinations, 10–15 minute reports.
> Any file you touch must conform to the patterns here.

---

## 1. PROJECT VISION

**SenseAI / DueSense** is a Kruncher-class VC deal intelligence platform:

- Accepts **any input combination**: PDF pitch deck, PPTX, company website URL, LinkedIn founder URL, raw pasted text — any mix
- **Multi-strategy OCR pipeline**: pdfplumber → pypdf → gpt-4o vision (image-based/scanned PDFs)
- **30+ specialized AI agents** across all scoring dimensions (run in parallel)
- **10+ free enrichment sources**: GitHub, HackerNews, Reddit, Wayback Machine, SEC EDGAR, App Stores, Product Hunt, Crunchbase, WHOIS, Open Corporates, Glassdoor, Competitors
- **Zero-hallucination architecture**: every LLM claim cites a source. Missing data → "not_mentioned". Never guess.
- **5–7 page investment memos** (13 required sections) + IC PPTX deck + JSON for CRM
- **100-point composite scoring** → Tier 1 / Tier 2 / Tier 3 / Pass classification
- Target: **1000+ deals/year** throughput, 10–15 min per company

---

## 2. TECH STACK

```
Backend:   FastAPI + Python 3.11.9  (Docker → Render)
Frontend:  React 19 + Tailwind CSS  (Vercel or same-origin SPA)
Database:  Supabase (PostgreSQL + JSONB columns)
LLM:       Z.ai ONLY — gpt-4o (quality) + gpt-4o-mini (bulk/fast)
OCR:       pdfplumber + pypdf + pdf2image + gpt-4o vision
Scraping:  ScraperAPI / httpx + BeautifulSoup4
Exports:   python-pptx + python-docx + reportlab (PDF)
Hosting:   Render (backend, Docker) + Vercel (frontend)
```

---

## 3. ⚠️ LLM PROVIDER — Z.AI ONLY

```
PRIMARY LLM:   Z_API_KEY  →  gpt-4o          (quality tasks)
FAST/BULK:     Z_API_KEY  →  gpt-4o-mini     (enrichment summaries, website pages)
FALLBACK:      Auto-downgrade gpt-4o → gpt-4o-mini on 429

❌  GROQ_API_KEY    — DISABLED. Too many rate-limit overshots in production.
❌  HUGGINGFACE     — DISABLED. Too slow for pipeline.
❌  Any other provider — Do NOT add without explicit user approval.
```

### Model Assignment by Task

| Task | Model | Rationale |
|------|-------|-----------|
| PDF OCR / chart reading | `gpt-4o` | Best multimodal vision |
| Deck JSON structuring | `gpt-4o` | Superior schema adherence |
| Founder Quality agent | `gpt-4o` | Calibrated scoring |
| Market Opportunity agent | `gpt-4o` | Research synthesis |
| Technical Moat agent | `gpt-4o` | Defensibility reasoning |
| Traction agent | `gpt-4o` | Financial analysis |
| Business Model agent | `gpt-4o` | Unit economics math |
| Competitive Intelligence agent | `gpt-4o` | Nuanced comparison |
| Market Timing agent | `gpt-4o` | Multi-step reasoning |
| Investment memo (full) | `gpt-4o` | Long-form professional quality |
| Bull/Base/Bear thesis | `gpt-4o` | Synthesis |
| HN / Reddit / Wayback summaries | `gpt-4o-mini` | Bulk, low-stakes |
| Website page extractions | `gpt-4o-mini` | 25+ pages, cost-effective |
| News API summaries | `gpt-4o-mini` | Bulk enrichment |

### `services/llm_provider.py` — Complete Implementation

```python
"""
services/llm_provider.py
Z.ai is the ONLY LLM provider.
gpt-4o for quality, gpt-4o-mini for bulk.
Auto-downgrade on 429. 3-attempt retry with exponential backoff.
"""
import os, json, re, asyncio, logging
import httpx

logger = logging.getLogger(__name__)


class LLMProvider:
    ZAI_BASE      = "https://api.zukijourney.com/v1"
    QUALITY_MODEL = "gpt-4o"
    FAST_MODEL    = "gpt-4o-mini"

    def __init__(self):
        self.api_key = os.getenv("Z_API_KEY")
        if not self.api_key:
            raise RuntimeError("Z_API_KEY not set — Z.ai is the only LLM provider.")

    async def generate(self, prompt: str,
                       system: str = "You are a helpful assistant.",
                       max_tokens: int = 1500,
                       temperature: float = 0.1,
                       use_fast: bool = False) -> str:
        model = self.FAST_MODEL if use_fast else self.QUALITY_MODEL
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    r = await client.post(
                        f"{self.ZAI_BASE}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json={"model": model,
                              "messages": [
                                  {"role": "system", "content": system},
                                  {"role": "user",   "content": prompt}],
                              "max_tokens": max_tokens,
                              "temperature": temperature})
                if r.status_code == 429:
                    model = self.FAST_MODEL   # downgrade on rate-limit
                    await asyncio.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except httpx.ReadTimeout:
                logger.warning(f"[LLM] Timeout attempt {attempt+1}")
                if attempt == 2:
                    return "Analysis temporarily unavailable. Please retry."
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"[LLM] Error attempt {attempt+1}: {e}")
                if attempt == 2:
                    return "Analysis temporarily unavailable. Please retry."
                await asyncio.sleep(2 ** attempt)
        return "Analysis temporarily unavailable."

    async def generate_json(self, prompt: str,
                            system: str = "Respond ONLY with valid JSON. No markdown fences.",
                            use_fast: bool = False) -> dict:
        text = await self.generate(prompt, system,
                                   max_tokens=3000, temperature=0.0, use_fast=use_fast)
        return self._parse_json(text)

    async def generate_with_vision(self, prompt: str, image_b64: str,
                                   system: str = "You are a document analyst.") -> str:
        """Send a base64 PNG page to gpt-4o vision. Used by OCR pipeline."""
        payload = {
            "model": self.QUALITY_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": system + "\n\n" + prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{image_b64}"}}
                ]}],
            "max_tokens": 2500
        }
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    r = await client.post(
                        f"{self.ZAI_BASE}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}",
                                 "Content-Type": "application/json"},
                        json=payload)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"[LLM Vision] attempt {attempt+1}: {e}")
                if attempt == 2: return ""
                await asyncio.sleep(2 ** attempt)
        return ""

    def _parse_json(self, text: str) -> dict:
        """Strip markdown fences, extract JSON object, return {} on failure."""
        text = text.strip()
        # Strip ```json ... ``` fences
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                try: return json.loads(m.group())
                except: pass
        logger.warning("[LLM] JSON parse failed — returning {}")
        return {}


# Singleton — import this everywhere
llm = LLMProvider()
```

---

## 4. REPOSITORY STRUCTURE

```
/
├── CLAUDE.md               ← THIS FILE — read every session
├── FREE_APIS.md            ← All free API clients + integration code
├── FRONTEND.md             ← React components + design system
├── BACKEND.md              ← Service patterns + agent implementations
├── ROADMAP.md              ← Prioritized feature plan
│
├── backend/
│   ├── server.py           ← FastAPI app, lifespan, SPA static serve
│   ├── db.py               ← Supabase lazy-init + SupabaseTable wrapper
│   ├── api/v1/
│   │   ├── router.py       ← Mounts all sub-routers at /api/v1
│   │   ├── auth.py         ← X-API-Key header authentication
│   │   ├── health.py       ← /health /live /ready — always 200
│   │   ├── deals.py        ← CRUD + pagination for companies
│   │   ├── ingestion.py    ← Multi-input upload handler
│   │   └── analytics.py   ← Dashboard stats + tier insights
│   │
│   ├── services/
│   │   ├── llm_provider.py          ← Z.ai ONLY (see above)
│   │   ├── ocr_processor.py         ← Multi-strategy PDF/PPTX extraction
│   │   ├── deck_processor.py        ← Calls OCR → LLM structuring → schema
│   │   ├── enrichment_engine.py     ← 13-source parallel orchestrator
│   │   ├── agents.py                ← 8 scoring agents (all in parallel)
│   │   ├── scorer.py                ← Composite score compiler + tier
│   │   ├── memo_generator.py        ← 13-section investment memo
│   │   ├── report_exporter.py       ← PDF / PPTX / DOCX / JSON exports
│   │   ├── rag_extractor.py         ← Citation-enforced fact extraction
│   │   ├── website_due_diligence.py ← 25-page crawl + citation analysis
│   │   └── website_intelligence.py  ← Deep 7-sub-agent crawl synthesis
│   │
│   ├── integrations/
│   │   └── clients.py      ← All API clients (GitHub, HN, Reddit, etc.)
│   ├── database/
│   │   └── schema.sql      ← Full Supabase schema (run once)
│   └── static/             ← React build (served as SPA by FastAPI)
│
└── frontend/src/
    ├── api.js              ← Axios client (same-origin or REACT_APP_BACKEND_URL)
    ├── App.js              ← Router + persistent Sidebar
    ├── components/ui/      ← ScoreRing, TierBadge, StatusBadge, MetricCard
    └── pages/
        ├── Dashboard.js        ← Bento grid: pipeline stats + recent deals
        ├── Upload.js           ← Multi-input: drag file + URL + LinkedIn + text
        ├── Companies.js        ← Table: logo, name, tier badge, score, status
        └── CompanyDetail.js    ← Tabbed: Overview / Intel / Scoring / Memo / Competitors / Export
```

---

## 5. MULTI-INPUT INGESTION (`api/v1/ingestion.py`)

Users can submit **any combination**:

| Input | Field | Notes |
|-------|-------|-------|
| PDF or PPTX deck | `file` (UploadFile) | OCR pipeline runs |
| Company website | `company_website` (Form str) | 25-page deep crawl |
| Founder LinkedIn | `linkedin_url` (Form str) | SerpAPI scrape |
| Raw pasted text | `raw_text` (Form str) | Direct to LLM structuring |
| Company name override | `company_name` (Form str) | If no deck provided |

At least one input is required. The pipeline adapts based on what was provided.

```python
@router.post("/upload")
async def upload_multi_input(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    company_website: Optional[str] = Form(None),
    linkedin_url:    Optional[str] = Form(None),
    raw_text:        Optional[str] = Form(None),
    company_name:    Optional[str] = Form(None),
    api_key: str = Depends(verify_api_key),
):
    if not file and not company_website and not raw_text:
        raise HTTPException(400, "Provide at least one: file, website URL, or text.")

    input_types = []
    if file:            input_types.append("pitch_deck")
    if company_website: input_types.append("website")
    if linkedin_url:    input_types.append("linkedin")
    if raw_text:        input_types.append("raw_text")

    name = company_name or "Processing..."
    now  = datetime.utcnow().isoformat()
    company = companies_tbl.insert({
        "name": name, "status": "processing",
        "website": company_website,
        "linkedin_provided": linkedin_url,
        "raw_text_provided": bool(raw_text),
        "input_types": input_types,
        "created_at": now, "updated_at": now,
    })
    company_id = company["id"]

    file_path, file_ext = None, None
    if file:
        file_ext = file.filename.rsplit(".", 1)[-1].lower()
        if file_ext not in ("pdf", "pptx", "ppt"):
            raise HTTPException(400, "Only PDF and PPTX files supported.")
        content = await file.read()
        file_path = f"/tmp/decks/{uuid.uuid4()}.{file_ext}"
        os.makedirs("/tmp/decks", exist_ok=True)
        open(file_path, "wb").write(content)

    background_tasks.add_task(
        run_full_pipeline,
        company_id, file_path, file_ext,
        company_website, linkedin_url, raw_text
    )
    return {"company_id": company_id, "status": "processing"}
```

---

## 6. FULL PIPELINE FLOW

```
INPUTS: [PDF/PPTX] + [Website URL] + [LinkedIn URL] + [Raw Text]
                              │
              ┌───────────────▼──────────────────┐
              │      STAGE 1: EXTRACTION          │
              │  (parallel where possible)        │
              │  • PDF/PPTX: OCR pipeline         │
              │    pdfplumber → pypdf → gpt-4o    │
              │  • Website: 25-page deep crawl    │
              │  • LinkedIn: SerpAPI + parse      │
              │  • Raw text: direct to LLM        │
              │  → All merged to extracted{}      │
              └───────────────┬──────────────────┘
                              │  status: "enriching"
              ┌───────────────▼──────────────────┐
              │    STAGE 2: ENRICHMENT            │
              │  (all parallel — asyncio.gather)  │
              │  GitHub · HackerNews · Reddit     │
              │  Wayback · ProductHunt · AppStore │
              │  News · Crunchbase · WHOIS        │
              │  OpenCorporates · SEC EDGAR       │
              │  Glassdoor · Competitors          │
              └───────────────┬──────────────────┘
                              │  status: "scoring"
              ┌───────────────▼──────────────────┐
              │    STAGE 3: AI SCORING AGENTS     │
              │  (all parallel — Z.ai gpt-4o)    │
              │  Agent 1: Founder Quality  /30    │
              │  Agent 2: Market Opp.      /20    │
              │  Agent 3: Technical Moat   /20    │
              │  Agent 4: Traction         /20    │
              │  Agent 5: Business Model   /10    │
              │  Agent 6: Website DD       /10*   │
              │  Agent 7: Website Intel    /10*   │
              │  Agent 8: Competitive Intel       │
              │  Agent 9: Market Timing           │
              └───────────────┬──────────────────┘
                              │  status: "generating_memo"
              ┌───────────────▼──────────────────┐
              │    STAGE 4: SYNTHESIS             │
              │  Composite score → Tier           │
              │  Bull / Base / Bear thesis        │
              │  Comparable companies             │
              │  Expected return estimate         │
              └───────────────┬──────────────────┘
                              │
              ┌───────────────▼──────────────────┐
              │    STAGE 5: OUTPUT GENERATION     │
              │  (sections in parallel)           │
              │  • 13-section investment memo     │
              │  • IC PPTX deck (10-15 slides)    │
              │  • JSON export for CRM            │
              │  • Dashboard update               │
              └──────────────────────────────────┘
                              │  status: "completed"

 *Supplemental scores — not counted in 100-pt composite
 Target: 10–15 minutes end-to-end
```

### Status Progression
```
processing → extracting → enriching → scoring → generating_memo → completed / failed
```
Update **both** tables at each transition:
```python
decks_tbl.update({"id": deck_id}, {"processing_status": stage})
companies_tbl.update({"id": company_id}, {"status": stage, "updated_at": now_iso()})
```

---

## 7. SCORING SYSTEM — 100-POINT COMPOSITE

### Agent Weights

| Agent | Max Score | Sub-criteria |
|-------|-----------|-------------|
| **Founder Quality** | **30** | Domain expertise (8) + Track record (7) + Technical credibility (8) + Team completeness (7) |
| **Market Opportunity** | **20** | TAM size (6) + Market timing (6) + Growth trajectory (4) + Competition intensity (4) |
| **Technical Moat** | **20** | Proprietary algorithms (6) + Data moat (5) + Engineering velocity (5) + Infra efficiency (4) |
| **Traction** | **20** | Revenue growth (7) + Unit economics (6) + Customer quality (4) + Product metrics (3) |
| **Business Model** | **10** | Revenue clarity (3) + Scalability (4) + Capital efficiency (3) |

**Supplemental (stored but not in 100-pt total):**
- `website_dd_score` 0–10: product clarity, pricing visibility, trust signals, customer proof
- `website_intelligence_score` 0–10: deep crawl synthesis

### Technical Moat Sub-scores (from SenseAI doc)

| Sub-criterion | Max | Key Question |
|---------------|-----|-------------|
| Proprietary Algorithms | 6 | Novel vs off-the-shelf? Time to replicate: months or years? Patents? |
| Data Moat | 5 | Unique data competitors can't access? Data flywheel present? |
| Engineering Velocity | 5 | Shipping 10x faster? Daily/weekly deploy frequency? |
| Infrastructure Efficiency | 4 | Can they serve customers 10x cheaper at scale? |

### Founder Quality Sub-scores (from SenseAI doc)

| Sub-criterion | Max | Evaluation |
|---------------|-----|-----------|
| Domain Expertise | 8 | Years solving the problem, industry depth, personal pain point |
| Track Record | 7 | Previous exits, leadership at growth companies, FAANG network |
| Technical Credibility | 8 | GitHub activity, engineering background, can they build it? |
| Team Completeness | 7 | Key roles filled, hiring velocity, senior/balanced team |

### Traction Benchmarks

| Revenue Growth | Score |
|---------------|-------|
| >200% YoY | 7/7 |
| >100% YoY | 5/7 |
| >50% YoY | 3/7 |
| <50% YoY | 1/7 |
| Pre-revenue | 0/7 (score on pipeline/LOIs instead) |

### Tier Classification

| Tier | Score | Label | Action |
|------|-------|-------|--------|
| TIER_1 | ≥ 85 | Generational — Top 1% | Term sheet immediately |
| TIER_2 | 70–84 | Strong — Top 10% | Proceed to deeper diligence |
| TIER_3 | 55–69 | Consider — Top 30% | Monitor 6 months, re-evaluate |
| PASS | < 55 | Does not meet bar | Pass on opportunity |

---

## 8. OCR PIPELINE — `services/ocr_processor.py`

### Strategy (in priority order)

```
1. pdfplumber   → Best: text PDFs, preserves table structure, columns
2. pypdf        → Fallback: standard PDFs
3. gpt-4o OCR   → Last resort: scanned/image-based PDFs (PDF → PNG → vision API)
4. ValueError   → All failed → user must provide URL or raw text instead
```

### Dockerfile Addition (required)
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
```

### requirements.txt Additions
```
pdfplumber>=0.10.0,<0.12.0
pdf2image>=1.16.0,<1.18.0
pypdf>=3.0.0,<5.0.0
Pillow>=10.0.0
python-pptx>=0.6.21
python-docx>=1.0.0
reportlab>=4.0.0
```

### Key Extraction Rules
- Always return text with `--- Page N ---` headers
- pdfplumber: extract tables as `col1 | col2 | col3` pipe-separated rows
- OCR: cap at 20 pages max; resize images to 1024×1024 max (reduce tokens)
- After extraction, cap total text at `60,000 chars` before passing to LLM structuring
- If text < 50 chars and no fallback inputs: raise HTTPException 400

---

## 9. FULL EXTRACTION SCHEMA (deck_processor.py output)

```python
extraction_schema = {
    "company": {
        "name": str,           # QUOTE exactly as written
        "tagline": str,
        "founded": str,        # Year or "not_mentioned"
        "hq_location": str,
        "website": str,
        "stage": str,          # pre-seed / seed / Series A / Series B / etc.
        "sector": str,
        "business_model": str, # B2B / B2C / B2B2C / marketplace
    },
    "founders": [{
        "name": str,
        "role": str,
        "linkedin": str,       # URL or "not_mentioned"
        "previous_company": str,
        "years_in_industry": int,
        "previous_exit": bool,
        "github_handle": str,  # if mentioned
    }],
    "problem": {
        "statement": str,      # QUOTE directly from deck
        "market_pain": str,
        "current_solutions": [str],
        "why_now": str,
    },
    "solution": {
        "product_description": str,
        "key_features": [str],
        "technology_stack": [str],
        "ai_usage": {
            "is_ai_core": bool,
            "ai_description": str,
            "proprietary_data": bool,
            "model_architecture": str,
        },
        "github_url": str,
    },
    "market": {
        "tam": str,            # exact figure or "not_mentioned"
        "sam": str,
        "som": str,
        "cagr": str,
        "market_source": str,
    },
    "traction": {
        "arr_mrr": str,
        "customers": str,
        "growth_rate": str,
        "key_customers": [str],
        "ltv_cac": str,
        "payback_period": str,
    },
    "funding": {
        "amount_sought": str,
        "previous_rounds": [str],
        "total_raised": str,
        "use_of_funds": [str],
        "lead_investors": [str],
    },
    "competitive_advantages": [str],
    "risks_mentioned": [str],
    "data_quality_flags": [str],  # TAM/SAM mismatch, inconsistent numbers, etc.
}
```

**Extraction rules (hallucination prevention):**
- ONLY extract explicitly stated information
- Use `"not_mentioned"` for any missing field — never infer
- Quote exact numbers — no rounding, no approximation
- Flag inconsistencies in `data_quality_flags`

---

## 10. INVESTMENT MEMO — 13 REQUIRED SECTIONS

```python
MEMO_SECTIONS = [
    "executive_summary",       # Score, tier, recommendation, 3 reasons, 3 risks, return estimate
    "company_overview",        # Problem, solution, product, stage, sector
    "founders_and_team",       # Deep dive: sub-scores, red/green flags, LinkedIn data
    "market_opportunity",      # TAM/SAM/SOM, timing, tech readiness, behavior shifts
    "competitive_landscape",   # 10–15 competitors matrix, positioning, threats
    "technical_moat",          # GitHub, algorithms, data flywheel, velocity, infra efficiency
    "traction_and_metrics",    # Revenue, customers, unit economics, product metrics
    "business_model",          # Revenue streams, GTM motion, scalability path
    "website_due_diligence",   # 25-page crawl findings, green flags, red flags
    "investment_thesis",       # Bull / Base / Bear cases, expected return, timeline
    "risks_and_mitigations",   # Top 5 concerns with proposed mitigations
    "diligence_roadmap",       # Next steps, key questions, data room requests
    "appendix",                # All sources with URLs + timestamps
]
```

**Rules for every section:**
1. Minimum 2 substantive paragraphs
2. Every factual claim ends with `[SOURCE: url or /page-name]`
3. `"not_mentioned"` for any unavailable data — never invent
4. Generate all sections in parallel with `asyncio.gather()`
5. Total memo target: 5–7 pages (3,500–5,000 words)

### Executive Summary Output Format (matches SenseAI sample)

```
INVESTMENT MEMORANDUM
{COMPANY NAME}
"{tagline}"

Date:     {today}
Stage:    {stage}
Business: {business model and sector}
Location: {hq_location}
Founded:  {founded}
Website:  {website}

RECOMMENDATION: {STRONG YES / YES / MAYBE / NO}
Investment Score: {score}/100 — {TIER}
Confidence Level: {HIGH / MEDIUM / LOW}

Score Breakdown:
• Founders:  {score}/30  — {one-line rationale}
• Market:    {score}/20  — {one-line rationale}
• Moat:      {score}/20  — {one-line rationale}
• Traction:  {score}/20  — {one-line rationale}
• Model:     {score}/10  — {one-line rationale}

Top 3 Reasons to Invest:
1. {Most compelling}  [SOURCE: url]
2. {Second most}      [SOURCE: url]
3. {Third most}       [SOURCE: url]

Top 3 Risks:
1. {Biggest risk}
2. {Second concern}
3. {Third concern}

Expected Return: {X}x in {Y} years (base case)
```

---

## 11. COMPETITIVE INTELLIGENCE — AGENT 8

The competitive intelligence agent discovers 10–15 competitors and builds a benchmarking matrix.

**Discovery sources (in order):**
1. SerpAPI: `"{company_category} startups 2024"`, `"{company_category} software competitors"`
2. Crunchbase: similar companies by category tag
3. Product Hunt: similar products launched
4. YC: same batch or category
5. Enrichment data: companies mentioned in extracted deck

**Output per competitor:**
```python
{
  "name": str,
  "url": str,
  "type": "direct | indirect | incumbent",
  "funding": str,        # "$50M Series B" or "bootstrapped" or "unknown"
  "est_arr": str,        # "$15M" or "unknown"
  "growth_yoy": str,     # "150%" or "unknown"
  "key_differentiator": str,
  "threat_level": "HIGH | MEDIUM | LOW",
  "verdict": str,        # "Winner / Moderate / Disadvantage" vs target co
}
```

**Competitive matrix output** (like SenseAI doc Table 4):
```
Metric      | Target  | Comp A  | Comp B  | Verdict
Funding     | $8M     | $50M    | $12M    | Disadvantage
Customers   | 150     | 400     | 80      | Moderate
ARR         | $2.5M   | $15M    | $1M     | Moderate
Growth YoY  | 300%    | 150%    | 200%    | Winner ✓
Product     | 94%     | 92%     | 88%     | Winner ✓
Cost/Unit   | $0.02   | $0.10   | $0.05   | 5x Advantage ✓
```

---

## 12. EXPORT FORMATS — `services/report_exporter.py`

| Format | Library | Output |
|--------|---------|--------|
| PDF | `reportlab` | 5–7 page professional investment memo |
| DOCX | `python-docx` | Editable Word document with citations |
| PPTX | `python-pptx` | 10–15 slide IC presentation deck |
| JSON | `json` | Structured data for CRM / Airtable / Notion |

**PPTX slide structure (10–15 slides):**
1. Cover slide: company name, score badge, tier, date
2. Executive summary: recommendation + score breakdown
3. Company overview: problem / solution diagram
4. Founders & team: photos, sub-scores, flags
5. Market opportunity: TAM/SAM/SOM chart
6. Competitive landscape: matrix table
7. Technical moat: radar chart (5 dimensions)
8. Traction & metrics: revenue chart, KPIs
9. Business model: GTM motion, revenue streams
10. Investment thesis: Bull / Base / Bear bullets
11. Risks & mitigations: table
12. Diligence roadmap: timeline + action items

---

## 13. RAG CITATION ARCHITECTURE — `services/rag_extractor.py`

Every fact in the memo must cite its source. No source → "not_mentioned".

```python
def build_cited_prompt(query: str, sources: list[dict]) -> str:
    """Build a prompt that forces citation on every claim."""
    blocks = []
    for i, s in enumerate(sources[:10], 1):
        url  = s.get("url", s.get("page", "pitch_deck"))
        text = s.get("text", "")[:1500]
        blocks.append(f"[SOURCE {i}: {url}]\n{text}")

    return f"""CITATION RULES — NON-NEGOTIABLE:
1. Use ONLY information from the sources below
2. Every factual claim MUST end with [SOURCE: url]
3. If data is NOT in sources → write "not_mentioned"
4. NEVER infer, guess, estimate, or extrapolate
5. Quote exact numbers — do not round or approximate
6. Flag suspicious claims in [FLAG: reason] notation

SOURCES:
{chr(10).join(blocks)}

QUESTION / TASK:
{query}

YOUR ANSWER (with [SOURCE: url] after every fact):"""


def validate_citations(response: str, sources: list[dict]) -> list[str]:
    """Return list of unverified citations (should be empty)."""
    import re
    cited  = re.findall(r'\[SOURCE:\s*([^\]]+)\]', response)
    known  = {s.get("url", s.get("page", "")) for s in sources}
    return [c for c in cited if not any(c.strip() in k for k in known)]
```

---

## 14. DATABASE SCHEMA ADDITIONS

Run in Supabase SQL editor (after base schema.sql):

```sql
-- Multi-input support
ALTER TABLE companies ADD COLUMN IF NOT EXISTS linkedin_provided    TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS raw_text_provided    BOOLEAN DEFAULT FALSE;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS input_types          TEXT[]  DEFAULT '{}';

-- Remove restrictive CHECK to allow all enrichment source types
ALTER TABLE enrichment_sources
  DROP CONSTRAINT IF EXISTS enrichment_sources_source_type_check;
-- Now accepts: github, hackernews, reddit, wayback, producthunt, appstore,
--   news, crunchbase, whois, opencorporates, sec_edgar, glassdoor,
--   competitors, linkedin_founder, website, website_intelligence,
--   website_due_diligence

-- Extended scoring sub-scores
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS founder_domain_score      NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS founder_track_record_score NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS founder_technical_score   NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS founder_team_score        NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS moat_algorithms_score     NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS moat_data_score           NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS moat_velocity_score       NUMERIC(4,1);
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS moat_efficiency_score     NUMERIC(4,1);

-- Thesis + competitive output
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS comparable_companies      JSONB;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS competitive_matrix        JSONB;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS bull_case                 TEXT;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS base_case                 TEXT;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS bear_case                 TEXT;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS expected_return           TEXT;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS confidence_level          TEXT;
ALTER TABLE investment_scores ADD COLUMN IF NOT EXISTS diligence_roadmap         JSONB;

-- Export tracking
ALTER TABLE companies ADD COLUMN IF NOT EXISTS exports_generated   TEXT[]  DEFAULT '{}';
ALTER TABLE companies ADD COLUMN IF NOT EXISTS memo_word_count      INTEGER;
```

---

## 15. ENVIRONMENT VARIABLES

### Required
```bash
SUPABASE_URL                  # Supabase project URL
SUPABASE_SERVICE_ROLE_KEY     # Service role key (NOT anon key)
Z_API_KEY                     # Z.ai — ONLY LLM provider
DUESENSE_API_KEY              # X-API-Key for protected endpoints
```

### Optional Enrichment (free tiers)
```bash
GITHUB_TOKEN                  # GitHub REST: 5000/hr authenticated
NEWS_API_KEY                  # NewsAPI.org: 100/day free
SERPAPI_KEY                   # SerpAPI: competitors + LinkedIn: 100/mo free
SCRAPER_API_KEY               # ScraperAPI: website crawl: 1000/mo free
CRUNCHBASE_KEY                # Crunchbase Basic: 200/day free
PRODUCTHUNT_TOKEN             # Product Hunt: 50/day free
WHOISXML_KEY                  # WHOIS XML: 500/mo free
OPENCORPORATES_KEY            # Open Corporates: 500/mo free
RAPIDAPI_KEY                  # Glassdoor + LinkedIn data scraping
SLACK_WEBHOOK_URL             # TIER_1 deal Slack alerts
```

### Explicitly Removed — Do Not Re-add
```bash
# GROQ_API_KEY    — too many rate-limit overshots
# HUGGINGFACE_API_KEY — too slow for production
```

---

## 16. CODING RULES

```python
# ✅ Always use .get() with defaults on LLM JSON output
result = await llm.generate_json(prompt, system)
score  = float(result.get("total_score", 10.0))
flags  = result.get("flags", [])

# ✅ Always wrap OCR in try/except with graceful fallback
try:
    text = await extract_pdf_text(content)
except ValueError as e:
    logger.warning(f"[OCR] All strategies failed: {e}")
    text = raw_text or ""
if len(text.strip()) < 50:
    raise HTTPException(400, "Could not extract text. Please also provide the company website or paste the deck text.")

# ✅ All enrichment tasks parallel — never sequential
results = await asyncio.gather(*[_safe(t) for t in tasks], return_exceptions=True)
for name, r in zip(names, results):
    enrichment[name] = {"error": str(r)} if isinstance(r, Exception) else r

# ✅ Status update at every pipeline stage
async def _update_status(company_id, deck_id, stage):
    now = datetime.utcnow().isoformat()
    companies_tbl.update({"id": company_id}, {"status": stage, "updated_at": now})
    if deck_id:
        decks_tbl.update({"id": deck_id}, {"processing_status": stage})

# ✅ Cap all LLM input to avoid context overflow
deck_text      = extracted_text[:12_000]
enrichment_str = json.dumps(enrichment, default=str)[:4_000]
prompt_data    = json.dumps(company_data, default=str)[:3_000]

# ✅ Citation system prompt on every agent call
CITATION_SYSTEM = (
    "You are a senior VC analyst. "
    "Every factual claim MUST end with [SOURCE: url/page]. "
    "Use 'not_mentioned' for absent data. NEVER fabricate or infer."
)

# ❌ Never use groq, openai SDK, or huggingface in any service
import groq        # FORBIDDEN
import openai      # FORBIDDEN (use httpx directly to Z.ai)

# ❌ Never open Supabase client directly in service files
supabase.create_client(...)  # Only in db.py

# ❌ Never use print() — always logger.*()
logger.info(f"[{company_id}] Stage 3/5: Scoring agents starting")
logger.error(f"[{company_id}] Agent failed: {e}")

# ❌ Never let one enrichment failure kill the pipeline
# Always use _safe() wrapper in enrichment_engine.py
```