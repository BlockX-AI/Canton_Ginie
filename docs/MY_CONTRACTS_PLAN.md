# My Contracts — Implementation Plan

User goal: after signing in, the user can view a list of all contracts they have
deployed through Ginie, see the audit report and metadata for each, and download
the artefacts (`.daml` source, compiled `.dar`, audit JSON/MD, full export bundle).

---

## Current State (what we already have)

- `deployed_contracts` table in PostgreSQL — already keyed on `party_id`, `job_id`,
  `contract_id`, `package_id`, `template_id`, `dar_path`, `canton_env`,
  `explorer_link`, `created_at` (`@/backend/db/models.py:74-93`).
- `job_history` table — owns `prompt`, `result_json` (full pipeline output incl.
  generated source, audit), `status`, also keyed on `party_id`.
- `JobResult` already exposed via `GET /jobs/{job_id}` and `GET /jobs/{job_id}/audit-report`.
- Authenticated users carry a JWT with `sub = party_id` (or `sub = email:<addr>`
  with `party_id` resolved server-side via `email_accounts.party_id`).

So no schema work is required — only a thin API + a frontend page.

---

## Backend

### New endpoints (all under `/api/v1`)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/contracts` | Paginated list of contracts deployed by the current user |
| `GET` | `/contracts/{contract_id}` | Single contract detail (joins `job_history` for source + audit) |
| `GET` | `/contracts/{contract_id}/download/source` | `.daml` source from `result_json` |
| `GET` | `/contracts/{contract_id}/download/dar` | Compiled `.dar` from disk via `dar_path` |
| `GET` | `/contracts/{contract_id}/download/audit` | Audit JSON + Markdown |
| `GET` | `/contracts/{contract_id}/download/bundle` | ZIP: source + dar + audit + UPGRADE_NOTES.md + README.md |

### Auth resolution helper

```python
# backend/api/contracts_routes.py

def _resolve_party_id(user: dict) -> str:
    sub = user["sub"]
    if sub.startswith("email:"):
        # Email-only token — pull linked party_id from email_accounts
        from auth.email_auth import get_email_account
        account = get_email_account(sub[len("email:"):])
        if not account or not account.get("party_id"):
            raise HTTPException(403, "No party linked to this account")
        return account["party_id"]
    return sub  # already a party_id
```

### List query

```python
@router.get("/contracts")
async def list_my_contracts(
    user: dict = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    canton_env: Optional[str] = None,
):
    party_id = _resolve_party_id(user)
    with get_db_session() as session:
        q = (session.query(DeployedContract, JobHistory)
                    .outerjoin(JobHistory, DeployedContract.job_id == JobHistory.job_id)
                    .filter(DeployedContract.party_id == party_id))
        if canton_env:
            q = q.filter(DeployedContract.canton_env == canton_env)
        total = q.count()
        rows = q.order_by(DeployedContract.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [_serialize(c, j) for c, j in rows],
    }
```

`_serialize` returns `{contract_id, package_id, template_id, prompt, status,
canton_env, explorer_link, created_at, security_score, deploy_gate}` — enough to
render a list row without a per-item fetch.

### Download bundle (ZIP)

```python
import io, zipfile

@router.get("/contracts/{contract_id}/download/bundle")
async def download_bundle(contract_id: str, user: dict = Depends(get_current_user)):
    contract, job = _load_owned_contract(contract_id, user)
    result = job.result_json or {}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("source/Main.daml", result.get("generated_code", ""))
        z.writestr("audit/audit_report.json", json.dumps(result.get("audit_report"), indent=2))
        z.writestr("audit/audit_report.md", result.get("audit_markdown", ""))
        z.writestr("UPGRADE_NOTES.md", _build_upgrade_notes(result))
        z.writestr("README.md", _build_readme(contract, job))
        if contract.dar_path and Path(contract.dar_path).exists():
            z.write(contract.dar_path, arcname="package.dar")

    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{contract_id}.zip"'},
    )
```

### Hardening

- Always filter by `party_id` server-side — never trust a `party_id` query param.
- Rate-limit downloads (e.g. `5/minute`) via `slowapi`.
- For `dar_path`, validate `Path(p).resolve().is_relative_to(JOBS_ROOT)` before
  reading to prevent path traversal.

---

## Frontend

### New page: `/contracts`

```
ginie-saas-frontend/saas/app/contracts/page.tsx
```

Tabs / filters:
- **Environment** — `localnet | sandbox | ginienet | mainnet`
- **Status** — `deployed | failed`
- **Search** — by `contract_id`, `template_id`, or prompt substring

### List item (card layout)

```
┌─────────────────────────────────────────────────────────┐
│ Bond Contract · ginienet              ✓ 5/5 audit gates │
│ #1:00:abc3d7…f92a                       Jan 14, 2026    │
│ Template: Main:Bond                                     │
│ "Create a bond between issuer and investor at 5%…"      │
│                                                         │
│ [View on CantonScan]  [Source]  [DAR]  [Audit]  [Bundle]│
└─────────────────────────────────────────────────────────┘
```

### Detail drawer

Click a card → slide-in drawer with:
- Full prompt
- 5-gate audit report (re-uses `<AuditReport />` component from sandbox page)
- Generated Daml source in Monaco read-only viewer
- Re-deploy / iterate buttons (already exist on sandbox page)

### Header link

Add `My Contracts` to the desktop nav (`@/components/header.tsx`) only when
`isAuthenticated && !needsParty`, next to `Ledger Explorer`.

### Download flow

```ts
async function downloadBundle(contractId: string, token: string) {
  const resp = await fetch(`${API_URL}/contracts/${contractId}/download/bundle`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) throw new Error(`Download failed (${resp.status})`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${contractId}.zip`; a.click();
  URL.revokeObjectURL(url);
}
```

---

## Phasing

| Phase | Scope | Effort |
|---|---|---|
| **P1 — list + single download** | `GET /contracts`, `GET /contracts/{id}/download/source`, `/contracts` page with cards. Wire from sandbox success page ("View all my contracts" CTA). | ~1 day |
| **P2 — full export bundle** | ZIP route, audit/dar individual downloads, detail drawer with audit viewer. | ~1 day |
| **P3 — bulk + cross-env** | Multi-select + "Download all as ZIP", environment filter, search. | ~0.5 day |
| **P4 — GitHub auto-commit (Curtis maintainability ask)** | OAuth + repo creation + PR-on-iterate. Pulled into M2 of grant proposal — separate plan. | M2 milestone |

---

## Open Questions

1. **Storage of `result_json`** — for very long contracts, `result_json` can hit
   ~200KB. Should we move `generated_code` to its own table or to S3 / object
   storage? Decide before P3.
2. **DAR retention** — `dar_path` points to local disk. On Railway / containerised
   deploys, files are ephemeral. We should upload DARs to S3 (or postgres `bytea`)
   on successful deploy and store the URL in `dar_path`. Required for downloads
   to work in production.
3. **CantonScan link availability** — only valid for `ginienet` and `mainnet`.
   For `localnet` / `sandbox`, hide the link and show contract ID only.

---

## Acceptance Criteria

- [ ] An authenticated user can navigate to `/contracts` and see only their own
      contracts (verified by querying with two parties — each sees only their own).
- [ ] Each row shows contract ID, template, environment, audit pass/fail, timestamp.
- [ ] User can download the source `.daml`, the compiled `.dar`, and the audit report.
- [ ] User can download a single ZIP bundle that includes all of the above plus a
      README and UPGRADE_NOTES placeholder.
- [ ] List endpoint is paginated (`limit`/`offset`) and totals are correct.
- [ ] Cross-tenant access is blocked: party A cannot fetch party B's contract by
      guessing the contract ID (returns 404).
