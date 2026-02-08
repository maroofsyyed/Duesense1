from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from typing import Optional
import os
import uuid
from datetime import datetime, timezone
import json
import logging
import certifi

load_dotenv()

# Configure logging - ensure no secrets are logged
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VC Deal Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

# Validate required environment variables
if not MONGO_URL or not DB_NAME:
    raise ValueError("MONGO_URL and DB_NAME environment variables are required")

if not MONGO_URL.startswith("mongodb+srv://") and not MONGO_URL.startswith("mongodb://"):
    raise ValueError("Invalid MongoDB URI format - must start with mongodb:// or mongodb+srv://")

# Create MongoDB client with proper SSL/TLS configuration
try:
    client = MongoClient(
        MONGO_URL,
        tls=True,
        tlsAllowInvalidCertificates=False,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
    )
    # Test connection
    client.admin.command('ping')
    logger.info("✓ Successfully connected to MongoDB")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    logger.error(f"✗ MongoDB connection failed: {str(e)}")
    raise ConnectionFailure(f"MongoDB connection failed: {str(e)}") from e
except Exception as e:
    logger.error(f"✗ Unexpected MongoDB error: {str(e)}")
    raise

db = client[DB_NAME]

# Collections
companies_col = db["companies"]
pitch_decks_col = db["pitch_decks"]
founders_col = db["founders"]
enrichment_col = db["enrichment_sources"]
competitors_col = db["competitors"]
scores_col = db["investment_scores"]
memos_col = db["investment_memos"]

# Create indexes
companies_col.create_index("name")
pitch_decks_col.create_index("company_id")
founders_col.create_index("company_id")
enrichment_col.create_index("company_id")
scores_col.create_index("company_id")


def serialize_doc(doc):
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def serialize_docs(docs):
    return [serialize_doc(d) for d in docs]


def validate_object_id(id_str: str) -> ObjectId:
    """Validate and return ObjectId, raise HTTPException if invalid."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")


@app.on_event("startup")
async def startup_event():
    """Startup event to ensure PORT is read from environment."""
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Server configured to run on port {port}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "vc-deal-intelligence"}


# ============ COMPANY ENDPOINTS ============

@app.get("/api/companies")
async def list_companies():
    companies = list(companies_col.find().sort("created_at", -1))
    result = []
    for c in companies:
        c["id"] = str(c.pop("_id"))
        score = scores_col.find_one({"company_id": c["id"]}, {"_id": 0})
        c["score"] = score
        result.append(c)
    return {"companies": result}


@app.get("/api/companies/{company_id}")
async def get_company(company_id: str):
    obj_id = validate_object_id(company_id)
    company = companies_col.find_one({"_id": obj_id})
    if not company:
        raise HTTPException(404, "Company not found")
    company = serialize_doc(company)

    # Get related data
    decks = serialize_docs(list(pitch_decks_col.find({"company_id": company_id})))
    founders_list = serialize_docs(list(founders_col.find({"company_id": company_id})))
    enrichments = serialize_docs(list(enrichment_col.find({"company_id": company_id})))
    score = scores_col.find_one({"company_id": company_id}, {"_id": 0})
    comps = serialize_docs(list(competitors_col.find({"company_id": company_id})))
    memo = memos_col.find_one({"company_id": company_id}, {"_id": 0})

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
    companies_col.delete_one({"_id": obj_id})
    pitch_decks_col.delete_many({"company_id": company_id})
    founders_col.delete_many({"company_id": company_id})
    enrichment_col.delete_many({"company_id": company_id})
    scores_col.delete_many({"company_id": company_id})
    competitors_col.delete_many({"company_id": company_id})
    memos_col.delete_many({"company_id": company_id})
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
    company_id = str(companies_col.insert_one({
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
    deck_id = str(pitch_decks_col.insert_one({
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
        pitch_decks_col.update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "extracting"}}
        )
        companies_col.update_one(
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
                    enrichment_col.insert_one({
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

        pitch_decks_col.update_one(
            {"_id": deck_obj_id},
            {"$set": {"extracted_data": extracted, "processing_status": "extracted"}}
        )

        # Update company with extracted data
        # User-provided website takes priority over deck-extracted website
        company_data = extracted.get("company", {})
        final_website = company_website or company_data.get("website")
        companies_col.update_one(
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
            founders_col.insert_one({
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
        pitch_decks_col.update_one(
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

        companies_col.update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "scoring"}}
        )

        # Step 3: Score
        pitch_decks_col.update_one(
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

        companies_col.update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "generating_memo"}}
        )

        # Step 4: Generate Memo
        pitch_decks_col.update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "generating_memo"}}
        )

        try:
            from services.memo_generator import generate_memo
            memo_data = await generate_memo(company_id, extracted, enrichment_data, score_data)
        except Exception as memo_err:
            logger.error(f"Memo generation failed for company {company_id}: {type(memo_err).__name__}")

        # Final status
        pitch_decks_col.update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "completed"}}
        )
        companies_col.update_one(
            {"_id": company_obj_id},
            {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    except Exception as e:
        # Sanitize error logging - no secrets exposed
        error_msg = str(e)
        logger.error(f"Pipeline failed for deck {deck_id}, company {company_id}: {error_msg}")
        pitch_decks_col.update_one(
            {"_id": deck_obj_id},
            {"$set": {"processing_status": "failed", "error_message": error_msg}}
        )
        companies_col.update_one(
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
    deck = pitch_decks_col.find_one({"_id": obj_id}, {"_id": 0})
    if not deck:
        raise HTTPException(404, "Deck not found")
    return deck


# ============ ENRICHMENT TRIGGER ============

@app.post("/api/companies/{company_id}/enrich")
async def trigger_enrichment(company_id: str, background_tasks: BackgroundTasks):
    obj_id = validate_object_id(company_id)
    company = companies_col.find_one({"_id": obj_id})
    if not company:
        raise HTTPException(404, "Company not found")

    deck = pitch_decks_col.find_one({"company_id": company_id})
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
    wi = enrichment_col.find_one(
        {"company_id": company_id, "source_type": "website_intelligence"},
        {"_id": 0}
    )
    if not wi:
        raise HTTPException(404, "Website intelligence not found")
    return wi.get("data", {})


@app.post("/api/companies/{company_id}/website-intelligence/rerun")
async def rerun_website_intelligence(company_id: str, background_tasks: BackgroundTasks):
    obj_id = validate_object_id(company_id)
    company = companies_col.find_one({"_id": obj_id})
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
    score = scores_col.find_one({"company_id": company_id}, {"_id": 0})
    if not score:
        raise HTTPException(404, "Score not found")
    return score


# ============ MEMO ============

@app.get("/api/companies/{company_id}/memo")
async def get_memo(company_id: str):
    memo = memos_col.find_one({"company_id": company_id}, {"_id": 0})
    if not memo:
        raise HTTPException(404, "Memo not found")
    return memo


# ============ DASHBOARD STATS ============

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    total = companies_col.count_documents({})
    processing = companies_col.count_documents({"status": {"$in": ["processing", "extracting", "enriching", "scoring", "generating_memo"]}})
    completed = companies_col.count_documents({"status": "completed"})
    failed = companies_col.count_documents({"status": "failed"})

    # Get tier distribution
    tier_1 = scores_col.count_documents({"tier": "TIER_1"})
    tier_2 = scores_col.count_documents({"tier": "TIER_2"})
    tier_3 = scores_col.count_documents({"tier": "TIER_3"})
    tier_pass = scores_col.count_documents({"tier": "PASS"})

    # Recent companies
    recent = list(companies_col.find({"status": "completed"}).sort("created_at", -1).limit(5))
    recent_list = []
    for r in recent:
        r["id"] = str(r.pop("_id"))
        score = scores_col.find_one({"company_id": r["id"]}, {"_id": 0})
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
