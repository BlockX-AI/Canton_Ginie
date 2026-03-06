from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=10, description="Plain-English description of the Canton contract")
    canton_environment: str = Field(default="sandbox", description="sandbox | devnet | mainnet")
    canton_url: Optional[str] = Field(default=None, description="Override Canton node URL")


class GenerateResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str = "Contract generation job queued"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: str
    progress: int
    updated_at: Optional[str] = None
    error_message: Optional[str] = None


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    contract_id: Optional[str] = None
    package_id: Optional[str] = None
    explorer_link: Optional[str] = None
    generated_code: Optional[str] = None
    structured_intent: Optional[dict] = None
    attempt_number: Optional[int] = None
    error_message: Optional[str] = None
    compile_errors: Optional[list] = None
    created_at: Optional[str] = None


class IterateRequest(BaseModel):
    feedback: str = Field(..., min_length=5, description="Changes or additions to make to the existing contract")
    original_code: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    daml_sdk: str
    rag_status: str
    redis_status: str
