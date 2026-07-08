import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.api.middleware import RequestLoggingMiddleware, setup_exception_handlers
from app.api.routes import auth, movies, ratings, recommend, system
from app.database.connection import Base, engine, SessionLocal
from app.database.models import Movie

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(filename="logs/app.log", mode="a", encoding="utf-8") if os.path.exists("logs") else logging.StreamHandler()
    ]
)
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("app.main")

# Initialize FastAPI App
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade Hybrid Movie Recommendation Service.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Standardized error exception handlers
setup_exception_handlers(app)

# Include API route sub-modules
app.include_router(auth.router, prefix="/api")
app.include_router(movies.router, prefix="/api")
app.include_router(ratings.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(system.router, prefix="/api")

@app.on_event("startup")
def startup_event():
    """Ties together table initialization, dataset downloads, database seeding, and initial training on launch."""
    if settings.APP_ENV == "testing":
        logger.info("Testing environment detected. Skipping startup database seeding and training.")
        return
        
    logger.info("Initializing application startup sequence...")
    
    # 1. Create database schema tables if not exist
    Base.metadata.create_all(bind=engine)
    
    # 2. Check if DB needs seeding
    db = SessionLocal()
    try:
        movie_count = db.query(Movie).count()
        if movie_count == 0:
            logger.info("Database is currently empty. Executing ingestion pipeline...")
            from app.pipeline.ingest import DataPipeline
            pipeline = DataPipeline()
            pipeline.run_pipeline()
            
            logger.info("Executing training pipeline to fit models on newly seeded data...")
            from app.models.trainer import train_and_evaluate_models
            train_and_evaluate_models(db)
        else:
            logger.info(f"Database contains {movie_count} movies. Seeding and training skipped.")
    except Exception as e:
        logger.error(f"Failed to execute startup migration / training tasks: {str(e)}")
    finally:
        db.close()
        
    logger.info("Application startup sequence completed.")

@app.get("/", tags=["System Management"])
def read_root():
    return {
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "docs_url": "/docs",
        "status": "online"
    }
