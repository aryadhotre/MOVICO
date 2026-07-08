import os
import json
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.config.settings import settings
from app.models.trainer import train_and_evaluate_models
from app.database.models import Movie, Rating
import redis
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System Management"])

# Global variable to track training status
training_in_progress = False

def run_retraining_task():
    global training_in_progress
    db = None
    try:
        logger.info("Background model training task started.")
        train_and_evaluate_models()
        logger.info("Background model training completed successfully.")
    except Exception as e:
        logger.error(f"Background training failed: {str(e)}")
    finally:
        training_in_progress = False

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Checks the health of PostgreSQL, Redis, and filesystems."""
    health_status = {
        "status": "healthy",
        "postgres": "healthy",
        "redis": "healthy",
        "models_exist": True
    }
    
    # 1. Test Postgres
    try:
        db.execute(func.select(1)) if hasattr(func, "select") else db.execute("SELECT 1")
    except Exception as e:
        logger.error(f"Healthcheck: PostgreSQL is unhealthy: {str(e)}")
        health_status["postgres"] = "unhealthy"
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

@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
def trigger_retraining(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Triggers background execution of the model training and evaluation pipeline."""
    global training_in_progress
    if training_in_progress:
        return {"status": "ignored", "detail": "Retraining is already in progress"}
        
    training_in_progress = True
    background_tasks.add_task(run_retraining_task)
    return {"status": "accepted", "detail": "Retraining task queued in background"}
