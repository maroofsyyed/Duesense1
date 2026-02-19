# Skill: Deploy Backend to Render

## Prerequisites

- Render account connected to GitHub repo
- All environment variables set in Render dashboard
- Supabase schema executed (`backend/database/schema.sql`)

## Steps

### 1. Verify Local Build

```bash
cd backend
docker build -t duesense-backend .
```

Ensure build completes without errors.

### 2. Verify Environment Variables in Render

Required variables (check in Render dashboard → Environment):

| Variable | Set? |
|----------|------|
| `SUPABASE_URL` | ☐ |
| `SUPABASE_SERVICE_ROLE_KEY` | ☐ |
| At least one LLM key | ☐ |
| `DUESENSE_API_KEY` | ☐ |
| `ENABLE_DEMO_KEY=false` | ☐ |
| `ALLOWED_ORIGINS` | ☐ |

### 3. Deploy

- Push changes to `main` branch (auto-deploys), OR
- Trigger manual deploy from Render dashboard
- Clear build cache if previous deploy failed

### 4. Verify Deployment

```bash
# Health check (expect 200)
curl https://YOUR-BACKEND-URL/health

# API auth test
curl -H "X-API-Key: YOUR_KEY" https://YOUR-BACKEND-URL/api/v1/deals

# Liveness probe
curl https://YOUR-BACKEND-URL/api/v1/health/live

# Readiness probe
curl https://YOUR-BACKEND-URL/api/v1/health/ready
```

### 5. Smoke Test

Upload a test pitch deck and verify the full pipeline completes:

```bash
curl -X POST \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@test.pdf" \
  https://YOUR-BACKEND-URL/api/v1/ingestion/upload
```

## Troubleshooting

See `PRODUCTION_CHECKLIST.md` for common issues and fixes.
