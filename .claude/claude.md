# SenseAI / DueSense — Detailed Project Brain

> This file supplements the root `CLAUDE.md` (the canonical spec). Read `CLAUDE.md` first.
> This file maps the codebase, defines behavioural constraints, and tells Claude how to think.

## What This Is

SenseAI / DueSense is a **Kruncher-class VC deal intelligence platform**:

- 300+ data points per company
- Zero hallucinations (every claim cites a source)
- 10–15 minute end-to-end reports
- 100-point composite scoring → Tier 1–3 / Pass

## Who It's For

- Venture capital analysts evaluating deal flow
- Investment partners making fund decisions
- Fund operations teams processing 1000+ deals/year

## Tech Stack (LOCKED — Do NOT Change)

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11.9, Docker → Render) |
| Frontend | React 19 + Tailwind CSS (Vercel or same-origin SPA) |
| Database | Supabase (PostgreSQL + JSONB) |
| **LLM** | **Z.ai ONLY** — gpt-4o (quality) + gpt-4o-mini (bulk) |
| OCR | pdfplumber → pypdf → gpt-4o vision (fallback chain) |
| Scraping | ScraperAPI / httpx + BeautifulSoup4 |
| Exports | python-pptx + python-docx + reportlab |
| Icons | lucide-react |
| Charts | Recharts |

> ❌ GROQ and HuggingFace are **permanently disabled**. Do not re-add.
> ❌ Do not import `openai` or `groq` SDKs. Use `httpx` directly to Z.ai.

## Repository Map

```
/
├── CLAUDE.md               ← CANONICAL SPEC (16 sections) — read first
├── FREE_APIS.md            ← All free API clients + integration code
├── FRONTEND.md             ← React components + design system
├── BACKEND.md              ← Service patterns + agent implementations
├── ROADMAP.md              ← Prioritized feature plan
├── design_guidelines.json  ← UI design system (Venture Obsidian)
│
├── backend/
│   ├── server.py           ← FastAPI app, lifespan, SPA static serve
│   ├── db.py               ← Supabase lazy-init + SupabaseTable wrapper
│   ├── api/v1/
│   │   ├── router.py       ← Mounts all sub-routers
│   │   ├── auth.py         ← X-API-Key header authentication
│   │   ├── health.py       ← /health /live /ready
│   │   ├── deals.py        ← CRUD + pagination
│   │   ├── ingestion.py    ← Multi-input upload (file + URL + LinkedIn + text)
│   │   └── analytics.py    ← Dashboard stats + tier insights
│   ├── services/
│   │   ├── llm_provider.py          ← Z.ai ONLY singleton
│   │   ├── ocr_processor.py         ← pdfplumber → pypdf → gpt-4o vision
│   │   ├── deck_processor.py        ← OCR → LLM structuring → schema
│   │   ├── enrichment_engine.py     ← 13-source parallel orchestrator
│   │   ├── agents.py                ← 8+ scoring agents (parallel)
│   │   ├── scorer.py                ← 100-point composite + tier
│   │   ├── memo_generator.py        ← 13-section investment memo
│   │   ├── report_exporter.py       ← PDF / PPTX / DOCX / JSON exports
│   │   ├── rag_extractor.py         ← Citation-enforced fact extraction
│   │   ├── website_due_diligence.py ← 25-page crawl + citations
│   │   └── website_intelligence.py  ← 7-sub-agent deep crawl synthesis
│   ├── integrations/clients.py      ← All API clients (GitHub, HN, Reddit, etc.)
│   ├── database/schema.sql          ← Full Supabase schema
│   └── static/                      ← React build (SPA)
│
└── frontend/src/
    ├── api.js                        ← Axios client
    ├── App.js                        ← Router + Sidebar
    ├── components/ui/                ← ScoreRing, TierBadge, StatusBadge, MetricCard
    └── pages/
        ├── Dashboard.js              ← Bento grid: pipeline + deals
        ├── Upload.js                 ← Multi-input: file + URL + LinkedIn + text
        ├── Companies.js              ← Table with tier badges + scores
        └── CompanyDetail.js          ← Tabs: Overview / Intel / Scoring / Memo / Competitors / Export
```

## How to Think

1. **Read CLAUDE.md first** before every task — it's the canonical 16-section spec
2. **Plan before building** — use Plan Mode for non-trivial changes
3. **Verify after building** — check health endpoints, test pipeline
4. **Zero hallucinations** — every fact must cite a source, use `"not_mentioned"` for missing data
5. **Parallel everything** — enrichment, scoring agents, memo sections all run via `asyncio.gather()`
6. **Graceful degradation** — one enrichment failure must never kill the pipeline
7. **Z.ai only** — never import openai/groq/huggingface SDKs
8. **Context caps** — always truncate LLM inputs (12k deck, 4k enrichment, 3k company data)
9. **Status updates** — update both `companies` and `pitch_decks` tables at every pipeline stage
10. **When unsure** — check `CLAUDE.md` sections 3–16, then `design_guidelines.json`
