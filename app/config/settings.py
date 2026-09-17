from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    
    APP_NAME: str = Field(default="MOVICO Recommendation Service")
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    PORT: int = Field(default=8000)
    SECRET_KEY: str = Field(default="replace-this-with-a-very-secure-random-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)
    # Required header value for the destructive maintenance endpoints. Empty
    # disables them entirely, which is the safe default for a public deployment.
    ADMIN_TOKEN: str = Field(default="")
    
    # Database Configurations (PostgreSQL or SQLite fallback)
    USE_SQLITE: bool = Field(default=True)
    POSTGRES_USER: str = Field(default="movico_user")
    POSTGRES_PASSWORD: str = Field(default="movico_pass")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="movico_db")
    
    # Redis is an optional shared cache tier. The in-process TTL cache is the
    # default so a single-instance deployment needs no external service.
    REDIS_ENABLED: bool = Field(default=False)
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    CACHE_EXPIRE_SECONDS: int = Field(default=600)

    # Comma-separated browser origins allowed to call the API. Localhost dev ports
    # are always permitted; this is for the deployed frontend.
    CORS_ORIGINS: str = Field(default="")
    
    # TMDB API Configuration
    TMDB_API_KEY: str = Field(default="your-tmdb-api-key-here")
    
    # Data & Models Configurations
    DATA_DIR: str = Field(default="./data")
    MODELS_DIR: str = Field(default="./models_checkpoint")
    
    # MovieLens dataset URL - use ml-latest for the biggest & most recent dataset
    # Options:
    #   ml-latest-small (100K ratings, 9K movies)  — fast dev/testing
    #   ml-25m          (25M ratings, 62K movies)   — large stable release
    #   ml-latest       (33M+ ratings, 86K+ movies) — largest, continuously updated
    MOVIELENS_DATASET_URL: str = Field(default="https://files.grouplens.org/datasets/movielens/ml-latest.zip")
    
    RECOMMENDATION_LIMIT: int = Field(default=10)
    COLD_START_THRESHOLD: int = Field(default=5)
    
    # Training Configuration
    # For large datasets (25M+), we sample a subset for SVD training to keep memory & time manageable.
    # Set to 0 to use all ratings (warning: 33M ratings SVD takes hours on CPU).
    TRAINING_SAMPLE_SIZE: int = Field(default=0)
    SVD_EPOCHS: int = Field(default=20)
    SVD_FACTORS: int = Field(default=100)

    @property
    def cors_origins(self) -> list[str]:
        """Explicit allowed origins, including the local dev server."""
        defaults = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://localhost:3000",
        ]
        configured = [
            origin.strip().rstrip("/")
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]
        return list(dict.fromkeys(defaults + configured))

    @property
    def database_url(self) -> str:
        # Check if DATABASE_URL is directly injected by docker-compose/orchestrator
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
        if self.USE_SQLITE:
            os.makedirs(self.DATA_DIR, exist_ok=True)
            # Use absolute path to ensure DB file is created reliably
            abs_data_dir = os.path.abspath(self.DATA_DIR)
            return f"sqlite:///{os.path.join(abs_data_dir, 'movico.db')}"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

# Global settings instance
settings = Settings()
