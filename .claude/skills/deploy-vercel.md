# Skill: Deploy Frontend to Vercel

## Prerequisites

- Vercel account connected to GitHub repo
- Backend already deployed and accessible

## Steps

### 1. Build Frontend Locally (Verify First)

```bash
cd frontend
npm install
npm run build
```

Ensure build exits cleanly with no errors.

### 2. Configure Vercel

Settings:
- **Root Directory:** `frontend`
- **Framework Preset:** Create React App
- **Build Command:** `npm run build`
- **Output Directory:** `build`

### 3. Set Environment Variables in Vercel

| Variable | Value |
|----------|-------|
| `REACT_APP_BACKEND_URL` | `https://your-backend.onrender.com` |

### 4. Deploy

- Push to `main` branch (auto-deploys), OR
- Run `vercel --prod` from the frontend directory

### 5. Verify

1. Open the Vercel URL in a browser
2. Confirm Dashboard loads without console errors
3. Confirm API calls reach the backend (check Network tab)
4. Test upload flow end-to-end

## Alternative: Same-Origin Deployment

If deploying frontend through the backend (no Vercel):

```bash
cd frontend
npm install
npm run build
rm -rf ../backend/static
cp -r build ../backend/static
```

Then deploy the backend to Render — it will serve the frontend at `/`.
