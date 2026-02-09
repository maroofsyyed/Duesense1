# MongoDB Atlas Configuration Verification

## STEP 1: Check Network Access

1. Go to https://cloud.mongodb.com
2. Select your project
3. Click "Network Access" in left menu
4. Look for IP whitelist entries

### What you MUST see:
```
IP Address: 0.0.0.0/0
Comment: Allow from anywhere (temporary for testing)
Status: Active
```

### If this is missing:
1. Click "Add IP Address"
2. Select "Allow Access from Anywhere"
3. Click "Confirm"
4. Wait 2-3 minutes for changes to propagate

## STEP 2: Check Database User

1. Click "Database Access" in left menu
2. Find your database user
3. Verify:
   - Authentication Method: Password
   - Database User Privileges: "readWriteAnyDatabase" or specific database access
   - Status: Active

### If user is missing or password forgotten:
1. Edit user
2. Reset password to something simple (for testing): `TestPass123`
3. Update your MONGODB_URI

## STEP 3: Check Cluster Status

1. Click "Database" in left menu (or "Clusters")
2. Your cluster should show:
   - Status: Active (green)
   - NOT "Paused" or "Deleting"

### If cluster is paused:
1. Click "Resume" button
2. Wait 3-5 minutes for cluster to start

## STEP 4: Get CORRECT Connection String

1. On your cluster, click "Connect"
2. Select "Connect your application"
3. Driver: Python
4. Version: 3.6 or later
5. Copy the connection string shown

### Expected format:
```
mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

### CRITICAL: Replace placeholders
```
<username> → your actual username (NO angle brackets!)
<password> → your actual password (NO angle brackets!)
```

### Example:
```
WRONG: mongodb+srv://<myuser>:<mypass>@cluster.mongodb.net/
RIGHT: mongodb+srv://myuser:mypass@cluster.mongodb.net/
```

## STEP 5: Test Connection String Locally

```bash
# Set the EXACT connection string from Atlas
export MONGODB_URI="mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"

# Run test script
python backend/test_connection_string.py
```

### Expected output:
```
✅ SUCCESS! Ping result: {'ok': 1.0}
✅ MongoDB version: 7.0.x
```

### If it fails:
- Check username/password are correct (no typos!)
- Check IP whitelist includes 0.0.0.0/0
- Check cluster is not paused

## STEP 6: Update Render Environment Variable

Once connection string works locally:

1. Go to Render Dashboard
2. Your service → Settings → Environment
3. Find MONGODB_URI
4. Update to the EXACT string that worked locally
5. Save
6. Redeploy

## COMMON MISTAKES

### Mistake 1: Angle brackets in connection string
```
WRONG: mongodb+srv://<user>:<pass>@...
RIGHT: mongodb+srv://actualuser:actualpass@...
```

### Mistake 2: Special characters in password not encoded
```
If password is: P@ssw0rd!
Must encode as: P%40ssw0rd%21

@ → %40
! → %21
# → %23
$ → %24
```

### Mistake 3: Wrong database name
```
mongodb+srv://user:pass@cluster.net/wrongdb  ❌
mongodb+srv://user:pass@cluster.net/correctdb  ✅
```


