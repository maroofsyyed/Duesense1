# VC Deal Intelligence System - PRD

## Original Problem Statement
Build a production VC Deal Intelligence System that automates comprehensive due diligence for venture capital firms. Core capabilities: pitch deck extraction, multi-source enrichment, AI scoring, memo generation, interactive dashboards. Enhanced with Deep Website Intelligence System.

## Architecture
- **Frontend**: React 18 + TailwindCSS 3.4 + Recharts + react-dropzone + react-router-dom
- **Backend**: FastAPI (Python) on port 8001
- **Database**: MongoDB (companies, pitch_decks, founders, enrichment_sources, competitors, investment_scores, investment_memos)
- **LLM**: GPT-4o via Emergent LLM key (provider abstraction supports Ollama swap)
- **APIs**: GitHub, NewsAPI, SerpAPI, ScraperAPI (all real keys configured)

## User Personas
- **VC Analysts**: Upload pitch decks, review AI-generated analysis
- **VC Partners**: Review investment scores, memos, make decisions

## Core Requirements (Static)
- Upload PDF/PPTX pitch decks (max 25MB)
- AI-powered extraction of structured company data
- Multi-source enrichment (GitHub, News, competitors, market, website)
- Deep website intelligence (30+ page crawl map, 7 specialized AI agents)
- 6 specialized scoring agents (Founder Quality, Market Opportunity, Technical Moat, Traction, Business Model, Website Intelligence)
- Investment scoring 0-100 with 6-dimension breakdown and tier classification
- 11-section investment memo generation
- Interactive dashboard with Recharts charts
- Source citations for AI findings

## What's Been Implemented

### Feb 8, 2026 - MVP
- [x] Full backend API (FastAPI + MongoDB, 10+ endpoints)
- [x] Pitch deck upload & AI extraction pipeline (PDF/PPTX)
- [x] LLM provider abstraction layer (Emergent GPT-4o / Ollama)
- [x] Multi-source enrichment engine (6 sources: GitHub, News, Competitors, Market, Website, Website Intelligence)
- [x] 5 core AI scoring agents + investment thesis generation
- [x] Investment scoring system (0-100, 4 tiers)
- [x] Investment memo generator (11 sections with citations)
- [x] Dashboard with stats, tier distribution, score charts
- [x] Upload page with drag-drop & real-time processing pipeline UI
- [x] Companies list with search & delete
- [x] Company detail with 5 tabs (Overview, Enrichment, Scoring, Memo, Competitors)
- [x] Dark "Venture Obsidian" theme
- [x] Testing: 100% backend, 95% frontend

### Feb 8, 2026 - Deep Website Intelligence Enhancement
- [x] WebsiteIntelligenceEngine with 35-page crawl map
- [x] 7 specialized AI extraction agents:
  1. Product Intelligence Extractor
  2. Revenue Model Analyzer
  3. Customer Validation Extractor
  4. Team & Hiring Intelligence
  5. Technical Depth Analyzer
  6. Traction & Growth Signals
  7. Compliance & Trust Signals
- [x] Tech stack detection (regex-based pattern matching)
- [x] Sales signal extraction (contact forms, demos, trials, etc.)
- [x] AI-powered intelligence synthesis (overall score 0-100 with breakdown)
- [x] Red/green flags with source citations
- [x] Updated scoring system: 6 dimensions (Founders 25, Market 20, Moat 20, Traction 15, Model 10, Website 10)
- [x] New "Website Intel" tab in Company Detail page with:
  - Circular score gauge
  - 5-dimension score breakdown bar chart
  - Green/Red flags panels
  - GTM Motion analysis
  - Sales signals detection grid
  - Tech stack display
  - Product intelligence details
  - Customer validation data
  - Team & hiring intelligence
  - Technical credibility assessment
  - Traction signals
  - Compliance & trust signals
  - Market positioning analysis
  - Revenue model assessment
- [x] Radar chart updated to 6 dimensions (hexagonal)
- [x] Bar chart shows all 6 score dimensions
- [x] Dedicated API endpoints for website intelligence (GET + rerun POST)
- [x] Testing: 100% backend (7/7), 100% frontend

## Prioritized Backlog
### P0 (Critical)
- [ ] PDF/DOCX/PPTX export for investment memos
- [ ] Authentication (JWT or Google OAuth)

### P1 (Important)
- [ ] RAG system with vector DB for zero-hallucination citations
- [ ] Competitive matrix visualization
- [ ] Real-time WebSocket status updates
- [ ] Batch upload multiple decks
- [ ] Wappalyzer API integration for more accurate tech detection

### P2 (Nice to Have)
- [ ] Email notifications when analysis complete
- [ ] Portfolio tracking & comparison
- [ ] Custom scoring rubric configuration
- [ ] Historical trend charts
- [ ] Redis caching for API responses
- [ ] Deal comparison mode (2-3 companies side-by-side)

## Next Tasks
1. Add PDF export for investment memos
2. Implement RAG with ChromaDB for citation tracking
3. Add authentication layer
4. Competitive matrix visualization
5. WebSocket for real-time processing updates
