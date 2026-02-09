"""
Analytics API - Dashboard statistics and insights.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
import db as database
from api.v1.auth import verify_api_key, optional_api_key

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# Pydantic Models
class PublicStatsResponse(BaseModel):
    """Public statistics - no auth required."""
    service: str = "DueSense"
    total_deals_processed: int
    system_status: str
    last_updated: str


class DetailedStatsResponse(BaseModel):
    """Detailed statistics - auth required."""
    total_companies: int
    status_breakdown: dict
    tier_distribution: dict
    processing_metrics: dict
    recent_companies: list
    timestamp: str


class TierInsight(BaseModel):
    """Tier insight model."""
    tier: str
    count: int
    percentage: float
    description: str


# Routes
@router.get("/public", response_model=PublicStatsResponse)
async def get_public_stats():
    """
    Get public statistics.
    
    No authentication required. Returns limited public data.
    """
    try:
        companies_col = database.companies_collection()
        total = companies_col.count_documents({})
        system_status = "operational"
    except Exception:
        total = 0
        system_status = "degraded"
    
    return PublicStatsResponse(
        service="DueSense",
        total_deals_processed=total,
        system_status=system_status,
        last_updated=datetime.now(timezone.utc).isoformat()
    )


@router.get("/dashboard", response_model=DetailedStatsResponse)
async def get_dashboard_stats(api_key: str = Depends(verify_api_key)):
    """
    Get detailed dashboard statistics.
    
    Requires API key authentication.
    """
    companies_col = database.companies_collection()
    scores_col = database.scores_collection()
    
    total = companies_col.count_documents({})
    
    # Status breakdown
    processing_statuses = ["processing", "extracting", "enriching", "scoring", "generating_memo"]
    status_breakdown = {
        "processing": companies_col.count_documents({"status": {"$in": processing_statuses}}),
        "completed": companies_col.count_documents({"status": "completed"}),
        "failed": companies_col.count_documents({"status": "failed"})
    }
    
    # Tier distribution
    tier_distribution = {
        "TIER_1": scores_col.count_documents({"tier": "TIER_1"}),
        "TIER_2": scores_col.count_documents({"tier": "TIER_2"}),
        "TIER_3": scores_col.count_documents({"tier": "TIER_3"}),
        "PASS": scores_col.count_documents({"tier": "PASS"})
    }
    
    # Processing metrics
    processing_metrics = {
        "success_rate": round(status_breakdown["completed"] / total * 100, 2) if total > 0 else 0,
        "failure_rate": round(status_breakdown["failed"] / total * 100, 2) if total > 0 else 0,
        "in_progress": status_breakdown["processing"]
    }
    
    # Recent companies
    recent = list(companies_col.find({"status": "completed"}).sort("created_at", -1).limit(5))
    recent_companies = []
    for r in recent:
        r_id = str(r["_id"])
        score = scores_col.find_one({"company_id": r_id}, {"_id": 0})
        recent_companies.append({
            "id": r_id,
            "name": r.get("name", "Unknown"),
            "status": r.get("status"),
            "tier": score.get("tier") if score else None,
            "score": score.get("total_score") if score else None,
            "created_at": r.get("created_at")
        })
    
    return DetailedStatsResponse(
        total_companies=total,
        status_breakdown=status_breakdown,
        tier_distribution=tier_distribution,
        processing_metrics=processing_metrics,
        recent_companies=recent_companies,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/tier-insights")
async def get_tier_insights(api_key: str = Depends(verify_api_key)):
    """
    Get insights about deal tiers.
    
    Requires API key authentication.
    """
    scores_col = database.scores_collection()
    total = scores_col.count_documents({})
    
    tiers = [
        {
            "tier": "TIER_1",
            "count": scores_col.count_documents({"tier": "TIER_1"}),
            "description": "High-priority deals - Strong investment potential",
            "criteria": "Score >= 80"
        },
        {
            "tier": "TIER_2", 
            "count": scores_col.count_documents({"tier": "TIER_2"}),
            "description": "Medium-priority deals - Worth further review",
            "criteria": "Score 60-79"
        },
        {
            "tier": "TIER_3",
            "count": scores_col.count_documents({"tier": "TIER_3"}),
            "description": "Low-priority deals - Significant concerns",
            "criteria": "Score 40-59"
        },
        {
            "tier": "PASS",
            "count": scores_col.count_documents({"tier": "PASS"}),
            "description": "Not recommended - Multiple red flags",
            "criteria": "Score < 40"
        }
    ]
    
    for tier in tiers:
        tier["percentage"] = round(tier["count"] / total * 100, 2) if total > 0 else 0
    
    return {
        "total_scored": total,
        "tiers": tiers,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/summary")
async def get_summary(authenticated: Optional[str] = Depends(optional_api_key)):
    """
    Get summary statistics.
    
    Returns more details if authenticated.
    """
    try:
        companies_col = database.companies_collection()
        scores_col = database.scores_collection()
        
        total = companies_col.count_documents({})
        completed = companies_col.count_documents({"status": "completed"})
        
        summary = {
            "total_deals": total,
            "completed_deals": completed,
            "system_status": "operational",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add more details for authenticated users
        if authenticated:
            summary["tier_1_deals"] = scores_col.count_documents({"tier": "TIER_1"})
            summary["average_score"] = _calculate_average_score(scores_col)
            summary["processing"] = companies_col.count_documents({
                "status": {"$in": ["processing", "extracting", "enriching", "scoring", "generating_memo"]}
            })
            summary["authenticated"] = True
        else:
            summary["authenticated"] = False
            summary["note"] = "Authenticate for detailed statistics"
        
        return summary
        
    except Exception as e:
        return {
            "total_deals": 0,
            "completed_deals": 0,
            "system_status": "degraded",
            "error": "Database temporarily unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def _calculate_average_score(scores_col):
    """Calculate average score across all scored deals."""
    pipeline = [
        {"$group": {"_id": None, "avg_score": {"$avg": "$total_score"}}}
    ]
    result = list(scores_col.aggregate(pipeline))
    if result and result[0].get("avg_score"):
        return round(result[0]["avg_score"], 2)
    return 0
