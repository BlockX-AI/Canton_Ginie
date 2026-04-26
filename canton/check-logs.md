# Canton Deployment Logs - What to Check

## How to View Logs in Railway

1. Go to Railway Dashboard
2. Click **Canton_Sandbox** service
3. Click **Deployments** tab
4. Click the latest deployment (top one)
5. Click **View Logs** button

---

## What to Look For in Logs

### ✅ SUCCESS Indicators

If Canton is working, you should see:

```
===================================
Canton Sandbox Starting on Railway
===================================
Parsing DATABASE_URL...
Canton Configuration:
  DB Host: postgres.railway.internal
  DB Port: 5432
  DB Name: railway
  DB User: postgres
Waiting for PostgreSQL...
PostgreSQL is ready!
Starting Canton daemon...
[INFO] Canton participant1 is running
[INFO] Canton domain local is running
[INFO] Ledger API listening on 0.0.0.0:7575
```

### ❌ FAILURE Indicators

#### Error 1: Binary Not Found
```
ERROR: Canton binary not found at /canton/bin/canton
bin directory does not exist
```
**Cause**: Extraction failed or wrong directory structure
**Fix**: Already fixed in latest commit, wait for rebuild

#### Error 2: PostgreSQL Connection Failed
```
ERROR: PostgreSQL not ready after 30 attempts
```
**Cause**: DATABASE_URL not set or PostgreSQL not reachable
**Fix**: Verify DATABASE_URL is set correctly

#### Error 3: Permission Denied
```
/canton/bin/canton: Permission denied
```
**Cause**: Binary not executable
**Fix**: Already fixed with chmod in Dockerfile

#### Error 4: Java Error
```
Error: Could not find or load main class
```
**Cause**: Canton installation incomplete
**Fix**: Check if extraction completed successfully

#### Error 5: Database Connection Error
```
Cannot connect to database
```
**Cause**: Wrong database credentials or host
**Fix**: Check DATABASE_URL format

---

## Common Issues & Solutions

### Issue: "Application failed to respond"

**Symptoms:**
- Public URL shows Railway error page
- Service shows as "Online" but not responding

**Possible Causes:**

1. **Canton crashed during startup**
   - Check logs for error messages
   - Look for Java exceptions or stack traces

2. **Canton is starting but taking too long**
   - First startup can take 2-3 minutes
   - Wait and refresh the page

3. **Port not exposed correctly**
   - Canton should listen on 0.0.0.0:7575
   - Check if EXPOSE 7575 is in Dockerfile (it is)

4. **Health check failing**
   - Railway may be killing the service
   - Canton doesn't have a built-in health endpoint

---

## Debugging Steps

### Step 1: Check Build Logs

Look for:
```
Download attempt 1 of 3...
100  223M  100  223M    0     0   243M      0
Extracting Canton...
Canton installation complete
```

If this fails, the build is broken.

### Step 2: Check Runtime Logs

Look for:
```
Canton Sandbox Starting on Railway
```

If you don't see this, the entrypoint isn't running.

### Step 3: Check for Errors

Search logs for:
- "ERROR"
- "Exception"
- "failed"
- "denied"

### Step 4: Verify Environment Variables

In Railway Canton_Sandbox service → Variables:
- `DATABASE_URL` should be set (reference from Postgres)
- Should show: `postgres://postgres:...@postgres.railway.internal:5432/railway`

---

## Quick Fixes

### Fix 1: Restart the Service

1. Go to Canton_Sandbox service
2. Click **Settings** → **Restart**
3. Wait 2-3 minutes
4. Check logs again

### Fix 2: Redeploy

1. Go to **Deployments** tab
2. Click the latest deployment
3. Click **Redeploy** button
4. Wait for build to complete

### Fix 3: Check Postgres is Online

1. Go to **Postgres** service
2. Should show green "Online" status
3. If offline, restart it first

---

## Expected Startup Time

- **Build**: 2-3 minutes (download + extract Canton)
- **Startup**: 1-2 minutes (connect to DB + initialize)
- **Total**: 3-5 minutes from deploy to ready

---

## What to Report

If Canton still isn't working, copy these from the logs:

1. **Last 50 lines of build logs**
2. **Last 50 lines of runtime logs**
3. **Any ERROR or Exception messages**
4. **The exact point where it stops/crashes**

---

## Alternative: Check if Canton Binary Exists

If you have Railway CLI installed:

```bash
railway run bash
ls -la /canton/bin/
cat /canton/config/canton-railway.conf
```

This will show if files are in the right place.

---

## Next Steps Based on Logs

### If logs show "Binary not found":
- Wait for the latest build to complete
- The fix is already pushed

### If logs show "PostgreSQL not ready":
- Verify DATABASE_URL is set
- Check Postgres service is online
- Try restarting Canton service

### If logs show "Permission denied":
- Latest Dockerfile has chmod fix
- Redeploy to get the fix

### If logs show Java errors:
- Canton version might be incompatible
- May need to try Canton 2.8.x instead

### If no logs at all:
- Service might not be starting
- Check if entrypoint.sh is being called
- Verify Dockerfile ENTRYPOINT is correct

---

## Contact Support

If none of these help, you may need to:

1. Check Railway status: https://status.railway.app/
2. Ask in Railway Discord: https://discord.gg/railway
3. Try deploying Canton 2.8.x instead of 2.9.3
