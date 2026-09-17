"""Health, statistics and maintenance endpoints.

The pipeline triggers are guarded by ``ADMIN_TOKEN``. They rebuild the catalogue
and retrain the models, which are expensive and destructive enough that leaving them
open on a public deployment would be a denial-of-service button.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import threading
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.connection import get_catalogue, get_db
from app.database.models import Movie
from app.database.schemas import CatalogueStats
from app.ml.ranker import engine
from app.services.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"])

_running: dict[str, bool] = {}
_lock = threading.Lock()


def require_admin(x_admin_token: Optional[str] = Header(None)) -> None:
    """Gates destructive maintenance endpoints.

    The comparison is constant-time. ``!=`` on strings short-circuits at the first
    differing byte, so the time it takes to reject a guess reveals how much of the
    prefix was right -- enough to recover the token byte by byte over a few
    thousand requests.
    """
    expected = os.getenv("ADMIN_TOKEN") or getattr(settings, "ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Maintenance endpoints are disabled because ADMIN_TOKEN is not set.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token"
        )


def _claim(name: str) -> bool:
    with _lock:
        if _running.get(name):
            return False
        _running[name] = True
        return True


def _release(name: str) -> None:
    with _lock:
        _running[name] = False


@router.get("/health")
def health_check(
    db: Session = Depends(get_catalogue),
    users: Session = Depends(get_db),
):
    """Liveness and readiness for both databases, the models and the cache.

    The two databases are reported separately because they fail independently and
    for different reasons: the catalogue ships in the image and is essentially
    always up, while the managed user database can pause, hit its connection cap
    or be unreachable across the network. Collapsing them into one field would
    hide the only one likely to break.

    This always answers **200**, including when it reports "unhealthy". Render
    restarts a service whose health check fails, and a restart fixes none of the
    conditions above -- a paused Supabase project stays paused. Meanwhile browse,
    search and recommendations run entirely off the catalogue and keep working, so
    taking the instance down would turn a partial outage into a total one. The
    body carries the detail for a human or a monitor; the status code answers only
    "is this process alive".
    """
    report = {
        "status": "healthy",
        "database": "up",
        "user_database": "up",
        "engine": "up",
        "cache": "up",
    }

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Health: catalogue unreachable: %s", exc)
        report["database"] = "down"
        report["status"] = "unhealthy"

    try:
        users.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Health: user database unreachable: %s", exc)
        report["user_database"] = "down"
        report["status"] = "unhealthy"

    if not engine.loaded and not engine.load():
        report["engine"] = "untrained"
        # The catalogue still browses without models, so this is degraded not down.
        if report["status"] == "healthy":
            report["status"] = "degraded"

    report["cache_stats"] = cache.stats()
    return report


@router.get("/stats", response_model=CatalogueStats)
def catalogue_stats(db: Session = Depends(get_catalogue)):
    """Catalogue coverage and engine state, for the status panel."""
    total = db.execute(select(func.count(Movie.id))).scalar_one()
    with_posters = db.execute(
        select(func.count(Movie.id)).where(Movie.poster_path.isnot(None))
    ).scalar_one()
    pending = db.execute(
        select(func.count(Movie.id)).where(
            Movie.enriched_at.is_(None),
            Movie.tmdb_id.isnot(None),
            Movie.tmdb_id.notin_(("", "nan", "None")),
        )
    ).scalar_one()
    modelled = db.execute(select(func.sum(Movie.rating_count))).scalar_one() or 0

    decades = db.execute(
        select(
            (Movie.release_year / 10 * 10).label("decade"), func.count(Movie.id)
        )
        .where(Movie.poster_path.isnot(None), Movie.release_year.isnot(None))
        .group_by(text("decade"))
        .order_by(text("decade"))
    ).all()

    return CatalogueStats(
        total_movies=int(total),
        with_posters=int(with_posters),
        poster_coverage=round(with_posters / total, 4) if total else 0.0,
        total_ratings_modelled=int(modelled),
        catalogue_years={f"{int(decade)}s": int(count) for decade, count in decades if decade},
        enrichment_pending=int(pending),
        engine=engine.status(),
    )


@router.get("/metrics")
def evaluation_metrics():
    """The evaluation report written by the last training run."""
    path = os.path.join(settings.MODELS_DIR, "evaluation_metrics.json")
    if not os.path.exists(path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evaluation report yet. Run `python -m app.ml.train`.",
        )
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@router.post("/reload-engine", status_code=status.HTTP_200_OK)
def reload_engine(_: None = Depends(require_admin)):
    """Re-reads model artifacts from disk without restarting the process."""
    ok = engine.load(force=True)
    cache.local.clear()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=engine.load_error
        )
    return {"status": "reloaded", "engine": engine.status()}


@router.post("/enrich", status_code=status.HTTP_202_ACCEPTED)
def trigger_enrichment(
    background_tasks: BackgroundTasks,
    limit: Optional[int] = Query(None, ge=1),
    _: None = Depends(require_admin),
):
    """Backfills TMDB metadata for catalogue rows that lack it."""
    if not _claim("enrich"):
        return {"status": "already_running"}

    def task() -> None:
        try:
            from app.pipeline.enrich import enrich_pending, recompute_scores

            asyncio.run(enrich_pending(limit=limit))
            recompute_scores()
            cache.local.clear()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Enrichment failed: %s", exc)
        finally:
            _release("enrich")

    background_tasks.add_task(task)
    return {"status": "accepted", "limit": limit}


@router.post("/import-recent", status_code=status.HTTP_202_ACCEPTED)
def trigger_import(
    background_tasks: BackgroundTasks,
    start_year: int = Query(2023, ge=1900),
    end_year: Optional[int] = Query(None),
    pages: int = Query(60, ge=1, le=500),
    _: None = Depends(require_admin),
):
    """Imports titles TMDB has that the catalogue does not."""
    if not _claim("import"):
        return {"status": "already_running"}

    def task() -> None:
        try:
            from app.pipeline.enrich import import_discover, recompute_scores

            asyncio.run(
                import_discover(start_year=start_year, end_year=end_year, pages=pages)
            )
            recompute_scores()
            cache.local.clear()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Import failed: %s", exc)
        finally:
            _release("import")

    background_tasks.add_task(task)
    return {"status": "accepted", "start_year": start_year, "pages": pages}


@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def trigger_training(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin),
):
    """Retrains the recommendation models and reloads them on completion."""
    if not _claim("train"):
        return {"status": "already_running"}

    def task() -> None:
        try:
            from app.ml.content import build_and_save
            from app.ml.train import train

            train()
            build_and_save()
            engine.load(force=True)
            cache.local.clear()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Training failed: %s", exc)
        finally:
            _release("train")

    background_tasks.add_task(task)
    return {"status": "accepted"}


@router.post("/cache/clear", status_code=status.HTTP_200_OK)
def clear_cache(_: None = Depends(require_admin)):
    cache.local.clear()
    return {"status": "cleared"}
