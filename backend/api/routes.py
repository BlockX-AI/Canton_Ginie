import os
import io
import uuid
import json
import zipfile
import threading
import structlog
import redis
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse, StreamingResponse
from datetime import datetime, timezone

from api.rate_limiter import limiter
from api.ws_routes import push_status_sync

from api.models import (
    GenerateRequest,
    GenerateResponse,
    JobStatusResponse,
    JobResultResponse,
    IterateRequest,
    HealthResponse,
)
from config import get_settings
from sqlalchemy import text as sa_text
from api.middleware import optional_auth, get_current_user
from utils.daml_utils import get_daml_sdk_version

logger = structlog.get_logger()
router = APIRouter()


def _get_redis():
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def _get_job(job_id: str) -> dict:
    """Fetch job data: Redis cache first, then PostgreSQL, then in-memory fallback."""
    # Layer 1: Redis cache (fast path)
    try:
        r = _get_redis()
        data = r.get(f"job:{job_id}")
        if data:
            return json.loads(data)
    except Exception:
        pass

    # Layer 2: PostgreSQL (source of truth)
    try:
        from db.session import get_db_session
        from db.models import JobHistory
        with get_db_session() as session:
            job = session.query(JobHistory).filter_by(job_id=job_id).first()
            if job:
                data = _job_row_to_dict(job)
                # Backfill Redis cache
                try:
                    r = _get_redis()
                    r.set(f"job:{job_id}", json.dumps(data), ex=3600)
                except Exception:
                    pass
                return data
    except Exception as e:
        logger.debug("DB lookup failed, falling back to in-memory", error=str(e))

    # Layer 3: In-memory fallback
    return _in_memory_jobs.get(job_id, {})


def _set_job(job_id: str, data: dict):
    """Persist job data to PostgreSQL (source of truth) + Redis (cache) + in-memory (fallback)."""
    # Always update in-memory for immediate availability
    _in_memory_jobs[job_id] = data

    # Layer 1: Redis cache
    try:
        r = _get_redis()
        r.set(f"job:{job_id}", json.dumps(data), ex=3600)
    except Exception:
        pass

    # Layer 2: PostgreSQL persistence
    try:
        from db.session import get_db_session
        from db.models import JobHistory
        with get_db_session() as session:
            job = session.query(JobHistory).filter_by(job_id=job_id).first()
            if job:
                job.status = data.get("status", job.status)
                job.current_step = data.get("current_step", job.current_step)
                job.progress = data.get("progress", job.progress)
                job.error_message = data.get("error_message")
                job.updated_at = datetime.now(timezone.utc)
                # Store full result on completion/failure
                if data.get("status") in ("complete", "failed"):
                    job.result_json = data
            else:
                job = JobHistory(
                    job_id=job_id,
                    prompt=data.get("prompt", data.get("user_input", "")),
                    status=data.get("status", "pending"),
                    current_step=data.get("current_step", "idle"),
                    progress=data.get("progress", 0),
                    canton_env=data.get("canton_environment", "sandbox"),
                    user_email=data.get("user_email"),
                    error_message=data.get("error_message"),
                )
                session.add(job)
            # Backfill user_email if it was learned later (e.g. linked after queue)
            if data.get("user_email") and not job.user_email:
                job.user_email = data.get("user_email")
    except Exception as e:
        logger.debug("DB write failed, data still in Redis/memory", error=str(e))


def _save_deployed_contract(job_id: str, deploy_result: dict, user_email: str | None = None):
    """Save deployed contract info to PostgreSQL."""
    try:
        from db.session import get_db_session
        from db.models import DeployedContract
        with get_db_session() as session:
            contract = DeployedContract(
                contract_id=deploy_result.get("contract_id", ""),
                package_id=deploy_result.get("package_id", ""),
                template_id=deploy_result.get("template_id", ""),
                job_id=job_id,
                party_id=deploy_result.get("party_id") or None,
                user_email=user_email or deploy_result.get("user_email") or None,
                dar_path=deploy_result.get("dar_path", "") or None,
                canton_env=deploy_result.get("environment") or deploy_result.get("canton_environment", "sandbox"),
                explorer_link=deploy_result.get("explorer_link", ""),
            )
            session.add(contract)
    except Exception as e:
        logger.debug("Failed to save deployed contract to DB", error=str(e))


def _job_row_to_dict(job) -> dict:
    """Convert a JobHistory ORM row to a plain dict."""
    # If we have a full result stored, return that
    if job.result_json and isinstance(job.result_json, dict):
        return job.result_json
    return {
        "job_id": job.job_id,
        "status": job.status,
        "current_step": job.current_step,
        "progress": job.progress,
        "error_message": job.error_message,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


_in_memory_jobs: dict = {}
_jobs_lock = threading.Lock()
_active_threads: dict[str, threading.Thread] = {}
_threads_lock = threading.Lock()


def _celery_has_workers() -> bool:
    try:
        from workers.celery_app import celery_app
        result = celery_app.control.inspect(timeout=1.0).ping()
        return bool(result)
    except Exception:
        return False


def _run_pipeline_thread(job_id: str, user_input: str, canton_environment: str, canton_url: str, party_id: str = "", user_email: str = ""):
    """Run pipeline in a dedicated thread — guaranteed to execute immediately."""
    logger.info("[THREAD] Starting pipeline", job_id=job_id, party_id=party_id or "(anonymous)")
    with _threads_lock:
        _active_threads[job_id] = threading.current_thread()
    try:
        # Immediately mark as running
        running_state = {
            "job_id":       job_id,
            "status":       "running",
            "current_step": "Initializing pipeline...",
            "progress":     10,
            "user_email":   user_email or None,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }
        with _jobs_lock:
            _in_memory_jobs[job_id] = running_state
        _set_job(job_id, running_state)
        logger.info("[THREAD] Job status set to running", job_id=job_id)

        def _status_callback(jid, status, step, progress):
            update = {
                "job_id":       jid,
                "status":       status,
                "current_step": step,
                "progress":     progress,
                "updated_at":   datetime.now(timezone.utc).isoformat(),
            }
            with _jobs_lock:
                _in_memory_jobs[jid] = {**_in_memory_jobs.get(jid, {}), **update}
            _set_job(jid, _in_memory_jobs[jid])
            push_status_sync(jid, update)
            logger.info("[THREAD] Status update", job_id=jid, step=step, progress=progress)

        from pipeline.orchestrator import run_pipeline

        final_state = run_pipeline(
            job_id=job_id,
            user_input=user_input,
            canton_environment=canton_environment,
            canton_url=canton_url,
            status_callback=_status_callback,
            party_id=party_id,
        )

        if final_state.get("contract_id"):
            result = {
                "job_id":            job_id,
                "status":            "complete",
                "current_step":      "Contract deployed successfully!",
                "progress":          100,
                "success":           True,
                "contract_id":       final_state.get("contract_id"),
                "package_id":        final_state.get("package_id"),
                "template_id":       final_state.get("template_id", ""),
                "template":          final_state.get("template", ""),
                "parties":           final_state.get("parties", {}),
                "fallback_used":     final_state.get("fallback_used", False),
                "explorer_link":     final_state.get("explorer_link"),
                "dar_path":          final_state.get("dar_path", ""),
                "generated_code":    final_state.get("generated_code"),
                "structured_intent": final_state.get("structured_intent"),
                "attempt_number":    final_state.get("attempt_number"),
                "security_score":    final_state.get("security_score"),
                "compliance_score":  final_state.get("compliance_score"),
                "enterprise_score":  final_state.get("enterprise_score"),
                "deploy_gate":       final_state.get("deploy_gate"),
                "audit_reports":     final_state.get("audit_reports", {}),
                "deployment_note":   final_state.get("deployment_note", ""),
                "diagram_mermaid":   final_state.get("diagram_mermaid", ""),
                "project_files":     final_state.get("original_project_files") or final_state.get("project_files"),
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            }
            # Stamp user_email so later /me/contracts queries can find this row
            if user_email:
                result["user_email"] = user_email
            # Persist deployed contract to PostgreSQL
            _save_deployed_contract(job_id, final_state, user_email=user_email or None)
        else:
            result = {
                "job_id":            job_id,
                "status":            "failed",
                "current_step":      final_state.get("current_step", "Failed"),
                "progress":          0,
                "error_message":     final_state.get("error_message", "Pipeline failed"),
                "generated_code":    final_state.get("generated_code", ""),
                "compile_errors":    final_state.get("compile_errors", []),
                "structured_intent": final_state.get("structured_intent"),
                "security_score":    final_state.get("security_score"),
                "compliance_score":  final_state.get("compliance_score"),
                "enterprise_score":  final_state.get("enterprise_score"),
                "deploy_gate":       final_state.get("deploy_gate"),
                "audit_reports":     final_state.get("audit_reports", {}),
                "diagram_mermaid":   final_state.get("diagram_mermaid", ""),
                "project_files":     final_state.get("original_project_files") or final_state.get("project_files"),
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            }

        with _jobs_lock:
            _in_memory_jobs[job_id] = result
        _set_job(job_id, result)
        push_status_sync(job_id, result)
        logger.info("[THREAD] Pipeline completed", job_id=job_id, status=result["status"])

    except Exception as e:
        logger.error("[THREAD] Pipeline crashed", job_id=job_id, error=str(e), exc_info=True)
        error_data = {
            "job_id":        job_id,
            "status":        "failed",
            "current_step":  "Internal error",
            "progress":      0,
            "error_message": str(e),
            "updated_at":    datetime.now(timezone.utc).isoformat(),
        }
        with _jobs_lock:
            _in_memory_jobs[job_id] = error_data
        _set_job(job_id, error_data)
        push_status_sync(job_id, error_data)
    finally:
        with _threads_lock:
            _active_threads.pop(job_id, None)


def _start_pipeline_job(job_id: str, user_input: str, canton_environment: str, canton_url: str, party_id: str = "", user_email: str = ""):
    """Launch the pipeline in a daemon thread so it starts immediately."""
    t = threading.Thread(
        target=_run_pipeline_thread,
        args=(job_id, user_input, canton_environment, canton_url, party_id, user_email),
        daemon=True,
        name=f"pipeline-{job_id[:8]}",
    )
    t.start()
    logger.info("Pipeline thread launched", job_id=job_id, thread=t.name)


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("5/minute")
async def generate_contract(request: Request, body: GenerateRequest, user: dict | None = Depends(optional_auth)):
    settings = get_settings()
    job_id = str(uuid.uuid4())

    canton_url = body.canton_url or settings.get_canton_url()

    # Extract authenticated party_id if user is logged in
    party_id = user.get("sub", "") if user else ""

    # Extract stable user identity (email) for cross-session, cross-party history.
    # The fingerprint claim is set to `email:<addr>` for email-account tokens; the
    # sub claim flips to the party_id once a party is linked, so prefer fingerprint.
    user_email = ""
    if user:
        fp = user.get("fingerprint", "") or ""
        if isinstance(fp, str) and fp.startswith("email:"):
            user_email = fp[len("email:"):]
        elif isinstance(party_id, str) and party_id.startswith("email:"):
            user_email = party_id[len("email:"):]

    initial_data = {
        "job_id":       job_id,
        "status":       "queued",
        "current_step": "Job queued...",
        "progress":     5,
        "party_id":     party_id,
        "user_email":   user_email or None,
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }
    with _jobs_lock:
        _in_memory_jobs[job_id] = initial_data
    _set_job(job_id, initial_data)

    # Launch pipeline in a dedicated thread (not BackgroundTasks which can silently fail)
    _start_pipeline_job(
        job_id=job_id,
        user_input=body.prompt,
        canton_environment=body.canton_environment or settings.canton_environment,
        canton_url=canton_url,
        party_id=party_id,
        user_email=user_email,
    )
    logger.info("Job created and pipeline thread launched", job_id=job_id, party_id=party_id or "(anonymous)", user_email=user_email or "(anonymous)")

    return GenerateResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    data = _get_job(job_id) or _in_memory_jobs.get(job_id)

    if not data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job_id,
        status=data.get("status", "unknown"),
        current_step=data.get("current_step", ""),
        progress=data.get("progress", 0),
        updated_at=data.get("updated_at"),
        error_message=data.get("error_message"),
    )


@router.get("/result/{job_id}", response_model=JobResultResponse)
async def get_job_result(job_id: str):
    data = _get_job(job_id) or _in_memory_jobs.get(job_id)

    if not data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if data.get("status") not in ("complete", "failed"):
        raise HTTPException(status_code=202, detail="Job still in progress")

    return JobResultResponse(
        job_id=job_id,
        status=data.get("status"),
        success=data.get("success"),
        contract_id=data.get("contract_id"),
        package_id=data.get("package_id"),
        template=data.get("template"),
        fallback_used=data.get("fallback_used"),
        explorer_link=data.get("explorer_link"),
        generated_code=data.get("generated_code"),
        structured_intent=data.get("structured_intent"),
        attempt_number=data.get("attempt_number"),
        error_message=data.get("error_message"),
        compile_errors=data.get("compile_errors"),
        security_score=data.get("security_score"),
        compliance_score=data.get("compliance_score"),
        enterprise_score=data.get("enterprise_score"),
        deploy_gate=data.get("deploy_gate"),
        audit_reports=data.get("audit_reports"),
        deployment_note=data.get("deployment_note"),
        diagram_mermaid=data.get("diagram_mermaid"),
        project_files=data.get("project_files"),
    )


@router.get("/me/contracts")
async def list_my_contracts(user: dict = Depends(get_current_user)):
    """Return every contract this user has ever deployed, across all of the
    parties they may have created in different sessions.

    Identity is keyed off the email account (stable) instead of party_id
    (which rotates each session by design), so users can always see and
    download their full deployment history.
    """
    fp = (user.get("fingerprint") or "")
    sub = (user.get("sub") or "")
    user_email = ""
    if isinstance(fp, str) and fp.startswith("email:"):
        user_email = fp[len("email:"):]
    elif isinstance(sub, str) and sub.startswith("email:"):
        user_email = sub[len("email:"):]
    if not user_email:
        # Token isn't an email-account token (legacy Ed25519-only login).
        # Fall back to filtering by party_id sub so the endpoint is still
        # useful for those users.
        return {"contracts": [], "count": 0, "user_email": None}

    items: list[dict] = []
    try:
        from db.session import get_db_session
        from db.models import DeployedContract, JobHistory
        with get_db_session() as session:
            rows = (
                session.query(DeployedContract, JobHistory)
                .outerjoin(JobHistory, DeployedContract.job_id == JobHistory.job_id)
                .filter(
                    (DeployedContract.user_email == user_email)
                    | (JobHistory.user_email == user_email)
                )
                .order_by(DeployedContract.created_at.desc())
                .all()
            )
            for c, j in rows:
                rj = (j.result_json if j and isinstance(j.result_json, dict) else {}) or {}
                items.append({
                    "job_id": c.job_id,
                    "contract_id": c.contract_id,
                    "package_id": c.package_id,
                    "template_id": c.template_id or rj.get("template_id") or rj.get("template", ""),
                    "party_id": c.party_id,
                    "canton_env": c.canton_env,
                    "explorer_link": c.explorer_link,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "signatories": [c.party_id] if c.party_id else [],
                    "observers": [],
                    "prompt": (j.prompt if j else "") or rj.get("user_input", ""),
                    "deploy_gate": rj.get("deploy_gate"),
                    "security_score": rj.get("security_score"),
                    "compliance_score": rj.get("compliance_score"),
                    "has_dar": bool(rj.get("dar_path") or c.dar_path),
                })
    except Exception as e:
        logger.warning("/me/contracts query failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to load contract history")

    return {"contracts": items, "count": len(items), "user_email": user_email}


@router.post("/iterate/{job_id}", response_model=GenerateResponse)
@limiter.limit("10/minute")
async def iterate_contract(request: Request, job_id: str, body: IterateRequest):
    original_data = _get_job(job_id) or _in_memory_jobs.get(job_id)

    if not original_data:
        raise HTTPException(status_code=404, detail=f"Original job {job_id} not found")

    original_code  = body.original_code or original_data.get("generated_code", "")
    original_input = original_data.get("user_input", "")

    new_prompt = f"""Modify the following existing Daml contract based on this feedback:

FEEDBACK: {body.feedback}

EXISTING CONTRACT CODE:
{original_code}

ORIGINAL REQUIREMENTS: {original_input}

Please update the contract to incorporate the requested changes while keeping the rest intact."""

    settings = get_settings()
    new_job_id = str(uuid.uuid4())

    initial_data = {
        "job_id":       new_job_id,
        "status":       "queued",
        "current_step": "Processing iteration request...",
        "progress":     5,
        "parent_job_id": job_id,
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }
    with _jobs_lock:
        _in_memory_jobs[new_job_id] = initial_data
    _set_job(new_job_id, initial_data)

    _start_pipeline_job(
        job_id=new_job_id,
        user_input=new_prompt,
        canton_environment=original_data.get("canton_environment", "sandbox"),
        canton_url=settings.get_canton_url(),
    )

    return GenerateResponse(job_id=new_job_id, message="Iteration job queued")


def _resolve_dar_path(job_id: str) -> str:
    """Locate a compiled DAR file for a given job.

    Resolution order:
      1. dar_path stored on the DeployedContract row.
      2. dar_path cached in the job result JSON.
      3. Filesystem scan of {dar_output_dir}/{job_id}/.daml/dist/*.dar.

    Returns empty string if none found or the file no longer exists on disk.
    """
    # Layer 1: DeployedContract row
    try:
        from db.session import get_db_session
        from db.models import DeployedContract
        with get_db_session() as session:
            row = (
                session.query(DeployedContract)
                .filter_by(job_id=job_id)
                .order_by(DeployedContract.created_at.desc())
                .first()
            )
            if row and row.dar_path and os.path.exists(row.dar_path):
                return row.dar_path
    except Exception as e:
        logger.debug("DAR lookup from DB failed", error=str(e))

    # Layer 2: Job result JSON
    data = _get_job(job_id) or {}
    dp = data.get("dar_path", "")
    if dp and os.path.exists(dp):
        return dp

    # Layer 3: Filesystem scan
    settings = get_settings()
    dist_dir = os.path.join(settings.dar_output_dir, job_id, ".daml", "dist")
    if os.path.isdir(dist_dir):
        for fname in os.listdir(dist_dir):
            if fname.endswith(".dar"):
                return os.path.join(dist_dir, fname)
    return ""


def _resolve_project_dir(job_id: str) -> str:
    """Locate the Daml project directory for a given job."""
    settings = get_settings()
    project_dir = os.path.join(settings.dar_output_dir, job_id)
    if os.path.isdir(project_dir):
        return project_dir
    return ""


@router.get("/download/{job_id}/dar")
async def download_dar(job_id: str):
    """Download the compiled DAR file for a completed job.

    Returns the raw DAR binary (application/octet-stream).
    """
    data = _get_job(job_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if data.get("status") != "complete":
        raise HTTPException(status_code=400, detail="Job is not complete; no DAR available")

    dar_path = _resolve_dar_path(job_id)
    if not dar_path:
        raise HTTPException(
            status_code=404,
            detail=(
                "DAR file not found on disk. It may have been cleaned up "
                "(ephemeral storage) or the job never produced a DAR."
            ),
        )

    filename = os.path.basename(dar_path) or f"{job_id}.dar"
    logger.info("Serving DAR download", job_id=job_id, path=dar_path, filename=filename)
    return FileResponse(
        path=dar_path,
        media_type="application/octet-stream",
        filename=filename,
    )


@router.get("/download/{job_id}/source")
async def download_source(job_id: str):
    """Download the full Daml project source as a zip archive.

    Excludes build artifacts (.daml/dist, .daml/build) to keep the archive small.
    """
    data = _get_job(job_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if data.get("status") not in ("complete", "failed"):
        raise HTTPException(status_code=400, detail="Job is still in progress")

    project_dir = _resolve_project_dir(job_id)
    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail="Project directory not found on disk (may have been cleaned up).",
        )

    # Zip project in memory, skipping build artifacts
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            # Skip build directories
            dirs[:] = [d for d in dirs if d not in (".daml", "__pycache__", "dist")]
            for fname in files:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, project_dir)
                try:
                    zf.write(full, arcname=os.path.join(job_id[:8], rel))
                except OSError:
                    continue
    buf.seek(0)

    logger.info("Serving source zip download", job_id=job_id, project_dir=project_dir)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job_id[:8]}-source.zip"'},
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    settings = get_settings()

    daml_version = get_daml_sdk_version(settings.daml_sdk_path)

    try:
        r = _get_redis()
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "unavailable (using in-memory fallback)"

    rag_status = "ready"
    if os.getenv("SKIP_RAG_INIT"):
        rag_status = "deferred (will initialize on first use)"
    else:
        try:
            from rag.vector_store import get_store_stats
            stats = get_store_stats(persist_dir=settings.chroma_persist_dir)
            rag_status = f"ready ({stats['patterns_count']} patterns, {stats['signatures_count']} signatures)"
        except Exception:
            rag_status = "not initialized (run /init-rag)"

    db_status = "unknown"
    try:
        from db.session import get_engine
        with get_engine().connect() as conn:
            conn.execute(sa_text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"unavailable ({e})"

    # Active pipeline threads
    with _threads_lock:
        active_pipelines = len(_active_threads)

    return HealthResponse(
        daml_sdk=daml_version,
        rag_status=rag_status,
        redis_status=redis_status,
        db_status=db_status,
        active_pipelines=active_pipelines,
    )


@router.get("/system/status")
async def system_status():
    """System status endpoint for frontend to determine initial app state."""
    settings = get_settings()

    # Canton connectivity
    canton_connected = False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.get_canton_url()}/livez")
            canton_connected = resp.status_code == 200
    except Exception:
        pass

    # Canton storage type
    canton_storage = "postgres" if settings.canton_db_name else "in-memory"

    # Registered parties count
    registered_parties_count = 0
    try:
        from db.session import get_db_session
        from db.models import RegisteredParty
        with get_db_session() as session:
            registered_parties_count = session.query(RegisteredParty).count()
    except Exception:
        pass

    # RAG status
    rag_document_count = 0
    rag_ready = False
    try:
        from rag.vector_store import get_store_stats
        stats = get_store_stats(persist_dir=settings.chroma_persist_dir)
        rag_document_count = stats.get("total_documents", 0)
        rag_ready = rag_document_count > 0
    except Exception:
        pass

    return {
        "canton_connected": canton_connected,
        "canton_storage": canton_storage,
        "canton_url": settings.get_canton_url(),
        "registered_parties_count": registered_parties_count,
        "rag_status": "ready" if rag_ready else "not_initialized",
        "rag_document_count": rag_document_count,
        "environment": settings.canton_environment,
    }


@router.post("/init-rag")
async def init_rag():
    # Deferred: rag may not be installed in all environments
    from rag.vector_store import build_vector_store, get_store_stats
    settings = get_settings()

    try:
        build_vector_store(persist_dir=settings.chroma_persist_dir, force_rebuild=True)
        stats = get_store_stats(persist_dir=settings.chroma_persist_dir)
        return {
            "status": "ok",
            "documents_indexed": stats["total_documents"],
            "patterns_count": stats["patterns_count"],
            "signatures_count": stats["signatures_count"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
