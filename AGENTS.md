# DueSense - Agent Knowledge Base

## Project Overview
DueSense is a VC Deal Intelligence platform that analyzes startup pitch decks and generates investment memos using AI.

## Repository Structure
```
DueSense/
├── backend/           # FastAPI backend
│   ├── server.py      # Main API server
│   ├── db.py          # Centralized MongoDB connection (lazy initialization)
│   ├── services/      # Business logic modules
│   │   ├── enrichment_engine.py
│   │   ├── scorer.py
│   │   ├── memo_generator.py
│   │   └── website_due_diligence.py
│   ├── integrations/  # External API clients
│   ├── requirements.txt
│   ├── runtime.txt    # Python version for Render (3.11.9)
│   └── Dockerfile
├── frontend/          # React frontend (Vercel deployment)
└── render.yaml        # Render deployment configuration
```

## Backend Architecture

### Database Connection Pattern
- **Lazy initialization**: MongoDB client is created on first use, not at import time
- **Centralized module**: All services import `db.py` for database access
- **Connection resilience**: App starts even if MongoDB is temporarily unavailable
- **Retries**: 3 connection attempts with 5-second delays during startup

### Key Files
- `backend/db.py` - Centralized MongoDB connection management
- `backend/server.py` - FastAPI app with lifespan manager
- `backend/runtime.txt` - Python version specification (`python-3.11.9`)

## Build & Run Commands

### Local Development
```bash
cd backend
pip install -r requirements.txt
export MONGODB_URI="mongodb+srv://..."
export DB_NAME="duesense"
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Build
```bash
cd backend
docker build -t duesense-backend .
docker run -p 10000:10000 -e MONGODB_URI="..." -e DB_NAME="..." duesense-backend
```

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `MONGODB_URI` or `MONGO_URL` | MongoDB Atlas connection string |
| `DB_NAME` | Database name (default: `duesense`) |

### Optional
| Variable | Description |
|----------|-------------|
| `PORT` | Server port (Render sets this, default: 8000) |
| `EMERGENT_LLM_KEY` | LLM API key for AI processing |
| `GROQ_API_KEY` | Alternative LLM provider |
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
