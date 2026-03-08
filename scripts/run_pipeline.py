import sys
import os
import asyncio
import json
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from pipeline.orchestrator import run_mvp_pipeline
from config import get_settings

settings = get_settings()


async def main():
    job_id = f"job-e2e-{uuid.uuid4().hex[:8]}"
    result = await run_mvp_pipeline(
        job_id=job_id,
        user_input="Create a bond contract between issuer and investor",
        canton_url="http://localhost:7575",
        auth_token=settings.canton_token,
        max_fix_attempts=3,
    )
    print()
    print("=== PIPELINE RESULT ===")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    success = result.get("success", False)
    print(f"\nExit: {'SUCCESS' if success else 'FAILURE'}")
    sys.exit(0 if success else 1)
