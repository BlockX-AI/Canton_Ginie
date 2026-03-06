import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Ginie Daml API starting", environment=settings.canton_environment)

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
        description="Agentic AI pipeline to generate, compile, and deploy Canton smart contracts from plain-English descriptions",
        version="1.0.0",
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
