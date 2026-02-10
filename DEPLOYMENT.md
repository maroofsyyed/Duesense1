# Production Deployment Guide

**For Non-Technical Founders**

This guide walks you through deploying DueSense to production using free hosting tiers. No coding or DevOps experience required—just follow the steps.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Backend Deployment (Render)](#backend-deployment-render)
3. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
4. [DNS Configuration](#dns-configuration)
5. [Production Verification](#production-verification)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- ✅ A GitHub account
- ✅ Your code pushed to GitHub repository: `maroofsyyed-duesense`
- ✅ All API keys and secrets ready (MongoDB Atlas, HuggingFace API key, GitHub token, optional: ScraperAPI, SerpAPI, NewsAPI)
- ✅ Domain name: `dominionvault.com` (with DNS access)
- ✅ Render account (free tier)
- ✅ Vercel account (free tier)

**Note:** All API keys should already exist. We will add them as environment variables—never paste them in code or documentation.

---

## Backend Deployment (Render)

### Step 1: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with your GitHub account (recommended) or email
3. Verify your email if prompted

### Step 2: Create New Web Service

1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Connect your GitHub account if not already connected
3. Select repository: **`maroofsyyed-duesense`**
4. Click **"Connect"**

### Step 3: Configure Service Settings

Fill in the following:

- **Name:** `duesense-backend` (or any name you prefer)
- **Region:** Choose closest to your users (e.g., `Oregon (US West)`)
- **Branch:** `main` (or your default branch)
- **Root Directory:** `backend`
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
  - ⚠️ **CRITICAL:** The command is `uvicorn` (not `vicorn`). This is a common typo that will cause deployment failures.

**Important:** 
- Render automatically sets the `PORT` environment variable. Your app reads it via `os.environ.get("PORT", 8000)`.
- **Python Version:** The repository includes `backend/runtime.txt` specifying Python 3.11.9. This version is required for MongoDB Atlas SSL/TLS compatibility. Render will automatically use this version. If you need to change it, update `runtime.txt` or set `PYTHON_VERSION=3.11.9` in Render environment variables.

### Step 4: Add Environment Variables

In the **"Environment"** section, add these variables one by one:

#### Required Variables

```
MONGODB_URI
```
- **Value:** Your MongoDB Atlas connection string (starts with `mongodb+srv://`)
- **Format:** `mongodb+srv://<username>:<password>@cluster.mongodb.net/<database>?retryWrites=true&w=majority`
- **Important:** 
  - You can use either `MONGODB_URI` or `MONGO_URL` (the app accepts both)
  - Password should be URL-encoded if it contains special characters
  - No spaces in the connection string

```
DB_NAME
```
- **Value:** Your MongoDB database name (e.g., `duesense`)

```
HUGGINGFACE_API_KEY
```
- **Value:** Your HuggingFace API token (starts with `hf_`)
- **Get it from:** [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
- **Note:** You can also use `HF_TOKEN` as the variable name

#### Optional Configuration

```
MAX_FILE_SIZE_MB
```
- **Value:** `25` (default, adjust if needed)

#### Optional Enrichment API Keys

```
GITHUB_TOKEN
```
- **Value:** Your GitHub personal access token (for repository analysis)

```
NEWS_API_KEY
```
- **Value:** Your NewsAPI key (for news enrichment)

```
SERPAPI_KEY
```
- **Value:** Your SerpAPI key (for search enrichment)

```
SCRAPER_API_KEY
```
- **Value:** Your ScraperAPI key (for web scraping)

**How to add each variable:**
1. Click **"Add Environment Variable"**
2. Enter the **Key** (exactly as shown above)
3. Paste the **Value** (your actual API key/secret)
4. Click **"Save Changes"**

### Step 5: Deploy

1. Scroll to the bottom
2. Click **"Create Web Service"**
3. Render will:
   - Clone your repository
   - Install dependencies from `requirements.txt`
   - Start your FastAPI server
4. Wait 3-5 minutes for the first deployment

**Note:** If you need to change Python version or update `runtime.txt` after initial deployment:
- Go to Render dashboard → Your Service → Manual Deploy
- Select **"Clear build cache & deploy"**
- This ensures Render uses the Python version from `runtime.txt`

### Step 6: Get Your Backend URL

Once deployed, Render provides a URL like:
```
https://duesense-backend-xxxx.onrender.com
```

**Save this URL**—you'll need it for the frontend configuration.

### Step 7: Test Backend Health

Open your browser and visit:
```
https://your-backend-url.onrender.com/api/health
```

You should see:
```json
{"status": "ok", "service": "vc-deal-intelligence"}
```

If you see this, your backend is live! ✅

---

## Frontend Deployment (Vercel)

### Step 1: Create Vercel Account

1. Go to [vercel.com](https://vercel.com)
2. Sign up with your GitHub account (recommended)
3. Complete onboarding

### Step 2: Import Project

1. In Vercel dashboard, click **"Add New..."** → **"Project"**
2. Find and select repository: **`maroofsyyed-duesense`**
3. Click **"Import"**

### Step 3: Configure Project Settings

- **Framework Preset:** `Create React App` (auto-detected)
- **Root Directory:** `frontend`
- **Build Command:** `npm run build` (auto-filled)
- **Output Directory:** `build` (auto-filled)
- **Install Command:** `npm install` (auto-filled)

### Step 4: Add Environment Variables

In the **"Environment Variables"** section, add:

```
REACT_APP_BACKEND_URL
```
- **Value:** Your Render backend URL (from Step 6 above)
  - Example: `https://duesense-backend-xxxx.onrender.com`
  - **Important:** Do NOT include a trailing slash

**How to add:**
1. Click **"Add"** under Environment Variables
2. Key: `REACT_APP_BACKEND_URL`
3. Value: Your backend URL
4. Click **"Save"**

### Step 5: Deploy

1. Click **"Deploy"**
2. Vercel will:
   - Install npm dependencies
   - Build your React app
   - Deploy to a Vercel URL
3. Wait 2-3 minutes for the first deployment

### Step 6: Get Your Frontend URL

Once deployed, Vercel provides a URL like:
```
https://duesense-frontend.vercel.app
```

**Save this URL**—you'll use it for DNS configuration.

---

## DNS Configuration

This section connects your domain `dominionvault.com` to your deployed applications.

### Step 1: Access Your Domain Registrar

1. Log in to where you purchased `dominionvault.com` (e.g., GoDaddy, Namecheap, Google Domains)
2. Find **"DNS Management"** or **"DNS Settings"**

### Step 2: Configure Frontend (dominionvault.com)

#### Option A: Using Vercel's DNS (Recommended)

1. In Vercel project settings, go to **"Domains"**
2. Click **"Add Domain"**
3. Enter: `dominionvault.com`
4. Vercel will show DNS records to add:
   - **Type:** `A` or `CNAME`
   - **Name:** `@` or `dominionvault.com`
   - **Value:** Vercel's IP or CNAME target
5. Copy these records
6. In your domain registrar's DNS settings, add the records Vercel provided
7. Wait 5-60 minutes for DNS propagation

#### Option B: Manual DNS Configuration

Add these DNS records in your registrar:

**For apex domain (dominionvault.com):**
- **Type:** `CNAME`
- **Name:** `@` (or leave blank, depends on registrar)
- **Value:** `cname.vercel-dns.com`

**Alternative (if CNAME not supported for apex):**
- **Type:** `A`
- **Name:** `@`
- **Value:** `76.76.21.21` (Vercel's IP - verify in Vercel dashboard)

### Step 3: Configure Backend Subdomain (api.dominionvault.com)

#### Option A: Using Render Custom Domain

1. In Render service settings, go to **"Custom Domains"**
2. Click **"Add Custom Domain"**
3. Enter: `api.dominionvault.com`
4. Render will provide DNS records:
   - **Type:** `CNAME`
   - **Name:** `api`
   - **Value:** Render's CNAME target (e.g., `duesense-backend-xxxx.onrender.com`)
5. Add this CNAME record in your domain registrar:
   - **Type:** `CNAME`
   - **Name:** `api`
   - **Value:** (the value Render provided)
6. Wait 5-60 minutes for DNS propagation

#### Option B: Keep Render URL (Simpler)

If you prefer not to set up a subdomain, you can:
- Keep using the Render URL directly
- Update `REACT_APP_BACKEND_URL` in Vercel to point to the Render URL
- No DNS changes needed for backend

### Step 4: Verify DNS Propagation

After adding DNS records, verify they're working:

1. Visit [whatsmydns.net](https://www.whatsmydns.net)
2. Check `dominionvault.com` → Should point to Vercel
3. Check `api.dominionvault.com` → Should point to Render (if configured)

**Note:** DNS changes can take up to 48 hours, but usually work within 1 hour.

---

## Production Verification

Run through this checklist to ensure everything works:

### Backend Checks

- [ ] **Health Endpoint**
  - Visit: `https://your-backend-url.onrender.com/api/health`
  - Expected: `{"status": "ok", "service": "vc-deal-intelligence"}`

- [ ] **Python Version**
  - Check Render logs for: "Using Python version 3.11.9"
  - Verify `backend/runtime.txt` contains `python-3.11.9`
  - If wrong version, clear build cache and redeploy

- [ ] **MongoDB Connection**
  - Check Render logs for MongoDB connection errors
  - If errors, verify `MONGO_URL` and `DB_NAME` are correct
  - Verify no SSL/TLS handshake errors (indicates Python version issue)

- [ ] **API Endpoints**
  - Test: `https://your-backend-url.onrender.com/api/companies`
  - Expected: JSON response (may be empty array `{"companies": []}`)

### Frontend Checks

- [ ] **Frontend Loads**
  - Visit: `https://your-frontend-url.vercel.app` or `https://dominionvault.com`
  - Expected: Your React app loads without errors

- [ ] **API Connection**
  - Open browser DevTools (F12) → Console tab
  - Look for API errors
  - If errors about CORS or connection, verify `REACT_APP_BACKEND_URL` is correct

- [ ] **Upload Functionality**
  - Try uploading a test PDF/PPTX file
  - Check if it reaches the backend (check Render logs)

### Domain Checks

- [ ] **Main Domain**
  - Visit: `https://dominionvault.com`
  - Expected: Your frontend loads

- [ ] **API Subdomain** (if configured)
  - Visit: `https://api.dominionvault.com/api/health`
  - Expected: `{"status": "ok", "service": "vc-deal-intelligence"}`

### Integration Checks

- [ ] **External APIs**
  - Test a full workflow (upload deck → processing → enrichment)
  - Check Render logs for API key errors
  - Verify all required API keys are set in Render environment variables

---

## Troubleshooting

### Backend Issues

#### Problem: Backend won't start

**Symptoms:**
- Render shows "Build failed" or "Deploy failed"
- Logs show import errors or missing dependencies

**Solutions:**
1. Check Render logs (click "Logs" tab in Render dashboard)
2. Verify `requirements.txt` exists in `backend/` directory
3. Ensure `server.py` is in the `backend/` directory
4. Check that all Python dependencies are listed in `requirements.txt`

#### Problem: "vicorn: command not found" error

**Symptoms:**
- Render logs show: `bash: vicorn: command not found`
- Deployment fails immediately after build succeeds

**Root Cause:**
- Typo in Render start command: `vicorn` instead of `uvicorn`

**Solutions:**
1. Go to Render dashboard → Your service → Settings
2. Scroll to "Start Command"
3. Verify it says: `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. If it says `vicorn`, change it to `uvicorn` (note the "u" at the beginning)
5. Save changes and redeploy
6. **Correct command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`

#### Problem: Python version SSL/TLS compatibility issues

**Symptoms:**
- MongoDB connection fails with SSL/TLS handshake errors
- Logs show: `SSL: CERTIFICATE_VERIFY_FAILED` or similar
- Application fails to connect to MongoDB Atlas

**Root Cause:**
- Python 3.13.4 has known SSL/TLS compatibility issues with MongoDB Atlas
- Application requires Python 3.11.9 for proper MongoDB connectivity

**Solutions:**
1. **Verify `runtime.txt` exists:**
   - Check that `backend/runtime.txt` contains: `python-3.11.9`
   - If missing or incorrect, create/update the file

2. **Clear Build Cache:**
   - In Render dashboard → Your Service
   - Click "Manual Deploy" → "Clear build cache & deploy"
   - This forces Render to use the Python version from `runtime.txt`

3. **Verify Python Version in Logs:**
   - After deployment, check Render logs
   - Look for: "Using Python version 3.11.9" (not 3.13.4)
   - If wrong version appears, verify `runtime.txt` is in `backend/` directory

4. **Alternative: Set Environment Variable:**
   - In Render → Environment Variables
   - Add: `PYTHON_VERSION=3.11.9`
   - This overrides any other Python version settings

#### Problem: MongoDB connection fails

**Symptoms:**
- Logs show: `MongoDB connection failed`
- Health endpoint returns 500 error
- SSL/TLS handshake errors

**Solutions:**
1. **Verify Python Version:**
   - Check Render logs for Python version (should be 3.11.9)
   - Verify `backend/runtime.txt` contains `python-3.11.9`
   - Python 3.13.4 has known SSL/TLS compatibility issues with MongoDB Atlas
   - If using wrong version, update `runtime.txt` and clear build cache

2. **Verify MongoDB Connection String:**
   - Environment variable must be `MONGO_URL` (not `MONGODB_URI`)
   - Should start with `mongodb+srv://`
   - Format: `mongodb+srv://<username>:<password>@cluster.mongodb.net/<database>?retryWrites=true&w=majority`
   - Check for typos
   - Password should be URL-encoded if it contains special characters

3. **Network Access:**
   - Ensure MongoDB Atlas allows connections from Render IPs
   - Go to MongoDB Atlas → Network Access
   - Add `0.0.0.0/0` (allow from anywhere) for testing, or whitelist Render IPs
   - Verify `DB_NAME` matches your MongoDB database name

4. **Clear Build Cache:**
   - In Render dashboard → Your Service → Manual Deploy
   - Select "Clear build cache & deploy"
   - This ensures the correct Python version is used

#### Problem: API keys not working

**Symptoms:**
- Enrichment fails
- External API calls return 401/403 errors

**Solutions:**
1. Double-check environment variable names in Render (case-sensitive)
2. Verify API keys are valid (test in API provider dashboard)
3. Check API rate limits (free tiers may have limits)
4. Review Render logs for specific error messages

#### Problem: File upload fails

**Symptoms:**
- Upload returns 400 error
- "File exceeds limit" message

**Solutions:**
1. Check `MAX_FILE_SIZE_MB` in Render (default: 25MB)
2. Verify file is under the limit
3. Check Render logs for detailed error messages

### Frontend Issues

#### Problem: Frontend shows blank page

**Symptoms:**
- Page loads but shows white/blank screen
- Browser console shows errors

**Solutions:**
1. Open browser DevTools (F12) → Console tab
2. Look for JavaScript errors
3. Common issues:
   - `REACT_APP_BACKEND_URL` not set or incorrect
   - Build failed (check Vercel deployment logs)
   - Missing environment variable

#### Problem: API calls fail (CORS errors)

**Symptoms:**
- Browser console shows: `CORS policy` errors
- API requests blocked

**Solutions:**
1. Verify `REACT_APP_BACKEND_URL` in Vercel matches your Render backend URL
2. Check backend CORS settings (your code allows `allow_origins=["*"]`, so this should work)
3. Ensure backend URL has no trailing slash
4. Try hard refresh (Ctrl+Shift+R or Cmd+Shift+R)

#### Problem: Frontend can't connect to backend

**Symptoms:**
- Network errors in browser console
- "Failed to fetch" messages

**Solutions:**
1. Verify `REACT_APP_BACKEND_URL` is set correctly in Vercel
2. Test backend URL directly in browser: `https://your-backend-url.onrender.com/api/health`
3. Check if backend is running (Render dashboard → check service status)
4. Rebuild frontend after changing environment variables (Vercel → Redeploy)

### DNS Issues

#### Problem: Domain not resolving

**Symptoms:**
- `dominionvault.com` shows "Site can't be reached"
- DNS lookup fails

**Solutions:**
1. Verify DNS records in your registrar:
   - Check record type (CNAME vs A)
   - Check record name (`@` vs `dominionvault.com`)
   - Check record value (must match Vercel/Render exactly)
2. Wait longer (DNS can take up to 48 hours)
3. Use [whatsmydns.net](https://www.whatsmydns.net) to check propagation globally
4. Clear DNS cache:
   - Windows: `ipconfig /flushdns`
   - Mac: `sudo dscacheutil -flushcache`
   - Linux: `sudo systemd-resolve --flush-caches`

#### Problem: SSL certificate errors

**Symptoms:**
- Browser shows "Not Secure" or SSL warnings
- Certificate not issued

**Solutions:**
1. Vercel and Render automatically provision SSL certificates
2. Wait 5-10 minutes after DNS propagation
3. If still failing after 24 hours, check:
   - DNS records are correct
   - Domain is properly connected in Vercel/Render dashboards
   - Contact Vercel/Render support if needed

### Performance Issues

#### Problem: Slow response times

**Symptoms:**
- API calls take 10+ seconds
- Frontend loads slowly

**Solutions:**
1. **Render Free Tier Limitations:**
   - Free tier services spin down after 15 minutes of inactivity
   - First request after spin-down takes 30-60 seconds (cold start)
   - This is normal for free tier
   - Consider upgrading to paid tier for consistent performance
2. **Vercel Free Tier:**
   - Generally fast, but check Vercel dashboard for any issues
3. **Database:**
   - MongoDB Atlas M0 (free) has performance limits
   - Check MongoDB Atlas dashboard for connection/query performance

#### Problem: Render service sleeping

**Symptoms:**
- Backend works but goes to sleep
- First request after inactivity times out

**Solutions:**
1. This is expected on Render free tier
2. Options:
   - Accept the cold start delay (30-60 seconds)
   - Upgrade to Render paid tier ($7/month) for always-on service
   - Use a free uptime monitor (e.g., UptimeRobot) to ping your service every 5 minutes

### Common Mistakes

1. **Typo in start command: `vicorn` instead of `uvicorn`**
   - ❌ `vicorn server:app --host 0.0.0.0 --port $PORT`
   - ✅ `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - This typo causes: `bash: vicorn: command not found`

2. **Wrong Python version causing MongoDB SSL/TLS issues**
   - ❌ Using Python 3.13.4 (has SSL/TLS compatibility issues)
   - ✅ Using Python 3.11.9 (specified in `backend/runtime.txt`)
   - **Fix:** Ensure `backend/runtime.txt` contains `python-3.11.9`
   - **Fix:** Clear build cache in Render after updating `runtime.txt`

3. **MongoDB environment variable**
   - ✅ Both `MONGODB_URI` and `MONGO_URL` are accepted
   - The app checks for either variable

4. **Trailing slashes in URLs**
   - ❌ `https://backend.onrender.com/`
   - ✅ `https://backend.onrender.com`

5. **Wrong environment variable names**
   - Must match exactly (case-sensitive)
   - Check spelling: `MONGO_URL` not `MONGO_URI` or `MONGODB_URI`

6. **Missing environment variables**
   - All required variables must be set
   - Check Render/Vercel dashboards to verify all are present

7. **Wrong root directory**
   - Render: `backend` (not root)
   - Vercel: `frontend` (not root)

8. **Build command errors**
   - Ensure `requirements.txt` is in `backend/`
   - Ensure `package.json` is in `frontend/`
   - Ensure `runtime.txt` is in `backend/` for Python version specification

---

## Next Steps

After successful deployment:

1. **Monitor Logs**
   - Check Render logs regularly for errors
   - Check Vercel logs for frontend issues

2. **Set Up Monitoring** (Optional)
   - Use free services like UptimeRobot to monitor your backend
   - Set up error alerts

3. **Backup Strategy**
   - MongoDB Atlas provides automatic backups on paid tiers
   - Consider exporting data regularly

4. **Security**
   - Never commit API keys to GitHub
   - Rotate API keys periodically
   - Review API key permissions

5. **Scaling Considerations**
   - Free tiers have limits (requests, compute time, etc.)
   - Monitor usage in Render/Vercel dashboards
   - Plan for paid tiers when you outgrow free limits

---

## Support Resources

- **Render Documentation:** [render.com/docs](https://render.com/docs)
- **Vercel Documentation:** [vercel.com/docs](https://vercel.com/docs)
- **MongoDB Atlas:** [docs.atlas.mongodb.com](https://docs.atlas.mongodb.com)
- **FastAPI Documentation:** [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **React Documentation:** [react.dev](https://react.dev)

---

## Quick Reference

### Backend URL
```
https://your-backend-name.onrender.com
```

### Frontend URL
```
https://your-frontend-name.vercel.app
```

### Production Domain
```
https://dominionvault.com
```

### API Subdomain (if configured)
```
https://api.dominionvault.com
```

### Health Check Endpoint
```
https://your-backend-url.onrender.com/api/health
```

---

**Last Updated:** Deployment guide for DueSense production deployment
**Version:** 1.0

