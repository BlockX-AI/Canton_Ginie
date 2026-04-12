import os
import subprocess
import structlog
import httpx

logger = structlog.get_logger()


def check_daml_sdk() -> dict:
    from agents.compile_agent import resolve_daml_sdk
    try:
        path = resolve_daml_sdk()
        proc = subprocess.run([path, "version"], capture_output=True, text=True, timeout=10)
        version = proc.stdout.strip().splitlines()[0] if proc.stdout else "unknown"
        return {"ok": True, "path": path, "version": version}
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"SDK found but failed to run: {exc}"}


def check_canton(canton_url: str, canton_environment: str) -> dict:
    try:
        auth = "Bearer sandbox-token" if canton_environment == "sandbox" else f"Bearer {os.environ.get('CANTON_TOKEN','')}"
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                f"{canton_url}/v1/query",
                content=b'{"templateIds":[]}',
                headers={"Authorization": auth, "Content-Type": "application/json"},
            )
        return {"ok": resp.status_code < 500, "status_code": resp.status_code, "url": canton_url}
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return {"ok": False, "error": f"Cannot reach Canton at {canton_url} — run: daml sandbox"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_anthropic(api_key: str) -> dict:
    if not api_key or not api_key.startswith("sk-ant-"):
        return {"ok": False, "error": "ANTHROPIC_API_KEY missing or invalid in backend/.env"}
    return {"ok": True, "key_prefix": api_key[:16] + "..."}


def check_redis(redis_url: str) -> dict:
    try:
        import redis as redis_lib
        r = redis_lib.from_url(redis_url, socket_connect_timeout=3)
        r.ping()
        return {"ok": True, "url": redis_url}
    except Exception as exc:
        return {"ok": False, "error": f"Redis not reachable at {redis_url}: {exc}"}


def run_all_checks() -> dict:
    from config import get_settings
    settings = get_settings()

    results = {
        "daml_sdk":  check_daml_sdk(),
        "canton":    check_canton(settings.get_canton_url(), settings.canton_environment),
        "anthropic": check_anthropic(settings.anthropic_api_key),
        "redis":     check_redis(settings.redis_url),
    }

    all_critical_ok = results["daml_sdk"]["ok"] and results["anthropic"]["ok"]
    results["pipeline_ready"] = all_critical_ok
    results["deploy_ready"]   = all_critical_ok and results["canton"]["ok"]

    for name, res in results.items():
        if isinstance(res, dict) and "ok" in res:
            status = "OK" if res["ok"] else "FAIL"
            logger.info(f"Preflight [{name}]", status=status, **{k: v for k, v in res.items() if k != "ok"})

    return results
