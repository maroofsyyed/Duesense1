# DueSense - VC Deal Intelligence Platform

AI-powered pitch deck analysis and investment memo generation for venture capitalists.

## Features

- **Pitch Deck Upload**: Upload PDF/PPTX pitch decks for automatic analysis
- **AI Analysis**: Automatic scoring across 6 investment dimensions using HuggingFace LLMs
- **Deep Enrichment**: Website analysis, GitHub activity, news, and competitor research
- **Investment Memos**: AI-generated comprehensive investment reports
- **Dashboard**: Deal pipeline overview with tier distribution

## Tech Stack

- **Backend**: FastAPI (Python 3.11.9)
- **Frontend**: React
- **Database**: MongoDB Atlas
- **LLM**: HuggingFace Inference API (Llama 3.1 70B, Mixtral 8x7B)
- **Deployment**: Render (backend), Vercel (frontend)

## Quick Start

### Prerequisites

- Python 3.11.9+
- Node.js 18+
- MongoDB Atlas account
- HuggingFace API key

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/DueSense.git
   cd DueSense
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   ```bash
   export MONGODB_URI="mongodb+srv://..."
   export DB_NAME="duesense"
   export HUGGINGFACE_API_KEY="hf_..."
   ```

4. **Run Backend**
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Frontend Setup** (optional - backend serves React build)
   ```bash
   cd frontend
   npm install
   npm run build
   cp -r build ../backend/static
   ```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with DB and LLM status |
| `POST /api/decks/upload` | Upload pitch deck |
| `GET /api/companies` | List all companies |
| `GET /api/companies/{id}` | Get company details |
| `GET /api/companies/{id}/score` | Get investment score |
| `GET /api/companies/{id}/memo` | Get investment memo |
| `GET /api/dashboard/stats` | Dashboard statistics |

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `DB_NAME` | Database name (default: `duesense`) |
| `HUGGINGFACE_API_KEY` | HuggingFace API token |

### Optional

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub token for repo analysis |
| `NEWS_API_KEY` | NewsAPI key for news enrichment |
| `SERPAPI_KEY` | SerpAPI key for search enrichment |
| `MAX_FILE_SIZE_MB` | Max upload size (default: 25) |

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

### Quick Deploy to Render

1. Connect GitHub repo to Render
2. Set root directory to `backend`
3. Add environment variables
4. Deploy

### Docker

```bash
cd backend
docker build -t duesense-backend .
docker run -p 10000:10000 \
  -e MONGODB_URI="mongodb+srv://..." \
  -e DB_NAME="duesense" \
  -e HUGGINGFACE_API_KEY="hf_..." \
  duesense-backend
```

## Architecture

```
DueSense/
├── backend/           # FastAPI backend
│   ├── server.py      # Main API server
│   ├── db.py          # MongoDB connection
│   ├── services/      # Business logic
│   │   ├── llm_provider.py      # HuggingFace LLM integration
│   │   ├── deck_processor.py    # Pitch deck extraction
│   │   ├── enrichment_engine.py # Data enrichment
│   │   ├── scorer.py            # Investment scoring
│   │   └── memo_generator.py    # Memo generation
│   └── api/           # API routes
├── frontend/          # React frontend
└── render.yaml        # Render deployment config
```

## LLM Models

DueSense uses HuggingFace Inference API with automatic fallback:

1. **Primary**: `meta-llama/Meta-Llama-3.1-70B-Instruct`
2. **Fallback 1**: `mistralai/Mixtral-8x7B-Instruct-v0.1`
3. **Fallback 2**: `meta-llama/Meta-Llama-3.1-8B-Instruct`
4. **Fallback 3**: `HuggingFaceH4/zephyr-7b-beta`

## License

MIT License

## Support

For deployment issues, see [DEPLOYMENT.md](./DEPLOYMENT.md) troubleshooting section.