# Persistent contract artifact storage — research note

> Goal: every contract a user has ever deployed (DAR + project source +
> generated Daml code + audit report) must be downloadable from the Ledger
> Explorer **at any time**, not just within the same deployment session.

This document captures the current state, why downloads break today, and the
options to make storage truly persistent.

---

## 1. Current architecture (post April 26 fixes)

| Concern | Where it lives | Lifetime |
| --- | --- | --- |
| Job status / progress / result JSON | `job_history` table in **PostgreSQL** (Railway managed) | Permanent ✅ |
| Generated Daml source files (string blobs) | `job_history.result_json.project_files` (JSONB) | Permanent ✅ |
| Generated `.daml` source files on disk | `${dar_output_dir}/${job_id}/...` (`/tmp/ginie_jobs` by default) | **Ephemeral on Railway** ❌ |
| Compiled DAR file | `${dar_output_dir}/${job_id}/.daml/dist/*.dar` | **Ephemeral on Railway** ❌ |
| Deployed-contract metadata (contract_id, package_id, dar_path, party, user_email) | `deployed_contracts` table in PostgreSQL | Permanent ✅ |
| User → contract linkage | `user_email` column on `job_history` and `deployed_contracts` (added in migration `003`) | Permanent ✅ |

The `/api/v1/download/{job_id}/dar` and `/api/v1/download/{job_id}/source`
endpoints already exist and resolve files via three layers
(`_resolve_dar_path` in `backend/api/routes.py`):

1. `DeployedContract.dar_path` from PostgreSQL.
2. `result_json.dar_path` from PostgreSQL.
3. Filesystem scan of `${dar_output_dir}/${job_id}/`.

**All three layers point at the same ephemeral filesystem path.** On Railway:

- Containers are restarted on every redeploy.
- `/tmp` is wiped on container restart.
- The build/runtime filesystem is read-only outside `/tmp` and the working
  directory.
- There is no persistent volume attached to this service today.

**Result:** Downloads work only as long as the container that produced the
DAR is still alive. After a redeploy or auto-scale event, every previous
job's `dar_path` becomes a 404. The `/me/contracts` endpoint will still list
the contracts (because their metadata is in Postgres) but the download
buttons will return *"DAR file not found on disk"*.

This is the gap the user observed.

---

## 2. Is persistent storage possible? — Yes, three viable options

### Option A — Object storage (recommended)

Push every artifact into S3-compatible blob storage at the moment the
pipeline finishes, and store **only the URL/key** in PostgreSQL.

**Provider candidates** (all S3-compatible, ordered by Railway-friendliness):

| Provider | Free tier | Why it fits |
| --- | --- | --- |
| **Cloudflare R2** | 10 GB storage + 1 M Class-A ops/month | Zero egress fees → cheap downloads, S3 API, single global endpoint. |
| **Backblaze B2** | 10 GB / 1 GB egress per day | S3 API, very cheap beyond free tier ($6/TB/mo). |
| **AWS S3** | 5 GB for 12 months | Industry standard, but egress $0.09/GB. |
| **Supabase Storage** | 1 GB, generous bandwidth | If you're already on Supabase. |
| **MinIO self-hosted on Railway** | n/a | Same Docker network, no egress, but you manage it. |

**Implementation sketch** (≈80 lines):

```python
# backend/storage/artifact_store.py
import boto3, os
from config import get_settings

_s3 = None
def _client():
    global _s3
    if _s3 is None:
        s = get_settings()
        _s3 = boto3.client(
            "s3",
            endpoint_url=s.r2_endpoint,           # https://<acct>.r2.cloudflarestorage.com
            aws_access_key_id=s.r2_access_key,
            aws_secret_access_key=s.r2_secret_key,
            region_name="auto",
        )
    return _s3

def upload_artifacts(job_id: str, project_dir: str, dar_path: str | None) -> dict:
    """Upload source zip + DAR to R2 and return their object keys."""
    keys = {}
    # 1. zip the project (reuse existing in-memory zip from /download/source)
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in (".daml", "__pycache__", "dist")]
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, arcname=os.path.relpath(full, project_dir))
    buf.seek(0)
    src_key = f"jobs/{job_id}/source.zip"
    _client().put_object(Bucket="ginie-artifacts", Key=src_key, Body=buf.getvalue())
    keys["source"] = src_key

    # 2. upload DAR if it exists
    if dar_path and os.path.exists(dar_path):
        dar_key = f"jobs/{job_id}/contract.dar"
        with open(dar_path, "rb") as f:
            _client().put_object(Bucket="ginie-artifacts", Key=dar_key, Body=f.read())
        keys["dar"] = dar_key
    return keys

def presigned_url(key: str, expires_in: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": "ginie-artifacts", "Key": key},
        ExpiresIn=expires_in,
    )
```

**Schema changes**: add two columns to `deployed_contracts`:

```python
source_object_key = Column(Text, nullable=True)
dar_object_key    = Column(Text, nullable=True)
```

**Wiring** (in `_run_pipeline_thread` in `backend/api/routes.py`, right after
`_save_deployed_contract`):

```python
keys = upload_artifacts(job_id, project_dir, final_state.get("dar_path"))
# update DeployedContract row with source_object_key/dar_object_key
```

**Download endpoints** become a simple 302 redirect:

```python
@router.get("/download/{job_id}/dar")
async def download_dar(job_id: str):
    row = ...query DeployedContract...
    if row.dar_object_key:
        return RedirectResponse(presigned_url(row.dar_object_key, 600))
    # fall back to filesystem (old jobs)
```

**Pros**: cheap, scales to terabytes, survives any redeploy / multi-instance
deployment, presigned URLs let the browser download directly without
roundtripping through your API.

**Cons**: introduces a new infra dependency + 4 secrets
(`R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET`).

### Option B — Store artifacts directly in PostgreSQL as `BYTEA`

Add `dar_bytes` (`BYTEA`) and `source_zip_bytes` (`BYTEA`) columns on
`deployed_contracts`. Write the bytes during the pipeline; serve them via
`StreamingResponse`.

**Pros**: zero new infrastructure, perfectly atomic with metadata, included
in your existing Postgres backups.

**Cons**:
- A typical generated DAR is 50–500 KB; a source zip is 5–50 KB. Per-job
  blob ≈ 100–600 KB. 10 000 jobs ≈ 1–6 GB. **Fine** for 6–12 months.
- Past ~10 GB Postgres on Railway gets expensive (~$5/GB/month vs ~$0.015 on R2).
- Backups become slow once the table is large.
- Postgres TOAST handles the storage, but you should keep `BYTEA` in a
  separate table joined by `job_id` so vacuum/backups stay fast.

**Recommended only as a stop-gap** until R2 is wired.

### Option C — Persistent volume on Railway

Railway supports **volumes** mounted at a path of your choice. Mount
`/data` and change `dar_output_dir = "/data/ginie_jobs"`.

**Pros**: zero code changes (the third resolution layer in `_resolve_dar_path`
will keep working).

**Cons**:
- Volumes are per-service and cannot be shared across replicas, so this
  blocks horizontal scaling.
- No automatic backups; if the volume is detached, all DARs vanish.
- More expensive than R2 per GB.

---

## 3. Recommendation

Phase 1 (already done in this PR):

- `user_email` column on `job_history` + `deployed_contracts` (migration
  `003_user_email_on_jobs.py`).
- `/api/v1/me/contracts` endpoint returns every contract the email account
  has ever deployed, regardless of the party that signed it.
- Ledger Explorer merges `/me/contracts` history with the live ACS, so
  switching parties (e.g. `mansi → mansi2`) no longer hides past contracts.
- Parties tab filters out unrelated parties (e.g. `portugal`).
- Result page exposes Source `.zip` and DAR download buttons.

Phase 2 (next step, ~1 day of work):

1. Provision a Cloudflare R2 bucket `ginie-artifacts`.
2. Add 4 env vars to Railway and `config.py`.
3. Implement `backend/storage/artifact_store.py` (sketch above) and call
   `upload_artifacts(...)` from the pipeline thread.
4. Migration `004_artifact_keys.py` — add `source_object_key`,
   `dar_object_key` to `deployed_contracts`.
5. Make `/download/{job_id}/{kind}` redirect to a presigned URL when an
   object key is present; keep the filesystem fallback so jobs created
   before R2 was enabled still work until they age out.

Phase 3 (optional, when retention matters):

- Add a nightly Celery beat task that purges `/tmp/ginie_jobs` for jobs
  older than 24h once they're confirmed in R2.
- Add `expires_at` on `deployed_contracts` and a soft-delete flow if you
  ever need to honour data-deletion requests.

---

## 4. Operational notes

- **Generated source code is already permanent** (it lives in
  `job_history.result_json.project_files` as JSONB). Even today, the result
  page can render it and the user can copy/paste — the only thing the user
  cannot persistently download today is the **compiled DAR**, because we
  don't checkpoint the binary anywhere durable.
- A pragmatic 5-minute fix that buys time without R2: move
  `dar_output_dir` to a Railway volume (Option C). This unblocks downloads
  for everything stored *after* the volume is attached. Old jobs are still
  lost.
- DAR files are deterministic given the source + Daml SDK version, so we
  could in principle **recompile on demand**. Keeping the project source
  in Postgres (already done) means a future `/download/{job_id}/dar` can
  fall back to: "no DAR on disk → unzip `result_json.project_files` to a
  temp dir → run `daml build` → stream the result". This avoids any blob
  storage but spends ~10 s of CPU per cold download.
