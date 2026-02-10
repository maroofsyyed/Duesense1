# DueSense - Agent Knowledge Base

## Project Overview
DueSense is a VC Deal Intelligence platform that analyzes startup pitch decks and generates investment memos using AI.

## Repository Structure
```
DueSense/
├── backend/           # FastAPI backend
│   ├── server.py      # Main API server (serves React frontend at /)
│   ├── db.py          # Centralized MongoDB connection (lazy initialization)
│   ├── static/        # React frontend build (served at root)
│   ├── services/      # Business logic modules
│   │   ├── llm_provider.py      # HuggingFace LLM integration
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
- **Primary**: HuggingFace Inference API with `meta-llama/Meta-Llama-3.1-70B-Instruct`
- **Fallback Models**: Mixtral 8x7B, Llama 3.1 8B, Zephyr 7B
- **Auto-fallback**: On rate limits or model unavailability
- **Configuration**: Set `HUGGINGFACE_API_KEY` or `HF_TOKEN` environment variable

### Database Connection Pattern
- **Lazy initialization**: MongoDB client is created on first use, not at import time
- **Centralized module**: All services import `db.py` for database access
- **Connection resilience**: App starts even if MongoDB is temporarily unavailable
- **Retries**: 3 connection attempts with 5-second delays during startup
- **SSL/TLS**: Uses certifi CA bundle for MongoDB Atlas compatibility

### Key Files
- `backend/db.py` - Centralized MongoDB connection management
- `backend/server.py` - FastAPI app with lifespan manager
- `backend/services/llm_provider.py` - HuggingFace LLM integration
- `backend/runtime.txt` - Python version specification (`python-3.11.9`)

## Build & Run Commands

### Local Development
```bash
cd backend
pip install -r requirements.txt
export MONGODB_URI="mongodb+srv://..."
export DB_NAME="duesense"
export HUGGINGFACE_API_KEY="hf_..."
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Build
```bash
cd backend
docker build -t duesense-backend .
docker run -p 10000:10000 \
  -e MONGODB_URI="..." \
  -e DB_NAME="duesense" \
  -e HUGGINGFACE_API_KEY="hf_..." \
  duesense-backend
```

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `MONGODB_URI` or `MONGO_URL` | MongoDB Atlas connection string |
| `DB_NAME` | Database name (default: `duesense`) |
| `HUGGINGFACE_API_KEY` or `HF_TOKEN` | HuggingFace API token for LLM |

### Optional
| Variable | Description |
|----------|-------------|
| `PORT` | Server port (Render sets this, default: 8000) |
| `GITHUB_TOKEN` | GitHub token for repo analysis |
| `NEWS_API_KEY` | NewsAPI key for news enrichment |
| `SERPAPI_KEY` | SerpAPI key for search |
| `MAX_FILE_SIZE_MB` | Max upload size (default: 25) |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated, default: *) |

## Render Deployment

### Configuration
- **Runtime**: Docker
- **Root Directory**: `backend`
- **Python Version**: 3.11.9 (specified in `backend/runtime.txt`)
- **Health Check**: `/health`

### Deployment Steps
1. Clear build cache in Render dashboard
2. Set `MONGODB_URI` and `DB_NAME` environment variables
3. Ensure MongoDB Atlas IP allowlist includes `0.0.0.0/0`
4. Deploy and verify `/health` endpoint returns `healthy`

### Troubleshooting
- **SSL/TLS errors**: Ensure Python 3.11.x (not 3.13)
- **Connection timeout**: Check MongoDB Atlas IP allowlist
- **Import errors**: Check all services use `db.py` module

## MongoDB Atlas Configuration

### Required Settings
1. **Network Access**: Add `0.0.0.0/0` to IP allowlist (for Render free tier)
2. **Connection String**: Use `mongodb+srv://` format with credentials

### Connection String Format
```
mongodb+srv://<username>:<password>@cluster.mongodb.net/<database>?retryWrites=true&w=majority
```

## API Endpoints

### Health Checks
- `GET /health` - Full health check with DB status
- `GET /api/health` - Simple API health check

### Core Endpoints
- `POST /api/decks/upload` - Upload pitch deck
- `GET /api/companies` - List all companies
- `GET /api/companies/{id}` - Get company details
- `GET /api/companies/{id}/score` - Get investment score
- `GET /api/companies/{id}/memo` - Get investment memo

## Code Style Notes
- All database access goes through `db.py` module
- Collection accessors are functions, not global variables
- Services import: `import db as database`
- Access collections via: `database.companies_collection()`

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
