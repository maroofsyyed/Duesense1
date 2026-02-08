# VC Deal Intelligence System - PRD

## Original Problem Statement
Build a production VC Deal Intelligence System that automates comprehensive due diligence for venture capital firms. Core capabilities: pitch deck extraction, multi-source enrichment, AI scoring, memo generation, interactive dashboards.

## Architecture
- **Frontend**: React 18 + TailwindCSS 3.4 + Recharts + react-dropzone + react-router-dom
- **Backend**: FastAPI (Python) on port 8001
- **Database**: MongoDB (companies, pitch_decks, founders, enrichment_sources, competitors, investment_scores, investment_memos)
- **LLM**: GPT-4o via Emergent LLM key (provider abstraction supports Ollama swap)
- **APIs**: GitHub, NewsAPI, SerpAPI, ScraperAPI (all real keys configured)

## User Personas
- **VC Analysts**: Upload pitch decks, review AI-generated analysis
- **VC Partners**: Review investment scores, memos, make decisions

## Core Requirements
- Upload PDF/PPTX pitch decks (max 25MB)
- AI-powered extraction of structured company data
- Multi-source enrichment (GitHub, News, competitors, market, website)
- 5 specialized AI agents (Founder Quality, Market Opportunity, Technical Moat, Traction, Business Model)
- Investment scoring 0-100 with tier classification
- 11-section investment memo generation
- Interactive dashboard with charts (Recharts)
- Zero hallucination with source citations

## What's Been Implemented (Feb 8, 2026)
- [x] Full backend API (FastAPI + MongoDB)
- [x] Pitch deck upload & AI extraction pipeline
- [x] LLM provider abstraction (Emergent/Ollama)
- [x] Multi-source enrichment engine (5 sources: GitHub, News, Competitors, Market, Website)
- [x] 5 specialized AI scoring agents
- [x] Investment scoring system (0-100, 4 tiers)
- [x] Investment memo generator (11 sections)
- [x] Dashboard with stats, tier distribution chart, score bar chart
- [x] Upload page with drag-drop & processing pipeline UI
- [x] Companies list with search & delete
- [x] Company detail with 5 tabs (Overview, Enrichment, Scoring, Memo, Competitors)
- [x] Radar chart & bar chart for score visualization
- [x] Dark "Venture Obsidian" theme
- [x] Testing: 100% backend, 95% frontend

## Prioritized Backlog
### P0 (Critical)
- [ ] PDF/DOCX/PPTX export for investment memos
- [ ] Authentication (JWT or Google OAuth)

### P1 (Important)
- [ ] RAG system with vector DB for zero-hallucination citations
- [ ] Competitive matrix visualization
- [ ] Real-time WebSocket status updates (instead of polling)
- [ ] Batch upload multiple decks

### P2 (Nice to Have)
- [ ] Email notifications when analysis complete
- [ ] Portfolio tracking & comparison
- [ ] Custom scoring rubric configuration
- [ ] Historical trend charts
- [ ] Redis caching for API responses

## Next Tasks
1. Add PDF export for investment memos
2. Implement RAG with ChromaDB/Qdrant for citation tracking
3. Add authentication layer
4. Competitive matrix visualization
5. WebSocket for real-time processing updates
