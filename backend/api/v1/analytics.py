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
        companies_tbl = database.companies_collection()
        total = companies_tbl.count()
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
    companies_tbl = database.companies_collection()
    scores_tbl = database.scores_collection()
    
    total = companies_tbl.count()
    
    # Status breakdown
    processing_statuses = ["processing", "extracting", "enriching", "scoring", "generating_memo"]
    status_breakdown = {
        "processing": companies_tbl.count({"status": {"$in": processing_statuses}}),
        "completed": companies_tbl.count({"status": "completed"}),
        "failed": companies_tbl.count({"status": "failed"})
    }
    
    # Tier distribution
    tier_distribution = {
        "TIER_1": scores_tbl.count({"tier": "TIER_1"}),
        "TIER_2": scores_tbl.count({"tier": "TIER_2"}),
        "TIER_3": scores_tbl.count({"tier": "TIER_3"}),
        "PASS": scores_tbl.count({"tier": "PASS"})
    }
    
    # Processing metrics
    processing_metrics = {
        "success_rate": round(status_breakdown["completed"] / total * 100, 2) if total > 0 else 0,
        "failure_rate": round(status_breakdown["failed"] / total * 100, 2) if total > 0 else 0,
        "in_progress": status_breakdown["processing"]
    }
    
    # Recent companies
    recent = companies_tbl.find_many(
        filters={"status": "completed"},
        order_by="created_at",
        order_desc=True,
        limit=5
    )
    recent_companies = []
    for r in recent:
        score = scores_tbl.find_one({"company_id": r["id"]})
        recent_companies.append({
            "id": r["id"],
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
    scores_tbl = database.scores_collection()
    total = scores_tbl.count()
    
    tiers = [
        {
            "tier": "TIER_1",
            "count": scores_tbl.count({"tier": "TIER_1"}),
            "description": "High-priority deals - Strong investment potential",
            "criteria": "Score >= 80"
        },
        {
            "tier": "TIER_2", 
            "count": scores_tbl.count({"tier": "TIER_2"}),
            "description": "Medium-priority deals - Worth further review",
            "criteria": "Score 60-79"
        },
        {
            "tier": "TIER_3",
            "count": scores_tbl.count({"tier": "TIER_3"}),
            "description": "Low-priority deals - Significant concerns",
            "criteria": "Score 40-59"
        },
        {
            "tier": "PASS",
            "count": scores_tbl.count({"tier": "PASS"}),
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
        companies_tbl = database.companies_collection()
        scores_tbl = database.scores_collection()
        
        total = companies_tbl.count()
        completed = companies_tbl.count({"status": "completed"})
        
        summary = {
            "total_deals": total,
            "completed_deals": completed,
            "system_status": "operational",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Add more details for authenticated users
        if authenticated:
            summary["tier_1_deals"] = scores_tbl.count({"tier": "TIER_1"})
            # Calculate average score
            all_scores = scores_tbl.find_many()
            if all_scores:
                avg = sum(s.get("total_score", 0) for s in all_scores) / len(all_scores)
                summary["average_score"] = round(avg, 2)
            else:
                summary["average_score"] = 0
            summary["processing"] = companies_tbl.count({
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
