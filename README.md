<div align="center">

# Ginie
### Plain English → Deployed Canton Smart Contract in 90 Seconds

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Canton Network](https://img.shields.io/badge/Canton-Network-00C896?style=flat)](https://canton.network)
[![License](https://img.shields.io/badge/License-Apache_2.0-gold?style=flat)](LICENSE)
[![Stars](https://img.shields.io/github/stars/BlockXAI/Canton_Ginie?color=gold&style=flat)](https://github.com/BlockXAI/Canton_Ginie/stargazers)

**No Daml. No SDK knowledge. No blockchain engineering required.**

[Live Demo](https://ginie-canton.vercel.app) · [Documentation](#quick-start) · [Canton Network](https://canton.network) · [BlockXAI](https://github.com/BlockXAI)

</div>

---

## What is Ginie?

Canton Network runs the world's most sophisticated institutional blockchain — $280B in daily repo settlement, $6T in tokenized assets, backed by Goldman Sachs, Broadridge, and Euroclear. Its smart contracts are written in **Daml**, a powerful but specialized functional language that takes months to learn.

**Ginie removes that barrier entirely.**

Describe what you want in plain English. Ginie handles intent parsing, Daml generation, real SDK compilation, automatic error correction, and deployment to the Canton ledger — returning a live, verified contract ID in under 90 seconds.
```
"Create a bond contract between an issuer and investor
 with a principal of $1M at 5% annual interest"

→  contract_id: 0050e287c28a17a7100a5db4160fb47c...
   package_id:  c6aa079b2bfd890db909a2a065c63f7b...
   status:      deployed ✓  |  35s
```

A product manager, compliance officer, DeFi developer, or university student can now deploy production-grade Canton smart contracts — without ever writing a line of Daml.

---

## Why Canton + Why Now

Canton is not a typical blockchain. It is the settlement infrastructure for institutional finance:

- **$280B** processed daily in repo agreements
- **$6T** in tokenized assets under management
- Partners: Goldman Sachs · Broadridge · Euroclear · Tradeweb · Nasdaq · JPMorgan
- DTCC treasury tokenization pilot underway (H1 2026)
- JPM Coin native integration rolling out throughout 2026

The bottleneck is not institutional interest. It is developer supply. Daml's learning curve keeps thousands of potential Canton builders on the sidelines. **Ginie is the onramp.**

---

## How It Works

Ginie runs a verified 7-stage agentic pipeline. Every contract passes all stages — no shortcuts, no mocks.
```
User Input (Natural Language)
       │
       ▼
 ┌─────────────┐
 │ Intent Agent│  ← Parses English → structured contract specification (JSON)
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │  RAG Layer  │  ← ChromaDB retrieves matching Daml patterns from 500+ verified examples
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │ Writer Agent│  ← Generates complete, idiomatic Daml module
 └──────┬──────┘
        │
        ▼
 ┌──────────────┐
 │Compile Agent │  ← Runs real `daml build` SDK — captures errors precisely
 └──────┬───────┘
        │
   [compile error?]
        │
        ▼
 ┌─────────────┐
 │  Fix Agent  │  ← LangGraph loop: reads error, rewrites, retries (max 3×)
 │   (Loop)    │    Handles all 11 known Daml error types. Never terminates on failure.
 └──────┬──────┘
        │
        ▼
 ┌──────────────┐
 │ Deploy Agent │  ← DAR upload · party allocation · JWT regen · ledger verification
 └──────┬───────┘
        │
        ▼
 ┌──────────────────────────────────┐
 │  contract_id + package_id        │  ← Real Canton ledger. Verifiable on CantonScan.
 │  party hashes + explorer link    │
 └──────────────────────────────────┘
```

**Every contract also passes a pre-deployment security audit** — automated checks for missing signatories, unchecked controllers, unguarded choices, and known Daml anti-patterns before anything touches the ledger.

---

## Use Cases

### Institutional Finance
Deploy production-grade Canton contracts without a Daml engineering team:
- **Bond issuance** — issuer/investor relationships, coupon schedules, settlement terms
- **Repo agreements** — collateral, repurchase obligations, margin calls
- **Custody contracts** — asset custody, transfer authorization, regulatory reporting hooks
- **RWA tokenization** — real-world asset representation, transfer restrictions, compliance gates

### DeFi & Digital Assets
Build privacy-preserving financial applications on institutional rails:
- **Escrow contracts** — multi-party hold and release with conditional triggers
- **Option contracts** — European/American options with exercise mechanics
- **Payment flows** — multi-party payment with atomic settlement guarantees
- **NFT and token standards** — CNTS-compliant digital asset contracts

### Enterprise & Compliance
Enable domain experts to prototype Canton workflows directly:
- Compliance officers drafting KYC attestation and audit trail contracts
- Product managers prototyping settlement flows before engineering engagement
- Legal teams encoding agreement terms into verifiable on-chain logic
- Regulators building supervisory access contracts on Canton's privacy model

### Education & Research
The fastest path for developers to learn Canton by doing:
- Deploy a live Canton contract in under 20 minutes, no prior Daml knowledge
- Explore the generated Daml code to learn by example
- Iterate on contracts conversationally — modify and redeploy from results page
- Full audit trail of every compilation attempt for learning from errors

---

## Production Audit Results

Ginie has passed a full production readiness audit:

| Component | Status | Notes |
|---|---|---|
| Daml Sandbox | ✅ Green | Isolated per job UUID, path traversal blocked |
| Compile Agent | ✅ Green | `sanitize_daml` preserves valid code, module header enforced |
| Fix Agent | ✅ Green | Handles all 11 error types, fallback after 3 attempts |
| Pipeline | ✅ Green | Never terminates on compile failure — fallback → compile → deploy |
| Canton Deploy | ✅ Green | DAR upload, party allocation, JWT regen, ledger verification |
| API Stability | ✅ Green | Thread-based execution, no stuck jobs |
| Frontend | ✅ Green | Progress UI, contract/package ID display, error handling |
| Security | ✅ Green | No injection vulnerabilities, keys gitignored |

**Benchmark:** 5/5 end-to-end success · 0 fallbacks needed · ~35s average · 3/3 concurrent jobs ✓

---

## Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Orchestration** | LangChain + LangGraph | Stateful multi-agent loop with supervisor |
| **LLM** | Anthropic Claude (primary) · Gemini 2.0 · GPT-4o | Intent parsing, Daml generation, error fixing |
| **RAG** | ChromaDB + SentenceTransformers | 500+ curated Daml pattern retrieval |
| **Smart Contract Runtime** | Daml SDK 2.10.3 | Real `daml build` + `daml ledger upload-dar` |
| **Backend** | FastAPI + Celery + Redis | Async pipeline, job queue, state management |
| **Frontend** | Next.js 15 + TailwindCSS | Live progress, contract display, iterate UI |
| **Ledger** | Canton HTTP Ledger API v1 | Party allocation, DAR upload, contract creation |
| **Deployment** | Docker + GitHub Actions | Containerized CI/CD, self-hostable |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Daml SDK](https://docs.daml.com/getting-started/installation.html) — for real compilation
- Redis (optional — falls back to `BackgroundTasks` without it)

### 1. Install Daml SDK
```bash
curl -sSL https://get.daml.com/ | sh
```

Without it, Ginie runs in **mock mode** — validates Daml structure and simulates compilation. Sufficient for exploration, required for real contract IDs.

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set your Anthropic API key and Canton environment

# Start API server
python -m api.main
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 4. (Optional) Redis + Celery for async jobs
```bash
# Terminal 1
redis-server

# Terminal 2
cd backend
celery -A workers.celery_app worker --loglevel=info
```

Enables full async job queue with status polling. Without Redis, jobs run inline via FastAPI `BackgroundTasks` — works fine for development and demos.

### 5. (Optional) Build RAG index
```bash
curl -X POST http://localhost:8000/api/v1/init-rag
```

Rebuilds the ChromaDB vector store from the Daml example library. Run this on first setup or when adding new examples.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/generate` | Submit English description → start generation job |
| `GET` | `/api/v1/status/{jobId}` | Poll real-time pipeline stage progress |
| `GET` | `/api/v1/result/{jobId}` | Retrieve contract ID, package ID, generated Daml |
| `POST` | `/api/v1/iterate/{jobId}` | Modify and redeploy an existing contract |
| `GET` | `/api/v1/health` | Service health check |
| `POST` | `/api/v1/init-rag` | Rebuild RAG vector store from examples |

### Example Request
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create an escrow contract between a buyer and seller for a real estate transaction. The escrow releases on confirmation from both parties.",
    "environment": "sandbox"
  }'
```

### Example Response
```json
{
  "job_id": "243f4527-7eba-449c-aaf8-c677f906429f",
  "status": "complete",
  "contract_id": "0050e287c28a17a7100a5db4160fb47c344d6fe847a7...",
  "package_id": "c6aa079b2bfd890db909a2a065c63f7b1ad7dc9f1e60...",
  "parties": {
    "buyer": "buyer::1220d220f9d440473e49fc8996...",
    "seller": "seller::1220d220f9d440473e49fc8996..."
  },
  "template_id": "c6aa079b...:Main:Escrow",
  "daml_source": "module Main where\n...",
  "stage": "complete",
  "elapsed_seconds": 31
}
```

---

## Canton Environments

| Environment | Purpose | Access |
|---|---|---|
| `sandbox` | Local development, instant startup | Default — no credentials needed |
| `devnet` | Public Canton test network | DevNet evaluation license |
| `mainnet` | Production Global Synchronizer | Canton Network membership |

Set `CANTON_ENVIRONMENT=devnet` in `.env` to target DevNet. Contract IDs deployed to DevNet are verifiable on [cantonscan.com](https://cantonscan.com).

---

## Contract Types Supported

Ginie's RAG library and Writer Agent cover the full range of Canton contract patterns:

| Category | Examples |
|---|---|
| **Fixed Income** | Bond issuance, coupon payments, maturity settlement |
| **Secured Lending** | Repo agreements, margin calls, collateral management |
| **Derivatives** | Options (European/American), futures, swap agreements |
| **Asset Custody** | Custody accounts, transfer authorization, asset servicing |
| **Trade Finance** | Letters of credit, escrow, multi-party settlement |
| **Digital Assets** | NFTs, tokenized securities, CNTS-compliant tokens |
| **Compliance** | KYC attestation, audit trails, access control lists |
| **Payments** | Multi-party transfers, conditional release, batch settlement |

---

## Project Structure
```
Canton_Ginie/
├── backend/
│   ├── agents/
│   │   ├── intent_agent.py      # English → structured JSON specification
│   │   ├── writer_agent.py      # JSON spec → complete Daml module
│   │   ├── compile_agent.py     # daml build integration + error capture
│   │   ├── fix_agent.py         # LangGraph error correction loop (11 error types)
│   │   └── deploy_agent.py      # DAR upload + Canton Ledger API
│   ├── rag/
│   │   ├── retriever.py         # ChromaDB query interface
│   │   ├── indexer.py           # Vector store builder
│   │   └── daml_examples/       # 500+ curated Daml contract patterns
│   ├── pipeline/
│   │   ├── orchestrator.py      # LangGraph supervisor + state machine
│   │   └── state.py             # Pipeline state definitions
│   ├── api/
│   │   ├── main.py              # FastAPI application entry
│   │   ├── routes.py            # All API endpoints
│   │   └── models.py            # Pydantic request/response models
│   ├── workers/
│   │   └── celery_app.py        # Async job queue worker
│   ├── utils/
│   │   ├── daml_utils.py        # Daml SDK integration utilities
│   │   └── canton_client.py     # Canton HTTP Ledger API client
│   └── config.py                # Pydantic settings + environment management
├── frontend/
│   ├── app/
│   │   ├── page.tsx                    # Contract description input
│   │   ├── generate/[jobId]/page.tsx   # Live pipeline progress (WebSocket)
│   │   └── result/[jobId]/page.tsx     # Contract ID + Daml source + iterate
│   └── lib/
│       └── api.ts                      # Typed API client
├── scripts/
│   ├── audit_report.txt                # Production readiness audit results
│   └── grant_audit.py                  # 20-contract audit test suite
├── rag/chroma_db/                      # Persisted vector store
└── canton-sandbox.conf                 # Local Canton sandbox configuration
```

---

## Environment Variables
```env
# Required
ANTHROPIC_API_KEY=sk-ant-...          # Primary LLM (Claude)

# Optional — multi-LLM support
OPENAI_API_KEY=sk-...                 # GPT-4o fallback
GOOGLE_API_KEY=...                    # Gemini 2.0 fallback

# Canton
CANTON_ENVIRONMENT=sandbox            # sandbox | devnet | mainnet
CANTON_LEDGER_HOST=localhost
CANTON_LEDGER_PORT=6865

# Async (optional — falls back to BackgroundTasks)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
```

---

## Self-Hosting with Docker
```bash
# Build and run the full stack
docker compose up --build

# Backend API:  http://localhost:8000
# Frontend:     http://localhost:3000
# Redis:        localhost:6379
```

---

## Contributing

Contributions are welcome. The most impactful areas:

- **Daml examples** — add verified contract patterns to `backend/rag/daml_examples/`
- **Fix agent** — expand error type coverage beyond the current 11 handled types
- **Contract types** — new industry verticals (insurance, trade finance, structured products)
- **LLM adapters** — additional model backends in `backend/agents/`

Please open an issue before submitting large PRs.

---

## Canton Network Resources

- [Canton Developer Docs](https://docs.dev.sync.global/)
- [Daml Language Reference](https://docs.daml.com/)
- [Canton Network Explorer](https://cantonscan.com/)
- [Canton SDK Quickstart](https://github.com/digital-asset/cn-quickstart)
- [Global Synchronizer Foundation](https://canton.foundation/)

---

## Built By

**BlockXAI** — building AI infrastructure for institutional blockchain.

[github.com/BlockXAI](https://github.com/BlockXAI)

---

<div align="center">

**Apache 2.0 Licensed · Built on Canton Network · Open Source**

*If you can describe it, Ginie can deploy it on Canton.*

</div>
