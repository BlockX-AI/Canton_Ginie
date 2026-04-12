# Ginie

Natural language to deployed Canton smart contracts.

[![CI](https://github.com/BlockX-AI/Canton_Ginie/actions/workflows/ci.yml/badge.svg)](https://github.com/BlockX-AI/Canton_Ginie/actions/workflows/ci.yml)
[![Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-gold?style=flat)](LICENSE)

---

## Overview

Ginie takes plain English contract descriptions and compiles them into deployed Daml contracts on Canton. The pipeline handles intent parsing, code generation, real SDK compilation, error correction, security auditing, and ledger deployment.

```
Input:  "Bond contract between issuer and investor, $1M principal at 5% annual"

Output: contract_id: 0050e287c28a17a7100a5db4160fb47c...
        package_id:  c6aa079b2bfd890db909a2a065c63f7b...
        deployed in 35s
```

Useful for prototyping Canton workflows without learning Daml first, or for domain experts (compliance, legal, product) to generate working contract drafts.

---

## Why Canton

Canton is the settlement layer for institutional finance — repo agreements, tokenized assets, custody. The contracts are written in Daml, which has a steep learning curve. This tool lowers that barrier for exploration and prototyping.

---

## How It Works

Eight-stage pipeline: intent parsing, RAG retrieval, code generation, compilation, error fixing, security audit, diagram generation, and deployment.

```
English Description
        │
        ▼
   Intent Agent        Parse to structured JSON spec
        │
        ▼
   RAG Retrieval       Match against 500+ Daml examples (ChromaDB)
        │
        ▼
   Writer Agent        Generate complete Daml module
        │
        ▼
   Compile Agent       Run `daml build`, capture errors
        │
        ├── [errors?] ──► Fix Agent (retry up to 3x)
        │
        ▼
   Security Audit      Hybrid LLM + static analysis
        │
        ▼
   Deploy Gate         Block if critical vulnerabilities found
        │
        ▼
   Deploy Agent        DAR upload, party allocation, contract creation
        │
        ▼
   contract_id + package_id + audit scores
```

### Security Layer

Contracts pass through a hybrid auditor before deployment:
- LLM analysis for context-aware vulnerability detection (DSV, SWC, CWE, OWASP)
- Static pattern matching for common Daml issues (missing signatories, unsafe controllers)
- Compliance checks against NIST 800-53, SOC 2, ISO 27001, and Canton-specific standards

The deploy gate blocks contracts with critical vulnerabilities. Lower-severity findings are reported but don't block.

---

## Use Cases

**Institutional Finance** — Bond issuance, repo agreements, custody, RWA tokenization. Generate working contract drafts without a Daml team.

**DeFi & Digital Assets** — Escrow, options, multi-party payments, tokenized securities. Privacy-preserving finance on institutional rails.

**Enterprise Prototyping** — Compliance officers, product managers, and legal teams can draft Canton workflows directly, before engineering engagement.

**Learning** — Deploy a live contract in minutes to understand how Canton and Daml work. Iterate on the generated code to learn by example.

---

## Testing

The system has been tested end-to-end across the full pipeline:

- Compilation: real `daml build` execution, error capture and retry
- Security audit: hybrid LLM + static analysis, 15 vulnerability checks
- Compliance: NIST 800-53, SOC2, ISO27001 validation
- Deployment: DAR upload, party allocation, contract creation, ledger verification
- Concurrency: multiple simultaneous jobs without blocking

Typical run: ~35 seconds from prompt to deployed contract.

---

## Stack

- **Backend**: FastAPI, LangGraph, Redis
- **LLM**: Claude (primary), GPT-4o, Gemini 2.0
- **RAG**: ChromaDB with curated Daml examples
- **Compilation**: Daml SDK 2.10.4
- **Frontend**: Next.js 16, TailwindCSS
- **Ledger**: Canton HTTP JSON API

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
cp .env.ginie.example .env.ginie
# Edit .env.ginie — set at least one LLM API key

# Start API server
python -m api.main
```

### 3. Frontend
```bash
cd frontend_dark
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

### Core Pipeline

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/generate` | Submit English description → start generation job |
| `GET` | `/api/v1/status/{jobId}` | Poll real-time pipeline stage progress |
| `GET` | `/api/v1/result/{jobId}` | Retrieve contract ID, package ID, generated Daml, security scores |
| `POST` | `/api/v1/iterate/{jobId}` | Modify and redeploy an existing contract |
| `GET` | `/api/v1/health` | Service health check |
| `POST` | `/api/v1/init-rag` | Rebuild RAG vector store from examples |

### Security & Compliance

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/audit/analyze` | Run security audit on raw Daml code |
| `POST` | `/api/v1/audit/byJob` | Audit a completed job's generated code |
| `POST` | `/api/v1/compliance/analyze` | Run compliance check (specify profile) |
| `POST` | `/api/v1/compliance/byJob` | Compliance check on completed job |
| `GET` | `/api/v1/compliance/profiles` | List available compliance frameworks |
| `GET` | `/api/v1/audit/report/{jobId}` | Get formatted audit reports (JSON/Markdown/HTML) |

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
  "security_score": 78,
  "compliance_score": 85,
  "enterprise_score": 81.5,
  "deploy_gate": true,
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

Ginie's RAG library and Writer Agent cover common Canton contract patterns:

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
│   ├── security/
│   │   ├── audit_agent.py       # LLM-based security vulnerability analysis
│   │   ├── compliance_engine.py # Multi-framework compliance validation
│   │   ├── hybrid_auditor.py    # Combined security + compliance orchestrator
│   │   ├── report_generator.py  # JSON/Markdown/HTML report formatting
│   │   └── audit_prompts.py     # Enterprise audit prompts (DSV, SWC, CWE, OWASP)
│   ├── rag/
│   │   ├── retriever.py         # ChromaDB query interface
│   │   ├── indexer.py           # Vector store builder
│   │   └── daml_examples/       # 500+ curated Daml contract patterns
│   ├── pipeline/
│   │   ├── orchestrator.py      # LangGraph supervisor + state machine (8 stages)
│   │   └── state.py             # Pipeline state definitions
│   ├── api/
│   │   ├── main.py              # FastAPI application entry
│   │   ├── routes.py            # Core pipeline endpoints
│   │   ├── audit_routes.py      # Security & compliance endpoints
│   │   └── models.py            # Pydantic request/response models
│   ├── workers/
│   │   └── celery_app.py        # Async job queue worker
│   ├── utils/
│   │   ├── daml_utils.py        # Daml SDK integration utilities
│   │   └── canton_client.py     # Canton HTTP Ledger API client
│   ├── canton/
│   │   └── canton_client_v2.py  # V1/V2 dual API support + OAuth2
│   └── config.py                # Pydantic settings + environment management
├── frontend/
│   ├── app/
│   │   ├── page.tsx                    # Contract description input
│   │   ├── sandbox/[jobId]/page.tsx    # Live progress + security dashboard
│   │   └── lib/
│   │       └── api.ts                  # Typed API client
├── sdk/
│   ├── client/
│   │   ├── ginie_client.py      # Core SDK client (11 methods)
│   │   ├── types.py             # Response types + exceptions
│   │   └── config.py            # SDK configuration
│   ├── examples/
│   │   ├── generate_and_deploy.py  # Basic example
│   │   ├── audit_contract.py       # Security audit example
│   │   └── full_pipeline.py        # E2E example
│   ├── tests/
│   │   └── test_sdk.py          # 16 tests (unit + integration)
│   ├── setup.py                 # pip installable package
│   └── README.md                # SDK documentation
├── scripts/
│   └── start-canton-sandbox.ps1 # Local Canton sandbox launcher
├── schemas/
│   └── idl-spec.json            # Canonical IDL schema (M2 architecture)
├── rag/chroma_db/               # Persisted vector store (gitignored, rebuilt via /api/v1/init-rag)
└── canton-sandbox.conf          # Local Canton sandbox configuration
```

---

## Python SDK

Programmatic access to the Ginie platform.

### Installation
```bash
pip install -e ./sdk
```

### Quick Start
```python
from sdk import GinieClient

client = GinieClient()

# Generate and deploy a contract
result = client.full_pipeline(
    "Create a bond contract between issuer and investor"
)

print(f"Contract ID: {result.contract_id}")
print(f"Security Score: {result.security_score}/100")
print(f"Compliance Score: {result.compliance_score}/100")
print(f"Deploy Gate: {'PASS' if result.deploy_gate else 'FAIL'}")
```

### SDK Methods

| Method | Description |
|--------|-------------|
| `generate_contract(prompt)` | Submit generation → returns job_id |
| `get_status(job_id)` | Poll current pipeline status |
| `get_result(job_id)` | Fetch completed job result |
| `wait_for_completion(job_id)` | Poll until terminal → return result |
| `full_pipeline(prompt)` | Generate + wait → return full result |
| `run_audit(code)` | Security + compliance hybrid audit |
| `run_compliance(code, profile)` | Compliance check (NIST, SOC2, ISO, etc.) |
| `get_audit_report(job_id)` | Get formatted reports (JSON/MD/HTML) |
| `iterate_contract(job_id, feedback)` | Modify existing contract |
| `health()` | Backend health check |

### SDK Examples
```bash
# Generate and deploy
python -m sdk.examples.generate_and_deploy

# Security audit
python -m sdk.examples.audit_contract

# Full pipeline with iteration
python -m sdk.examples.full_pipeline
```

### SDK Tests
```bash
python -m sdk.tests.test_sdk
```

Full SDK documentation: [`sdk/README.md`](sdk/README.md)

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
# Start Postgres + Redis (Canton sandbox runs locally)
docker compose up -d

# Then start backend and frontend separately (see Quick Start above)
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — open an issue first for large changes.

---

## Resources

- [Canton Docs](https://docs.dev.sync.global/)
- [Daml Reference](https://docs.daml.com/)
- [Canton Explorer](https://cantonscan.com/)

---

## License

Apache 2.0. Built by [BlockXAI](https://github.com/BlockX-AI).
