# DueSense Production Deployment Checklist

**Last Updated:** February 2024  
**Status:** Ready for deployment after fixes applied

---

## Summary of Fixes Applied

### Critical Build Fixes ✅
1. **Dockerfile** - Removed pymongo references, updated to verify Supabase SDK
2. **api/v1/health.py** - Changed from MongoDB commands to Supabase queries
3. **render.yaml** - Updated environment variables for Supabase

### Documentation Updates ✅
1. **DEPLOYMENT.md** - Comprehensive update for Supabase configuration
2. **AGENTS.md** - Updated architecture and environment variable documentation

---

## Pre-Deployment Checklist

### Supabase Setup (REQUIRED)

- [ ] Create Supabase project at [supabase.com](https://supabase.com)
- [ ] Go to **Settings → API** and copy:
  - [ ] Project URL → `SUPABASE_URL`
  - [ ] Service Role Key → `SUPABASE_SERVICE_ROLE_KEY` (NOT anon key!)
- [ ] Run schema in Supabase:
  - [ ] Go to **SQL Editor → New Query**
  - [ ] Copy contents of `backend/database/schema.sql`
  - [ ] Execute the SQL
- [ ] Verify tables created:
  - [ ] `companies`
  - [ ] `pitch_decks`
  - [ ] `founders`
  - [ ] `enrichment_sources`
  - [ ] `competitors`
  - [ ] `investment_scores`
  - [ ] `investment_memos`

### Render Backend Setup (REQUIRED)

- [ ] Create Render account at [render.com](https://render.com)
- [ ] Create new Web Service from GitHub repo
- [ ] Configure settings:
  - [ ] **Root Directory:** `backend`
  - [ ] **Runtime:** Docker
  - [ ] **Dockerfile Path:** `./Dockerfile`
  - [ ] **Health Check Path:** `/health`

### Environment Variables (REQUIRED)

Set these in Render dashboard → Environment:

| Variable | Required | Value |
|----------|----------|-------|
| `SUPABASE_URL` | ✅ | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | `eyJ...` (from Supabase) |
| **LLM key:** | | |
| `Z_API_KEY` | ✅ | Z.ai API key (required) |
| **Security:** | | |
| `DUESENSE_API_KEY` | ✅ Prod | Generate: `openssl rand -hex 32` |
| `ENABLE_DEMO_KEY` | ✅ Prod | `false` (IMPORTANT!) |
| **CORS:** | | |
| `ALLOWED_ORIGINS` | ✅ Prod | Your frontend URL(s), comma-separated |

### Optional Environment Variables

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub repository analysis |
| `NEWS_API_KEY` | News article enrichment |
| `SERPAPI_KEY` | Search/competitor research |
| `MAX_FILE_SIZE_MB` | Upload limit (default: 25) |
| `LOG_LEVEL` | Logging verbosity (default: INFO) |

---

## Vercel Frontend Setup (OPTIONAL)

If deploying frontend separately:

- [ ] Create Vercel account at [vercel.com](https://vercel.com)
- [ ] Import GitHub repository
- [ ] Configure settings:
  - [ ] **Root Directory:** `frontend`
  - [ ] **Framework:** Create React App
- [ ] Set environment variable:
  - [ ] `REACT_APP_BACKEND_URL` = Your Render backend URL

---

## Post-Deployment Verification

### Health Check Endpoints

After deployment, verify these URLs return expected responses:

```bash
# Main health check (should return 200)
curl https://YOUR-BACKEND-URL/health

# Expected response:
{
  "status": "healthy",
  "database": {"status": "connected", "type": "supabase", ...},
  "llm": {"status": "ready", ...},
  ...
}

# API v1 health
curl https://YOUR-BACKEND-URL/api/v1/health

# Liveness probe
curl https://YOUR-BACKEND-URL/api/v1/health/live

# Readiness probe
curl https://YOUR-BACKEND-URL/api/v1/health/ready
```

### API Authentication Test

```bash
# Test with your API key
curl -H "X-API-Key: YOUR_DUESENSE_API_KEY" \
  https://YOUR-BACKEND-URL/api/v1/deals

# Expected: 200 OK with deals list (possibly empty)
```

### Full Pipeline Test

1. Upload a test pitch deck:
```bash
curl -X POST \
  -H "X-API-Key: YOUR_DUESENSE_API_KEY" \
  -F "file=@test.pdf" \
  -F "company_website=https://example.com" \
  https://YOUR-BACKEND-URL/api/v1/ingestion/upload
```

2. Check processing status:
```bash
curl -H "X-API-Key: YOUR_DUESENSE_API_KEY" \
  https://YOUR-BACKEND-URL/api/v1/ingestion/status/{deck_id}
```

3. Verify company data:
```bash
curl -H "X-API-Key: YOUR_DUESENSE_API_KEY" \
  https://YOUR-BACKEND-URL/api/v1/deals/{company_id}
```

---

## Expected Behavior After Deployment

| Metric | Expected Value |
|--------|----------------|
| Build Time | 2-3 minutes |
| Health Check | 200 OK |
| Cold Start | 30-60 seconds (free tier) |
| Upload Response | ~1 second |
| Full Processing | 2-5 minutes |
| Max File Size | 25 MB (configurable) |

---

## Troubleshooting Quick Reference

### Build Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: pymongo` | Old Dockerfile | Pull latest code with fixed Dockerfile |
| `No module named 'supabase'` | Missing dependency | Check requirements.txt |
| SSL/TLS errors | Python version | Ensure Docker runtime is used |

### Runtime Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "SUPABASE_URL not set" | Missing env var | Add in Render dashboard |
| "No LLM API keys" | Missing env var | Add at least one LLM key |
| Database "unhealthy" | Schema not run | Run schema.sql in Supabase |
| 401 Unauthorized | Invalid API key | Check DUESENSE_API_KEY |
| CORS errors | Missing origin | Add frontend URL to ALLOWED_ORIGINS |

### Performance Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Slow first request | Cold start | Normal for free tier, or upgrade |
| Timeout on upload | File too large | Check MAX_FILE_SIZE_MB |
| LLM timeout | Model unavailable | System will auto-fallback |

---

## Security Checklist

- [ ] `ENABLE_DEMO_KEY` set to `false`
- [ ] `DUESENSE_API_KEY` is a strong random string
- [ ] No API keys in git repository
- [ ] `ALLOWED_ORIGINS` restricts CORS appropriately
- [ ] Service role key (not anon key) used for Supabase

---

## Monitoring Recommendations

1. **UptimeRobot** (free) - Ping `/health` every 5 minutes
2. **Render Logs** - Check for errors regularly
3. **Supabase Dashboard** - Monitor database usage
4. **LLM Provider Dashboard** - Monitor API usage/limits

---

## Files Changed in This Fix

| File | Change |
|------|--------|
| `backend/Dockerfile` | Removed pymongo, verify Supabase SDK |
| `backend/api/v1/health.py` | Changed to Supabase queries, added LLM check |
| `render.yaml` | Updated env vars for Supabase |
| `DEPLOYMENT.md` | Comprehensive Supabase documentation |
| `AGENTS.md` | Updated architecture documentation |

---

**Ready to deploy!** Follow the checklist above in order.
