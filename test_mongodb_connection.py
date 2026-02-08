#!/usr/bin/env python3
"""
MongoDB Connection Test Script
Tests SSL/TLS connection to MongoDB Atlas with proper certificate handling.
"""

import os
import sys
import certifi
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_python_version():
    """Verify Python version"""
    print_section("Python Version Check")
    version = sys.version
    print(f"Python Version: {version}")
    
    major, minor = sys.version_info[:2]
    if major == 3 and minor == 11:
        print("✅ Python 3.11.x detected (CORRECT)")
        return True
    else:
        print(f"❌ Python {major}.{minor} detected (SHOULD BE 3.11)")
        return False

def check_certifi():
    """Verify certifi is installed and working"""
    print_section("Certifi SSL Certificate Check")
    
    try:
        cert_path = certifi.where()
        print(f"✅ certifi is installed")
        print(f"   Certificate bundle location: {cert_path}")
        
        if os.path.exists(cert_path):
            print(f"✅ Certificate bundle exists")
            return True
        else:
            print(f"❌ Certificate bundle not found at {cert_path}")
            return False
    except Exception as e:
        print(f"❌ certifi check failed: {str(e)}")
        return False

def check_ssl_version():
    """Check SSL/OpenSSL version"""
    print_section("SSL/OpenSSL Version Check")
    
    try:
        import ssl
        print(f"SSL Version: {ssl.OPENSSL_VERSION}")
        print(f"✅ SSL module available")
        return True
    except Exception as e:
        print(f"❌ SSL check failed: {str(e)}")
        return False

def test_mongodb_connection():
    """Test MongoDB connection with SSL"""
    print_section("MongoDB Connection Test")
    
    # Get MongoDB URI from environment (check both MONGO_URL and MONGODB_URI)
    mongodb_uri = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        print("❌ MONGO_URL or MONGODB_URI environment variable not set")
        print("\nSet it with:")
        print('export MONGO_URL="your-mongodb-connection-string"')
        print('  OR')
        print('export MONGODB_URI="your-mongodb-connection-string"')
        return False
    
    print(f"MongoDB URI: {mongodb_uri[:30]}...{mongodb_uri[-10:]}")
    
    try:
        print("\nConnecting to MongoDB with SSL/TLS...")
        
        client = MongoClient(
            mongodb_uri,
            tls=True,
            tlsAllowInvalidCertificates=False,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000
        )
        
        # Test connection
        print("Sending ping command...")
        client.admin.command('ping')
        
        print("✅ Successfully connected to MongoDB")
        print("✅ SSL/TLS handshake successful")
        
        # Get server info
        server_info = client.server_info()
        print(f"\nServer Info:")
        print(f"  MongoDB Version: {server_info.get('version', 'Unknown')}")
        
        client.close()
        return True
        
    except ConnectionFailure as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        return False
    except ServerSelectionTimeoutError as e:
        print(f"❌ MongoDB server selection timeout: {str(e)}")
        print("\nPossible causes:")
        print("  - Incorrect MongoDB URI")
        print("  - Network connectivity issues")
        print("  - MongoDB Atlas IP whitelist restrictions")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  MongoDB SSL Connection Test Suite")
    print("="*60)
    
    results = {
        "Python Version": check_python_version(),
        "Certifi": check_certifi(),
        "SSL": check_ssl_version(),
        "MongoDB Connection": test_mongodb_connection()
    }
    
    print_section("Test Results Summary")
    
    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! Ready to deploy.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
