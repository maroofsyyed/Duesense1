"""Alternative MongoDB connection using synchronous PyMongo with an asyncio wrapper.

This module is intended as a **fallback** when async drivers (e.g. Motor)
or certain SSL configurations are problematic.

Usage pattern (example with FastAPI):

    from fastapi import FastAPI
    from backend.db_alternative1 import (
        db,
        async_mongo_operation,
        get_companies_sync,
    )

    app = FastAPI()

    # Wrap sync operations for use in async routes
    get_companies = async_mongo_operation(get_companies_sync)

    @app.get("/api/companies-alt")
    async def list_companies_alt():
        companies = await get_companies()
        return {"companies": companies}
"""

import os
import asyncio
from functools import wraps
from typing import Any, Callable, TypeVar, Coroutine, List, Dict

import certifi
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


T = TypeVar("T")


def get_sync_client() -> MongoClient:
    """Create a **synchronous** MongoDB client using PyMongo.

    This mirrors the configuration used in `backend/server.py`
    but is kept in a separate module so it can be swapped in easily.
    """
    mongodb_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL")
    db_name = os.getenv("DB_NAME")

    if not mongodb_uri:
        raise ValueError("MONGODB_URI (or legacy MONGO_URL) environment variable not set")

    client = MongoClient(
        mongodb_uri,
        # TLS/SSL settings
        tls=True,
        tlsAllowInvalidCertificates=False,
        tlsCAFile=certifi.where(),
        # Connection settings
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
        socketTimeoutMS=30000,
        # Connection pool settings
        maxPoolSize=10,
        minPoolSize=1,
        maxIdleTimeMS=45000,
        # Retry settings
        retryWrites=True,
        retryReads=True,
        # Write concern
        w="majority",
        journal=True,
    )

    # Select database
    if db_name:
        db = client[db_name]
    else:
        db = client.get_default_database()

    # Light-touch connectivity check (optional)
    try:
        client.admin.command("ping")
    except ConnectionFailure:
        # Let callers handle actual failures; this just surfaces early
        raise

    return client


def async_mongo_operation(
    func: Callable[..., T]
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Decorator to run **synchronous** PyMongo operations in an async context.

    The wrapped function is executed in the default thread pool via
    `loop.run_in_executor`, so your FastAPI endpoints can remain `async`
    while still using the stable synchronous PyMongo client.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    return wrapper


# Global client & db handles for convenience
_client = get_sync_client()
db = _client.get_database()


def find_companies_sync() -> List[Dict[str, Any]]:
    """Example synchronous operation: fetch all companies.

    This is intended as a reference for how to structure sync operations
    that you then wrap with `async_mongo_operation` in your routes.
    """
    return list(db.companies.find())


# Example async-ready wrapper that can be imported directly if desired:
find_companies = async_mongo_operation(find_companies_sync)


