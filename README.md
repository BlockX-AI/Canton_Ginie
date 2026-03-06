# Ginie — Canton Smart Contract Generator

Agentic AI pipeline that takes plain-English descriptions and produces deployed Canton/Daml smart contracts automatically.

## Architecture

```
User Input (English)
    → Intent Agent       (Claude parses requirements → structured JSON)
    → RAG Retrieval      (ChromaDB finds similar Daml patterns)
    → Writer Agent       (Claude generates Daml code)
    → Compile Agent      (daml SDK compiles → DAR file)
    → Fix Agent Loop     (LangGraph: auto-fix errors, max 3 attempts)
    → Deploy Agent       (Canton Ledger API uploads DAR)
    → Result             (contract_id + explorer link returned)
```

## Stack

| Layer     | Tech                                              |
|-----------|---------------------------------------------------|
| LLM       | Claude claude-sonnet-4-20250514 (Anthropic)              |
| Agents    | LangChain + LangGraph                             |
| RAG       | ChromaDB + SentenceTransformers                   |
| Backend   | FastAPI + Celery + Redis                          |
| Frontend  | Next.js 15 + TailwindCSS                          |
| Contracts | Daml SDK + Canton Ledger API                      |

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy and fill env vars
cp .env.example .env

# Start API server
python -m api.main
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### 3. (Optional) Redis + Celery worker for async jobs

```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — Celery worker
cd backend
celery -A workers.celery_app worker --loglevel=info
```

Without Redis, the API falls back to FastAPI `BackgroundTasks` (works fine for dev).

### 4. (Optional) Build RAG index

```bash
curl -X POST http://localhost:8000/api/v1/init-rag
```

## API Endpoints

| Method | Path                     | Description                        |
|--------|--------------------------|------------------------------------|
| POST   | `/api/v1/generate`       | Start contract generation job      |
| GET    | `/api/v1/status/{jobId}` | Poll job progress                  |
| GET    | `/api/v1/result/{jobId}` | Get final result                   |
| POST   | `/api/v1/iterate/{jobId}`| Iterate on existing contract       |
| GET    | `/api/v1/health`         | Health check                       |
| POST   | `/api/v1/init-rag`       | Rebuild RAG vector store           |

## Canton Environments

| Env       | Use                          |
|-----------|------------------------------|
| sandbox   | Local dev (default, instant) |
| devnet    | Public test network          |
| mainnet   | Production financial network |

Set `CANTON_ENVIRONMENT` in `.env` to switch.

## Daml SDK

Install the Daml SDK for real compilation:

```bash
curl -sSL https://get.daml.com/ | sh
```

Without it, the system runs in **mock mode** — it validates basic Daml structure and simulates compilation. This is enough for demo/dev purposes.

## Project Structure

```
Ginie_Daml/
├── backend/
│   ├── agents/           # 5 AI agents (intent, writer, compile, fix, deploy)
│   ├── rag/              # ChromaDB vector store + Daml example library
│   │   └── daml_examples/ # 7 production Daml contract examples
│   ├── pipeline/         # LangGraph orchestrator + state
│   ├── api/              # FastAPI routes, models, app
│   ├── workers/          # Celery async job worker
│   ├── utils/            # Daml utils, Canton HTTP client
│   └── config.py         # Pydantic settings
└── frontend/
    ├── app/
    │   ├── page.tsx                   # Input page
    │   ├── generate/[jobId]/page.tsx  # Live progress page
    │   └── result/[jobId]/page.tsx    # Result + iterate page
    └── lib/api.ts                     # API client
```
