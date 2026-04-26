"""Smoke test: audit_node honours the wall-clock deadline and never hangs.

Patches ``run_hybrid_audit`` with a slow stub, sets ``audit_max_seconds``
to 2s, and asserts that ``audit_node`` returns within ~3s with the
timeout signal in ``current_step``.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from pipeline import orchestrator as o  # noqa: E402
from config import get_settings  # noqa: E402


def slow_audit(daml_code, contract_name, compliance_profile):
    time.sleep(10)  # would normally hang the pipeline forever
    return {
        "combined_scores": {
            "security_score": 100,
            "compliance_score": 100,
            "enterprise_score": 100,
            "deploy_gate": True,
        },
        "reports": {},
        "findings": [],
    }


def main() -> None:
    o.run_hybrid_audit = slow_audit
    s = get_settings()
    s.audit_max_seconds = 2.0  # type: ignore[attr-defined]

    state = {
        "job_id": "smoke-timeout",
        "generated_code": "module Main where\n",
        "structured_intent": {"daml_templates_needed": ["Foo"]},
        "events": [],
    }

    start = time.time()
    out = o.audit_node(state)
    elapsed = time.time() - start

    assert elapsed < 4.0, f"audit_node should have returned in <4s, took {elapsed:.1f}s"
    assert out.get("audit_result") is None, out
    assert out.get("security_score") is None, out
    assert out.get("deploy_gate") is True, out
    assert "timed out" in (out.get("current_step") or "").lower(), out

    print(f"audit timeout smoke OK (returned in {elapsed:.2f}s, "
          f"deploy_gate={out['deploy_gate']}, current_step={out['current_step']!r})")


if __name__ == "__main__":
    main()
