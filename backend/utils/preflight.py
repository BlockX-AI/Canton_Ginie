import os
import shutil
import subprocess
import structlog
import httpx

logger = structlog.get_logger()

_LLM_KEY_PREFIXES = {
    "anthropic": ("sk-ant-",),
    "openai":    ("sk-",),
    "gemini":    (),
}


def check_daml_sdk() -> dict:
    from agents.compile_agent import resolve_daml_sdk
    try:
        path = resolve_daml_sdk()
        proc = subprocess.run([path, "version"], capture_output=True, text=True, timeout=10)
        version = proc.stdout.strip().splitlines()[0] if proc.stdout else "unknown"
        return {"ok": True, "path": path, "version": version}
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "DAML SDK version check timed out"}
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
        return {
            "ok": False,
            "error": f"Cannot reach Canton at {canton_url} — start with: canton sandbox --config canton-sandbox-memory.conf",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_llm(provider: str, api_key: str, model: str = "") -> dict:
    """Check that the configured LLM provider has a usable API key.

    Replaces the old check_anthropic() which hard-wired Anthropic regardless
    of the configured provider, causing pipeline_ready to always be False
    for OpenAI or Gemini deployments.
    """
    provider = provider.strip().lower()

    if provider == "gemini":
        if not api_key:
            return {"ok": False, "provider": "gemini", "error": "GEMINI_API_KEY not set in backend/.env.ginie"}
        return {"ok": True, "provider": "gemini", "key_prefix": api_key[:12] + "..."}

    if provider == "anthropic":
        if not api_key or not api_key.startswith("sk-ant-"):
            return {"ok": False, "provider": "anthropic", "error": "ANTHROPIC_API_KEY missing or does not start with sk-ant-"}
        return {"ok": True, "provider": "anthropic", "key_prefix": api_key[:16] + "..."}

    if provider == "openai":
        if not api_key or not api_key.startswith("sk-"):
            return {"ok": False, "provider": "openai", "error": "OPENAI_API_KEY missing or does not start with sk-"}
        return {"ok": True, "provider": "openai", "key_prefix": api_key[:12] + "..."}

    return {"ok": False, "provider": provider, "error": f"Unknown LLM provider '{provider}'; expected openai, anthropic, or gemini"}


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

    provider = settings.llm_provider.strip().lower()
    key_map = {
        "anthropic": settings.anthropic_api_key,
        "openai":    settings.openai_api_key,
        "gemini":    settings.gemini_api_key,
    }
    llm_api_key = key_map.get(provider, "")

    results = {
        "daml_sdk": check_daml_sdk(),
        "canton":   check_canton(settings.get_canton_url(), settings.canton_environment),
        "llm":      check_llm(provider, llm_api_key, settings.llm_model),
        "redis":    check_redis(settings.redis_url),
    }

    all_critical_ok = results["daml_sdk"]["ok"] and results["llm"]["ok"]
    results["pipeline_ready"] = all_critical_ok
    results["deploy_ready"]   = all_critical_ok and results["canton"]["ok"]

    for name, res in results.items():
        if isinstance(res, dict) and "ok" in res:
            status = "OK" if res["ok"] else "FAIL"
            logger.info(f"Preflight [{name}]", status=status, **{k: v for k, v in res.items() if k != "ok"})

    return results
