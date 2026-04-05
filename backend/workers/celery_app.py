import json
import structlog
from celery import Celery
from datetime import datetime, timezone

from config import get_settings

logger = structlog.get_logger()

settings = get_settings()
celery_app = Celery(
    "ginie_daml",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
)


@celery_app.task(bind=True, name="ginie.generate_contract")
def generate_contract_task(self, job_id: str, user_input: str, canton_environment: str = "sandbox", canton_url: str = ""):
    import redis
    from pipeline.orchestrator import run_pipeline

    redis_client = redis.from_url(settings.redis_url)
    job_key = f"job:{job_id}"

    def update_status(step: str, progress: int, extra: dict = None):
        data = {
            "job_id":       job_id,
            "status":       "running",
            "current_step": step,
            "progress":     progress,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            data.update(extra)
        redis_client.set(job_key, json.dumps(data), ex=3600)

    try:
        update_status("Analyzing your contract description...", 10)
        self.update_state(state="PROGRESS", meta={"step": "intent", "progress": 10})

        final_state = run_pipeline(
            job_id=job_id,
            user_input=user_input,
            canton_environment=canton_environment,
            canton_url=canton_url,
        )

        if final_state.get("contract_id"):
            result = {
                "job_id":          job_id,
                "status":          "complete",
                "current_step":    "Deployment complete!",
                "progress":        100,
                "contract_id":     final_state.get("contract_id"),
                "package_id":      final_state.get("package_id"),
                "explorer_link":   final_state.get("explorer_link"),
                "generated_code":  final_state.get("generated_code"),
                "structured_intent": final_state.get("structured_intent"),
                "attempt_number":  final_state.get("attempt_number"),
                "updated_at":      datetime.now(timezone.utc).isoformat(),
            }
        else:
            result = {
                "job_id":        job_id,
                "status":        "failed",
                "current_step":  final_state.get("current_step", "Failed"),
                "progress":      0,
                "error_message": final_state.get("error_message", "Pipeline failed"),
                "generated_code": final_state.get("generated_code", ""),
                "compile_errors": final_state.get("compile_errors", []),
                "updated_at":    datetime.now(timezone.utc).isoformat(),
            }

        redis_client.set(job_key, json.dumps(result), ex=3600)
        logger.info("Job completed", job_id=job_id, status=result["status"])
        return result

    except Exception as e:
        logger.error("Job failed with exception", job_id=job_id, error=str(e))
        error_data = {
            "job_id":        job_id,
            "status":        "failed",
            "current_step":  "Internal error",
            "progress":      0,
            "error_message": str(e),
            "updated_at":    datetime.now(timezone.utc).isoformat(),
        }
        redis_client.set(job_key, json.dumps(error_data), ex=3600)
        raise
