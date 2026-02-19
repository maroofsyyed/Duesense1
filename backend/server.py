"""
DueSense Backend API Server

Production-ready FastAPI server with:
- Lazy Supabase initialization
- Versioned API (v1)
- API Key authentication
- Production landing page
- Comprehensive error handling
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from typing import Optional
from contextlib import asynccontextmanager
import os
import sys
import uuid
from datetime import datetime, timezone
import logging
import asyncio
from pathlib import Path

load_dotenv()

# Enhanced logging configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger("duesense")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Reduce noise from dependencies
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger.info(f"Logging configured at {LOG_LEVEL} level")

# Import the centralized database module (lazy initialization)
import db as database

# Import API v1 router
from api.v1.router import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup (Supabase connection, LLM validation) and shutdown.
    The app will start even if some services are temporarily unavailable.
    """
    logger.info("=" * 60)
    logger.info("Starting DueSense Backend API")
    logger.info(f"   Python version: {sys.version.split()[0]}")
    logger.info("=" * 60)

    # Validate environment variables at startup
    _validate_environment()

    # Try to connect to Supabase with retries
    db_connected = False
    try:
        logger.info("Connecting to Supabase...")
        database.test_connection(max_retries=3, retry_delay=2)
        database.create_indexes()
        db_connected = True
        logger.info("Supabase connected")
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        logger.error("   The app will start but database operations will fail")

    # Test LLM provider (non-blocking)
    llm_ready = False
    try:
        from services.llm_provider import llm
        llm._validate_token()
        logger.info(f"LLM provider initialized: {llm.current_model}")
        llm_ready = True
    except Exception as e:
        logger.error(f"LLM provider initialization failed: {e}")

    # Summary
    port = int(os.environ.get("PORT", 8000))
    logger.info("=" * 60)
    if db_connected and llm_ready:
        logger.info("All systems operational")
    else:
        status = []
        if not db_connected:
            status.append("Database")
        if not llm_ready:
            status.append("LLM")
        logger.warning(f"Starting with issues: {', '.join(status)}")
    logger.info(f"   Server ready on port {port}")
    logger.info("=" * 60)

    yield  # App is running

    # Shutdown
    logger.info("Shutting down DueSense Backend API...")
    database.close_connection()
    logger.info("Shutdown complete")


def _validate_environment():
    """Enhanced environment validation with helpful error messages."""
    logger.info("Environment validation:")

    critical_missing = []
    warnings = []

    # Critical: Database
    if not os.environ.get("SUPABASE_URL"):
        critical_missing.append("SUPABASE_URL")
    else:
        logger.info(f"   Supabase URL: {os.environ.get('SUPABASE_URL')[:40]}...")

    if not (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")):
        critical_missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")
    else:
        logger.info("   Supabase credentials configured")

    # Critical: LLM Provider
    z_key = os.environ.get("Z_API_KEY")
    sarvam_key = os.environ.get("SARVAM_API_KEY")
    
    if z_key:
        logger.info("   LLM provider: Z.ai initialized")
    if sarvam_key:
        logger.info("   LLM provider: Sarvam AI initialized")
        
    if not z_key and not sarvam_key:
        critical_missing.append("Z_API_KEY or SARVAM_API_KEY (required LLM provider)")

    # Warnings: Optional but recommended
    if not os.environ.get("GITHUB_TOKEN"):
        warnings.append("GITHUB_TOKEN not set - GitHub analysis disabled")
    if not os.environ.get("NEWS_API_KEY"):
        warnings.append("NEWS_API_KEY not set - News enrichment disabled")
    if not os.environ.get("SERPAPI_KEY"):
        warnings.append("SERPAPI_KEY not set - Competitor/market research disabled")

    # Security
    demo_key_enabled = os.environ.get("ENABLE_DEMO_KEY", "true").lower() == "true"
    if demo_key_enabled:
        warnings.append("ENABLE_DEMO_KEY=true - Disable in production!")

    if not os.environ.get("DUESENSE_API_KEY"):
        warnings.append("DUESENSE_API_KEY not set - Using default demo key")

    # Log warnings
    if warnings:
        logger.warning("Configuration warnings:")
        for w in warnings:
            logger.warning(f"   {w}")

    # Fail fast if critical vars missing
    if critical_missing:
        logger.error("CRITICAL: Missing required environment variables:")
        for var in critical_missing:
            logger.error(f"   {var}")
        raise ValueError(
            f"Missing required environment variables: {', '.join(critical_missing)}\n"
            "Please check DEPLOYMENT.md for configuration instructions."
        )

    logger.info("Environment validation passed")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="DueSense - VC Deal Intelligence API",
    description="""
## AI-Powered VC Deal Intelligence

DueSense transforms pitch decks into actionable investment insights.

### Features
- **Deck Extraction**: Upload PDF/PPTX pitch decks
- **AI Analysis**: Automatic scoring across 6 dimensions
- **Deep Enrichment**: Website, GitHub, news, competitor data
- **Investment Memos**: AI-generated comprehensive reports

### Authentication
Protected endpoints require an API key in the `X-API-Key` header.
See `/api/v1/auth/info` for details.

### Versioning
All API endpoints are versioned under `/api/v1/`.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Authentication", "description": "API key management"},
        {"name": "Deals", "description": "VC deal management"},
        {"name": "Ingestion", "description": "Pitch deck upload and processing"},
        {"name": "Analytics", "description": "Dashboard and statistics"},
        {"name": "Health", "description": "System health checks"},
    ]
)

# Request ID middleware for tracing
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)

# CORS middleware - production configuration
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").strip()
if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == "*":
    logger.warning("CORS set to allow all origins. Set ALLOWED_ORIGINS in production!")
    origins = ["*"]
else:
    origins = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
    logger.info(f"CORS restricted to: {', '.join(origins)}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_detail = str(exc)[:500] if str(exc) else "Unknown error"
    logger.error(f"Unhandled exception on {request.url.path}: {type(exc).__name__}: {error_detail}")
    logger.error(f"Traceback:\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": error_detail,
            "type": type(exc).__name__,
            "path": str(request.url.path)
        }
    )


# Include API v1 router
app.include_router(api_v1_router)


# Helper functions for collection access (lazy)
def get_companies_col():
    return database.companies_collection()

def get_pitch_decks_col():
    return database.pitch_decks_collection()

def get_founders_col():
    return database.founders_collection()

def get_enrichment_col():
    return database.enrichment_collection()

def get_competitors_col():
    return database.competitors_collection()

def get_scores_col():
    return database.scores_collection()

def get_memos_col():
    return database.memos_collection()


def validate_uuid(id_str: str) -> str:
    """Validate UUID format, raise HTTPException if invalid."""
    try:
        uuid.UUID(id_str)
        return id_str
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")


# Check if React frontend build exists
STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_BUILD_EXISTS = (STATIC_DIR / "index.html").exists()

if FRONTEND_BUILD_EXISTS:
    logger.info("Frontend build found - serving React app at /")
else:
    logger.info("Frontend build not found - serving landing page at /")


@app.get("/", response_class=HTMLResponse)
async def root():
    static_index = Path(__file__).parent / "static" / "index.html"
    if static_index.exists():
        with open(static_index, "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)

    template_path = Path(__file__).parent / "templates" / "landing.html"
    try:
        with open(template_path, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>DueSense API</title>
                <style>
                    body { font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #f8fafc; }
                    a { color: #6366f1; }
                </style>
            </head>
            <body>
                <h1>DueSense</h1>
                <p>AI-Powered VC Deal Intelligence</p>
                <p><a href="/docs">View API Documentation</a></p>
            </body>
            </html>
            """,
            status_code=200
        )


@app.get("/health")
async def health_check():
    """
    Comprehensive health check with system diagnostics.
    ALWAYS returns 200 OK. Reports status in response body.
    """
    start_time = datetime.now(timezone.utc)

    db_status = "disconnected"
    db_latency_ms = None
    db_error = None
    try:
        db_start = datetime.now(timezone.utc)
        client = database.get_client()
        client.table("companies").select("id").limit(1).execute()
        db_latency_ms = round((datetime.now(timezone.utc) - db_start).total_seconds() * 1000, 2)
        db_status = "connected"
    except Exception as e:
        db_error = str(e)[:200]

    llm_status = "unavailable"
    llm_model = None
    llm_error = None
    try:
        from services.llm_provider import llm
        llm._validate_token()
        llm_status = "ready"
        llm_model = f"{llm.current_provider['name']}: {llm.current_model}"
    except Exception as e:
        llm_error = str(e)[:200]

    overall_status = "healthy" if (db_status == "connected" and llm_status == "ready") else "degraded"
    response_time_ms = round((datetime.now(timezone.utc) - start_time).total_seconds() * 1000, 2)

    return JSONResponse(
        status_code=200,
        content={
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "duesense-backend",
            "version": "1.0.0",
            "database": {
                "status": db_status,
                "type": "supabase",
                "latency_ms": db_latency_ms,
                **({"error": db_error} if db_error else {}),
            },
            "llm": {
                "status": llm_status,
                "model": llm_model,
                **({"error": llm_error} if llm_error else {}),
            },
            "system": {
                "python_version": sys.version.split()[0],
                "response_time_ms": response_time_ms,
            },
        }
    )


@app.get("/api/health")
async def api_health():
    db_ok = False
    try:
        client = database.get_client()
        client.table("companies").select("id").limit(1).execute()
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "vc-deal-intelligence",
        "database": "connected" if db_ok else "disconnected"
    }


# ============ COMPANY ENDPOINTS ============

@app.get("/api/companies")
async def list_companies():
    companies_tbl = get_companies_col()
    companies = companies_tbl.find_many(order_by="created_at", order_desc=True)
    scores_tbl = get_scores_col()
    result = []
    for c in companies:
        score = scores_tbl.find_one({"company_id": c["id"]})
        if score:
            score.pop("id", None)
        c["score"] = score
        result.append(c)
    return {"companies": result}


@app.get("/api/companies/{company_id}")
async def get_company(company_id: str):
    validate_uuid(company_id)
    companies_tbl = get_companies_col()
    company = companies_tbl.find_by_id(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    cid = company["id"]
    decks = get_pitch_decks_col().find_many({"company_id": cid})
    founders_list = get_founders_col().find_many({"company_id": cid})
    enrichments = get_enrichment_col().find_many({"company_id": cid})
    score = get_scores_col().find_one({"company_id": cid})
    if score:
        score.pop("id", None)
    comps = get_competitors_col().find_many({"company_id": cid})
    memo = get_memos_col().find_one({"company_id": cid})
    if memo:
        memo.pop("id", None)

    return {
        "company": company,
        "pitch_decks": decks,
        "founders": founders_list,
        "enrichments": enrichments,
        "score": score,
        "competitors": comps,
        "memo": memo,
    }


@app.delete("/api/companies/{company_id}")
async def delete_company(company_id: str):
    validate_uuid(company_id)
    # CASCADE handles related records via FK constraints, but let's be explicit
    get_pitch_decks_col().delete({"company_id": company_id})
    get_founders_col().delete({"company_id": company_id})
    get_enrichment_col().delete({"company_id": company_id})
    get_scores_col().delete({"company_id": company_id})
    get_competitors_col().delete({"company_id": company_id})
    get_memos_col().delete({"company_id": company_id})
    get_companies_col().delete({"id": company_id})
    return {"status": "deleted"}


# ============ DECK UPLOAD & PROCESSING ============

@app.post("/api/decks/upload")
async def upload_deck(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_website: Optional[str] = Form(None),
):
    try:
        logger.info(f"Upload request: {file.filename} ({file.size} bytes)")

        # Validate file extension
        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in ["pdf", "pptx", "ppt"]:
            raise HTTPException(400, f"Only PDF and PPTX files are supported. Got: .{file_ext}")

        # Validate website URL if provided
        if company_website:
            company_website = company_website.strip()
            if company_website and not company_website.startswith("http"):
                company_website = "https://" + company_website

        # Read and validate file content
        content = await file.read()
        file_size = len(content)

        # Validate file size
        def get_max_file_size_mb():
            raw = os.environ.get("MAX_FILE_SIZE_MB", "25")
            if "=" in str(raw):
                raw = str(raw).split("=")[-1]
            try:
                return int(raw)
            except (ValueError, TypeError):
                return 25

        max_mb = get_max_file_size_mb()
        max_size = max_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(400, f"File exceeds {max_mb}MB limit.")
        if file_size < 1000:
            raise HTTPException(400, "File appears to be empty or corrupted (less than 1KB)")

        # Create company placeholder
        now_iso = datetime.now(timezone.utc).isoformat()
        company_row = get_companies_col().insert({
            "name": "Processing...",
            "status": "processing",
            "website": company_website,
            "website_source": "user_provided" if company_website else None,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        company_id = company_row["id"]
        logger.info(f"Company record created: {company_id}")

        # Save file locally
        file_path = f"/tmp/decks/{uuid.uuid4()}.{file_ext}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)

        # Create deck record
        deck_row = get_pitch_decks_col().insert({
            "company_id": company_id,
            "file_path": file_path,
            "file_name": file.filename,
            "file_size": file_size,
            "website_source": company_website,
            "processing_status": "uploading",
            "created_at": now_iso,
        })
        deck_id = deck_row["id"]
        logger.info(f"Deck record created: {deck_id}")

        # Process in background
        background_tasks.add_task(process_deck_pipeline, deck_id, company_id, file_path, file_ext, company_website)

        return {
            "deck_id": deck_id,
            "company_id": company_id,
            "status": "processing",
            "website_provided": bool(company_website),
            "message": "Deck uploaded successfully. Analysis in progress." + (" Website due diligence will run in parallel." if company_website else ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Upload failed: {type(e).__name__}: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)[:200]}")


async def process_deck_pipeline(deck_id: str, company_id: str, file_path: str, file_ext: str, company_website: str = None):
    """Full processing pipeline: extract -> enrich -> score -> memo"""
    logger.info(f"Starting pipeline for deck {deck_id}, company {company_id}")

    pitch_decks_tbl = get_pitch_decks_col()
    companies_tbl = get_companies_col()

    try:
        # Step 1: Extract
        logger.info("Step 1/4: Extracting deck content...")
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "extracting"})
        companies_tbl.update({"id": company_id}, {"status": "extracting"})

        from services.deck_processor import extract_deck

        tasks = [extract_deck(file_path, file_ext)]
        if company_website:
            from services.website_due_diligence import run_website_due_diligence
            tasks.append(run_website_due_diligence(company_id, company_website))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted = {}
        if isinstance(results[0], Exception):
            raise RuntimeError(f"Deck extraction failed: {results[0]}")
        else:
            extracted = results[0]

        # Handle website DD result
        if company_website and len(results) > 1:
            if isinstance(results[1], Exception):
                logger.warning(f"Website DD failed: {results[1]}")
                get_enrichment_col().insert({
                    "company_id": company_id,
                    "source_type": "website_due_diligence",
                    "source_url": company_website,
                    "data": {"status": "failed", "error": str(results[1]), "website_url": company_website},
                    "citations": [],
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "is_valid": False,
                })

        pitch_decks_tbl.update({"id": deck_id}, {"extracted_data": extracted, "processing_status": "extracted"})

        # Update company with extracted data
        company_data = extracted.get("company", {})
        company_name = company_data.get("name", "Unknown Company")
        final_website = company_website or company_data.get("website")

        companies_tbl.update({"id": company_id}, {
            "name": company_name,
            "tagline": company_data.get("tagline"),
            "website": final_website,
            "stage": company_data.get("stage"),
            "founded_year": company_data.get("founded"),
            "hq_location": company_data.get("hq_location"),
            "status": "enriching",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        if company_website and "company" in extracted:
            extracted["company"]["website"] = company_website

        # Save founders
        founders = extracted.get("founders", [])
        for f in founders:
            get_founders_col().insert({
                "company_id": company_id,
                "name": f.get("name", "Unknown"),
                "role": f.get("role"),
                "linkedin_url": f.get("linkedin"),
                "github_url": f.get("github"),
                "previous_companies": f.get("previous_companies", []),
                "years_in_industry": f.get("years_in_industry"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        # Step 2: Enrich
        logger.info("Step 2/4: Running enrichment...")
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "enriching"})

        enrichment_data = {}
        try:
            from services.enrichment_engine import enrich_company
            enrichment_data = await enrich_company(company_id, extracted)
        except Exception as enrich_err:
            logger.error(f"Enrichment failed: {type(enrich_err).__name__}: {enrich_err}")
            enrichment_data = {"error": str(enrich_err)}

        companies_tbl.update({"id": company_id}, {"status": "scoring"})

        # Step 3: Score
        logger.info("Step 3/4: Calculating investment score...")
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "scoring"})

        score_data = {}
        try:
            from services.scorer import calculate_investment_score
            score_data = await calculate_investment_score(company_id, extracted, enrichment_data)
        except Exception as score_err:
            logger.error(f"Scoring failed: {type(score_err).__name__}: {score_err}")
            score_data = {"error": str(score_err)}

        companies_tbl.update({"id": company_id}, {"status": "generating_memo"})

        # Step 4: Generate Memo
        logger.info("Step 4/4: Generating investment memo...")
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "generating_memo"})

        try:
            from services.memo_generator import generate_memo
            await generate_memo(company_id, extracted, enrichment_data, score_data)
        except Exception as memo_err:
            logger.error(f"Memo generation failed: {type(memo_err).__name__}: {memo_err}")

        # Final status
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "completed"})
        companies_tbl.update({"id": company_id}, {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()})

        logger.info(f"Pipeline COMPLETED for {company_name}")

    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"Pipeline FAILED for deck {deck_id}: {error_msg}")
        logger.error(traceback.format_exc())

        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "failed", "error_message": error_msg[:500]})
        companies_tbl.update({"id": company_id}, {"status": "failed", "updated_at": datetime.now(timezone.utc).isoformat()})
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as cleanup_err:
            logger.warning(f"Failed to cleanup file {file_path}: {cleanup_err}")


# ============ PROCESSING STATUS ============

@app.get("/api/decks/{deck_id}/status")
async def get_deck_status(deck_id: str):
    validate_uuid(deck_id)
    deck = get_pitch_decks_col().find_by_id(deck_id)
    if not deck:
        raise HTTPException(404, "Deck not found")
    deck.pop("id", None)
    return deck


# ============ ENRICHMENT TRIGGER ============

@app.post("/api/companies/{company_id}/enrich")
async def trigger_enrichment(company_id: str, background_tasks: BackgroundTasks):
    validate_uuid(company_id)
    company = get_companies_col().find_by_id(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    deck = get_pitch_decks_col().find_one({"company_id": company_id})
    extracted = deck.get("extracted_data", {}) if deck else {}

    background_tasks.add_task(run_enrichment, company_id, extracted)
    return {"status": "enrichment_started"}


async def run_enrichment(company_id, extracted):
    try:
        from services.enrichment_engine import enrich_company
        await enrich_company(company_id, extracted)
    except Exception as e:
        logger.error(f"Enrichment task failed for company {company_id}: {type(e).__name__}")


# ============ WEBSITE INTELLIGENCE ============

@app.get("/api/companies/{company_id}/website-intelligence")
async def get_website_intelligence(company_id: str):
    wi = get_enrichment_col().find_one(
        {"company_id": company_id, "source_type": "website_intelligence"}
    )
    if not wi:
        raise HTTPException(404, "Website intelligence not found")
    return wi.get("data", {})


@app.post("/api/companies/{company_id}/website-intelligence/rerun")
async def rerun_website_intelligence(company_id: str, background_tasks: BackgroundTasks):
    validate_uuid(company_id)
    company = get_companies_col().find_by_id(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    website = company.get("website")
    if not website:
        raise HTTPException(400, "Company has no website URL")
    background_tasks.add_task(_run_website_intel, company_id, website)
    return {"status": "website_intelligence_rerun_started"}


async def _run_website_intel(company_id, website):
    try:
        from services.enrichment_engine import _enrich_website_deep
        await _enrich_website_deep(company_id, website)
    except Exception as e:
        logger.error(f"Website intelligence task failed for company {company_id}: {type(e).__name__}")


# ============ SCORING ============

@app.get("/api/companies/{company_id}/score")
async def get_score(company_id: str):
    score = get_scores_col().find_one({"company_id": company_id})
    if not score:
        raise HTTPException(404, "Score not found")
    score.pop("id", None)
    return score


# ============ MEMO ============

@app.get("/api/companies/{company_id}/memo")
async def get_memo(company_id: str):
    memo = get_memos_col().find_one({"company_id": company_id})
    if not memo:
        raise HTTPException(404, "Memo not found")
    memo.pop("id", None)
    return memo


# ============ DASHBOARD STATS ============

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    companies_tbl = get_companies_col()
    scores_tbl = get_scores_col()

    total = companies_tbl.count()
    processing = companies_tbl.count({"status": {"$in": ["processing", "extracting", "enriching", "scoring", "generating_memo"]}})
    completed = companies_tbl.count({"status": "completed"})
    failed = companies_tbl.count({"status": "failed"})

    tier_1 = scores_tbl.count({"tier": "TIER_1"})
    tier_2 = scores_tbl.count({"tier": "TIER_2"})
    tier_3 = scores_tbl.count({"tier": "TIER_3"})
    tier_pass = scores_tbl.count({"tier": "PASS"})

    recent = companies_tbl.find_many({"status": "completed"}, order_by="created_at", order_desc=True, limit=5)
    recent_list = []
    for r in recent:
        score = scores_tbl.find_one({"company_id": r["id"]})
        r["score"] = score
        recent_list.append(r)

    return {
        "total_companies": total,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "tiers": {"tier_1": tier_1, "tier_2": tier_2, "tier_3": tier_3, "pass": tier_pass},
        "recent_companies": recent_list,
    }


# ============ STATIC FILES & CLIENT-SIDE ROUTING ============

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists() and (_static_dir / "static").exists():
    app.mount("/static", StaticFiles(directory=_static_dir / "static"), name="static-assets")
    logger.info("Mounted static assets from /static")

if _static_dir.exists():
    for static_file in ["favicon.ico", "manifest.json", "robots.txt", "logo192.png", "logo512.png"]:
        file_path = _static_dir / static_file
        if file_path.exists():
            @app.get(f"/{static_file}")
            async def serve_static_file(file_path=file_path):
                return FileResponse(file_path)


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path in ["docs", "redoc", "openapi.json", "health"]:
        raise HTTPException(status_code=404, detail="Not found")

    static_index = Path(__file__).parent / "static" / "index.html"
    if static_index.exists():
        with open(static_index, "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)

    raise HTTPException(status_code=404, detail="Not found")
