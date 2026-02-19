# Skill: Supabase Database Setup

## Prerequisites

- Supabase account at [supabase.com](https://supabase.com)
- Access to the project's SQL Editor

## Steps

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Choose a name and region
3. Note the database password (you won't see it again)

### 2. Get Connection Credentials

1. Go to **Settings → API**
2. Copy:
   - **Project URL** → use as `SUPABASE_URL`
   - **Service Role Key** → use as `SUPABASE_SERVICE_ROLE_KEY`

> ⚠️ Use the **service role key**, NOT the anon key. The service role key bypasses RLS.

### 3. Execute Schema

1. Go to **SQL Editor → New Query**
2. Copy the contents of `backend/database/schema.sql`
3. Click **Run**

### 4. Verify Tables

Go to **Table Editor** and confirm these tables exist:

| Table | Purpose |
|-------|---------|
| `companies` | Company information |
| `pitch_decks` | Uploaded deck metadata and extracted data |
| `founders` | Founder information |
| `enrichment_sources` | External data (GitHub, news) |
| `competitors` | Competitor information |
| `investment_scores` | 6-dimension investment scores |
| `investment_memos` | AI-generated investment memos |

### 5. Set Environment Variables

Add to your `.env` or hosting platform:

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

### 6. Test Connection

```bash
cd backend
python -c "import db; print(db.get_supabase_client())"
```

Should initialize without errors.

## Schema Updates

When modifying the schema:
1. Write migration SQL
2. Test in Supabase SQL Editor (staging project first)
3. Update `backend/database/schema.sql`
4. Document the change
