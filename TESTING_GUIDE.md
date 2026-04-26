# Ginie Full Stack Testing Guide

Complete testing guide for the deployed Railway backend + local frontend setup.

## 🚀 Quick Start

### 1. Start Frontend Locally
```bash
cd frontend_dark
npm install
npm run dev
```
Frontend will be available at: **http://localhost:3000**

### 2. Verify Backend Connection
Open: https://canton-ginie-production.up.railway.app/api/v1/health

Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "daml_sdk": "SDK not installed — run: curl -sSL https://get.daml.com/ | sh",
  "rag_status": "deferred (will initialize on first use)",
  "redis_status": "connected",
  "db_status": "connected",
  "active_pipelines": 0
}
```

### 3. Check Canton Connection
Open: https://canton-ginie-production.up.railway.app/api/v1/system/status

Expected response:
```json
{
  "canton_connected": true,
  "canton_storage": "postgres",
  "canton_url": "http://canton-sandbox.railway.internal:7575",
  "registered_parties_count": 0,
  "rag_status": "ready",
  "rag_document_count": 2121,
  "environment": "sandbox"
}
```

---

## ✅ Pre-Flight Checklist

### Railway Services Status
- [ ] **Postgres**: Online
- [ ] **Redis**: Online  
- [ ] **Canton_Sandbox**: Online
- [ ] **Canton-Ginie** (Backend): Online

### Environment Variables Set

**Canton_Sandbox:**
- [ ] `DATABASE_URL` (reference from Postgres)

**Canton-Ginie (Backend):**
- [ ] `DATABASE_URL` (reference from Postgres)
- [ ] `REDIS_URL` (reference from Redis)
- [ ] `CANTON_SANDBOX_URL` = `http://canton-sandbox.railway.internal:7575`
- [ ] `SKIP_RAG_INIT` = `true`
- [ ] `OPENAI_API_KEY` = `sk-...` (your actual key)
- [ ] `CORS_ORIGINS` includes `http://localhost:3000`

### Canton Domain Generated
- [ ] Railway Canton_Sandbox service has domain generated on port **7575**

---

## 🧪 Test Cases

### Test 1: Simple Asset Transfer Contract

**Description:**
```
Create a simple asset transfer contract where Alice can transfer 100 tokens to Bob
```

**Expected Flow:**
1. Frontend sends request to backend
2. Backend parses intent using LLM
3. RAG retrieves relevant Daml examples
4. LLM generates Daml code
5. Code is compiled using Daml SDK
6. Security audit is performed
7. Mermaid diagram is generated
8. Contract is deployed to Canton

**Expected Result:**
- ✅ Job completes successfully
- ✅ Daml code is generated
- ✅ No compilation errors
- ✅ Security audit passes
- ✅ Diagram is generated
- ✅ Contract deployed to Canton

**Time:** ~30-60 seconds

---

### Test 2: Multi-Party Escrow Contract

**Description:**
```
Create a three-party escrow contract where a buyer, seller, and arbiter must all agree before funds are released
```

**Expected Result:**
- ✅ Contract includes three parties
- ✅ Choice requires all three signatures
- ✅ Security audit checks for authorization
- ✅ Diagram shows all three parties

**Time:** ~45-90 seconds

---

### Test 3: Time-Based Subscription

**Description:**
```
Create a subscription contract that charges a user monthly and can be cancelled by either party
```

**Expected Result:**
- ✅ Contract includes time-based logic
- ✅ Cancellation choice for both parties
- ✅ Recurring payment structure
- ✅ Security audit checks for proper authorization

**Time:** ~45-90 seconds

---

### Test 4: Conditional Payment

**Description:**
```
Create a contract where payment is only released if a delivery confirmation is received within 7 days
```

**Expected Result:**
- ✅ Contract includes conditional logic
- ✅ Time constraint (7 days)
- ✅ Delivery confirmation choice
- ✅ Payment release logic

**Time:** ~45-90 seconds

---

## 📊 Monitoring & Debugging

### Frontend Debugging

**Browser Console (F12):**
```javascript
// Check API URL
console.log(process.env.NEXT_PUBLIC_API_URL)
// Should show: https://canton-ginie-production.up.railway.app/api/v1
```

**Network Tab:**
- Watch for API calls to Railway backend
- Check response status codes (should be 200)
- Verify CORS headers are present

### Backend Debugging

**Railway Logs:**
1. Go to Railway dashboard
2. Click on **Canton-Ginie** service
3. Click **Deployments** → Latest → **View Logs**

**Look for:**
```
[info] Ginie Daml API starting
[info] PostgreSQL database initialized
[info] RAG initialization skipped
[info] Canton connected
```

### Canton Debugging

**Railway Logs:**
1. Click on **Canton_Sandbox** service
2. Check logs for:
```
Canton Sandbox Starting on Railway
PostgreSQL is ready!
Starting Canton daemon...
Participant participant1 is running
Domain local is running
```

---

## 🔍 Common Issues & Solutions

### Issue: Frontend can't connect to backend

**Symptoms:**
- CORS errors in browser console
- Network requests fail with 0 status

**Solutions:**
1. Check `CORS_ORIGINS` in Railway backend includes `http://localhost:3000`
2. Verify backend is online in Railway
3. Check `.env.local` has correct API URL

---

### Issue: Contract generation fails

**Symptoms:**
- Job status shows "failed"
- Error in backend logs

**Solutions:**
1. **Check OpenAI API key:**
   - Verify `OPENAI_API_KEY` is set in Railway
   - Check OpenAI account has credits
   - Test key: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`

2. **Check Canton connection:**
   - Visit: `/api/v1/system/status`
   - Should show `canton_connected: true`
   - If false, check `CANTON_SANDBOX_URL` variable

3. **Check Daml SDK:**
   - Backend logs should show Daml SDK version
   - If missing, this is expected (SDK not needed for basic operations)

---

### Issue: RAG initialization slow

**Symptoms:**
- First request takes very long
- Subsequent requests are fast

**Solution:**
- This is expected behavior with `SKIP_RAG_INIT=true`
- RAG initializes on first use (indexes 2121 documents)
- Takes ~60-90 seconds on first request
- Cached for subsequent requests

---

### Issue: Canton deployment fails

**Symptoms:**
- Contract generates but deployment fails
- Error: "Canton not reachable"

**Solutions:**
1. Check Canton_Sandbox service is online
2. Verify `CANTON_SANDBOX_URL` uses `.railway.internal` domain
3. Check Canton logs for errors
4. Verify domain is generated on port 7575

---

## 📈 Performance Benchmarks

### Expected Response Times

| Operation | Time | Notes |
|-----------|------|-------|
| Health check | <500ms | Simple status check |
| System status | <1s | Includes Canton ping |
| First RAG request | 60-90s | One-time initialization |
| Subsequent RAG | <2s | Cached |
| Simple contract | 30-60s | Full pipeline |
| Complex contract | 45-90s | More LLM iterations |

### Resource Usage

**Railway Free Tier Limits:**
- $5 free credit/month
- Shared CPU/memory
- Good for testing and development

**Expected Monthly Cost (Production):**
- Backend: ~$5-10
- Canton: ~$10-15
- Postgres: ~$5
- Redis: ~$5
- **Total: ~$25-35/month**

---

## 🎯 Success Criteria

### Deployment Success
- [x] All Railway services online
- [x] Backend health check returns 200
- [x] Canton connected
- [x] Redis connected
- [x] PostgreSQL connected

### Functionality Success
- [ ] Frontend loads at localhost:3000
- [ ] Can submit contract description
- [ ] Job status updates in real-time
- [ ] Contract code is generated
- [ ] Security audit completes
- [ ] Diagram is generated
- [ ] Contract deploys to Canton

### Performance Success
- [ ] Health check < 1s
- [ ] Contract generation < 90s
- [ ] No errors in logs
- [ ] CORS working correctly

---

## 📝 Test Results Template

```
Test Date: _______________
Tester: _______________

Services Status:
- Postgres: ☐ Online ☐ Offline
- Redis: ☐ Online ☐ Offline
- Canton: ☐ Online ☐ Offline
- Backend: ☐ Online ☐ Offline

Test 1 - Simple Asset Transfer:
- Status: ☐ Pass ☐ Fail
- Time: _____ seconds
- Notes: _______________________

Test 2 - Multi-Party Escrow:
- Status: ☐ Pass ☐ Fail
- Time: _____ seconds
- Notes: _______________________

Test 3 - Subscription:
- Status: ☐ Pass ☐ Fail
- Time: _____ seconds
- Notes: _______________________

Test 4 - Conditional Payment:
- Status: ☐ Pass ☐ Fail
- Time: _____ seconds
- Notes: _______________________

Overall Result: ☐ Pass ☐ Fail
Issues Found: _______________________
```

---

## 🚀 Next Steps After Testing

1. **If all tests pass:**
   - Deploy frontend to Vercel/Netlify
   - Update `CORS_ORIGINS` with production URL
   - Set up monitoring (Sentry, LogRocket)
   - Configure custom domain

2. **If tests fail:**
   - Check logs in Railway
   - Verify environment variables
   - Review this troubleshooting guide
   - Check Railway service status

3. **Production Readiness:**
   - Enable Canton TLS
   - Set strong `JWT_SECRET`
   - Configure rate limiting
   - Set up backups
   - Add monitoring/alerting
