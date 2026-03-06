import uuid
import json
import structlog
import redis
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime

from api.models import (
    GenerateRequest,
    GenerateResponse,
    JobStatusResponse,
    JobResultResponse,
    IterateRequest,
    HealthResponse,
)
from config import get_settings
from utils.daml_utils import get_daml_sdk_version

logger = structlog.get_logger()
router = APIRouter()


def _get_redis():
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def _get_job(job_id: str) -> dict:
    try:
        r = _get_redis()
        data = r.get(f"job:{job_id}")
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning("Redis unavailable, using in-memory fallback", error=str(e))
    return {}


def _set_job(job_id: str, data: dict):
    try:
        r = _get_redis()
        r.set(f"job:{job_id}", json.dumps(data), ex=3600)
    except Exception as e:
        logger.warning("Failed to persist job to Redis", error=str(e))


_in_memory_jobs: dict = {}


def _run_pipeline_background(job_id: str, user_input: str, canton_environment: str, canton_url: str):
    from pipeline.orchestrator import run_pipeline

    try:
        initial = {
            "job_id":       job_id,
            "status":       "running",
            "current_step": "Analyzing your contract description...",
            "progress":     10,
            "updated_at":   datetime.utcnow().isoformat(),
        }
        _in_memory_jobs[job_id] = initial
        _set_job(job_id, initial)

        final_state = run_pipeline(
            job_id=job_id,
            user_input=user_input,
            canton_environment=canton_environment,
            canton_url=canton_url,
        )

        if final_state.get("contract_id"):
            result = {
                "job_id":            job_id,
                "status":            "complete",
                "current_step":      "Deployment complete!",
                "progress":          100,
                "contract_id":       final_state.get("contract_id"),
                "package_id":        final_state.get("package_id"),
                "explorer_link":     final_state.get("explorer_link"),
                "generated_code":    final_state.get("generated_code"),
                "structured_intent": final_state.get("structured_intent"),
                "attempt_number":    final_state.get("attempt_number"),
                "updated_at":        datetime.utcnow().isoformat(),
            }
        else:
            result = {
                "job_id":         job_id,
                "status":         "failed",
                "current_step":   final_state.get("current_step", "Failed"),
                "progress":       0,
                "error_message":  final_state.get("error_message", "Pipeline failed"),
                "generated_code": final_state.get("generated_code", ""),
                "compile_errors": final_state.get("compile_errors", []),
                "updated_at":     datetime.utcnow().isoformat(),
            }

        _in_memory_jobs[job_id] = result
        _set_job(job_id, result)
        logger.info("Background job completed", job_id=job_id, status=result["status"])

    except Exception as e:
        logger.error("Background job crashed", job_id=job_id, error=str(e))
        error_data = {
            "job_id":        job_id,
            "status":        "failed",
            "current_step":  "Internal error",
            "progress":      0,
            "error_message": str(e),
            "updated_at":    datetime.utcnow().isoformat(),
        }
        _in_memory_jobs[job_id] = error_data
        _set_job(job_id, error_data)


@router.post("/generate", response_model=GenerateResponse)
async def generate_contract(request: GenerateRequest, background_tasks: BackgroundTasks):
    settings = get_settings()
    job_id = str(uuid.uuid4())

    canton_url = request.canton_url or settings.get_canton_url()

    initial_data = {
        "job_id":       job_id,
        "status":       "queued",
        "current_step": "Job queued...",
        "progress":     5,
        "updated_at":   datetime.utcnow().isoformat(),
    }
    _in_memory_jobs[job_id] = initial_data
    _set_job(job_id, initial_data)

    try:
        from workers.celery_app import generate_contract_task
        generate_contract_task.delay(
            job_id=job_id,
            user_input=request.prompt,
            canton_environment=request.canton_environment,
            canton_url=canton_url,
        )
        logger.info("Job queued via Celery", job_id=job_id)
    except Exception:
        logger.warning("Celery unavailable, running in background thread", job_id=job_id)
        background_tasks.add_task(
            _run_pipeline_background,
            job_id=job_id,
            user_input=request.prompt,
            canton_environment=request.canton_environment,
            canton_url=canton_url,
        )

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
        contract_id=data.get("contract_id"),
        package_id=data.get("package_id"),
        explorer_link=data.get("explorer_link"),
        generated_code=data.get("generated_code"),
        structured_intent=data.get("structured_intent"),
        attempt_number=data.get("attempt_number"),
        error_message=data.get("error_message"),
        compile_errors=data.get("compile_errors"),
    )


@router.post("/iterate/{job_id}", response_model=GenerateResponse)
async def iterate_contract(job_id: str, request: IterateRequest, background_tasks: BackgroundTasks):
    original_data = _get_job(job_id) or _in_memory_jobs.get(job_id)

    if not original_data:
        raise HTTPException(status_code=404, detail=f"Original job {job_id} not found")

    original_code  = request.original_code or original_data.get("generated_code", "")
    original_input = original_data.get("user_input", "")

    new_prompt = f"""Modify the following existing Daml contract based on this feedback:

FEEDBACK: {request.feedback}

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
        "updated_at":   datetime.utcnow().isoformat(),
    }
    _in_memory_jobs[new_job_id] = initial_data
    _set_job(new_job_id, initial_data)

    background_tasks.add_task(
        _run_pipeline_background,
        job_id=new_job_id,
        user_input=new_prompt,
        canton_environment=original_data.get("canton_environment", "sandbox"),
        canton_url=settings.get_canton_url(),
    )

    return GenerateResponse(job_id=new_job_id, message="Iteration job queued")


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
    try:
        from rag.vector_store import get_vector_store
        get_vector_store(persist_dir=settings.chroma_persist_dir)
    except Exception:
        rag_status = "not initialized (run /init-rag)"

    return HealthResponse(
        daml_sdk=daml_version,
        rag_status=rag_status,
        redis_status=redis_status,
    )


@router.post("/init-rag")
async def init_rag():
    from config import get_settings
    from rag.vector_store import build_vector_store
    settings = get_settings()

    try:
        store = build_vector_store(persist_dir=settings.chroma_persist_dir, force_rebuild=True)
        count = store._collection.count()
        return {"status": "ok", "documents_indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
