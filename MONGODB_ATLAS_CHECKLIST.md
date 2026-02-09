# MongoDB Atlas Configuration Checklist

## 1. Network Access

### Check IP Whitelist
1. Go to MongoDB Atlas Dashboard.
2. Navigate to **Network Access**.
3. Ensure one of the following:
   - `0.0.0.0/0` is allowed (allow from anywhere), or
   - Render's IP ranges are whitelisted.

**Note**: Render uses dynamic IPs, so `0.0.0.0/0` is recommended for testing.

⚠️ For production, restrict to specific IPs or use VPC peering.

## 2. Database User

### Verify Credentials
1. Go to **Database Access**.
2. Check a user exists with password authentication.
3. Ensure the user has `readWrite` permission on your database.
4. Ensure the password doesn't contain special characters that need URL encoding (or that they are properly encoded).

### Connection String Format

```text
mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
```

Special characters in password must be URL-encoded:

- `@` → `%40`
- `:` → `%3A`
- `/` → `%2F`
- `#` → `%23`
- `?` → `%3F`

### Connection String Variations (SSL / TLS Options)

Sometimes it is useful to tweak SSL/TLS options directly in the URI to debug issues:

- **Standard (recommended):**

  ```text
  mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<db>?retryWrites=true&w=majority
  ```

- **Explicit TLS enabled:**

  ```text
  mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<db>?retryWrites=true&w=majority&tls=true
  ```

- **Explicit TLS with strict certificate validation (recommended):**

  ```text
  mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<db>?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=false
  ```

- **Debug-only (NOT for production) with relaxed validation:**

  ```text
  mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<db>?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true
  ```

Use the last variant only temporarily to confirm whether certificate validation is the root cause of failures; then revert to a secure URI.

## 3. Cluster Configuration

### Check Cluster Version
- MongoDB version should be **4.4+** (5.0+ recommended).
- TLS/SSL should be enabled (default for Atlas).

### Check Cluster Region
- Ideally the same region as your Render deployment (e.g. Oregon/US West).
- Cross-region may add latency but should still work.

## 4. Environment Variable in Render

### Set `MONGODB_URI`
1. Go to **Render Dashboard**.
2. Open your service → **Settings** → **Environment**.
3. Add:

   - **Key**: `MONGODB_URI`  
   - **Value**: `mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority`

4. Save changes.
5. Redeploy the service.

## 5. Test Connection Locally

Before deploying to Render, test locally:

```bash
export MONGODB_URI="your-connection-string"
python backend/verify_env.py
```

All checks should pass.

## 6. Common Issues

### Issue: "Authentication failed"
- Check username/password are correct.
- Check password is URL-encoded.
- Check user has correct permissions.

### Issue: "Network timeout"
- Check IP whitelist includes `0.0.0.0/0` (for testing).
- Check cluster is running (not paused).

### Issue: "SSL handshake failed"
- Update to `python:3.11.9-bullseye` in `Dockerfile`.
- Ensure `certifi` is installed.
- Check OpenSSL version with `backend/verify_env.py`.

### Issue: "Database not found"
- Ensure database name in connection string matches actual database.
- Ensure user has access to that specific database.


