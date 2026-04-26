# canton-ginie v0.1.0 — Initial Public Release

**Release date:** 2026-04-23
**PyPI:** [`pip install canton-ginie`](https://pypi.org/project/canton-ginie/)
**Live demo:** [canton.ginie.xyz](https://canton.ginie.xyz)

---

## What is it

Ginie turns plain-English contract descriptions into deployed Daml smart
contracts on Canton. The full pipeline — intent parsing, code generation,
compilation, security audit, compliance check, and on-ledger deployment —
completes in roughly 35 seconds for a standard contract.

This is the **first publicly-installable release** of the Python SDK and the
first tagged build of the end-to-end system.

---

## Highlights

- **One-command install:** `pip install canton-ginie`
- **Hosted UI:** Deploy a Canton contract in the browser at
  [canton.ginie.xyz](https://canton.ginie.xyz) — no install required.
- **End-to-end pipeline:** Intent → RAG retrieval → Writer → Compile → Fix loop
  → Security audit → Compliance check → Canton deployment.
- **Hybrid security auditor:** LLM analysis (DSV / SWC / CWE / OWASP) combined
  with static pattern matching; blocks deploys with critical findings.
- **Multi-framework compliance:** NIST 800-53, SOC 2 Type II, ISO 27001,
  DeFi-security, Canton-DLT, and generic profiles.
- **Canton environments:** `sandbox` (local), `devnet` (public testnet), and
  `mainnet` (Global Synchronizer) — switch via one env var.
- **Session recovery:** Ed25519 key-file login flow; no passwords, no servers
  hold your private keys.
- **Downloadable artifacts:** Every deployed job exposes the compiled `.dar`
  and the full Daml project as a zip.

---

## What's in the box

| Component | Path | Status |
|---|---|---|
| Python SDK (`canton-ginie`) | `ginie/`, `sdk/` | ✅ Published on PyPI |
| FastAPI backend | `backend/` | ✅ Live at `api.ginie.xyz` |
| Next.js frontend (dark) | `frontend_dark/` | ✅ Live at `canton.ginie.xyz` |
| Security & compliance auditor | `backend/security/` | ✅ 15 vuln checks, 6 profiles |
| Canton sandbox launcher | `scripts/start-canton-sandbox.ps1` | ✅ Working |
| Daml example library (RAG) | `backend/rag/daml_examples/` | ✅ 500+ patterns |
| Test suite | `backend/tests/`, `sdk/tests/` | ✅ CI passing, 51 commits |

---

## Verification — for grant / PR reviewers

All three checks below can be run in under 5 minutes:

```bash
# 1. PyPI package resolves
pip install canton-ginie
python -c "from ginie import GinieClient; print(GinieClient)"

# 2. Hosted end-to-end works
#    Open canton.ginie.xyz → describe a contract in English →
#    receive a Contract ID deployed on Canton in ~35s.

# 3. CI passing
#    See https://github.com/BlockX-AI/Canton_Ginie/actions
```

External Contract IDs deployed by the community are tracked in
[COMMUNITY_CONTRACTS.md](COMMUNITY_CONTRACTS.md).

---

## Known limitations

- **Daml SDK version:** Currently pinned to 2.10.4. A migration to Daml 3.x /
  `dpm` is tracked for v0.2.
- **Canton mainnet:** Requires Canton Network membership and is gated behind
  feature flags; default demo runs on sandbox + devnet.
- **LLM spend:** Each pipeline run consumes tokens from your configured
  provider (Anthropic / OpenAI / Google). Self-hosters must provide their
  own API key.
- **English only:** Intent agent is tuned for English prompts; multilingual
  support is planned.

---

## What's next (v0.2 preview)

- Migrate build pipeline to Daml 3.x + `dpm`.
- Async `GinieAsyncClient` and WebSocket streaming in the SDK.
- CLI (`ginie generate`, `ginie audit`, `ginie deploy`).
- Batch contract generation.
- JavaScript / TypeScript SDK.

---

## Install

```bash
pip install canton-ginie
```

Full docs: [sdk/README.md](sdk/README.md).

---

## Acknowledgements

Thanks to the Canton Network Global Synchronizer Foundation community, the
Daml team at Digital Asset, and every external tester who submitted a
Contract ID to help validate this release.

---

**Apache 2.0 licensed.** Built by [BlockX AI](https://github.com/BlockX-AI).
