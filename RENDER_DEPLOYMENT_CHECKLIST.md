# Render Deployment Checklist

**Critical Steps to Fix MongoDB SSL Error and Deploy Successfully**

---

## Pre-Deployment Verification

### ✅ Step 1: Verify Local Setup

Before deploying, test locally:

```bash
# Navigate to backend directory
cd backend

# Run the MongoDB connection test
python ../test_mongodb_connection.py
```

**Expected Output:**
```
✅ Python version is correct (3.11.x)
✅ certifi is installed
✅ pymongo is installed
✅ Successfully connected to MongoDB!
```

If any checks fail, fix them locally first.

---

### ✅ Step 2: Verify Files Are Correct

Check these files exist and have correct content:

#### `backend/runtime.txt`
**Location:** `DueSense/backend/runtime.txt`  
**Content (exactly):**
```
python-3.11.9
```

**Verify:**
- ✅ File exists in `backend/` folder (not root)
- ✅ Contains exactly `python-3.11.9` (no extra spaces, no capital letters)
- ✅ No blank lines after the version

#### `backend/requirements.txt`
**Must include:**
```
certifi==2024.8.30
pymongo==4.10.1
```

**Verify:**
- ✅ Both packages are listed
- ✅ Versions are specified (not just `certifi` and `pymongo`)

#### `backend/server.py`
**MongoDB connection code (lines 42-61) should include:**
```python
import certifi
...
client = MongoClient(
    MONGO_URL,
    tls=True,
    tlsAllowInvalidCertificates=False,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=10000,
)
```

**Verify:**
- ✅ `import certifi` is present
- ✅ `tlsCAFile=certifi.where()` is set
- ✅ `tls=True` is set

---

## Git Commit & Push

### ✅ Step 3: Stage All Changes

```bash
# From repository root
cd /Users/maroofakhtar/Documents/GitHub/DueSense

# Check what changed
git status

# Stage all changes
git add backend/runtime.txt
git add test_mongodb_connection.py
git add RENDER_DEPLOYMENT_CHECKLIST.md

# If runtime.txt was modified in root, remove it (we only need it in backend/)
git rm runtime.txt  # Only if it exists in root and shouldn't be there
```

### ✅ Step 4: Commit Changes

```bash
git commit -m "Fix: Add runtime.txt to backend folder for Render deployment

- Add runtime.txt in backend/ folder (Render Root Directory is backend)
- Create test_mongodb_connection.py for local verification
- Add RENDER_DEPLOYMENT_CHECKLIST.md with deployment steps
- Ensures Python 3.11.9 is used for MongoDB Atlas SSL compatibility"
```

### ✅ Step 5: Push to GitHub

```bash
git push origin main
```

**Verify push succeeded:**
- Check GitHub repository
- Confirm `backend/runtime.txt` exists in the repo
- Confirm it contains `python-3.11.9`

---

## Render Dashboard Configuration

### ✅ Step 6: Verify Render Service Settings

Go to: https://dashboard.render.com → Your Service → Settings

**Check these settings:**

1. **Root Directory:** Must be `backend`
   - ✅ Should say: `backend`
   - ❌ Should NOT be empty or `/`

2. **Build Command:** 
   - ✅ Should be: `pip install -r requirements.txt`

3. **Start Command:**
   - ✅ Should be: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - ❌ Should NOT be: `vicorn` (common typo)

4. **Environment Variables:**
   - ✅ `MONGO_URL` is set (not `MONGODB_URI`)
   - ✅ `DB_NAME` is set
   - ✅ All required API keys are set

---

## CRITICAL: Clear Build Cache

### ✅ Step 7: Clear Build Cache & Deploy

**THIS IS THE MOST IMPORTANT STEP!**

Render caches the Python installation. Even if `runtime.txt` is correct, Render will keep using the cached Python 3.13.4 unless you clear the cache.

**Steps:**

1. Go to Render Dashboard: https://dashboard.render.com
2. Click on your service (DueSense backend)
3. Click **"Manual Deploy"** dropdown (top right of the page)
4. Select **"Clear build cache & deploy"** ⚠️ **NOT** "Deploy latest commit"
5. Click **"Deploy"**
6. Wait for deployment to start

**Why this matters:**
- Regular "Deploy latest commit" does NOT clear the build cache
- Only "Clear build cache & deploy" forces Render to re-read `runtime.txt`
- Without clearing cache, Python 3.13.4 will continue to be used

---

## Monitor Deployment Logs

### ✅ Step 8: Watch for Python Version

**What to look for in logs:**

#### ✅ **SUCCESS - Correct Python Version:**
```
==> Installing Python version 3.11.9...
==> Using Python version 3.11.9 (default)
```

#### ❌ **FAILURE - Wrong Python Version:**
```
==> Installing Python version 3.13.4...
==> Using Python version 3.13.4 (default)
```

**If you see 3.13.4:**
1. Stop the deployment
2. Verify `backend/runtime.txt` exists in GitHub repo
3. Verify it contains exactly `python-3.11.9`
4. Clear build cache again
5. Redeploy

---

### ✅ Step 9: Watch for MongoDB Connection

**What to look for in logs:**

#### ✅ **SUCCESS - MongoDB Connected:**
```
✓ Successfully connected to MongoDB
INFO:     Uvicorn running on http://0.0.0.0:10000 (Press CTRL+C to quit)
```

#### ❌ **FAILURE - SSL Error:**
```
✗ MongoDB connection failed: SSL handshake failed: [SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error
```

**If you see SSL error:**
1. Check logs for Python version (should be 3.11.9)
2. If Python is 3.13.4, clear build cache and redeploy
3. If Python is 3.11.9 but still fails, check:
   - `certifi` is in requirements.txt
   - `tlsCAFile=certifi.where()` is in server.py
   - MongoDB Atlas network access allows Render IPs

---

## Success Indicators

### ✅ Step 10: Verify Deployment Success

**Check these in order:**

1. **Deployment Status:**
   - ✅ Render dashboard shows "Live" (green)
   - ❌ Not "Build failed" or "Deploy failed"

2. **Python Version in Logs:**
   - ✅ Logs show: `Using Python version 3.11.9`
   - ❌ NOT: `Using Python version 3.13.4`

3. **MongoDB Connection:**
   - ✅ Logs show: `✓ Successfully connected to MongoDB`
   - ❌ NOT: SSL handshake errors

4. **Server Running:**
   - ✅ Logs show: `Uvicorn running on http://0.0.0.0:XXXX`
   - ❌ NOT: Connection errors or crashes

5. **Health Check:**
   - Visit: `https://your-backend-url.onrender.com/api/health`
   - ✅ Should return: `{"status": "ok", "service": "vc-deal-intelligence"}`
   - ❌ Should NOT return: 500 error or connection refused

---

## Troubleshooting

### Problem: Still Using Python 3.13.4

**Symptoms:**
- Logs show: `Using Python version 3.13.4`
- MongoDB SSL errors persist

**Solutions (try in order):**

1. **Verify runtime.txt location:**
   ```bash
   # Check on GitHub
   # Should be at: backend/runtime.txt
   # NOT at: runtime.txt (root level)
   ```

2. **Verify runtime.txt content:**
   ```bash
   # On GitHub, view raw file
   # Should contain EXACTLY: python-3.11.9
   # No extra spaces, no capital letters
   ```

3. **Clear build cache again:**
   - Render Dashboard → Manual Deploy → Clear build cache & deploy
   - Wait for deployment to complete

4. **Alternative: Use Environment Variable:**
   - Render Dashboard → Environment
   - Add: `PYTHON_VERSION` = `3.11.9`
   - Save and redeploy with cleared cache

5. **Nuclear option:**
   - Delete the service in Render
   - Create a new service
   - Connect to GitHub repo
   - Fresh service should pick up runtime.txt correctly

---

### Problem: MongoDB SSL Error Persists

**Symptoms:**
- Python 3.11.9 is being used ✅
- But MongoDB connection still fails with SSL error

**Solutions:**

1. **Verify certifi is installed:**
   - Check deployment logs for: `Collecting certifi`
   - Should see: `Successfully installed certifi-2024.8.30`

2. **Verify server.py configuration:**
   - Check that `import certifi` is present
   - Check that `tlsCAFile=certifi.where()` is in MongoClient call

3. **Check MongoDB Atlas:**
   - MongoDB Atlas Dashboard → Network Access
   - Ensure "Allow access from anywhere" (0.0.0.0/0) is enabled
   - Or add Render's IP addresses

4. **Test connection string:**
   - Verify `MONGO_URL` environment variable is correct
   - Test it locally with `test_mongodb_connection.py`

---

### Problem: Build Fails

**Symptoms:**
- Deployment shows "Build failed"
- Logs show import errors or missing dependencies

**Solutions:**

1. **Check requirements.txt:**
   - Ensure all dependencies are listed
   - Verify no syntax errors

2. **Check Python version:**
   - If build fails with "Python version not found"
   - Verify `runtime.txt` contains `python-3.11.9` (not `3.11.9` or `Python-3.11.9`)

3. **Check Root Directory:**
   - Render Settings → Root Directory should be `backend`
   - This ensures `requirements.txt` and `runtime.txt` are found

---

## Quick Reference

### Files to Commit:
- ✅ `backend/runtime.txt` (contains `python-3.11.9`)
- ✅ `test_mongodb_connection.py` (for local testing)
- ✅ `RENDER_DEPLOYMENT_CHECKLIST.md` (this file)

### Render Settings:
- **Root Directory:** `backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`

### Critical Step:
- **MUST clear build cache** before deploying
- Use: Manual Deploy → "Clear build cache & deploy"
- NOT: "Deploy latest commit"

### Success Log Messages:
```
==> Using Python version 3.11.9 (default)
✓ Successfully connected to MongoDB
INFO:     Uvicorn running on http://0.0.0.0:XXXX
```

---

## Final Checklist

Before considering deployment complete:

- [ ] `backend/runtime.txt` exists and contains `python-3.11.9`
- [ ] All changes committed and pushed to GitHub
- [ ] Build cache cleared in Render dashboard
- [ ] Deployment logs show Python 3.11.9 (not 3.13.4)
- [ ] Deployment logs show "✓ Successfully connected to MongoDB"
- [ ] Health check endpoint returns `{"status": "ok"}`
- [ ] No SSL/TLS errors in logs

**If all checkboxes are ✅, your deployment is successful!**

---

## Need Help?

If deployment still fails after following all steps:

1. **Share deployment logs** (especially the Python version line)
2. **Share error messages** (full text, not just summary)
3. **Verify file locations** on GitHub (screenshot if needed)
4. **Check Render service settings** (screenshot if needed)

Common issues are:
- Build cache not cleared (most common)
- Wrong runtime.txt location
- Wrong runtime.txt format
- Missing environment variables

