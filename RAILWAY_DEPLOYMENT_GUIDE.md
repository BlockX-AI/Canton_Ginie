# Railway Deployment Guide - Complete Setup

## Current Status ✅
- ✅ Backend API deployed: `https://canton-ginie-production.up.railway.app/`
- ✅ PostgreSQL database connected
- ✅ Redis database added
- ✅ Canton sandbox files pushed to GitHub

## Next Steps: Deploy Canton Sandbox

### Step 1: Create Canton Service in Railway

1. **Go to your Railway project**:
   - URL: https://railway.app/project/4d7c89d1-99cc-4520-9aa5-5868e269f449
   - Or click on your project in Railway dashboard

2. **Add new service**:
   - Click **"+ New"** button (top right)
   - Select **"GitHub Repo"**
   - Choose your **`BlockX-AI/Canton_Ginie`** repository
   - Railway will ask for the root directory

3. **Configure root directory**:
   - Set **Root Directory** to: `canton`
   - Click **"Deploy"**

4. **Name the service**:
   - Rename service to `Canton-Sandbox` (optional but recommended)
   - Click on service → Settings → change name

### Step 2: Link PostgreSQL to Canton

1. **Open Canton service settings**:
   - Click on **Canton-Sandbox** service
   - Go to **Variables** tab

2. **Add database reference**:
   - Click **"+ New Variable"**
   - Select **"Add Reference"**
   - Choose your **Postgres** service
   - Select **`DATABASE_URL`** variable
   - This will automatically link the database

   **Alternative (manual setup)**:
   If you want separate variables, add these references:
   - `DATABASE_HOST` → Postgres `PGHOST`
   - `DATABASE_PORT` → Postgres `PGPORT`  
   - `DATABASE_NAME` → Postgres `PGDATABASE`
   - `DATABASE_USER` → Postgres `PGUSER`
   - `DATABASE_PASSWORD` → Postgres `PGPASSWORD`

3. **Save and redeploy**:
   - Railway will automatically redeploy Canton with database access

### Step 3: Update Backend Environment Variables

1. **Open Canton-Ginie (backend) service**:
   - Click on your **Canton-Ginie** service
   - Go to **Variables** tab

2. **Add/Update these variables**:

   **Redis Connection**:
   ```
   REDIS_URL=redis://default:[password]@[host]:[port]
   ```
   - Get the actual Redis URL from your Redis service variables
   - Or add reference: `REDIS_URL` → Redis `REDIS_URL`

   **Canton Sandbox URL**:
   ```
   CANTON_SANDBOX_URL=http://canton-sandbox.railway.internal:7575
   ```
   - Replace `canton-sandbox` with your actual Canton service name (lowercase, hyphens)
   - Use Railway's internal networking (`.railway.internal`)

3. **Redeploy backend**:
   - Click **"Deploy"** or it will auto-deploy on variable change

### Step 4: Verify Deployment

1. **Check Canton logs**:
   - Open Canton-Sandbox service
   - Go to **Deployments** → Latest deployment → **View Logs**
   - Look for:
     ```
     PostgreSQL is ready!
     Canton daemon starting...
     Participant participant1 is running
     Domain local is running
     ```

2. **Check backend connection**:
   - Visit: `https://canton-ginie-production.up.railway.app/api/v1/system/status`
   - Should show:
     ```json
     {
       "canton_connected": true,
       "canton_url": "http://canton-sandbox.railway.internal:7575",
       ...
     }
     ```

3. **Test health endpoint**:
   - Visit: `https://canton-ginie-production.up.railway.app/api/v1/health`
   - Should show all services connected

### Step 5: Test End-to-End

1. **Generate a simple contract**:
   ```bash
   curl -X POST https://canton-ginie-production.up.railway.app/api/v1/generate \
     -H "Content-Type: application/json" \
     -d '{
       "description": "Create a simple asset transfer contract",
       "user_id": "test-user"
     }'
   ```

2. **Check job status**:
   - The response will include a `job_id`
   - Poll: `GET /api/v1/jobs/{job_id}`

## Environment Variables Summary

### Backend (Canton-Ginie) Service

| Variable | Value | Source |
|----------|-------|--------|
| `DATABASE_URL` | Auto | Reference from Postgres |
| `REDIS_URL` | `redis://...` | Reference from Redis |
| `CANTON_SANDBOX_URL` | `http://canton-sandbox.railway.internal:7575` | Manual |
| `SKIP_RAG_INIT` | `true` | Manual (already set) |
| `OPENAI_API_KEY` | Your key | Manual |
| `CORS_ORIGINS` | Your frontend URL | Manual |

### Canton-Sandbox Service

| Variable | Value | Source |
|----------|-------|--------|
| `DATABASE_URL` | Auto | Reference from Postgres |

### Redis Service
- No additional configuration needed
- Just ensure it's running

### Postgres Service
- No additional configuration needed
- Shared by backend and Canton

## Troubleshooting

### Canton won't start
**Symptom**: Canton service crashes or restarts continuously

**Solutions**:
1. Check PostgreSQL connection in Canton logs
2. Verify `DATABASE_URL` is set correctly
3. Check if database is accessible from Canton service
4. Review Canton logs for Java errors

### Backend can't connect to Canton
**Symptom**: `"canton_connected": false` in system status

**Solutions**:
1. Verify Canton service is running (check Railway dashboard)
2. Check `CANTON_SANDBOX_URL` format:
   - Must use `.railway.internal` domain
   - Must use service name (lowercase with hyphens)
   - Port must be `7575`
3. Ensure both services are in the same Railway project
4. Try redeploying backend after Canton is fully up

### Redis connection fails
**Symptom**: `"redis_status": "unavailable"` in health check

**Solutions**:
1. Check Redis service is running
2. Verify `REDIS_URL` format: `redis://default:password@host:port`
3. Get correct URL from Redis service variables
4. Use Railway internal networking if possible

### Build fails
**Symptom**: Canton Docker build fails

**Solutions**:
1. Check Canton version (2.9.3) is available
2. Verify Dockerfile syntax
3. Check Railway build logs for specific errors
4. Ensure `canton/` directory structure is correct

## Production Checklist

Before going to production:

- [ ] Enable Canton TLS/SSL
- [ ] Set up proper authentication
- [ ] Configure resource limits
- [ ] Set up monitoring/alerting
- [ ] Use separate database for Canton
- [ ] Configure backup strategy
- [ ] Set up proper logging
- [ ] Review security settings
- [ ] Test failover scenarios
- [ ] Document deployment process

## Cost Estimation (Railway)

**Free Tier**:
- $5 free credit/month
- Shared resources
- Good for development/testing

**Estimated Monthly Cost (Production)**:
- Backend API: ~$5-10
- Canton Sandbox: ~$10-15
- PostgreSQL: ~$5
- Redis: ~$5
- **Total**: ~$25-35/month

**Optimization Tips**:
- Use Railway's sleep feature for non-prod environments
- Share PostgreSQL between services
- Monitor resource usage
- Scale based on actual load

## Next Steps After Deployment

1. **Set up monitoring**:
   - Railway provides basic metrics
   - Consider adding Sentry for error tracking
   - Set up uptime monitoring (UptimeRobot, etc.)

2. **Configure CI/CD**:
   - Railway auto-deploys on git push
   - Add GitHub Actions for testing
   - Set up staging environment

3. **Deploy frontend**:
   - Deploy to Vercel/Netlify
   - Update CORS_ORIGINS in backend
   - Configure environment variables

4. **Documentation**:
   - Update API documentation
   - Create user guides
   - Document deployment process

## Support

If you encounter issues:
1. Check Railway logs for all services
2. Review this guide's troubleshooting section
3. Check Railway status page: https://status.railway.app/
4. Railway Discord: https://discord.gg/railway
