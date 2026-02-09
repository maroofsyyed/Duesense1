"""
Deals API - Manage VC deal/company data.
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.errors import InvalidId
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
def serialize_company(doc) -> dict:
    """Serialize MongoDB document to dict."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def validate_object_id(id_str: str) -> ObjectId:
    """Validate and return ObjectId."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
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
    companies_col = database.companies_collection()
    scores_col = database.scores_collection()
    
    # Build query
    query = {}
    if status:
        query["status"] = status
    
    # Get total count
    total = companies_col.count_documents(query)
    
    # Get paginated results
    skip = (page - 1) * page_size
    companies = list(
        companies_col.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    
    # Serialize and add scores
    deals = []
    for c in companies:
        deal = serialize_company(c)
        score = scores_col.find_one({"company_id": deal["id"]}, {"_id": 0})
        deal["score"] = score
        deals.append(deal)
    
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
    companies_col = database.companies_collection()
    scores_col = database.scores_collection()
    
    total = companies_col.count_documents({})
    
    # Status breakdown
    by_status = {
        "processing": companies_col.count_documents({"status": {"$in": ["processing", "extracting", "enriching", "scoring", "generating_memo"]}}),
        "completed": companies_col.count_documents({"status": "completed"}),
        "failed": companies_col.count_documents({"status": "failed"})
    }
    
    # Tier breakdown
    by_tier = {
        "tier_1": scores_col.count_documents({"tier": "TIER_1"}),
        "tier_2": scores_col.count_documents({"tier": "TIER_2"}),
        "tier_3": scores_col.count_documents({"tier": "TIER_3"}),
        "pass": scores_col.count_documents({"tier": "PASS"})
    }
    
    # Recent activity
    recent = list(companies_col.find().sort("created_at", -1).limit(5))
    recent_activity = [
        {
            "id": str(r["_id"]),
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
    obj_id = validate_object_id(deal_id)
    
    companies_col = database.companies_collection()
    company = companies_col.find_one({"_id": obj_id})
    
    if not company:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    company_data = serialize_company(company)
    
    # Get related data
    pitch_decks = list(database.pitch_decks_collection().find({"company_id": deal_id}))
    founders = list(database.founders_collection().find({"company_id": deal_id}))
    enrichments = list(database.enrichment_collection().find({"company_id": deal_id}))
    score = database.scores_collection().find_one({"company_id": deal_id}, {"_id": 0})
    memo = database.memos_collection().find_one({"company_id": deal_id}, {"_id": 0})
    
    return DealDetailResponse(
        company=company_data,
        score=score,
        memo=memo,
        pitch_decks=[serialize_company(d) for d in pitch_decks],
        founders=[serialize_company(f) for f in founders],
        enrichments=[serialize_company(e) for e in enrichments]
    )


@router.delete("/{deal_id}")
async def delete_deal(deal_id: str, api_key: str = Depends(verify_api_key)):
    """
    Delete a deal and all related data.
    
    Requires API key authentication.
    """
    obj_id = validate_object_id(deal_id)
    
    # Delete from all collections
    database.companies_collection().delete_one({"_id": obj_id})
    database.pitch_decks_collection().delete_many({"company_id": deal_id})
    database.founders_collection().delete_many({"company_id": deal_id})
    database.enrichment_collection().delete_many({"company_id": deal_id})
    database.scores_collection().delete_many({"company_id": deal_id})
    database.competitors_collection().delete_many({"company_id": deal_id})
    database.memos_collection().delete_many({"company_id": deal_id})
    
    return {"status": "deleted", "deal_id": deal_id}
