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
    
    # Database Configurations (PostgreSQL)
    POSTGRES_USER: str = Field(default="movico_user")
    POSTGRES_PASSWORD: str = Field(default="movico_pass")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="movico_db")
    
    # Redis Configurations
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    CACHE_EXPIRE_SECONDS: int = Field(default=3600)
    
    # Data & Models Configurations
    DATA_DIR: str = Field(default="./data")
    MODELS_DIR: str = Field(default="./models_checkpoint")
    MOVIELENS_DATASET_URL: str = Field(default="https://files.grouplens.org/datasets/movielens/ml-latest-small.zip")
    RECOMMENDATION_LIMIT: int = Field(default=10)
    COLD_START_THRESHOLD: int = Field(default=5)

    @property
    def database_url(self) -> str:
        # Check if DATABASE_URL is directly injected by docker-compose/orchestrator
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

# Global settings instance
settings = Settings()
