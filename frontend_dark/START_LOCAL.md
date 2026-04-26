# Start Frontend Locally with Railway Backend

This guide helps you run the Ginie frontend locally while connecting to your deployed Railway backend.

## Quick Start

### 1. Install Dependencies (if not already done)
```bash
cd frontend_dark
npm install
```

### 2. Start Development Server
```bash
npm run dev
```

The frontend will start on: **http://localhost:3000**

## Configuration

The `.env.local` file is already configured to connect to:
```
NEXT_PUBLIC_API_URL=https://canton-ginie-production.up.railway.app/api/v1
```

This means:
- ✅ Frontend runs locally (http://localhost:3000)
- ✅ Backend API calls go to Railway (https://canton-ginie-production.up.railway.app)
- ✅ Canton sandbox runs on Railway
- ✅ PostgreSQL and Redis run on Railway

## Testing the Full Pipeline

### Step 1: Open the Frontend
Navigate to: http://localhost:3000

### Step 2: Generate a Contract

1. **Click "Get Started"** or navigate to the main page
2. **Enter a contract description**, for example:
   ```
   Create a simple asset transfer contract where Alice can transfer tokens to Bob
   ```
3. **Click "Generate Contract"**
4. **Wait for the pipeline** to complete (30-60 seconds)

### Step 3: Monitor Progress

You should see the 8-stage pipeline:
1. ✅ Intent Parsing
2. ✅ RAG Retrieval
3. ✅ Code Generation
4. ✅ Compilation
5. ✅ Error Fixing (if needed)
6. ✅ Security Audit
7. ✅ Diagram Generation
8. ✅ Deployment to Canton

### Step 4: View Results

Once complete, you'll see:
- **Generated Daml code**
- **Security audit report**
- **Architecture diagram**
- **Deployment status**

## Verify Backend Connection

### Check System Status
Open: http://localhost:3000/api/status (or check the frontend UI)

Should show:
```json
{
  "canton_connected": true,
  "canton_url": "http://canton-sandbox.railway.internal:7575",
  "rag_status": "ready (2121 documents)",
  "redis_status": "connected",
  "db_status": "connected"
}
```

### Check Health Endpoint
You can also directly check the backend:
```bash
curl https://canton-ginie-production.up.railway.app/api/v1/health
```

## Troubleshooting

### Frontend won't start
**Error**: `npm: command not found`
**Fix**: Install Node.js from https://nodejs.org/

**Error**: `Module not found`
**Fix**: Run `npm install` again

### Can't connect to backend
**Error**: CORS errors in browser console
**Fix**: Backend `CORS_ORIGINS` needs to include `http://localhost:3000`

Add to Railway backend variables:
```
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,https://canton.ginie.xyz
```

### Contract generation fails
**Check**:
1. Backend logs in Railway for errors
2. OpenAI API key is set correctly
3. Canton sandbox is running

## Railway Backend URLs

- **API Base**: https://canton-ginie-production.up.railway.app
- **Health Check**: https://canton-ginie-production.up.railway.app/api/v1/health
- **System Status**: https://canton-ginie-production.up.railway.app/api/v1/system/status
- **API Docs**: https://canton-ginie-production.up.railway.app/docs

## Next Steps

After testing locally:
1. Deploy frontend to Vercel/Netlify
2. Update backend `CORS_ORIGINS` with production URL
3. Set up monitoring and analytics
4. Configure custom domain

## Development Tips

### Hot Reload
The frontend has hot reload enabled. Any changes you make to the code will automatically refresh in the browser.

### API Calls
All API calls are made through the `API_URL` constant defined in `lib/auth-context.tsx` and other files. This automatically uses the Railway backend URL from `.env.local`.

### Debugging
- Open browser DevTools (F12)
- Check Console tab for errors
- Check Network tab to see API requests
- Backend logs are in Railway dashboard

## Example Test Cases

### 1. Simple Asset Transfer
```
Create a contract where Alice can transfer 100 tokens to Bob
```

### 2. Multi-Party Agreement
```
Create a three-party escrow contract where a buyer, seller, and arbiter must all agree before funds are released
```

### 3. Time-Based Contract
```
Create a subscription contract that charges a user monthly and can be cancelled by either party
```

### 4. Conditional Transfer
```
Create a contract where payment is only released if a delivery confirmation is received within 7 days
```

## Support

If you encounter issues:
1. Check Railway logs for backend errors
2. Check browser console for frontend errors
3. Verify all Railway services are online
4. Check environment variables are set correctly
