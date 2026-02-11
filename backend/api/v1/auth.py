"""
Authentication module for DueSense API.

Implements API Key authentication for protected endpoints.
"""
import os
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Security, Depends, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# API Key header scheme
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# In production, store API keys in database or secure vault
# For now, we support environment-based keys
def get_valid_api_keys() -> set:
    """Get valid API keys from environment with security checks."""
    keys = set()
    
    # Primary API key
    primary_key = os.environ.get("DUESENSE_API_KEY")
    if primary_key and primary_key != "demo-key-for-testing":
        keys.add(primary_key)
    
    # Additional keys (comma-separated)
    additional_keys = os.environ.get("DUESENSE_API_KEYS", "")
    if additional_keys:
        for key in additional_keys.split(","):
            key = key.strip()
            if key and len(key) >= 16:  # Minimum key length
                keys.add(key)
    
    # Demo key ONLY if explicitly enabled (NEVER in production)
    if os.environ.get("ENABLE_DEMO_KEY", "false").lower() == "true":
        keys.add("demo-key-for-testing")
        logger.warning("Demo API key enabled - NOT for production use!")
    
    if not keys:
        logger.error("No valid API keys configured!")
        raise ValueError(
            "No API keys configured. Set DUESENSE_API_KEY environment variable.\n"
            "Never use 'demo-key-for-testing' in production."
        )
    
    logger.info(f"{len(keys)} API key(s) configured")
    return keys


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Verify API key from request header.
    
    Use as a dependency for protected endpoints:
        @router.get("/protected", dependencies=[Depends(verify_api_key)])
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    valid_keys = get_valid_api_keys()
    
    if api_key not in valid_keys:
        logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    
    return api_key


def optional_api_key(api_key: str = Security(API_KEY_HEADER)) -> Optional[str]:
    """
    Optional API key verification - doesn't fail if missing.
    
    Use for endpoints that have different behavior based on auth status.
    """
    if not api_key:
        return None
    
    valid_keys = get_valid_api_keys()
    return api_key if api_key in valid_keys else None


# Pydantic models
class APIKeyResponse(BaseModel):
    """Response model for API key generation."""
    api_key: str = Field(..., description="The generated API key")
    created_at: str = Field(..., description="ISO timestamp of creation")
    note: str = Field(..., description="Usage instructions")


class AuthStatusResponse(BaseModel):
    """Response model for auth status check."""
    authenticated: bool
    key_prefix: Optional[str] = None
    message: str


# Routes
@router.get("/status", response_model=AuthStatusResponse)
async def check_auth_status(api_key: Optional[str] = Depends(optional_api_key)):
    """
    Check authentication status.
    
    Returns whether the provided API key is valid.
    """
    if api_key:
        return AuthStatusResponse(
            authenticated=True,
            key_prefix=api_key[:8] + "...",
            message="API key is valid"
        )
    return AuthStatusResponse(
        authenticated=False,
        key_prefix=None,
        message="No valid API key provided"
    )


@router.post("/generate-key", response_model=APIKeyResponse)
async def generate_api_key(master_key: str = Security(API_KEY_HEADER)):
    """
    Generate a new API key (requires master key).
    
    Only users with the master API key can generate new keys.
    In production, implement proper key storage.
    """
    master = os.environ.get("DUESENSE_MASTER_KEY")
    
    if not master:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Key generation not configured. Set DUESENSE_MASTER_KEY."
        )
    
    if master_key != master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master key required for key generation"
        )
    
    # Generate a secure API key
    new_key = f"ds_{secrets.token_urlsafe(32)}"
    
    # In production, store this key in database
    logger.info(f"Generated new API key: {new_key[:12]}...")
    
    return APIKeyResponse(
        api_key=new_key,
        created_at=datetime.now(timezone.utc).isoformat(),
        note="Store this key securely. Add to DUESENSE_API_KEYS environment variable."
    )


@router.get("/info")
async def auth_info():
    """
    Get authentication information and requirements.
    
    Public endpoint explaining how to authenticate.
    """
    return {
        "auth_method": "API Key",
        "header_name": "X-API-Key",
        "example": {
            "curl": 'curl -H "X-API-Key: your-api-key" https://api.dominionvault.com/api/v1/deals',
            "python": 'requests.get(url, headers={"X-API-Key": "your-api-key"})',
            "javascript": 'fetch(url, { headers: { "X-API-Key": "your-api-key" } })'
        },
        "public_endpoints": [
            "/",
            "/health",
            "/docs",
            "/api/v1/health",
            "/api/v1/auth/info",
            "/api/v1/auth/status",
            "/api/v1/analytics/public"
        ],
        "protected_endpoints": [
            "/api/v1/deals/*",
            "/api/v1/ingestion/*",
            "/api/v1/analytics/detailed"
        ]
    }
