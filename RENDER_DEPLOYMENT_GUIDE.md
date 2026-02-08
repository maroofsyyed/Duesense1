# RENDER DEPLOYMENT GUIDE
## Complete Step-by-Step Instructions for DueSense Backend

---

## ⚠️ CRITICAL: Understanding Render's Build Cache System

### Why "Deploy latest commit" Doesn't Work

**Render's Build Process:**
1. Checks cache for existing Python installation
2. If Python 3.13.4 is cached → **USES IT** (ignores `runtime.txt`)
3. Only reads `runtime.txt` on **FRESH BUILD** (no cache)

**Why This Matters:**
- ❌ Regular deploy = uses cached Python 3.13.4
- ✅ Clear cache deploy = reads `runtime.txt`, installs Python 3.11.9

**Root Directory Setting:**
- If set to `backend/` → looks for `runtime.txt` in `backend/runtime.txt`
- If set to `/` → looks for `runtime.txt` in root `runtime.txt`

---

## 📋 STEP 1: PRE-DEPLOYMENT CHECKLIST

### Code Changes Verification (by Agents 1-3)

- [ ] **requirements.txt** has compatible motor + pymongo versions
  - ✅ Current: `motor==3.7.1`, `pymongo==4.10.1`
  - ✅ `certifi==2024.8.30` is included
  
- [ ] **backend/runtime.txt** exists with `python-3.11.9`
  - ✅ Verified: File exists at `backend/runtime.txt`
  - ✅ Content: `python-3.11.9`

- [ ] **backend/server.py** has MongoDB SSL config with certifi
  - ✅ Verified: Line 14 imports `certifi`
  - ✅ Verified: Line 48 uses `tlsCAFile=certifi.where()`
  - ✅ Verified: SSL/TLS configuration is present

- [ ] **test_mongodb_connection.py** created
  - ✅ Verified: File exists at root level

- [ ] **render.yaml** exists with correct configuration
  - ✅ Verified: File exists
  - ✅ Root directory: `backend`
  - ✅ Python version env var: `3.11.9`

### Local Testing

- [ ] Run: `python test_mongodb_connection.py`
  ```bash
  cd /Users/maroofakhtar/Documents/GitHub/DueSense
  python test_mongodb_connection.py
  ```
  
- [ ] All tests pass locally
  - Python 3.11.x detected
  - Certifi installed and working
  - MongoDB connection works
  - SSL/TLS handshake successful

### Git Status

- [ ] All changes committed
  ```bash
  git status
  # Should show "nothing to commit, working tree clean"
  ```

- [ ] All changes pushed to GitHub
  ```bash
  git log --oneline -1
  # Verify latest commit is present
  ```

- [ ] Correct branch (main/master)
  ```bash
  git branch
  # Should be on main or master
  ```

### Render Dashboard

- [ ] Service exists and is selected
  - Navigate to: https://dashboard.render.com
  - Select your service: `duesense-backend`

- [ ] Root Directory = `backend/`
  - Go to Settings tab
  - Verify "Root Directory" is set to `backend/`

- [ ] Environment variables set
  - `MONGODB_URI` or `MONGO_URL` (with MongoDB connection string)
  - `DB_NAME` (database name)
  - Any other required env vars

- [ ] Ready to clear build cache
  - Have Render dashboard open
  - Know which service to deploy

---

## 🔧 STEP 2: GIT COMMIT COMMANDS

**⚠️ Only run these if you haven't committed changes yet!**

```bash
# Navigate to repository
cd /Users/maroofakhtar/Documents/GitHub/DueSense

# Check what changed
git status

# Review changes (optional)
git diff

# Stage all changes
git add backend/runtime.txt \
        backend/requirements.txt \
        backend/server.py \
        test_mongodb_connection.py \
        render.yaml

# Commit with descriptive message
git commit -m "Fix: Resolve deployment issues for Render

- Fix motor/pymongo dependency conflict (pymongo 4.10.1)
- Add backend/runtime.txt for Python 3.11.9
- Update MongoDB connection with certifi SSL config
- Add test_mongodb_connection.py for verification
- Add render.yaml for explicit deployment config

Fixes SSL handshake error and dependency conflicts"

# Push to GitHub
git push origin main

# Verify push
git log --oneline -1
```

**Note:** If you're on a different branch, replace `main` with your branch name (e.g., `master`).

---

## 🚀 STEP 3: RENDER DEPLOYMENT STEPS (CRITICAL)

### EXACT STEPS IN RENDER DASHBOARD

#### Step 1: Navigate to Service
1. Go to: https://dashboard.render.com
2. Click on your service name (`duesense-backend` or similar)

#### Step 2: Clear Build Cache (CRITICAL!)
3. Look in **top-right corner** for "Manual Deploy" button
4. Click **dropdown arrow** next to "Manual Deploy"
5. Select **"Clear build cache & deploy"**
6. Confirm the action

⚠️ **DO NOT** select "Deploy latest commit" - it won't clear cache!
⚠️ **MUST** select "Clear build cache & deploy"

#### Alternative Method (if above doesn't work):
1. Go to **Settings** tab
2. Scroll to **"Danger Zone"** section
3. Click **"Suspend Service"**
4. Wait 30 seconds
5. Click **"Resume Service"**
   - This forces a completely fresh build

#### Step 3: Monitor Deployment
7. Click **"Logs"** tab
8. Watch build output in real-time
9. Look for success/failure indicators (see Step 4)

---

## 📊 STEP 4: LOG MONITORING GUIDE

### ✅ SUCCESS INDICATORS (in order):

#### 1. Python Version
```
==> Installing Python version 3.11.9...
==> Using Python version 3.11.9 (default)
```
✅ **This confirms build cache was cleared!**

#### 2. Dependency Installation
```
Successfully installed motor-3.7.1 pymongo-4.10.1 certifi-2024.8.30
```
(Note: versions may differ based on requirements.txt)

#### 3. MongoDB Connection
```
INFO:     Application startup complete
✓ MongoDB client initialized successfully
✓ Successfully connected to MongoDB
```

#### 4. Server Start
```
INFO:     Uvicorn running on http://0.0.0.0:XXXX
```

---

### ❌ FAILURE INDICATORS:

#### 1. Wrong Python Version
```
==> Using Python version 3.13.4 (default)
```
**Problem:** Build cache NOT cleared!
**Solution:** 
- Try "Clear build cache & deploy" again
- Or use Suspend/Resume method
- Verify `backend/runtime.txt` exists and is correct

#### 2. Dependency Conflict
```
ERROR: Cannot install motor 3.7.1 and pymongo==4.10.1
```
**Problem:** requirements.txt not updated or conflict exists
**Solution:**
- Check if changes were committed: `git log --oneline -1`
- Verify requirements.txt on GitHub matches local
- Check motor/pymongo compatibility

#### 3. SSL Error
```
SSL: TLSV1_ALERT_INTERNAL_ERROR
[SSL: TLSV1_ALERT_INTERNAL_ERROR] sslv3 alert internal error
```
**Problem:** Either wrong Python OR missing certifi
**Solution:**
- Check which Python version is being used
- If 3.11.9 → check if certifi installed (should see in logs)
- If 3.13.4 → clear build cache again

#### 4. Module Not Found
```
ModuleNotFoundError: No module named 'certifi'
```
**Problem:** requirements.txt incomplete
**Solution:**
- Verify requirements.txt has `certifi==2024.8.30`
- Check for syntax errors in requirements.txt
- Re-run: `git diff requirements.txt`

#### 5. MongoDB Connection Failure
```
✗ MongoDB connection failed during startup
ConnectionFailure: [Errno 61] Connection refused
```
**Problem:** Environment variables not set or incorrect
**Solution:**
- Check Render dashboard → Environment tab
- Verify `MONGODB_URI` or `MONGO_URL` is set
- Verify `DB_NAME` is set
- Check MongoDB Atlas IP whitelist

---

## 🔍 STEP 5: TROUBLESHOOTING DECISION TREE

### IF you see Python 3.13.4:
**Problem:** Build cache wasn't cleared

**Actions:**
1. Try "Clear build cache & deploy" again
2. If still fails, use Suspend/Resume method
3. Verify `backend/runtime.txt` exists and contains `python-3.11.9`
4. Check Render Settings → Root Directory is `backend/`

---

### IF you see dependency conflict:
**Problem:** requirements.txt not updated

**Actions:**
1. Check if Agent 1's changes were committed
   ```bash
   git log --oneline -1
   ```
2. Verify requirements.txt on GitHub matches local
   ```bash
   git diff HEAD origin/main -- backend/requirements.txt
   ```
3. If mismatch, push changes:
   ```bash
   git push origin main
   ```
4. Clear build cache and deploy again

---

### IF you see SSL error:
**Problem:** Either wrong Python OR missing certifi

**Actions:**
1. Check which Python version is being used in logs
2. If 3.11.9 → check if certifi installed:
   - Look for `Successfully installed certifi` in logs
   - If missing, verify requirements.txt has certifi
3. If 3.13.4 → clear build cache again
4. Verify server.py imports certifi (line 14)

---

### IF you see "Module not found":
**Problem:** requirements.txt incomplete or corrupted

**Actions:**
1. Verify requirements.txt has all packages:
   ```bash
   grep -E "(certifi|motor|pymongo)" backend/requirements.txt
   ```
2. Check for syntax errors in requirements.txt
3. Re-run: `git diff backend/requirements.txt`
4. Ensure all dependencies are listed

---

### IF you see MongoDB connection error:
**Problem:** Environment variables or network issue

**Actions:**
1. Check Render dashboard → Environment tab
2. Verify `MONGODB_URI` or `MONGO_URL` is set correctly
3. Verify `DB_NAME` is set
4. Check MongoDB Atlas:
   - IP whitelist includes Render IPs (0.0.0.0/0 for testing)
   - Database user has correct permissions
   - Connection string format is correct

---

## ✅ STEP 6: POST-DEPLOYMENT VERIFICATION

### 1. Health Check Endpoint
```bash
curl https://your-app.onrender.com/api/health
# Expected: {"status": "ok", "service": "vc-deal-intelligence"}
```

**Replace `your-app.onrender.com` with your actual Render URL**

### 2. Check Application Logs
Look for these in Render dashboard → Logs tab:
```
✓ MongoDB client initialized successfully
✓ Successfully connected to MongoDB
✓ MongoDB connection verified on startup
INFO:     Uvicorn running on http://0.0.0.0:XXXX
INFO:     Application startup complete
```

### 3. Test API Endpoints
```bash
# Test companies endpoint
curl https://your-app.onrender.com/api/companies

# Test dashboard stats
curl https://your-app.onrender.com/api/dashboard/stats
```

### 4. Monitor for Errors
- Leave logs open for 5 minutes
- Watch for any errors or warnings
- Check memory usage is normal
- Verify no SSL/TLS errors appear

---

## 🔄 STEP 7: ROLLBACK PROCEDURE

**If deployment fails completely and you need to rollback:**

```bash
# Navigate to repository
cd /Users/maroofakhtar/Documents/GitHub/DueSense

# Check current commit
git log --oneline -3

# Revert last commit (if needed)
git revert HEAD --no-commit
git commit -m "Revert: Emergency rollback - deployment issues"
git push origin main

# Then deploy in Render dashboard
# Use "Deploy latest commit" (no need to clear cache for rollback)
```

**Or restore from a previous working commit:**
```bash
# Find working commit
git log --oneline -10

# Reset to that commit (DANGEROUS - only if necessary)
git reset --hard <commit-hash>
git push origin main --force

# Then deploy in Render dashboard
```

⚠️ **Warning:** Force push rewrites history. Only use if absolutely necessary.

---

## 📝 QUICK REFERENCE CHECKLIST

### Before Deployment:
- [ ] All code changes committed and pushed
- [ ] Local tests pass (`python test_mongodb_connection.py`)
- [ ] Render dashboard open
- [ ] Service selected
- [ ] Environment variables verified

### During Deployment:
- [ ] Selected "Clear build cache & deploy" (NOT "Deploy latest commit")
- [ ] Monitoring logs in real-time
- [ ] Verified Python 3.11.9 in logs
- [ ] Verified dependencies installed
- [ ] Verified MongoDB connection successful

### After Deployment:
- [ ] Health check endpoint returns 200
- [ ] Application logs show successful startup
- [ ] No SSL/TLS errors in logs
- [ ] API endpoints responding correctly
- [ ] Monitored for 5 minutes with no errors

---

## 🆘 EMERGENCY CONTACTS & RESOURCES

### Render Support:
- Documentation: https://render.com/docs
- Support: https://render.com/support
- Status: https://status.render.com

### MongoDB Atlas:
- Documentation: https://docs.atlas.mongodb.com
- Support: https://support.mongodb.com

### Common Issues:
1. **Build cache not clearing:** Use Suspend/Resume method
2. **Python version wrong:** Verify `backend/runtime.txt` exists
3. **SSL errors:** Check Python version AND certifi installation
4. **Dependency conflicts:** Verify requirements.txt on GitHub
5. **MongoDB connection:** Check environment variables and IP whitelist

---

## 📌 NOTES

- **Root Directory:** Must be `backend/` for Render to find `backend/runtime.txt`
- **Build Cache:** Always clear on first deploy after Python version change
- **Environment Variables:** Use `MONGODB_URI` or `MONGO_URL` (server.py checks both)
- **Monitoring:** Keep logs open during and after deployment
- **Testing:** Always test locally before deploying

---

**Last Updated:** Based on current codebase state
**Python Version:** 3.11.9
**Root Directory:** backend/
**Deployment Platform:** Render

---

## ✅ DEPLOYMENT SUCCESS CRITERIA

Your deployment is successful when:
1. ✅ Python 3.11.9 is installed (visible in logs)
2. ✅ All dependencies install without conflicts
3. ✅ MongoDB connection succeeds with SSL/TLS
4. ✅ Server starts on correct port
5. ✅ Health check endpoint returns 200
6. ✅ No errors in logs for 5+ minutes
7. ✅ API endpoints respond correctly

**If all criteria are met, deployment is successful! 🎉**

