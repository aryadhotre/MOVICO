import os
import json
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.connection import get_db
from app.config.settings import settings
from app.models.trainer import train_and_evaluate_models
from app.database.models import Movie, Rating
import redis
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System Management"])

# Global variables to track background task status
training_in_progress = False
enrichment_in_progress = False

def run_retraining_task():
    global training_in_progress
    try:
        logger.info("Background model training task started.")
        train_and_evaluate_models()
        logger.info("Background model training completed successfully.")
    except Exception as e:
        logger.error(f"Background training failed: {str(e)}")
    finally:
        training_in_progress = False

def run_enrichment_task(limit: int = None):
    global enrichment_in_progress
    try:
        logger.info("Background TMDB enrichment task started.")
        from app.database.connection import SessionLocal
        from app.pipeline.tmdb_enricher import enrich_movies_from_tmdb
        db = SessionLocal()
        try:
            enrich_movies_from_tmdb(db, limit=limit)
        finally:
            db.close()
        logger.info("Background TMDB enrichment completed successfully.")
    except Exception as e:
        logger.error(f"Background enrichment failed: {str(e)}")
    finally:
        enrichment_in_progress = False

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Checks the health of the database, Redis, and ML models."""
    health_status = {
        "status": "healthy",
        "database": "healthy",
        "redis": "healthy",
        "models_exist": True
    }
    
    # 1. Test Database
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Healthcheck: Database is unhealthy: {str(e)}")
        health_status["database"] = "unhealthy"
        health_status["status"] = "degraded"
        
    # 2. Test Redis
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, socket_timeout=1)
        r.ping()
    except Exception as e:
        logger.warning(f"Healthcheck: Redis is unhealthy: {str(e)}")
        health_status["redis"] = "unhealthy"
        # Not marking overall status as unhealthy since cache is optional but degraded
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"
            
    # 3. Test Models
    model_path = os.path.join(settings.MODELS_DIR, "svd_model.pkl")
    if not os.path.exists(model_path):
        health_status["models_exist"] = False
        health_status["status"] = "degraded"
        
    return health_status

@router.get("/metrics")
def get_metrics():
    """Retrieves the evaluation metrics from the last training run."""
    metrics_path = os.path.join(settings.MODELS_DIR, "evaluation_metrics.json")
    if not os.path.exists(metrics_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation metrics not found. Models have not been trained yet."
        )
        
    with open(metrics_path, "r") as f:
        metrics = json.load(f)
    return metrics

@router.get("/stats")
def get_database_stats(db: Session = Depends(get_db)):
    """Returns database population statistics and TMDB enrichment progress."""
    from sqlalchemy import func as sql_func
    
    movie_count = db.query(sql_func.count(Movie.id)).scalar()
    rating_count = db.query(sql_func.count(Rating.id)).scalar()
    
    enriched_count = db.query(sql_func.count(Movie.id)).filter(
        Movie.poster_path.isnot(None),
        Movie.poster_path != ""
    ).scalar()
    
    unenriched_count = db.query(sql_func.count(Movie.id)).filter(
        Movie.tmdb_id.isnot(None),
        Movie.tmdb_id != "",
        Movie.tmdb_id != "nan",
        Movie.poster_path.is_(None)
    ).scalar()
    
    return {
        "total_movies": movie_count,
        "total_ratings": rating_count,
        "tmdb_enriched_movies": enriched_count,
        "tmdb_pending_movies": unenriched_count,
        "enrichment_progress_pct": round((enriched_count / movie_count) * 100, 1) if movie_count > 0 else 0
    }

@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def trigger_retraining(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers background execution of the model training and evaluation pipeline."""
    global training_in_progress
    if training_in_progress:
        return {"status": "ignored", "detail": "Retraining is already in progress"}
        
    training_in_progress = True
    background_tasks.add_task(run_retraining_task)
    return {"status": "accepted", "detail": "Retraining task queued in background"}

@router.post("/enrich", status_code=status.HTTP_202_ACCEPTED)
def trigger_tmdb_enrichment(
    background_tasks: BackgroundTasks,
    limit: int = Query(None, description="Max number of movies to enrich in this batch (None = all)")
):
    """Triggers background TMDB metadata enrichment for all unenriched movies.
    
    Requires TMDB_API_KEY to be configured in .env.
    For large catalogs (86K+ movies), consider running in batches using the 'limit' parameter.
    """
    global enrichment_in_progress
    if enrichment_in_progress:
        return {"status": "ignored", "detail": "TMDB enrichment is already in progress"}

    if not settings.TMDB_API_KEY or settings.TMDB_API_KEY == "your-tmdb-api-key-here":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TMDB_API_KEY not configured. Add your free API key to .env file. Get one at https://www.themoviedb.org/settings/api"
        )
        
    enrichment_in_progress = True
    background_tasks.add_task(run_enrichment_task, limit)
    return {
        "status": "accepted", 
        "detail": f"TMDB enrichment task queued in background" + (f" (limit: {limit} movies)" if limit else " (all unenriched movies)")
    }
