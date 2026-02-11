# DueSense - AI-Powered VC Deal Intelligence

Enterprise-grade pitch deck analysis and investment memo generation for venture capitalists.

## Quick Start (Production)

### Prerequisites
- Supabase account (database)
- Render account (backend hosting)
- Vercel account (frontend hosting)
- API keys: Z.ai/GROQ/HuggingFace (at least one)

### Deployment Steps

1. **Database Setup**
   ```bash
   # Run schema.sql in Supabase SQL Editor
   # File: backend/database/schema.sql
   ```

2. **Backend Deployment (Render)**
   - Connect GitHub repo to Render
   - Set root directory: `backend`
   - Add environment variables (see below)
   - Deploy

3. **Frontend Deployment (Vercel)**
   - Connect GitHub repo to Vercel
   - Set root directory: `frontend`
   - Add `REACT_APP_BACKEND_URL`
   - Deploy

### Required Environment Variables

**Backend (Render):**
```bash
# Database
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# LLM (at least one)
Z_API_KEY=xxx
GROQ_API_KEY=xxx
HUGGINGFACE_API_KEY=xxx

# Security
DUESENSE_API_KEY=your-secure-api-key-here
ENABLE_DEMO_KEY=false

# Optional Enrichment
GITHUB_TOKEN=xxx
NEWS_API_KEY=xxx
SERPAPI_KEY=xxx
```

**Frontend (Vercel):**
```bash
REACT_APP_BACKEND_URL=https://your-backend.onrender.com
```

## Documentation

- [Deployment Guide](./DEPLOYMENT.md) - Full deployment instructions
- [Architecture](./AGENTS.md) - AI agents and scoring system
- [API Documentation](https://your-backend.onrender.com/docs) - Interactive API docs

## Security

- API key authentication required
- CORS configured for production domains
- Row-level security enabled on Supabase
- No sensitive data in logs or responses

## Features

- Pitch deck analysis (PDF/PPTX)
- 7 AI agents for comprehensive scoring
- Website due diligence
- Investment memo generation
- Dashboard & analytics

## Tech Stack

- **Backend:** FastAPI + Python 3.11.9
- **Frontend:** React + Tailwind CSS
- **Database:** Supabase (PostgreSQL)
- **LLMs:** Z.ai / GROQ / HuggingFace
- **Hosting:** Render + Vercel

## Local Development

```bash
cd backend
pip install -r requirements.txt
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="xxx"
export HUGGINGFACE_API_KEY="hf_..."
export ENABLE_DEMO_KEY=true
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with DB/LLM status and latency |
| `POST /api/decks/upload` | Upload pitch deck |
| `GET /api/companies` | List all companies |
| `GET /api/companies/{id}` | Get company details |
| `GET /api/companies/{id}/score` | Get investment score |
| `GET /api/companies/{id}/memo` | Get investment memo |
| `GET /api/dashboard/stats` | Dashboard statistics |

## License

MIT License
