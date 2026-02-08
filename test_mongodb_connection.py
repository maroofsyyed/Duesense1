#!/usr/bin/env python3
"""
MongoDB Connection Test Script
Tests MongoDB Atlas SSL/TLS connection with proper certificate handling.
Run this locally before deploying to verify everything works.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_python_version():
    """Check if Python version is 3.11.x"""
    version = sys.version_info
    print(f"Python Version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor != 11:
        print("⚠️  WARNING: Python 3.11.x is recommended for MongoDB Atlas SSL compatibility")
        print("   Python 3.13.4 has known SSL/TLS issues with MongoDB Atlas")
    else:
        print("✅ Python version is correct (3.11.x)")
    
    return version.major == 3 and version.minor == 11

def check_certifi():
    """Check if certifi is installed and working"""
    try:
        import certifi
        cert_path = certifi.where()
        print(f"✅ certifi is installed")
        print(f"   Certificate file location: {cert_path}")
        
        # Check if file exists
        if os.path.exists(cert_path):
            file_size = os.path.getsize(cert_path)
            print(f"   Certificate file size: {file_size:,} bytes")
            print("✅ Certificate file exists and is readable")
            return True
        else:
            print("❌ Certificate file does not exist!")
            return False
    except ImportError:
        print("❌ certifi is NOT installed")
        print("   Install it with: pip install certifi")
        return False

def check_pymongo():
    """Check if pymongo is installed"""
    try:
        import pymongo
        print(f"✅ pymongo is installed (version: {pymongo.__version__})")
        return True
    except ImportError:
        print("❌ pymongo is NOT installed")
        print("   Install it with: pip install pymongo")
        return False

def test_mongodb_connection():
    """Test MongoDB connection with SSL/TLS"""
    import certifi
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    
    if not mongo_url:
        print("❌ MONGO_URL environment variable is not set")
        print("   Set it in .env file or export it:")
        print("   export MONGO_URL='mongodb+srv://...'")
        return False
    
    if not db_name:
        print("❌ DB_NAME environment variable is not set")
        print("   Set it in .env file or export it:")
        print("   export DB_NAME='your_database_name'")
        return False
    
    print(f"\n📡 Testing MongoDB connection...")
    print(f"   Database: {db_name}")
    print(f"   Connection string: {mongo_url[:30]}...{mongo_url[-20:]}")
    
    try:
        print("\n   Creating MongoDB client with SSL/TLS configuration...")
        client = MongoClient(
            mongo_url,
            tls=True,
            tlsAllowInvalidCertificates=False,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
        )
        
        print("   Testing connection with ping...")
        result = client.admin.command('ping')
        print(f"   Ping result: {result}")
        
        # Test database access
        db = client[db_name]
        collections = db.list_collection_names()
        print(f"   ✅ Successfully connected to MongoDB!")
        print(f"   Available collections: {len(collections)}")
        if collections:
            print(f"   Collections: {', '.join(collections[:5])}")
            if len(collections) > 5:
                print(f"   ... and {len(collections) - 5} more")
        
        client.close()
        return True
        
    except ConnectionFailure as e:
        print(f"   ❌ Connection failed: {str(e)}")
        print("\n   Troubleshooting:")
        print("   1. Check if MONGO_URL is correct")
        print("   2. Verify MongoDB Atlas network access (IP whitelist)")
        print("   3. Check if database user credentials are correct")
        print("   4. Ensure Python 3.11.x is being used (not 3.13.4)")
        return False
        
    except ServerSelectionTimeoutError as e:
        print(f"   ❌ Server selection timeout: {str(e)}")
        print("\n   Troubleshooting:")
        print("   1. Check network connectivity")
        print("   2. Verify MongoDB Atlas cluster is running")
        print("   3. Check firewall settings")
        return False
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"   ❌ Unexpected error ({error_type}): {error_msg}")
        
        if "SSL" in error_msg or "TLS" in error_msg or "certificate" in error_msg.lower():
            print("\n   SSL/TLS Error detected!")
            print("   This is likely a Python version issue.")
            print("   Solutions:")
            print("   1. Ensure Python 3.11.9 is installed and being used")
            print("   2. Verify certifi is installed: pip install certifi")
            print("   3. Check runtime.txt contains: python-3.11.9")
            print("   4. On Render: Clear build cache before deploying")
        
        return False

def main():
    """Run all checks"""
    print("=" * 60)
    print("MongoDB Connection Test")
    print("=" * 60)
    print()
    
    all_checks_passed = True
    
    # Check Python version
    print("1. Checking Python version...")
    if not check_python_version():
        all_checks_passed = False
    print()
    
    # Check certifi
    print("2. Checking certifi installation...")
    if not check_certifi():
        all_checks_passed = False
    print()
    
    # Check pymongo
    print("3. Checking pymongo installation...")
    if not check_pymongo():
        all_checks_passed = False
    print()
    
    # Test MongoDB connection
    print("4. Testing MongoDB connection...")
    if not test_mongodb_connection():
        all_checks_passed = False
    print()
    
    # Summary
    print("=" * 60)
    if all_checks_passed:
        print("✅ ALL CHECKS PASSED!")
        print("   Your MongoDB connection is configured correctly.")
        print("   You can proceed with deployment to Render.")
    else:
        print("❌ SOME CHECKS FAILED")
        print("   Please fix the issues above before deploying.")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    main()

