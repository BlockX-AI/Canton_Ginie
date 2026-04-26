# Ginie Local Development - Quick Start

This guide walks you through starting all 4 services needed to run Ginie end-to-end.

---

## Architecture Overview

```
┌─────────────┐
│  Frontend   │ :3000  ──┐
│  (Next.js)  │          │
└─────────────┘          │
                         ▼
                  ┌──────────────┐
                  │ Backend API  │ :8000
                  │  (FastAPI)   │
                  └──────────────┘
                         │
                         ├──► LLM (Claude/GPT-4o)
                         │
                         ▼
                  ┌──────────────┐
                  │Canton Sandbox│ :6865 (gRPC)
                  │   + JSON API │ :7575 (HTTP)
                  └──────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  PostgreSQL  │ :5432
                  │    Redis     │ :6379
                  └──────────────┘
```

### Service Roles

| Service | Port | Purpose | What It Does |
|---------|------|---------|--------------|
| **Frontend** | 3000 | User Interface | Submit prompts, view contract generation progress, see deployed contracts |
| **Backend API** | 8000 | Orchestration | LLM calls, Daml code generation, compilation, deployment, RAG retrieval |
| **Canton Sandbox** | 6865 | Ledger (gRPC) | Stores contracts, processes transactions, manages parties |
| **Canton JSON API** | 7575 | Ledger (HTTP) | REST interface to Canton for contract queries and creation |
| **PostgreSQL** | 5432 | Persistence | Stores Canton ledger state and Ginie job metadata |
| **Redis** | 6379 | Job Queue | Async job processing (optional, falls back to BackgroundTasks) |

---

## Prerequisites

1. **Docker Desktop** - For PostgreSQL and Redis
2. **Daml SDK 2.10.4** - For Canton sandbox and compilation
   ```bash
   curl -sSL https://get.daml.com/ | sh
   ```
3. **Python 3.10+** - For backend
4. **Node.js 18+** - For frontend
5. **LLM API Key** - OpenAI, Anthropic, or Gemini

---

## Setup (One-Time)

### 1. Configure Backend Environment
```bash
cd backend
cp .env.ginie.example .env.ginie
```

Edit `backend/.env.ginie` and set **at least one** LLM API key:
```bash
# Choose one:
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
```

### 2. Install Backend Dependencies
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies
```bash
cd frontend_dark
npm install
```

---

## Starting Services

### Option A: Automated Startup (Recommended)

Run the master startup script:
```powershell
.\start-all-services.ps1
```

This will:
1. ✓ Check all prerequisites
2. ✓ Start PostgreSQL + Redis (Docker)
3. ✓ Show commands for the 3 remaining services

Then **open 3 new terminals** and run the commands shown.

---

### Option B: Manual Startup (Step-by-Step)

#### Terminal 1: Infrastructure (PostgreSQL + Redis)
```bash
docker-compose up -d postgres redis
```

Wait ~5 seconds for PostgreSQL to be ready.

#### Terminal 2: Canton Sandbox
```powershell
.\scripts\start-canton-sandbox.ps1
```

Wait for:
```
Canton sandbox is ready.
Listening on http://localhost:6865 (gRPC)
JSON API on http://localhost:7575 (HTTP)
```

#### Terminal 3: Backend API
```bash
cd backend
.\venv\Scripts\activate
python -m api.main
```

Wait for:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Terminal 4: Frontend
```bash
cd frontend_dark
npm run dev
```

Wait for:
```
✓ Ready on http://localhost:3000
```

---

## Testing the Full Pipeline

### 1. Open Frontend
Navigate to: **http://localhost:3000**

### 2. Submit a Prompt
Example prompts:
```
Bond contract between issuer and investor, $1M principal at 5% annual rate
```
```
Asset transfer between seller and buyer with escrow party
```
```
Simple token holding contract with transfer choice
```

### 3. Watch the Pipeline
The frontend will show:
1. **Intent Parsing** - Extracting parties, features, constraints
2. **Code Generation** - LLM writes Daml code
3. **Compilation** - Daml SDK compiles to .dar
4. **Deployment** - Contract deployed to Canton ledger
5. **Result** - Contract ID and package ID displayed

### 4. Verify Deployment
Check the backend logs (Terminal 3) for:
```
INFO: Contract deployed successfully
INFO: contract_id=0050e287c28a17a7...
INFO: package_id=c6aa079b2bfd890d...
```

---

## API Endpoints (for Testing)

### Backend API (http://localhost:8000)
- **Swagger Docs**: http://localhost:8000/docs
- **Generate Contract**: `POST /api/v1/generate`
- **Job Status**: `GET /api/v1/jobs/{job_id}`
- **Health Check**: `GET /api/v1/health`

### Example cURL Test
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Bond contract between issuer and investor",
    "deploy": true
  }'
```

Response:
```json
{
  "job_id": "abc123",
  "status": "pending"
}
```

Check status:
```bash
curl http://localhost:8000/api/v1/jobs/abc123
```

---

## Troubleshooting

### Canton Sandbox Won't Start
**Error**: `PostgreSQL not reachable`
- **Fix**: Ensure Docker is running: `docker-compose up -d postgres`
- **Alternative**: Use in-memory mode: `.\scripts\start-canton-sandbox.ps1 -InMemory`

### Backend API Fails
**Error**: `LLM_PROVIDER not configured`
- **Fix**: Set API key in `backend/.env.ginie`

**Error**: `Canton sandbox not reachable`
- **Fix**: Ensure Canton is running on port 6865

### Frontend Can't Connect
**Error**: `Failed to fetch`
- **Fix**: Ensure backend is running on port 8000
- **Check CORS**: `backend/.env.ginie` should have `CORS_ORIGINS=http://localhost:3000`

### Compilation Fails
**Error**: `daml: command not found`
- **Fix**: Install Daml SDK or set `DAML_SDK_PATH` in `.env.ginie`

---

## Stopping Services

### Stop All Services
```bash
# Stop Docker services
docker-compose down

# Stop Canton, Backend, Frontend
# Press Ctrl+C in each terminal
```

### Clean Restart (Reset Ledger)
```bash
# Stop all services first, then:
docker-compose down -v  # Deletes PostgreSQL data
docker-compose up -d postgres redis
# Restart Canton, Backend, Frontend
```

---

## Service Health Checks

| Service | Health Check URL | Expected Response |
|---------|------------------|-------------------|
| Backend | http://localhost:8000/api/v1/health | `{"status": "healthy"}` |
| Canton JSON | http://localhost:7575/v1/query | `{"errors": [...]}` (needs auth) |
| Frontend | http://localhost:3000 | Ginie landing page |

---

## Next Steps

1. **Initialize RAG** (optional, for better code generation):
   ```bash
   curl -X POST http://localhost:8000/api/v1/init-rag
   ```

2. **Run Tests**:
   ```bash
   cd backend
   pytest tests/test_pipeline.py -v
   ```

3. **Deploy to Production**: See `docker-compose.yml` for containerized deployment

---

## Support

- **Logs**: Check terminal outputs for errors
- **API Docs**: http://localhost:8000/docs for interactive API testing
- **Canton Logs**: Check `log/canton.log` if Canton fails
