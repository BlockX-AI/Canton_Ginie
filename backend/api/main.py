import asyncio
import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from api.routes import router
from api.audit_routes import audit_router
from api.auth_routes import auth_router as auth_api_router
from api.ledger_routes import ledger_router
from api.ws_routes import ws_router
from api.rate_limiter import limiter, rate_limit_exceeded_handler
from config import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Ginie Daml API starting", environment=settings.canton_environment)

    # Initialize PostgreSQL tables (safe to call multiple times)
    try:
        from db.session import init_db
        init_db()
        logger.info("PostgreSQL database initialized")
    except Exception as e:
        logger.warning("PostgreSQL initialization deferred — jobs will use Redis/memory fallback", error=str(e))

    # Validate Canton token for non-sandbox environments
    if settings.canton_environment != "sandbox":
        if not settings.canton_token:
            logger.error(
                "CANTON_TOKEN is required for non-sandbox environments",
                environment=settings.canton_environment,
            )
            raise RuntimeError(
                f"CANTON_TOKEN env var is required for {settings.canton_environment}. "
                "Set it in backend/.env.ginie"
            )
        # Lightweight validation: try a /v1/parties call
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.get_canton_url()}/v1/parties",
                    headers={"Authorization": f"Bearer {settings.canton_token}"},
                )
                if resp.status_code == 401:
                    logger.error("CANTON_TOKEN is invalid (401 Unauthorized)")
                    raise RuntimeError("CANTON_TOKEN is invalid — received 401 from Canton")
                logger.info("Canton token validated", status=resp.status_code)
        except httpx.ConnectError:
            logger.warning("Canton not reachable at startup — token will be validated on first request",
                          url=settings.get_canton_url())
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning("Canton token validation skipped", error=str(e))

    try:
        from rag.vector_store import get_vector_store
        get_vector_store(persist_dir=settings.chroma_persist_dir)
        logger.info("RAG vector store initialized")
    except Exception as e:
        logger.warning("RAG initialization deferred", error=str(e))

    os.makedirs(settings.dar_output_dir, exist_ok=True)

    from api.ws_routes import set_main_event_loop
    set_main_event_loop(asyncio.get_running_loop())
    logger.info("Event loop stored for WebSocket thread bridge")

    yield

    logger.info("Ginie Daml API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ginie Daml API",
        description="Agentic AI pipeline to generate, audit, and deploy Canton smart contracts with enterprise security & compliance",
        version="2.0.0",
        lifespan=lifespan,
    )

    settings = get_settings()
    allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    logger.info("CORS allowed origins", origins=allowed_origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.include_router(router, prefix="/api/v1", tags=["contracts"])
    app.include_router(auth_api_router, prefix="/api/v1", tags=["auth"])
    app.include_router(audit_router, prefix="/api/v1", tags=["audit", "compliance"])
    app.include_router(ledger_router, prefix="/api/v1", tags=["ledger-explorer"])
    app.include_router(ws_router, tags=["websocket"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
