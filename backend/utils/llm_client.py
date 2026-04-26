import structlog

logger = structlog.get_logger()


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    from config import get_settings
    settings = get_settings()

    if settings.llm_provider == "openai" and settings.openai_api_key:
        return _call_openai(settings, system_prompt, user_message, max_tokens)
    elif settings.llm_provider == "gemini" and settings.gemini_api_key:
        return _call_gemini(settings, system_prompt, user_message, max_tokens)
    elif settings.anthropic_api_key:
        return _call_anthropic(settings, system_prompt, user_message, max_tokens)
    else:
        raise EnvironmentError(
            "No LLM API key configured.\n"
            "Set OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY in backend/.env.ginie."
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

    elif settings.anthropic_api_key:
        try:
            _call_anthropic(settings, "You are a test assistant.", "Reply with the single word OK.", max_tokens=5)
            return {"ok": True, "provider": "anthropic", "model": settings.llm_model}
        except Exception as e:
            return {"ok": False, "provider": "anthropic", "error": str(e)}

    return {"ok": False, "provider": "none", "error": "No API key configured"}
