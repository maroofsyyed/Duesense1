"""
Health check endpoints for API v1.
"""
import sys
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
import db as database

router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Overall system status")
    service: str = Field(default="duesense-api", description="Service name")
    version: str = Field(default="1.0.0", description="API version")
    timestamp: str = Field(..., description="ISO timestamp")
    components: dict = Field(..., description="Component health status")


class ComponentHealth(BaseModel):
    """Individual component health."""
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns status of all system components including database and LLM.
    """
    components = {}
    overall_status = "healthy"
    
    # Check Supabase database
    db_start = datetime.now(timezone.utc)
    try:
        client = database.get_client()
        # Simple SELECT to verify connection
        client.table("companies").select("id").limit(1).execute()
        db_latency = (datetime.now(timezone.utc) - db_start).total_seconds() * 1000
        components["database"] = {
            "status": "healthy",
            "latency_ms": round(db_latency, 2),
            "type": "supabase"
        }
    except Exception as e:
        components["database"] = {
            "status": "unhealthy",
            "message": str(e)[:100],
            "type": "supabase"
        }
        overall_status = "degraded"
    
    # Check LLM provider
    try:
        from services.llm_provider import llm
        llm._validate_token()
        components["llm"] = {
            "status": "healthy",
            "provider": llm.current_provider["name"],
            "model": llm.current_model
        }
    except Exception as e:
        components["llm"] = {
            "status": "unhealthy",
            "message": str(e)[:100]
        }
        overall_status = "degraded"
    
    # Check Python runtime
    components["runtime"] = {
        "status": "healthy",
        "python_version": sys.version.split()[0],
        "platform": sys.platform
    }
    
    return HealthResponse(
        status=overall_status,
        service="duesense-api",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components
    )


@router.get("/live")
async def liveness():
    """
    Kubernetes-style liveness probe.
    
    Returns 200 if the service is running.
    """
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """
    Kubernetes-style readiness probe.
    
    Returns 200 if the service is ready to accept traffic (database connected).
    """
    try:
        client = database.get_client()
        client.table("companies").select("id").limit(1).execute()
        return {"status": "ready", "database": "connected"}
    except Exception:
        return {"status": "not_ready", "database": "disconnected"}
