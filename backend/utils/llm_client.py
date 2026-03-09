import structlog

logger = structlog.get_logger()


def call_llm(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    from config import get_settings
    settings = get_settings()

    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return _call_gemini(settings, system_prompt, user_message, max_tokens)
    elif settings.anthropic_api_key:
        return _call_anthropic(settings, system_prompt, user_message, max_tokens)
    else:
        raise EnvironmentError(
            "No LLM API key configured.\n"
            "Set GEMINI_API_KEY in backend/.env, or ANTHROPIC_API_KEY."
        )


def _call_gemini(settings, system_prompt: str, user_message: str, max_tokens: int) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
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
                if content and hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            return part.text.strip()
        logger.warning("Gemini returned empty response", finish_reason=getattr(response.candidates[0] if response.candidates else None, "finish_reason", "unknown"))
        return ""
    return text.strip()


def _call_anthropic(settings, system_prompt: str, user_message: str, max_tokens: int) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
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

    if settings.llm_provider == "gemini" and settings.gemini_api_key:
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
