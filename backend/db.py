"""
Centralized Supabase database connection management.

This module provides lazy initialization of Supabase connections.
It exposes collection-like accessor functions that return the Supabase
client scoped to a specific table, maintaining the same interface pattern
that the rest of the codebase expects.
"""
import os
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Global connection state - lazy initialized
_client: Optional[Client] = None
_connection_tested: bool = False


def get_supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise ValueError("SUPABASE_URL environment variable not set.")
    return url


def get_supabase_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY not set.")
    return key


def get_client() -> Client:
    """Get or create the Supabase client (lazy initialization)."""
    global _client
    if _client is None:
        url = get_supabase_url()
        key = get_supabase_key()
        logger.info(f"Creating Supabase client: {url[:40]}...")
        _client = create_client(url, key)
        logger.info("Supabase client created")
    return _client


def test_connection(max_retries: int = 3, retry_delay: float = 2.0) -> bool:
    """Test the Supabase connection with retries."""
    import time
    global _connection_tested

    client = get_client()
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Testing Supabase connection (attempt {attempt}/{max_retries})...")
            result = client.table("companies").select("id").limit(1).execute()
            logger.info("Supabase connection successful!")
            _connection_tested = True
            return True
        except Exception as e:
            logger.warning(f"Supabase connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                raise
    return False


def is_connected() -> bool:
    return _connection_tested


def close_connection():
    global _client, _connection_tested
    _client = None
    _connection_tested = False
    logger.info("Supabase connection reference cleared")


def create_indexes():
    """No-op for Supabase (indexes created in SQL schema)."""
    logger.info("Database indexes managed via Supabase SQL schema")


# ---------------------------------------------------------------------------
# Table accessor helpers – each returns a SupabaseTable wrapper
# ---------------------------------------------------------------------------

class SupabaseTable:
    """
    Thin wrapper around a Supabase table that provides convenience methods.
    Maintains a similar interface to the legacy MongoDB pattern for easy migration.
    """

    def __init__(self, table_name: str):
        self.table_name = table_name

    @property
    def _table(self):
        return get_client().table(self.table_name)

    # -- Insert --
    def insert(self, data: dict) -> dict:
        """Insert a row and return the inserted row (with id)."""
        result = self._table.insert(data).execute()
        return result.data[0] if result.data else {}

    # -- Select helpers --
    def find_by_id(self, row_id: str) -> Optional[dict]:
        result = self._table.select("*").eq("id", row_id).limit(1).execute()
        return result.data[0] if result.data else None

    def find_one(self, filters: dict, exclude_fields: list = None) -> Optional[dict]:
        q = self._table.select("*")
        for k, v in filters.items():
            q = q.eq(k, v)
        result = q.limit(1).execute()
        if not result.data:
            return None
        row = result.data[0]
        if exclude_fields:
            for f in exclude_fields:
                row.pop(f, None)
        return row

    def find_many(self, filters: dict = None, order_by: str = None, 
                  order_desc: bool = True, limit: int = None, 
                  offset: int = None) -> list:
        q = self._table.select("*")
        if filters:
            for k, v in filters.items():
                if isinstance(v, dict) and "$in" in v:
                    q = q.in_(k, v["$in"])
                else:
                    q = q.eq(k, v)
        if order_by:
            q = q.order(order_by, desc=order_desc)
        if offset is not None:
            q = q.offset(offset)
        if limit is not None:
            q = q.limit(limit)
        result = q.execute()
        return result.data or []

    # -- Update --
    def update(self, filters: dict, data: dict) -> list:
        q = self._table.update(data)
        for k, v in filters.items():
            q = q.eq(k, v)
        result = q.execute()
        return result.data or []

    def upsert(self, data: dict, conflict_column: str = "company_id") -> dict:
        """Upsert a row based on conflict column."""
        result = self._table.upsert(data, on_conflict=conflict_column).execute()
        return result.data[0] if result.data else {}

    # -- Delete --
    def delete(self, filters: dict) -> int:
        q = self._table.delete()
        for k, v in filters.items():
            q = q.eq(k, v)
        result = q.execute()
        return len(result.data) if result.data else 0

    # -- Count --
    def count(self, filters: dict = None) -> int:
        q = self._table.select("id", count="exact")
        if filters:
            for k, v in filters.items():
                if isinstance(v, dict) and "$in" in v:
                    q = q.in_(k, v["$in"])
                else:
                    q = q.eq(k, v)
        result = q.execute()
        return result.count if result.count is not None else 0


# Collection accessor functions – maintain same names for minimal diff
def companies_collection() -> SupabaseTable:
    return SupabaseTable("companies")


def pitch_decks_collection() -> SupabaseTable:
    return SupabaseTable("pitch_decks")


def founders_collection() -> SupabaseTable:
    return SupabaseTable("founders")


def enrichment_collection() -> SupabaseTable:
    return SupabaseTable("enrichment_sources")


def competitors_collection() -> SupabaseTable:
    return SupabaseTable("competitors")


def scores_collection() -> SupabaseTable:
    return SupabaseTable("investment_scores")


def memos_collection() -> SupabaseTable:
    return SupabaseTable("investment_memos")
