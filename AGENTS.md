# DueSense - Agent Knowledge Base

## Project Overview
DueSense is a VC Deal Intelligence platform that analyzes startup pitch decks and generates investment memos using AI.

## Repository Structure
```
DueSense/
├── backend/           # FastAPI backend
│   ├── server.py      # Main API server (serves React frontend at /)
│   ├── db.py          # Centralized Supabase connection (lazy initialization)
│   ├── database/      # Database schema and migrations
│   │   └── schema.sql # PostgreSQL schema for Supabase
│   ├── api/v1/        # Versioned API endpoints
│   │   ├── auth.py    # API key authentication
│   │   ├── health.py  # Health check endpoints
│   │   ├── deals.py   # Deal management
│   │   ├── ingestion.py # Pitch deck upload
│   │   └── analytics.py # Dashboard stats
│   ├── static/        # React frontend build (served at root)
│   ├── services/      # Business logic modules
│   │   ├── llm_provider.py      # Multi-provider LLM (Z.ai, GROQ, HuggingFace)
│   │   ├── enrichment_engine.py
│   │   ├── scorer.py
│   │   ├── memo_generator.py
│   │   └── website_due_diligence.py
│   ├── integrations/  # External API clients
│   ├── templates/     # Landing page (fallback if no React build)
│   ├── requirements.txt
│   ├── runtime.txt    # Python version for Render (3.11.9)
│   └── Dockerfile     # Uses python:3.11.9-bullseye for OpenSSL compatibility
├── frontend/          # React frontend source
│   ├── src/
│   │   ├── pages/     # Dashboard, Upload, Companies, CompanyDetail
│   │   ├── components/# Sidebar, HealthCheck, ErrorBoundary
│   │   └── api.js     # API client (supports same-origin deployment)
│   └── build/         # Built files (not tracked, copied to backend/static)
└── render.yaml        # Render deployment configuration
```

## Backend Architecture

### LLM Provider
- **Multi-provider support** with automatic fallback:
  1. **Z.ai** (OpenAI-compatible, fast and reliable) - `Z_API_KEY`
  2. **GROQ** (fast inference) - `GROQ_API_KEY`
  3. **HuggingFace** (free tier fallback) - `HUGGINGFACE_API_KEY`
- **Auto-fallback**: On rate limits or model unavailability
- **At least one provider required**

### Database: Supabase (PostgreSQL)
- **Lazy initialization**: Supabase client is created on first use
- **Centralized module**: All services import `db.py` for database access
- **Connection resilience**: App starts even if Supabase is temporarily unavailable
- **Retries**: 3 connection attempts with 2-second delays during startup
- **Tables**: companies, pitch_decks, founders, enrichment_sources, competitors, investment_scores, investment_memos

### Key Files
- `backend/db.py` - Centralized Supabase connection management
- `backend/database/schema.sql` - PostgreSQL schema (run in Supabase SQL Editor)
- `backend/server.py` - FastAPI app with lifespan manager
- `backend/services/llm_provider.py` - Multi-provider LLM integration
- `backend/api/v1/auth.py` - API key authentication
- `backend/runtime.txt` - Python version specification (`python-3.11.9`)

## Build & Run Commands

### Local Development
```bash
cd backend
pip install -r requirements.txt
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
export Z_API_KEY="..." # or GROQ_API_KEY or HUGGINGFACE_API_KEY
export DUESENSE_API_KEY="your-api-key"
export ENABLE_DEMO_KEY="true" # Only for local testing
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Build
```bash
cd backend
docker build -t duesense-backend .
docker run -p 10000:10000 \
  -e SUPABASE_URL="https://xxx.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="eyJ..." \
  -e Z_API_KEY="..." \
  -e DUESENSE_API_KEY="your-api-key" \
  -e ENABLE_DEMO_KEY="false" \
  duesense-backend
```

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL (e.g., `https://xxx.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (not anon key) |
| LLM API Key | At least one: `Z_API_KEY`, `GROQ_API_KEY`, or `HUGGINGFACE_API_KEY` |

### Recommended for Production
| Variable | Description |
|----------|-------------|
| `DUESENSE_API_KEY` | API key for protected endpoints |
| `ENABLE_DEMO_KEY` | Set to `false` in production (IMPORTANT!) |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated, e.g., `https://dominionvault.com,https://www.dominionvault.com`) |

### Optional
| Variable | Description |
|----------|-------------|
| `PORT` | Server port (Render sets this, default: 8000) |
| `GITHUB_TOKEN` | GitHub token for repo analysis |
| `NEWS_API_KEY` | NewsAPI key for news enrichment |
| `SERPAPI_KEY` | SerpAPI key for search |
| `MAX_FILE_SIZE_MB` | Max upload size (default: 25) |

## Render Deployment

### Configuration
- **Runtime**: Docker
- **Root Directory**: `backend`
- **Dockerfile Path**: `./Dockerfile`
- **Health Check**: `/health`

### Deployment Steps
1. Clear build cache in Render dashboard
2. Set all required environment variables (see above)
3. Run `backend/database/schema.sql` in Supabase SQL Editor
4. Deploy and verify `/health` endpoint returns `healthy`

### Troubleshooting
- **Build failure (pymongo)**: Ensure Dockerfile doesn't reference pymongo
- **SSL/TLS errors**: Ensure Docker runtime is used (not Python)
- **Database errors**: Verify schema.sql was executed in Supabase
- **LLM errors**: Check at least one LLM API key is set and valid

## Supabase Configuration

### Setup Steps
1. Create a new Supabase project
2. Go to Settings → API to get URL and service role key
3. Go to SQL Editor and run `backend/database/schema.sql`
4. Verify tables were created in Table Editor

### Required Tables
- `companies` - Company information
- `pitch_decks` - Uploaded deck metadata and extracted data
- `founders` - Founder information
- `enrichment_sources` - External data (GitHub, news, etc.)
- `competitors` - Competitor information
- `investment_scores` - 6-dimension investment scores
- `investment_memos` - AI-generated investment memos

## API Endpoints

### Health Checks
- `GET /health` - Full health check with DB and LLM status
- `GET /api/v1/health` - Comprehensive health check
- `GET /api/v1/health/live` - Kubernetes liveness probe
- `GET /api/v1/health/ready` - Kubernetes readiness probe

### Core Endpoints (API v1, require X-API-Key header)
- `POST /api/v1/ingestion/upload` - Upload pitch deck
- `GET /api/v1/ingestion/status/{deck_id}` - Get processing status
- `GET /api/v1/deals` - List all deals/companies
- `GET /api/v1/deals/{id}` - Get deal details with score and memo
- `GET /api/v1/analytics/dashboard` - Dashboard statistics

### Legacy Endpoints (still available)
- `POST /api/decks/upload` - Upload pitch deck
- `GET /api/companies` - List all companies
- `GET /api/companies/{id}` - Get company details
- `GET /api/companies/{id}/score` - Get investment score
- `GET /api/companies/{id}/memo` - Get investment memo

## Code Style Notes
- All database access goes through `db.py` module
- Table accessors are functions returning `SupabaseTable` wrapper
- Services import: `import db as database`
- Access tables via: `database.companies_collection()`
- API key auth: `from api.v1.auth import verify_api_key`

## Frontend Deployment Architecture

### Same-Origin Deployment (Current)
The backend serves the React frontend from `backend/static/` at the root URL (`/`).

**How it works:**
1. Frontend is built with `npm run build` in `frontend/`
2. Build output is copied to `backend/static/`
3. Backend serves index.html for non-API routes
4. Static assets (JS, CSS) served from `/static/`
5. API routes (`/api/*`, `/health`, `/docs`) work normally

**To update frontend:**
```bash
cd frontend
npm install
npm run build
rm -rf ../backend/static
cp -r build ../backend/static
```

### Separate Deployment (Alternative)
Frontend can be deployed separately (e.g., Vercel) with:
```bash
REACT_APP_BACKEND_URL=https://api.dominionvault.com npm run build
```

### Frontend Features
- **Dashboard**: Deal Pipeline overview with stats and tier distribution
- **Upload**: Drag & drop pitch deck upload with optional website URL
- **Companies**: List view with search and status filtering
- **CompanyDetail**: Tabbed view with:
  - Overview (scores, key metrics)
  - Website Intel (deep website analysis)
  - Enrichment (GitHub, news, research data)
  - Scoring (6-dimension breakdown including Website DD)
  - Memo (AI-generated investment memo)
  - Competitors (competitive landscape)

### Website Due Diligence Integration
- Upload includes optional company website URL field
- Website DD runs in parallel with deck extraction
- Circular score visualization with breakdown
- Green/red flags displayed on company detail page
- Score includes `website_dd_score` (0-10 scale)
