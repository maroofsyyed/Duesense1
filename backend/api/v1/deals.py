"""
Deals API - Manage VC deal/company data.
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import uuid
import db as database
from api.v1.auth import verify_api_key, optional_api_key

router = APIRouter(prefix="/deals", tags=["Deals"])


# Pydantic Models
class CompanyBase(BaseModel):
    """Base company model."""
    name: str = Field(..., description="Company name")
    website: Optional[str] = Field(None, description="Company website URL")
    tagline: Optional[str] = Field(None, description="Company tagline")
    stage: Optional[str] = Field(None, description="Funding stage")
    hq_location: Optional[str] = Field(None, description="Headquarters location")


class CompanyResponse(CompanyBase):
    """Company response model."""
    id: str = Field(..., description="Unique identifier")
    status: str = Field(..., description="Processing status")
    created_at: str = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class DealListResponse(BaseModel):
    """Response for deal list endpoint."""
    deals: List[CompanyResponse]
    total: int
    page: int
    page_size: int


class DealDetailResponse(BaseModel):
    """Detailed deal response."""
    company: CompanyResponse
    score: Optional[dict] = None
    memo: Optional[dict] = None
    pitch_decks: List[dict] = []
    founders: List[dict] = []
    enrichments: List[dict] = []


class DealStatsResponse(BaseModel):
    """Deal statistics response."""
    total_deals: int
    by_status: dict
    by_tier: dict
    recent_activity: List[dict]


# Helper functions
def validate_uuid(id_str: str) -> str:
    """Validate UUID format."""
    try:
        uuid.UUID(id_str)
        return id_str
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")


# Routes
@router.get("", response_model=DealListResponse)
async def list_deals(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    api_key: str = Depends(verify_api_key)
):
    """
    List all deals with pagination.
    
    Requires API key authentication.
    """
    companies_tbl = database.companies_collection()
    scores_tbl = database.scores_collection()
    
    # Build query filters
    filters = {}
    if status:
        filters["status"] = status
    
    # Get total count
    total = companies_tbl.count(filters)
    
    # Get paginated results
    skip = (page - 1) * page_size
    companies = companies_tbl.find_many(
        filters=filters,
        order_by="created_at",
        order_desc=True,
        offset=skip,
        limit=page_size
    )
    
    # Add scores
    deals = []
    for c in companies:
        score = scores_tbl.find_one({"company_id": c["id"]})
        if score:
            score.pop("id", None)
        c["score"] = score
        deals.append(c)
    
    return DealListResponse(
        deals=deals,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/stats", response_model=DealStatsResponse)
async def get_deal_stats(api_key: str = Depends(verify_api_key)):
    """
    Get deal statistics and analytics.
    
    Requires API key authentication.
    """
    companies_tbl = database.companies_collection()
    scores_tbl = database.scores_collection()
    
    total = companies_tbl.count()
    
    # Status breakdown
    by_status = {
        "processing": companies_tbl.count({"status": {"$in": ["processing", "extracting", "enriching", "scoring", "generating_memo"]}}),
        "completed": companies_tbl.count({"status": "completed"}),
        "failed": companies_tbl.count({"status": "failed"})
    }
    
    # Tier breakdown
    by_tier = {
        "tier_1": scores_tbl.count({"tier": "TIER_1"}),
        "tier_2": scores_tbl.count({"tier": "TIER_2"}),
        "tier_3": scores_tbl.count({"tier": "TIER_3"}),
        "pass": scores_tbl.count({"tier": "PASS"})
    }
    
    # Recent activity
    recent = companies_tbl.find_many(order_by="created_at", order_desc=True, limit=5)
    recent_activity = [
        {
            "id": r["id"],
            "name": r.get("name", "Unknown"),
            "status": r.get("status"),
            "created_at": r.get("created_at")
        }
        for r in recent
    ]
    
    return DealStatsResponse(
        total_deals=total,
        by_status=by_status,
        by_tier=by_tier,
        recent_activity=recent_activity
    )


@router.get("/{deal_id}", response_model=DealDetailResponse)
async def get_deal(deal_id: str, api_key: str = Depends(verify_api_key)):
    """
    Get detailed information about a specific deal.
    
    Requires API key authentication.
    """
    validate_uuid(deal_id)
    
    companies_tbl = database.companies_collection()
    company = companies_tbl.find_by_id(deal_id)
    
    if not company:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Get related data
    pitch_decks = database.pitch_decks_collection().find_many({"company_id": deal_id})
    founders = database.founders_collection().find_many({"company_id": deal_id})
    enrichments = database.enrichment_collection().find_many({"company_id": deal_id})
    score = database.scores_collection().find_one({"company_id": deal_id})
    if score:
        score.pop("id", None)
    memo = database.memos_collection().find_one({"company_id": deal_id})
    if memo:
        memo.pop("id", None)
    
    return DealDetailResponse(
        company=company,
        score=score,
        memo=memo,
        pitch_decks=pitch_decks,
        founders=founders,
        enrichments=enrichments
    )


@router.delete("/{deal_id}")
async def delete_deal(deal_id: str, api_key: str = Depends(verify_api_key)):
    """
    Delete a deal and all related data.
    
    Requires API key authentication.
    """
    validate_uuid(deal_id)
    
    # Delete from all tables
    database.pitch_decks_collection().delete({"company_id": deal_id})
    database.founders_collection().delete({"company_id": deal_id})
    database.enrichment_collection().delete({"company_id": deal_id})
    database.scores_collection().delete({"company_id": deal_id})
    database.competitors_collection().delete({"company_id": deal_id})
    database.memos_collection().delete({"company_id": deal_id})
    database.companies_collection().delete({"id": deal_id})
    
    return {"status": "deleted", "deal_id": deal_id}
