from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config.settings import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Check connection health before executing queries
    pool_size=10,        # Connection pool size
    max_overflow=20      # Temporary connections above pool_size
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base class for models
Base = declarative_base()

# FastAPI dependency for database sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
