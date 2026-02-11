"""
Ingestion API - Upload and process pitch decks.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field
import db as database
from api.v1.auth import verify_api_key
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


# Pydantic Models
class IngestionResponse(BaseModel):
    """Response after initiating ingestion."""
    deck_id: str = Field(..., description="Unique deck identifier")
    company_id: str = Field(..., description="Associated company identifier")
    status: str = Field(..., description="Current processing status")
    message: str = Field(..., description="Status message")


class IngestionStatusResponse(BaseModel):
    """Ingestion status response."""
    deck_id: str
    company_id: str
    status: str
    processing_status: str
    created_at: str
    error_message: Optional[str] = None


class ProcessingStage(BaseModel):
    """Processing stage information."""
    stage: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# Background task for processing
async def process_deck_pipeline(deck_id: str, company_id: str, file_path: str, file_ext: str, company_website: str = None):
    """Process deck through the full pipeline."""
    pitch_decks_tbl = database.pitch_decks_collection()
    companies_tbl = database.companies_collection()
    founders_tbl = database.founders_collection()
    enrichment_tbl = database.enrichment_collection()
    
    try:
        # Step 1: Extract
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "extracting"})
        companies_tbl.update({"id": company_id}, {"status": "extracting"})
        
        from services.deck_processor import extract_deck
        import asyncio
        
        tasks = [extract_deck(file_path, file_ext)]
        if company_website:
            from services.website_due_diligence import run_website_due_diligence
            tasks.append(run_website_due_diligence(company_id, company_website))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        extracted = results[0] if not isinstance(results[0], Exception) else {}
        
        if isinstance(results[0], Exception):
            raise results[0]
        
        pitch_decks_tbl.update(
            {"id": deck_id},
            {"extracted_data": extracted, "processing_status": "extracted"}
        )
        
        # Update company with extracted data
        company_data = extracted.get("company", {})
        final_website = company_website or company_data.get("website")
        companies_tbl.update({"id": company_id}, {
            "name": company_data.get("name", "Unknown Company"),
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
        for f in extracted.get("founders", []):
            founders_tbl.insert({
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
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "enriching"})
        
        enrichment_data = {}
        try:
            from services.enrichment_engine import enrich_company
            enrichment_data = await enrich_company(company_id, extracted)
        except Exception as e:
            logger.error(f"Enrichment failed: {type(e).__name__}")
            enrichment_data = {"error": "Enrichment failed"}
        
        companies_tbl.update({"id": company_id}, {"status": "scoring"})
        
        # Step 3: Score
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "scoring"})
        
        score_data = {}
        try:
            from services.scorer import calculate_investment_score
            score_data = await calculate_investment_score(company_id, extracted, enrichment_data)
        except Exception as e:
            logger.error(f"Scoring failed: {type(e).__name__}")
            score_data = {"error": "Scoring failed"}
        
        companies_tbl.update({"id": company_id}, {"status": "generating_memo"})
        
        # Step 4: Generate Memo
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "generating_memo"})
        
        try:
            from services.memo_generator import generate_memo
            await generate_memo(company_id, extracted, enrichment_data, score_data)
        except Exception as e:
            logger.error(f"Memo generation failed: {type(e).__name__}")
        
        # Final status
        pitch_decks_tbl.update({"id": deck_id}, {"processing_status": "completed"})
        companies_tbl.update({"id": company_id}, {
            "status": "completed",
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Pipeline failed for deck {deck_id}: {error_msg}")
        pitch_decks_tbl.update({"id": deck_id}, {
            "processing_status": "failed",
            "error_message": error_msg
        })
        companies_tbl.update({"id": company_id}, {
            "status": "failed",
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup file: {e}")


# Routes
@router.post("/upload", response_model=IngestionResponse)
async def upload_deck(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Pitch deck file (PDF or PPTX)"),
    company_website: Optional[str] = Form(None, description="Company website URL"),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload a pitch deck for processing.
    
    Accepts PDF and PPTX files. Optionally provide company website for 
    enhanced due diligence.
    
    Requires API key authentication.
    """
    # Validate file type
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["pdf", "pptx", "ppt"]:
        raise HTTPException(
            status_code=400, 
            detail="Only PDF and PPTX files are supported"
        )
    
    # Validate website URL
    if company_website:
        company_website = company_website.strip()
        if company_website and not company_website.startswith("http"):
            company_website = "https://" + company_website
    
    # Read and validate file size
    content = await file.read()
    file_size = len(content)
    max_size = int(os.environ.get("MAX_FILE_SIZE_MB", 25)) * 1024 * 1024
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {os.environ.get('MAX_FILE_SIZE_MB', 25)}MB limit"
        )
    
    companies_tbl = database.companies_collection()
    pitch_decks_tbl = database.pitch_decks_collection()
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Create company placeholder
    company_row = companies_tbl.insert({
        "name": "Processing...",
        "status": "processing",
        "website": company_website,
        "website_source": "user_provided" if company_website else None,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    company_id = company_row["id"]
    
    # Save file locally
    file_path = f"/tmp/decks/{uuid.uuid4()}.{file_ext}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create deck record
    deck_row = pitch_decks_tbl.insert({
        "company_id": company_id,
        "file_path": file_path,
        "file_name": file.filename,
        "file_size": file_size,
        "website_source": company_website,
        "processing_status": "uploading",
        "created_at": now_iso,
    })
    deck_id = deck_row["id"]
    
    # Process in background
    background_tasks.add_task(
        process_deck_pipeline, 
        deck_id, 
        company_id, 
        file_path, 
        file_ext, 
        company_website
    )
    
    return IngestionResponse(
        deck_id=deck_id,
        company_id=company_id,
        status="processing",
        message="Deck uploaded. Processing started." + 
                (" Website due diligence will run in parallel." if company_website else "")
    )


@router.get("/status/{deck_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(deck_id: str, api_key: str = Depends(verify_api_key)):
    """
    Get the processing status of an uploaded deck.
    
    Requires API key authentication.
    """
    try:
        uuid.UUID(deck_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid deck ID format")
    
    pitch_decks_tbl = database.pitch_decks_collection()
    deck = pitch_decks_tbl.find_by_id(deck_id)
    
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    return IngestionStatusResponse(
        deck_id=deck["id"],
        company_id=deck.get("company_id"),
        status=deck.get("processing_status", "unknown"),
        processing_status=deck.get("processing_status", "unknown"),
        created_at=deck.get("created_at"),
        error_message=deck.get("error_message")
    )


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Get list of supported file formats for ingestion.
    
    Public endpoint - no authentication required.
    """
    return {
        "supported_formats": [
            {
                "extension": "pdf",
                "mime_type": "application/pdf",
                "description": "PDF documents"
            },
            {
                "extension": "pptx",
                "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "description": "PowerPoint presentations (modern)"
            },
            {
                "extension": "ppt",
                "mime_type": "application/vnd.ms-powerpoint",
                "description": "PowerPoint presentations (legacy)"
            }
        ],
        "max_file_size_mb": int(os.environ.get("MAX_FILE_SIZE_MB", 25)),
        "processing_time": "2-5 minutes depending on file complexity"
    }
