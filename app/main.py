"""FastAPI application entry point.

Startup is deliberately non-blocking. The previous version ran the full ingestion
and training pipeline inside the startup hook, which meant a cold container either
took 30+ minutes to answer its first request or timed out its health check and was
killed. Data loading is now an explicit offline step (``app.pipeline.ingest`` and
``app.ml.train``); startup only reconciles the schema and warms the model artifacts
that already exist on disk.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.middleware import RequestLoggingMiddleware, setup_exception_handlers
from app.api.routes import auth, movies, ratings, recommend, system
from app.api.security import SecurityHeadersMiddleware
from app.config.settings import settings

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(filename="logs/app.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Reconciles the schema and loads model artifacts, if present."""
    if settings.APP_ENV == "testing":
        yield
        return

    started = time.perf_counter()
    try:
        from app.pipeline.migrate import reconcile_schema

        reconcile_schema()
    except Exception as exc:  # noqa: BLE001 - never block startup on migration
        logger.error("Schema reconciliation failed: %s", exc)

    try:
        from app.ml.ranker import engine

        if engine.load():
            logger.info("Recommendation engine warm: %s", engine.status())
        else:
            logger.warning(
                "No trained models found (%s). Catalogue browsing works; "
                "recommendations will return 503 until `python -m app.ml.train` runs.",
                engine.load_error,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Engine warm-up failed: %s", exc)

    logger.info("Startup completed in %.2fs", time.perf_counter() - started)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Hybrid movie recommendation service. Collaborative signal from implicit ALS "
        "and an item-item neighbourhood, content signal from weighted multi-channel "
        "TF-IDF, fused and diversity re-ranked."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Vercel preview deployments get a generated subdomain per commit, so they
    # cannot be enumerated as fixed origins. The pattern is anchored to this
    # project's slug; see settings.cors_origin_regex for why a broad
    # "*.vercel.app" would be a hole rather than a convenience.
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Explicit rather than "*": with allow_credentials, a wildcard invites
    # requests carrying headers no endpoint here reads.
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
    expose_headers=["X-Process-Time"],
    max_age=86400,
)

# JSON catalogue payloads compress by roughly 5x, which matters far more than the
# CPU cost on a small instance.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(SecurityHeadersMiddleware, production=settings.is_production)
app.add_middleware(RequestLoggingMiddleware)
setup_exception_handlers(app)

app.include_router(auth.router, prefix="/api")
app.include_router(movies.router, prefix="/api")
app.include_router(ratings.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(system.router, prefix="/api")


@app.get("/", tags=["System"])
def read_root():
    return {
        "app": settings.APP_NAME,
        "version": "3.0.0",
        "status": "online",
        "docs": "/docs",
    }
