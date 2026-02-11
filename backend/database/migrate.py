"""
Database migration script for Supabase
Run this once to set up production schema
"""
import os
from pathlib import Path


def run_migration():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    # Read schema file
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r") as f:
        schema = f.read()

    print("Running Supabase schema migration...")
    print("Please run the SQL from schema.sql in your Supabase SQL Editor")
    print(f"Schema file location: {schema_path}")

    return schema


if __name__ == "__main__":
    run_migration()
