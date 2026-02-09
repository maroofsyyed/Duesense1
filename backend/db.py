"""
Centralized MongoDB connection management.

This module provides lazy initialization of MongoDB connections to ensure:
1. The app can boot even if MongoDB is temporarily unavailable
2. Connection pooling is properly managed
3. All services use the same connection pool
4. Environment variable validation happens at connection time, not import time
"""
import os
import logging
import certifi
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, ConfigurationError

logger = logging.getLogger(__name__)

# Global connection state - lazy initialized
_client: Optional[MongoClient] = None
_db: Optional[Database] = None
_connection_tested: bool = False


def get_mongo_uri() -> str:
    """Get MongoDB URI from environment variables with validation."""
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
    if not uri:
        raise ValueError(
            "MongoDB connection string not configured. "
            "Set MONGODB_URI or MONGO_URL environment variable."
        )
    if not (uri.startswith("mongodb+srv://") or uri.startswith("mongodb://")):
        raise ValueError(
            "Invalid MongoDB URI format. "
            "Must start with 'mongodb://' or 'mongodb+srv://'"
        )
    return uri


def get_db_name() -> str:
    """Get database name from environment or URI."""
    return os.environ.get("DB_NAME", "duesense")


def _clean_uri(uri: str) -> str:
    """Clean and rebuild MongoDB URI with essential parameters only."""
    if "?" in uri:
        base_uri = uri.split("?", 1)[0]
    else:
        base_uri = uri
    return f"{base_uri}?retryWrites=true&w=majority"


def get_client() -> MongoClient:
    """
    Get or create the MongoDB client (lazy initialization).
    
    The client is created on first access, not at module import time.
    This allows the app to start even if MongoDB is temporarily unavailable.
    """
    global _client
    
    if _client is None:
        uri = get_mongo_uri()
        clean_uri = _clean_uri(uri)
        
        # Log connection attempt (mask credentials)
        safe_uri = clean_uri[:40] + "..." if len(clean_uri) > 40 else clean_uri
        logger.info(f"Creating MongoDB client: {safe_uri}")
        
        _client = MongoClient(
            clean_uri,
            tls=True,
            tlsAllowInvalidCertificates=False,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=20000,
            socketTimeoutMS=30000,
            maxPoolSize=50,
            minPoolSize=5,
            retryWrites=True,
            retryReads=True,
        )
        logger.info("MongoDB client created (connection not yet tested)")
    
    return _client


def get_database() -> Database:
    """Get the MongoDB database instance."""
    global _db
    
    if _db is None:
        client = get_client()
        db_name = get_db_name()
        _db = client[db_name]
        logger.info(f"Using database: {db_name}")
    
    return _db


def get_collection(name: str) -> Collection:
    """Get a collection from the database."""
    return get_database()[name]


def test_connection(max_retries: int = 3, retry_delay: float = 2.0) -> bool:
    """
    Test the MongoDB connection with retries.
    
    Returns True if connection is successful, raises exception otherwise.
    """
    import asyncio
    global _connection_tested
    
    client = get_client()
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Testing MongoDB connection (attempt {attempt}/{max_retries})...")
            result = client.admin.command("ping")
            logger.info(f"✓ MongoDB connection successful! Ping: {result}")
            
            # Get server info for logging
            try:
                server_info = client.server_info()
                logger.info(f"✓ MongoDB version: {server_info.get('version', 'unknown')}")
            except Exception:
                pass  # Server info is optional
            
            _connection_tested = True
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"MongoDB connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                import time
                time.sleep(retry_delay)
            else:
                raise
        except Exception as e:
            logger.error(f"Unexpected error testing MongoDB connection: {e}")
            if attempt < max_retries:
                import time
                time.sleep(retry_delay)
            else:
                raise
    
    return False


def is_connected() -> bool:
    """Check if MongoDB connection has been tested successfully."""
    return _connection_tested


def close_connection():
    """Close the MongoDB connection."""
    global _client, _db, _connection_tested
    
    if _client is not None:
        try:
            _client.close()
            logger.info("✓ MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")
        finally:
            _client = None
            _db = None
            _connection_tested = False


def create_indexes():
    """Create database indexes (called during startup)."""
    try:
        db = get_database()
        
        # Companies collection
        db["companies"].create_index("name")
        db["companies"].create_index("created_at")
        
        # Pitch decks
        db["pitch_decks"].create_index("company_id")
        
        # Founders
        db["founders"].create_index("company_id")
        
        # Enrichment sources
        db["enrichment_sources"].create_index("company_id")
        db["enrichment_sources"].create_index([("company_id", 1), ("source_type", 1)])
        
        # Investment scores
        db["investment_scores"].create_index("company_id", unique=True)
        
        # Investment memos
        db["investment_memos"].create_index("company_id", unique=True)
        
        # Competitors
        db["competitors"].create_index("company_id")
        
        logger.info("✓ Database indexes created successfully")
        
    except Exception as e:
        # Don't fail startup if indexes already exist or there's a transient issue
        logger.warning(f"Index creation note: {e}")


# Collection accessor functions for convenience
def companies_collection() -> Collection:
    return get_collection("companies")


def pitch_decks_collection() -> Collection:
    return get_collection("pitch_decks")


def founders_collection() -> Collection:
    return get_collection("founders")


def enrichment_collection() -> Collection:
    return get_collection("enrichment_sources")


def competitors_collection() -> Collection:
    return get_collection("competitors")


def scores_collection() -> Collection:
    return get_collection("investment_scores")


def memos_collection() -> Collection:
    return get_collection("investment_memos")
