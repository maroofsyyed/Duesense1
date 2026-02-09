#!/usr/bin/env python3
"""
Test different MongoDB connection string formats
This will tell us EXACTLY what works and what doesn't
"""

import os
import sys
from pymongo import MongoClient
from urllib.parse import quote_plus  # noqa: F401  # kept for potential manual tests
import certifi


def test_connection(uri, description):
    """Test a single connection string"""
    print(f"\n{'=' * 60}")
    print(f"Testing: {description}")
    print(f"{'=' * 60}")
    print(f"URI format: {uri[:50]}...")

    try:
        print("Attempting connection...")
        client = MongoClient(
            uri,
            tls=True,
            tlsAllowInvalidCertificates=False,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
        )

        # Test ping
        result = client.admin.command("ping")
        print(f"✅ SUCCESS! Ping result: {result}")

        # Get server info
        info = client.server_info()
        print(f"✅ MongoDB version: {info.get('version')}")

        client.close()
        return True

    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}")
        print(f"   Error: {str(e)[:200]}")
        return False


def main():
    """Test different connection string formats"""

    # Get base URI
    base_uri = os.getenv("MONGODB_URI")
    if not base_uri:
        print("❌ MONGODB_URI not set!")
        return 1

    print("=" * 60)
    print("MONGODB CONNECTION STRING TESTING")
    print("=" * 60)

    results = {}

    # Test 1: Original URI as-is
    results["Original URI"] = test_connection(
        base_uri,
        "Original URI from environment (as-is)",
    )

    # Test 2: Force SSL in URI
    if "?" in base_uri:
        uri_with_ssl = f"{base_uri}&tls=true&tlsAllowInvalidCertificates=false"
    else:
        uri_with_ssl = f"{base_uri}?tls=true&tlsAllowInvalidCertificates=false"

    results["URI with explicit TLS"] = test_connection(
        uri_with_ssl,
        "URI with explicit tls=true parameter",
    )

    # Test 3: Minimal URI (remove all params except retryWrites)
    if "?" in base_uri:
        base_part = base_uri.split("?", 1)[0]
        minimal_uri = f"{base_part}?retryWrites=true"
    else:
        minimal_uri = f"{base_uri}?retryWrites=true"

    results["Minimal URI"] = test_connection(
        minimal_uri,
        "Minimal URI (only retryWrites)",
    )

    # Test 4: SRV warning
    if base_uri.startswith("mongodb+srv://"):
        print("\n⚠️  SRV connection string detected")
        print("   This requires DNS resolution + TLS")
        print("   If this is the issue, we need to use standard mongodb:// format")

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test}")

    if not any(results.values()):
        print("\n🚨 ALL TESTS FAILED!")
        print("\nPossible causes:")
        print("1. MongoDB Atlas IP whitelist doesn't include Render's IPs")
        print("2. Wrong username/password in connection string")
        print("3. MongoDB cluster is paused or deleted")
        print("4. Connection string uses unsupported format")

        print("\n📋 NEXT STEPS:")
        print("1. Go to MongoDB Atlas → Network Access")
        print("2. Add IP: 0.0.0.0/0 (allow all)")
        print("3. Go to Database Access → verify user exists")
        print("4. Try connection string tester again")

        return 1
    else:
        working = [k for k, v in results.items() if v]
        print(f"\n✅ Working format: {working[0]}")
        print("Use this format in your application!")
        return 0


if __name__ == "__main__":
    sys.exit(main())


