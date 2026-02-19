# Security Rules

## Secrets Management

- Never log secrets, API keys, or tokens
- Never hardcode secrets — always use environment variables
- Never expose secrets to the client / frontend
- Never commit `.env` or `.env.local` files
- Use `SUPABASE_SERVICE_ROLE_KEY` (not anon key) for backend operations

## API Authentication

- All protected endpoints must use `verify_api_key` from `api/v1/auth.py`
- API key is passed via the `X-API-Key` header
- `ENABLE_DEMO_KEY` must be `false` in production
- `DUESENSE_API_KEY` must be a strong random string (use `openssl rand -hex 32`)

## LLM Provider Security

- Z.ai is the **only** allowed LLM provider
- GROQ and HuggingFace are **permanently disabled** — do not re-add
- Never import `openai`, `groq`, or `huggingface` SDKs — use `httpx` directly
- Z_API_KEY must never be exposed to the frontend

## Input Validation

- Validate all client input server-side
- Enforce file size limits via `MAX_FILE_SIZE_MB` (default 25)
- Only accept PDF, PPTX, and PPT file types for deck upload
- Sanitize all user-provided strings before database insertion
- Text extraction < 50 chars with no fallback → reject with 400

## CORS

- `ALLOWED_ORIGINS` must be explicitly set in production
- Never use `*` for allowed origins in production
- Origins are comma-separated in the environment variable

## Database Security

- Row-level security (RLS) is enabled on Supabase
- Use parameterized queries — never construct SQL strings manually
- Service role key grants admin access — treat with extreme care
- All DB access through `db.py` — never create Supabase clients in service files

## Citation / Hallucination Prevention

- Every LLM output must cite sources with `[SOURCE: url]`
- Missing data → `"not_mentioned"` — never infer or fabricate
- Validate citations with `rag_extractor.validate_citations()`
- Flag suspicious claims with `[FLAG: reason]`

## Transport

- All production traffic must be HTTPS
- Webhook endpoints must verify signatures where applicable

## Environment Variables

### Required
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `Z_API_KEY`, `DUESENSE_API_KEY`

### Explicitly Banned
- `GROQ_API_KEY` — removed, do not re-add
- `HUGGINGFACE_API_KEY` — removed, do not re-add
