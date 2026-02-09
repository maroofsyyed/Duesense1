"""
DueSense Backend API Server

Production-ready FastAPI server with lazy MongoDB initialization.
The server starts successfully even if MongoDB is temporarily unavailable,
with connection retries during the startup event.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from typing import Optional
from contextlib import asynccontextmanager
import os
import sys
import uuid
from datetime import datetime, timezone
import logging
import asyncio

load_dotenv()

# Configure logging - ensure no secrets are logged
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the centralized database module (lazy initialization)
import db as database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup (MongoDB connection, indexes) and shutdown (connection cleanup).
    The app will start even if MongoDB is temporarily unavailable, with retries.
    """
    logger.info("=" * 60)
    logger.info("Starting DueSense Backend API...")
    logger.info(f"Python version: {sys.version}")
    logger.info("=" * 60)
    
    # Validate environment variables at startup (warn but don't crash)
    _validate_environment()
    
    # Try to connect to MongoDB with retries
    max_retries = 3
    retry_delay = 5
    db_connected = False
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempting MongoDB connection (attempt {attempt}/{max_retries})...")
            database.test_connection(max_retries=1, retry_delay=1)
            database.create_indexes()
            db_connected = True
            logger.info("✓ MongoDB connection established successfully")
            break
        except Exception as e:
            logger.warning(f"MongoDB connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error("⚠ MongoDB connection failed after all retries")
                logger.error("The app will start but database operations will fail until MongoDB is available")
    
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Server ready on port {port}")
    logger.info("=" * 60)
    
    yield  # App is running
    
    # Shutdown
    logger.info("Shutting down DueSense Backend API...")
    database.close_connection()
    logger.info("✓ Shutdown complete")


def _validate_environment():
    """Validate required environment variables and log warnings."""
    required_vars = ["MONGODB_URI", "MONGO_URL"]  # At least one must be set
    optional_vars = ["DB_NAME", "EMERGENT_LLM_KEY", "GROQ_API_KEY", "MAX_FILE_SIZE_MB"]
    
    # Check MongoDB URL
    mongo_url = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
    if not mongo_url:
        logger.warning("⚠ Neither MONGODB_URI nor MONGO_URL is set. Database operations will fail.")
    else:
        # Mask the URL for logging
        safe_url = mongo_url[:30] + "..." if len(mongo_url) > 30 else mongo_url
        logger.info(f"MongoDB URL configured: {safe_url}")
    
    # Log optional vars status
    db_name = os.environ.get("DB_NAME", "duesense")
    logger.info(f"Database name: {db_name}")
    
    max_file_size = os.environ.get("MAX_FILE_SIZE_MB", "25")
    logger.info(f"Max file size: {max_file_size}MB")
    
    # Check LLM providers
    if os.environ.get("EMERGENT_LLM_KEY"):
        logger.info("✓ EMERGENT_LLM_KEY configured")
    elif os.environ.get("GROQ_API_KEY"):
        logger.info("✓ GROQ_API_KEY configured")
    else:
        logger.warning("⚠ No LLM API key configured (EMERGENT_LLM_KEY or GROQ_API_KEY)")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="DueSense - VC Deal Intelligence API",
    description="AI-powered startup analysis and investment memo generation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - for production, specify allowed origins
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def serialize_doc(doc):
    """Serialize MongoDB document, converting _id to id string."""
    if doc is None:
        return None
    doc = dict(doc)  # Make a copy to avoid modifying original
    doc["id"] = str(doc.pop("_id"))
    return doc


def serialize_docs(docs):
    """Serialize a list of MongoDB documents."""
    return [serialize_doc(d) for d in docs]


def validate_object_id(id_str: str) -> ObjectId:
    """Validate and return ObjectId, raise HTTPException if invalid."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint - Welcome page for DueSense Backend.
    
    Returns a visible HTML page confirming the backend is live.
    """
    # Check database status for display
    db_status = "🔴 Disconnected"
    db_connected = False
    try:
        client = database.get_client()
        client.admin.command('ping')
        db_status = "🟢 Connected"
        db_connected = True
    except Exception:
        pass
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DueSense API</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #e6e6e6;
            }}
            .container {{
                text-align: center;
                padding: 40px;
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.1);
                max-width: 500px;
                margin: 20px;
            }}
            .logo {{
                font-size: 3rem;
                margin-bottom: 10px;
            }}
            h1 {{
                font-size: 2.5rem;
                margin-bottom: 10px;
                background: linear-gradient(90deg, #00d4ff, #7b2cbf);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            .tagline {{
                color: #a0a0a0;
                margin-bottom: 30px;
                font-size: 1.1rem;
            }}
            .status {{
                display: flex;
                flex-direction: column;
                gap: 12px;
                margin-bottom: 30px;
            }}
            .status-item {{
                display: flex;
                justify-content: space-between;
                padding: 12px 20px;
                background: rgba(255,255,255,0.03);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            .status-label {{ color: #888; }}
            .status-value {{ font-weight: 600; }}
            .status-ok {{ color: #00d4ff; }}
            .status-db {{ color: {'#00ff88' if db_connected else '#ff6b6b'}; }}
            .links {{
                display: flex;
                gap: 15px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            a {{
                color: #00d4ff;
                text-decoration: none;
                padding: 10px 20px;
                border: 1px solid #00d4ff;
                border-radius: 8px;
                transition: all 0.3s;
            }}
            a:hover {{
                background: #00d4ff;
                color: #1a1a2e;
            }}
            .version {{
                margin-top: 30px;
                font-size: 0.85rem;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🚀</div>
            <h1>DueSense</h1>
            <p class="tagline">VC Deal Intelligence API</p>
            
            <div class="status">
                <div class="status-item">
                    <span class="status-label">API Status</span>
                    <span class="status-value status-ok">✓ Online</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Database</span>
                    <span class="status-value status-db">{db_status}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Python</span>
                    <span class="status-value">{sys.version.split()[0]}</span>
                </div>
            </div>
            
            <div class="links">
                <a href="/docs">📚 API Docs</a>
                <a href="/health">💚 Health Check</a>
                <a href="/api/health">🔗 API Status</a>
            </div>
            
            <p class="version">v1.0.0 • Powered by FastAPI</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Render and other monitoring systems.

    ALWAYS returns 200 OK to keep the service alive.
    Reports database connectivity status in the response body.
    """
    db_connected = False
    db_error = None
    
    try:
        # Test MongoDB connection
        client = database.get_client()
        client.admin.command('ping')
        db_connected = True
    except Exception as e:
        db_error = str(e)[:100]  # Truncate error message
    
    # Always return 200 OK - Render health checks expect this
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "duesense-backend",
            "db_connected": db_connected,
            "python_version": sys.version.split()[0],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **({"db_error": db_error} if db_error else {}),
        }
    )


@app.get("/api/health")
async def api_health():
    """Simple health check for API consumers."""
    return {"status": "ok", "service": "vc-deal-intelligence"}


# ============ COMPANY ENDPOINTS ============

@app.get("/api/companies")
async def list_companies():
    companies = list(get_companies_col().find().sort("created_at", -1))
    result = []
    for c in companies:
        c["id"] = str(c.pop("_id"))
        score = get_scores_col().find_one({"company_id": c["id"]}, {"_id": 0})
        c["score"] = score
        result.append(c)
    return {"companies": result}


@app.get("/api/companies/{company_id}")
async def get_company(company_id: str):
    obj_id = validate_object_id(company_id)
    company = get_companies_col().find_one({"_id": obj_id})
    if not company:
        raise HTTPException(404, "Company not found")
    company = serialize_doc(company)

    # Get related data
    decks = serialize_docs(list(get_pitch_decks_col().find({"company_id": company_id})))
    founders_list = serialize_docs(list(get_founders_col().find({"company_id": company_id})))
    enrichments = serialize_docs(list(get_enrichment_col().find({"company_id": company_id})))
    score = get_scores_col().find_one({"company_id": company_id}, {"_id": 0})
    comps = serialize_docs(list(get_competitors_col().find({"company_id": company_id})))
    memo = get_memos_col().find_one({"company_id": company_id}, {"_id": 0})

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
    obj_id = validate_object_id(company_id)
    get_companies_col().delete_one({"_id": obj_id})
    get_pitch_decks_col().delete_many({"company_id": company_id})
    get_founders_col().delete_many({"company_id": company_id})
    get_enrichment_col().delete_many({"company_id": company_id})
    get_scores_col().delete_many({"company_id": company_id})
    get_competitors_col().delete_many({"company_id": company_id})
    get_memos_col().delete_many({"company_id": company_id})
    return {"status": "deleted"}


# ============ DECK UPLOAD & PROCESSING ============

@app.post("/api/decks/upload")
async def upload_deck(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_website: Optional[str] = Form(None),
):
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["pdf", "pptx", "ppt"]:
        raise HTTPException(400, "Only PDF and PPTX files are supported")

    # Validate website URL if provided
    if company_website:
        company_website = company_website.strip()
        if company_website and not company_website.startswith("http"):
            company_website = "https://" + company_website

    content = await file.read()
    file_size = len(content)
    max_size = int(os.environ.get("MAX_FILE_SIZE_MB", 25)) * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(400, f"File exceeds {os.environ.get('MAX_FILE_SIZE_MB', 25)}MB limit")

    # Create company placeholder
    company_id = str(get_companies_col().insert_one({
        "name": "Processing...",
        "status": "processing",
        "stage": None,
        "website": company_website,
        "tagline": None,
        "founded_year": None,
        "hq_location": None,
        "website_source": "user_provided" if company_website else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).inserted_id)

    # Save file locally
    file_path = f"/tmp/decks/{uuid.uuid4()}.{file_ext}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    # Create deck record
    deck_id = str(get_pitch_decks_col().insert_one({
        "company_id": company_id,
        "file_path": file_path,
        "file_name": file.filename,
        "file_size": file_size,
        "website_source": company_website,
        "processing_status": "uploading",
        "extracted_data": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).inserted_id)

    # Process in background
    background_tasks.add_task(process_deck_pipeline, deck_id, company_id, file_path, file_ext, company_website)

    return {
        "deck_id": deck_id,
        "company_id": company_id,
        "status": "processing",
        "website_provided": bool(company_website),
        "message": "Deck uploaded. Processing started." + (" Website due diligence will run in parallel." if company_website else ""),
    }


async def process_deck_pipeline(deck_id: str, company_id: str, file_path: str, file_ext: str, company_website: str = None):
    """Full pipeline: extract (+website DD in parallel) -> enrich -> score -> memo"""
    import asyncio
    deck_obj_id = validate_object_id(deck_id)
    company_obj_id = validate_object_id(company_id)
    
    try:
        # Step 1: Extract deck + optional website DD in parallel
        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "extracting"}}
        )
        get_companies_col().update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "extracting"}}
        )

        from services.deck_processor import extract_deck

        # Run deck extraction and website due diligence in parallel
        tasks = [extract_deck(file_path, file_ext)]
        if company_website:
            from services.website_due_diligence import run_website_due_diligence
            tasks.append(run_website_due_diligence(company_id, company_website))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        extracted = results[0] if not isinstance(results[0], Exception) else {}
        if isinstance(results[0], Exception):
            raise results[0]

        # Handle website DD result - ensure failures are persisted cleanly
        website_dd_result = None
        if company_website and len(results) > 1:
            if isinstance(results[1], Exception):
                # Persist website DD failure in enrichment_sources
                try:
                    get_enrichment_col().insert_one({
                        "company_id": company_id,
                        "source_type": "website_due_diligence",
                        "source_url": company_website,
                        "data": {
                            "status": "failed",
                            "error": str(results[1]),
                            "website_url": company_website,
                        },
                        "citations": [],
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "is_valid": False,
                    })
                except Exception as persist_err:
                    logger.error(f"Failed to persist website DD error: {persist_err}")
            website_dd_result = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}

        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"extracted_data": extracted, "processing_status": "extracted"}}
        )

        # Update company with extracted data
        # User-provided website takes priority over deck-extracted website
        company_data = extracted.get("company", {})
        final_website = company_website or company_data.get("website")
        get_companies_col().update_one(
            {"_id": company_obj_id},
            {"$set": {
                "name": company_data.get("name", "Unknown Company"),
                "tagline": company_data.get("tagline"),
                "website": final_website,
                "stage": company_data.get("stage"),
                "founded_year": company_data.get("founded"),
                "hq_location": company_data.get("hq_location"),
                "status": "enriching",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        # Inject user-provided website into extracted data for downstream enrichment
        if company_website and "company" in extracted:
            extracted["company"]["website"] = company_website

        # Save founders
        for f in extracted.get("founders", []):
            get_founders_col().insert_one({
                "company_id": company_id,
                "name": f.get("name", "Unknown"),
                "role": f.get("role"),
                "linkedin_url": f.get("linkedin"),
                "github_url": f.get("github"),
                "previous_companies": f.get("previous_companies", []),
                "years_in_industry": f.get("years_in_industry"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        # Step 2: Enrich (website_intelligence in enrichment engine will use the website)
        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "enriching"}}
        )

        enrichment_data = {}
        try:
            from services.enrichment_engine import enrich_company
            enrichment_data = await enrich_company(company_id, extracted)
        except Exception as enrich_err:
            logger.error(f"Enrichment failed for company {company_id}: {type(enrich_err).__name__}")
            enrichment_data = {"error": "Enrichment failed"}

        get_companies_col().update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "scoring"}}
        )

        # Step 3: Score
        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "scoring"}}
        )

        score_data = {}
        try:
            from services.scorer import calculate_investment_score
            score_data = await calculate_investment_score(company_id, extracted, enrichment_data)
        except Exception as score_err:
            logger.error(f"Scoring failed for company {company_id}: {type(score_err).__name__}")
            score_data = {"error": "Scoring failed"}

        get_companies_col().update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "generating_memo"}}
        )

        # Step 4: Generate Memo
        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "generating_memo"}}
        )

        try:
            from services.memo_generator import generate_memo
            memo_data = await generate_memo(company_id, extracted, enrichment_data, score_data)
        except Exception as memo_err:
            logger.error(f"Memo generation failed for company {company_id}: {type(memo_err).__name__}")

        # Final status
        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "completed"}}
        )
        get_companies_col().update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    except Exception as e:
        # Sanitize error logging - no secrets exposed
        error_msg = str(e)
        logger.error(f"Pipeline failed for deck {deck_id}, company {company_id}: {error_msg}")
        get_pitch_decks_col().update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "failed", "error_message": error_msg}}
        )
        get_companies_col().update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "failed", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    finally:
        # Cleanup temporary file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as cleanup_err:
            logger.warning(f"Failed to cleanup file {file_path}: {cleanup_err}")


# ============ PROCESSING STATUS ============

@app.get("/api/decks/{deck_id}/status")
async def get_deck_status(deck_id: str):
    obj_id = validate_object_id(deck_id)
    deck = get_pitch_decks_col().find_one({"_id": obj_id}, {"_id": 0})
    if not deck:
        raise HTTPException(404, "Deck not found")
    return deck


# ============ ENRICHMENT TRIGGER ============

@app.post("/api/companies/{company_id}/enrich")
async def trigger_enrichment(company_id: str, background_tasks: BackgroundTasks):
    obj_id = validate_object_id(company_id)
    company = get_companies_col().find_one({"_id": obj_id})
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
        {"company_id": company_id, "source_type": "website_intelligence"},
        {"_id": 0}
    )
    if not wi:
        raise HTTPException(404, "Website intelligence not found")
    return wi.get("data", {})


@app.post("/api/companies/{company_id}/website-intelligence/rerun")
async def rerun_website_intelligence(company_id: str, background_tasks: BackgroundTasks):
    obj_id = validate_object_id(company_id)
    company = get_companies_col().find_one({"_id": obj_id})
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
    score = get_scores_col().find_one({"company_id": company_id}, {"_id": 0})
    if not score:
        raise HTTPException(404, "Score not found")
    return score


# ============ MEMO ============

@app.get("/api/companies/{company_id}/memo")
async def get_memo(company_id: str):
    memo = get_memos_col().find_one({"company_id": company_id}, {"_id": 0})
    if not memo:
        raise HTTPException(404, "Memo not found")
    return memo


# ============ DASHBOARD STATS ============

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    total = get_companies_col().count_documents({})
    processing = get_companies_col().count_documents({"status": {"$in": ["processing", "extracting", "enriching", "scoring", "generating_memo"]}})
    completed = get_companies_col().count_documents({"status": "completed"})
    failed = get_companies_col().count_documents({"status": "failed"})

    # Get tier distribution
    tier_1 = get_scores_col().count_documents({"tier": "TIER_1"})
    tier_2 = get_scores_col().count_documents({"tier": "TIER_2"})
    tier_3 = get_scores_col().count_documents({"tier": "TIER_3"})
    tier_pass = get_scores_col().count_documents({"tier": "PASS"})

    # Recent companies
    recent = list(get_companies_col().find({"status": "completed"}).sort("created_at", -1).limit(5))
    recent_list = []
    for r in recent:
        r["id"] = str(r.pop("_id"))
        score = get_scores_col().find_one({"company_id": r["id"]}, {"_id": 0})
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
