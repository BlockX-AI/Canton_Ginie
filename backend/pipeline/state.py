from typing import Optional
from pydantic import BaseModel, Field


class PipelineState(BaseModel):
    job_id: str = ""
    user_input: str = ""

    structured_intent: dict = Field(default_factory=dict)

    rag_context: list[str] = Field(default_factory=list)

    generated_code: str = ""

    compile_result: str = ""
    compile_success: bool = False
    compile_errors: list[dict] = Field(default_factory=list)

    attempt_number: int = 0

    dar_path: str = ""

    contract_id: str = ""
    package_id: str = ""
    explorer_link: str = ""

    error_message: str = ""
    is_fatal_error: bool = False

    current_step: str = "idle"
    progress: int = 0

    canton_environment: str = "sandbox"
    canton_url: str = ""

    # Authenticated user's party ID (if set, used as primary signatory)
    party_id: str = ""

    class Config:
        arbitrary_types_allowed = True


def make_initial_state(job_id: str, user_input: str, canton_environment: str = "sandbox", canton_url: str = "") -> PipelineState:
    return PipelineState(
        job_id=job_id,
        user_input=user_input,
        canton_environment=canton_environment,
        canton_url=canton_url,
        current_step="starting",
        progress=0,
    )
