#!/usr/bin/env python3
"""
Environment and MongoDB Atlas Configuration Verification Script
Run this to check if your setup is correct before deploying.
"""

import os
import sys
import certifi
import ssl


def check_environment():
    """Check environment variables"""
    print("=" * 60)
    print("ENVIRONMENT VARIABLES CHECK")
    print("=" * 60)

    mongodb_uri = os.getenv("MONGODB_URI")

    if not mongodb_uri:
        print("❌ MONGODB_URI not set!")
        print("\nSet it with:")
        print('export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/dbname"')
        return False

    # Mask the URI for security
    if "@" in mongodb_uri:
        parts = mongodb_uri.split("@")
        masked = f"{parts[0][:20]}...@{parts[1]}"
    else:
        masked = f"{mongodb_uri[:30]}..."

    print(f"✓ MONGODB_URI is set: {masked}")

    # Check URI format
    if mongodb_uri.startswith("mongodb+srv://"):
        print("✓ Using SRV connection string (correct for Atlas)")
    elif mongodb_uri.startswith("mongodb://"):
        print("⚠ Using standard connection string (should be mongodb+srv:// for Atlas)")
    else:
        print("❌ Invalid MongoDB URI format")
        return False

    # Check for required parameters
    if "retryWrites=true" not in mongodb_uri:
        print("⚠ Missing retryWrites=true in URI (recommended for Atlas)")

    if "w=majority" not in mongodb_uri:
        print("⚠ Missing w=majority in URI (recommended for Atlas)")

    return True


def check_python_version():
    """Check Python version"""
    print("\n" + "=" * 60)
    print("PYTHON VERSION CHECK")
    print("=" * 60)

    version = sys.version
    major, minor = sys.version_info[:2]

    print(f"Python version: {version}")

    if major == 3 and minor == 11:
        print("✓ Python 3.11.x detected (recommended)")
        return True
    elif major == 3 and minor == 12:
        print("✓ Python 3.12.x detected (also compatible)")
        return True
    else:
        print(f"⚠ Python {major}.{minor} - recommend Python 3.11 or 3.12")
        return True


def check_openssl():
    """Check OpenSSL version"""
    print("\n" + "=" * 60)
    print("OPENSSL VERSION CHECK")
    print("=" * 60)

    try:
        openssl_version = ssl.OPENSSL_VERSION
        print(f"OpenSSL version: {openssl_version}")

        # Extract version number
        if "OpenSSL 1.1.1" in openssl_version:
            print("✓ OpenSSL 1.1.1 detected (BEST for MongoDB Atlas)")
            return True
        elif "OpenSSL 3.0" in openssl_version:
            print("⚠ OpenSSL 3.0.x detected (may have issues with MongoDB Atlas)")
            print("   Recommendation: Use python:3.11.9-bullseye instead of -slim")
            return False
        elif "OpenSSL 3.1" in openssl_version or "OpenSSL 3.2" in openssl_version:
            print("✓ OpenSSL 3.1+ detected (should work with MongoDB Atlas)")
            return True
        else:
            print(f"⚠ Unknown OpenSSL version: {openssl_version}")
            return True
    except Exception as e:
        print(f"❌ Error checking OpenSSL: {e}")
        return False


def check_certifi():
    """Check certifi package"""
    print("\n" + "=" * 60)
    print("CERTIFI CHECK")
    print("=" * 60)

    try:
        cert_path = certifi.where()
        print("✓ certifi installed")
        print(f"  Certificate bundle: {cert_path}")

        if os.path.exists(cert_path):
            print("✓ Certificate bundle exists")
            return True
        else:
            print("❌ Certificate bundle not found!")
            return False
    except Exception as e:
        print(f"❌ certifi error: {e}")
        return False


def check_pymongo():
    """Check pymongo and motor"""
    print("\n" + "=" * 60)
    print("MONGODB DRIVERS CHECK")
    print("=" * 60)

    try:
        import pymongo

        print(f"✓ pymongo version: {pymongo.__version__}")

        if pymongo.version_tuple[0] >= 4 and pymongo.version_tuple[1] >= 10:
            print("  ✓ Version is 4.10.0+")
        else:
            print("  ⚠ Version is older than 4.10.0")
    except ImportError:
        print("❌ pymongo not installed!")
        return False

    try:
        import motor

        print(f"✓ motor version: {motor.version}")

        if motor.version_tuple[0] >= 3 and motor.version_tuple[1] >= 7:
            print("  ✓ Version is 3.7.0+")
        else:
            print("  ⚠ Version is older than 3.7.0")
    except ImportError:
        print("❌ motor not installed!")
        return False

    return True


def check_ssl_protocols():
    """Check available SSL/TLS protocols"""
    print("\n" + "=" * 60)
    print("SSL/TLS PROTOCOLS CHECK")
    print("=" * 60)

    try:
        # Check TLS 1.2 support
        try:
            ssl.TLSVersion.TLSv1_2
            print("✓ TLS 1.2 supported")
        except AttributeError:
            print("❌ TLS 1.2 not available")

        # Check TLS 1.3 support
        try:
            ssl.TLSVersion.TLSv1_3
            print("✓ TLS 1.3 supported")
        except AttributeError:
            print("  TLS 1.3 not available (not required)")

        return True
    except Exception as e:
        print(f"❌ Error checking TLS protocols: {e}")
        return False


def main():
    """Run all checks"""
    print("\n" + "=" * 60)
    print("MONGODB ATLAS CONNECTION VERIFICATION")
    print("=" * 60)

    results = {
        "Environment": check_environment(),
        "Python Version": check_python_version(),
        "OpenSSL": check_openssl(),
        "Certifi": check_certifi(),
        "MongoDB Drivers": check_pymongo(),
        "SSL/TLS Protocols": check_ssl_protocols(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for check, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All checks passed! Your setup should work with MongoDB Atlas.")
        return 0
    else:
        print("\n⚠️ Some checks failed. Review the issues above before deploying.")
        print("\nMost common fixes:")
        print("1. If OpenSSL 3.0.x: Use python:3.11.9-bullseye in Dockerfile")
        print("2. If MONGODB_URI missing: Set environment variable in Render")
        print("3. If drivers outdated: Update requirements.txt versions")
        return 1


if __name__ == "__main__":
    sys.exit(main())


