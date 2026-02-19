# Testing Rules

## Frontend

- All interactive elements must have `data-testid` attributes
- Test file location: alongside source files as `*.test.js`
- Use React Testing Library patterns
- Test user-visible behavior, not implementation details

## Backend

- Test with `pytest`
- API tests should verify:
  - Correct HTTP status codes
  - Response structure
  - Authentication (401 without API key)
  - Input validation (400 on bad input)
- Service tests should be unit-level with mocked dependencies

## Verification After Changes

1. Backend health: `curl http://localhost:8000/health` → `200 OK`
2. API auth: `curl -H "X-API-Key: $KEY" http://localhost:8000/api/v1/deals` → `200 OK`
3. Frontend build: `cd frontend && npm run build` → exits cleanly
4. No console errors in browser dev tools

## When to Write Tests

- When adding a new API endpoint
- When adding a new service function
- When fixing a bug (add a regression test)
- When changing scoring or memo logic (critical path)

## What to Skip

- Don't test Supabase SDK internals
- Don't test third-party LLM responses (mock them)
- Don't test static file serving
