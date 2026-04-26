"""Inspect the audit result stored in Postgres for a given job_id.

Useful when you want to know *why* a deployed contract slipped past the
security gate \u2014 did the audit hit zero findings, did it time out, did
the LLM return malformed JSON?

Usage (locally with the same .env.ginie that points at the prod DB):

    python -m backend.scripts.inspect_job_audit <job_id>

Or with an explicit DATABASE_URL:

    DATABASE_URL=postgres://... python -m backend.scripts.inspect_job_audit <job_id>

Output is a single JSON blob to stdout so you can pipe it into ``jq``.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any


def _load_job(job_id: str) -> dict[str, Any]:
    # Defer SQLAlchemy import so a missing DATABASE_URL fails with a
    # clear message instead of an import-time pydantic crash.
    from db.session import get_db_session
    from db.models import JobHistory, DeployedContract

    with get_db_session() as session:
        job = (
            session.query(JobHistory)
            .filter(JobHistory.job_id == job_id)
            .first()
        )
        if not job:
            return {"error": f"Job {job_id} not found in job_history"}

        contracts = (
            session.query(DeployedContract)
            .filter(DeployedContract.job_id == job_id)
            .order_by(DeployedContract.created_at.asc())
            .all()
        )
        rj = job.result_json if isinstance(job.result_json, dict) else {}
        audit = rj.get("audit_result") or {}
        combined = audit.get("combined_scores") or {}
        sec = audit.get("security_audit") or {}
        comp = audit.get("compliance_analysis") or {}

        return {
            "job_id": job.job_id,
            "status": job.status,
            "current_step": job.current_step,
            "canton_env": job.canton_env,
            "user_email": job.user_email,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "deployed_contracts": [
                {
                    "contract_id": c.contract_id,
                    "template_id": c.template_id,
                    "party_id": c.party_id,
                }
                for c in contracts
            ],
            "audit_present": bool(audit),
            "audit_summary": {
                "security_score": combined.get("security_score"),
                "compliance_score": combined.get("compliance_score"),
                "enterprise_score": combined.get("enterprise_score"),
                "deploy_gate": combined.get("deploy_gate"),
                "enterprise_readiness": combined.get("enterprise_readiness"),
                "elapsed_seconds": audit.get("elapsed_seconds"),
            },
            "security_audit": {
                "success": sec.get("success"),
                "error": sec.get("error"),
                "findings_count": sec.get("findings_count")
                or len((sec.get("audit_report") or {}).get("findings", [])),
                "executive_summary": sec.get("executive_summary"),
                "findings": (sec.get("audit_report") or {}).get("findings", []),
            },
            "compliance_analysis": {
                "success": comp.get("success"),
                "error": comp.get("error"),
                "compliance_score": comp.get("compliance_score"),
            },
            "audit_phases": audit.get("phases"),
            "result_json_keys": sorted(list(rj.keys())),
        }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m backend.scripts.inspect_job_audit <job_id>", file=sys.stderr)
        return 2

    job_id = sys.argv[1]

    # Make ``backend/`` importable as a top-level package when the script
    # is invoked as ``python backend/scripts/inspect_job_audit.py``.
    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(here)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    try:
        out = _load_job(job_id)
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, indent=2))
        return 1

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
