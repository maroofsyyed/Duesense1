## MongoDB Insecure SSL Testing (DEBUG ONLY)

**⚠️ WARNING: The configurations in this document are INSECURE and must NEVER be used in production.**

Use these steps only temporarily to confirm whether SSL/TLS verification is the root cause of connection failures.

---

## 1. Insecure Motor/AsyncIOMotorClient Example

If you are using Motor (async driver), you can temporarily disable SSL verification:

```python
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URI = os.getenv("MONGODB_URI")

client = AsyncIOMotorClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True,  # ⚠️ INSECURE!
    tlsInsecure=True,                  # ⚠️ INSECURE!
    serverSelectionTimeoutMS=30000,
)
```

If this insecure configuration works while the secure one fails, the problem is almost certainly **certificate validation / SSL handshake related**.

Immediately switch back to a secure configuration and focus on fixing:

- System CA bundle
- `certifi` installation
- Docker base image / OpenSSL version

---

## 2. Insecure PyMongo Example (Synchronous)

For quick debugging with the synchronous PyMongo driver:

```python
from pymongo import MongoClient
import os

MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True,  # ⚠️ INSECURE!
    tlsInsecure=True,                  # ⚠️ INSECURE!
    serverSelectionTimeoutMS=30000,
)

client.admin.command("ping")
print("Connected INSECURELY to MongoDB")
```

Again, **do not commit or deploy** code that uses these insecure flags.

---

## 3. Cleanup Checklist After Testing

- Remove any use of `tlsAllowInvalidCertificates=True` or `tlsInsecure=True`.
- Rebuild Docker images to ensure no insecure snippets remain.
- Re-run `test_mongodb_connection.py` to validate secure SSL/TLS connectivity.


