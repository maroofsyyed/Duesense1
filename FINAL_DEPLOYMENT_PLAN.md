## Final Deployment Plan - MongoDB Atlas SSL Fix

### Phase 1: Local Preparation (10 minutes)

#### Step 1: Update Dockerfile

```bash
# Use Agent 1's Dockerfile with python:3.11.9-bullseye
# This fixes OpenSSL compatibility

# File: backend/Dockerfile
# - Ensure FROM python:3.11.9-bullseye is used
# - Keep OpenSSL version verification (RUN openssl version)
```

#### Step 2: Update MongoDB Connection Code

```bash
# Use Agent 2's optimized connection code

# File: backend/server.py
# - Ensure proper SSL/TLS configuration (tls=True, tlsCAFile=certifi.where(), etc.)
# - Ensure TLS 1.2+ is supported by the platform (verified via verify_env.py)
# - Keep startup event with retry logic for MongoDB connection
```

#### Step 3: Run Local Verification

```bash
# Set environment variable
export MONGODB_URI="your-mongodb-atlas-uri"

# Run verification script
python backend/verify_env.py

# Expected output (exit code 0):
# 🎉 All checks passed! Your setup should work with MongoDB Atlas.
```

### Phase 2: MongoDB Atlas Configuration (5 minutes)

#### Step 1: Check Network Access

1. Log in to MongoDB Atlas.
2. Go to **Network Access**.
3. Add IP: `0.0.0.0/0` (allow all - for testing only).
4. Save changes.

#### Step 2: Verify Database User

1. Go to **Database Access**.
2. Confirm the application user exists.
3. Confirm it has at least `readWrite` permission on the target database.
4. Note: If the password contains special characters, it must be URL-encoded.

#### Step 3: Test Connection String

```bash
# Format check
mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/DATABASE?retryWrites=true&w=majority

# Common URL encodings for special characters in password:
# @ → %40
# : → %3A
# / → %2F
```

### Phase 3: Render Configuration (5 minutes)

#### Step 1: Update Environment Variables

1. Go to **Render Dashboard → Your Service → Settings**.
2. In the **Environment** section, update or add:

```bash
MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true&w=majority"
```

3. Save changes and trigger a redeploy if required.

#### Step 2: Verify Dockerfile Settings

In Render service settings:

- **Build & Deploy → Root Directory**: `backend`
- **Dockerfile Path**: `./Dockerfile`
- **Docker Context**: `.`

### Phase 4: Deployment (10 minutes)

#### Step 1: Commit Changes

```bash
cd /path/to/DueSense

git add backend/Dockerfile backend/server.py backend/verify_env.py
git commit -m "Fix: MongoDB Atlas SSL compatibility

- Use python:3.11.9-bullseye for OpenSSL 1.1.1
- Add robust MongoDB client configuration
- Add connection retry logic
- Add environment verification script"

git push origin main
```

#### Step 2: Deploy on Render

1. Go to **Render Dashboard**.
2. Select your backend service.
3. Click **Manual Deploy → Clear build cache & deploy**.
4. Monitor logs in real time.

#### Step 3: Watch for Success Indicators

Look for:

- Docker build:
  - A step like: `FROM python:3.11.9-bullseye`
  - `RUN openssl version` output showing `OpenSSL 1.1.1...`
- Application logs:
  - `✓ MongoDB client configured successfully`
  - `INFO: Started server process`
  - `INFO: Application startup complete`
  - `✓ MongoDB connection successful!`

### Phase 5: Verification (5 minutes)

#### Step 1: Check Application Health

```bash
curl https://your-app.onrender.com/health
# Expected: {"status": "healthy", "database": "connected", ...}
```

#### Step 2: Monitor Logs

1. Watch logs for at least 5 minutes after deploy.
2. Confirm:
   - No SSL handshake errors.
   - No repeated MongoDB connection failures.
   - Normal API traffic and MongoDB operations.

#### Step 3: Test API Endpoints

```bash
# Example endpoint test
curl https://your-app.onrender.com/api/companies
```

Expect a valid JSON response (empty list is fine if there is no data yet).

### Troubleshooting Decision Tree

If deployment fails or errors appear in logs:

- **Still SSL error?**
  - Check OpenSSL version in logs (from `RUN openssl version`).
  - If OpenSSL 3.0.x appears, verify Dockerfile uses `python:3.11.9-bullseye` and not `-slim`.

- **MongoDB connection timeout?**
  - Check Atlas IP allowlist includes `0.0.0.0/0` (for testing) or the correct Render egress IPs.

- **Authentication failed?**
  - Double-check `MONGODB_URI` in Render:
    - Username and password correct.
    - Password URL-encoded for special characters.

- **Different error?**
  - Capture the full error message and context.
  - Compare against `MONGODB_ATLAS_CHECKLIST.md` and `MONGODB_INSECURE_TESTING.md`.

### Rollback Plan

If deployment fails and you need to roll back:

```bash
cd /path/to/DueSense

git revert HEAD
git push origin main
```

Then, in Render:

1. Trigger a manual deploy of the reverted commit.
2. Confirm the previously working version starts successfully.

### Success Criteria

- Docker build uses `python:3.11.9-bullseye`.
- OpenSSL version is `1.1.1.x`.
- MongoDB connection is successful in application logs.
- No SSL handshake errors.
- Application startup completes without exceptions.
- `/health` endpoint responds with `"status": "healthy"`.
- Core API endpoints (e.g., `/api/companies`) respond successfully.


