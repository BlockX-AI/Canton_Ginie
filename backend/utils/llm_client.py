import structlog

logger = structlog.get_logger()


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    from config import get_settings
    settings = get_settings()

    if settings.llm_provider == "openai" and settings.openai_api_key:
        return _call_openai(settings, system_prompt, user_message, max_tokens)
    elif settings.llm_provider == "gemini" and settings.gemini_api_key:
        return _call_gemini(settings, system_prompt, user_message, max_tokens)
    elif settings.llm_provider == "bedrock" and settings.aws_access_key_id:
        return _call_bedrock(settings, system_prompt, user_message, max_tokens)
    elif settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return _call_anthropic(settings, system_prompt, user_message, max_tokens)
    elif settings.anthropic_api_key:
        # Backwards-compat: a bare ``ANTHROPIC_API_KEY`` with no provider
        # set still routes to direct Anthropic.
        return _call_anthropic(settings, system_prompt, user_message, max_tokens)
    else:
        raise EnvironmentError(
            "No LLM API key configured.\n"
            "Set OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, or "
            "AWS_ACCESS_KEY_ID (with LLM_PROVIDER=bedrock) in backend/.env "
            "or backend/.env.ginie."
        )


def _call_gemini(settings, system_prompt: str, user_message: str, max_tokens: int) -> str:
    from google import genai
    from google.genai import types

    # google-genai's transport accepts a per-client httpx timeout via
    # ``http_options``. Bound it to ``llm_request_timeout_seconds`` so a
    # hung Gemini request can never stall the audit / writer pipeline.
    timeout_s = float(getattr(settings, "llm_request_timeout_seconds", 90.0) or 90.0)
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
    )
    response = client.models.generate_content(
        model=settings.llm_model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=settings.llm_temperature,
        ),
    )
    text = response.text
    if text is None:
        # Gemini may block content or return empty — try candidates
        if response.candidates:
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                if content and hasattr(content, "parts") and content.parts:
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            return part.text.strip()
        logger.warning("Gemini returned empty response", finish_reason=getattr(response.candidates[0] if response.candidates else None, "finish_reason", "unknown"))
        return ""
    return text.strip()


def _call_openai(settings, system_prompt: str, user_message: str, max_tokens: int) -> str:
    from openai import OpenAI

    timeout_s = float(getattr(settings, "llm_request_timeout_seconds", 90.0) or 90.0)
    # ``timeout`` on the client applies to every request made through it,
    # including the underlying httpx connect/read/write phases. Without
    # this the SDK defaults to ~10 minutes, which silently stalls the
    # audit / writer / fix nodes when OpenAI is slow or the network blips.
    client = OpenAI(api_key=settings.openai_api_key, timeout=timeout_s)
    response = client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        temperature=settings.llm_temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    text = response.choices[0].message.content
    return text.strip() if text else ""


def _call_anthropic(settings, system_prompt: str, user_message: str, max_tokens: int) -> str:
    from anthropic import Anthropic

    timeout_s = float(getattr(settings, "llm_request_timeout_seconds", 90.0) or 90.0)
    client = Anthropic(api_key=settings.anthropic_api_key, timeout=timeout_s)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def _call_bedrock(settings, system_prompt: str, user_message: str, max_tokens: int) -> str:
    """Call Anthropic Claude via AWS Bedrock's Messages API.

    Bedrock exposes the Anthropic Messages API shape under
    ``invoke_model``: the request body is the same JSON you'd send
    directly to Anthropic, but the auth + transport is AWS SigV4 over
    ``bedrock-runtime``. This lets the user bill Claude usage to AWS
    (e.g. via existing committed-spend) without changing the prompt
    contract for the rest of the pipeline.
    """
    import json
    import boto3
    from botocore.config import Config

    timeout_s = float(getattr(settings, "llm_request_timeout_seconds", 90.0) or 90.0)
    boto_cfg = Config(
        region_name=settings.aws_region,
        connect_timeout=min(15.0, timeout_s),
        read_timeout=timeout_s,
        retries={"max_attempts": 2, "mode": "standard"},
    )
    client_kwargs = {
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
        "config": boto_cfg,
    }
    if settings.aws_session_token:
        client_kwargs["aws_session_token"] = settings.aws_session_token

    client = boto3.client("bedrock-runtime", **client_kwargs)

    # Bedrock's Anthropic adapter requires ``anthropic_version`` and uses
    # the same Messages-API field names as the direct Anthropic SDK.
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": float(getattr(settings, "llm_temperature", 0.1) or 0.1),
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    model_id = settings.bedrock_model_id or settings.llm_model
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    payload = json.loads(resp["body"].read())
    # Response shape: {"content": [{"type": "text", "text": "..."}], ...}
    content = payload.get("content") or []
    for block in content:
        if block.get("type") == "text" and block.get("text"):
            return block["text"].strip()
    logger.warning("Bedrock returned no text block", payload=payload)
    return ""


def check_llm_available() -> dict:
    from config import get_settings
    settings = get_settings()

    if settings.llm_provider == "openai" and settings.openai_api_key:
        try:
            _call_openai(settings, "You are a test assistant.", "Reply with the single word OK.", max_tokens=5)
            return {"ok": True, "provider": "openai", "model": settings.llm_model}
        except Exception as e:
            return {"ok": False, "provider": "openai", "error": str(e)}

    elif settings.llm_provider == "gemini" and settings.gemini_api_key:
        try:
            _call_gemini(settings, "You are a test assistant.", "Reply with the single word OK.", max_tokens=5)
            return {"ok": True, "provider": "gemini", "model": settings.llm_model}
        except Exception as e:
            return {"ok": False, "provider": "gemini", "error": str(e)}

    elif settings.llm_provider == "bedrock" and settings.aws_access_key_id:
        try:
            _call_bedrock(settings, "You are a test assistant.", "Reply with the single word OK.", max_tokens=8)
            return {"ok": True, "provider": "bedrock", "model": settings.bedrock_model_id}
        except Exception as e:
            return {"ok": False, "provider": "bedrock", "error": str(e)}

    elif settings.anthropic_api_key:
        try:
            _call_anthropic(settings, "You are a test assistant.", "Reply with the single word OK.", max_tokens=5)
            return {"ok": True, "provider": "anthropic", "model": settings.llm_model}
        except Exception as e:
            return {"ok": False, "provider": "anthropic", "error": str(e)}

    return {"ok": False, "provider": "none", "error": "No API key configured"}
