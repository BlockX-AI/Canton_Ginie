import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.audit_routes import audit_router
from api.auth_routes import auth_router as auth_api_router
from api.ledger_routes import ledger_router
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

    try:
        from rag.vector_store import get_vector_store
        get_vector_store(persist_dir=settings.chroma_persist_dir)
        logger.info("RAG vector store initialized")
    except Exception as e:
        logger.warning("RAG initialization deferred", error=str(e))

    import os
    os.makedirs(settings.dar_output_dir, exist_ok=True)

    yield

    logger.info("Ginie Daml API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ginie Daml API",
        description="Agentic AI pipeline to generate, audit, and deploy Canton smart contracts with enterprise security & compliance",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1", tags=["contracts"])
    app.include_router(auth_api_router, prefix="/api/v1", tags=["auth"])
    app.include_router(audit_router, prefix="/api/v1", tags=["audit", "compliance"])
    app.include_router(ledger_router, prefix="/api/v1", tags=["ledger-explorer"])

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
