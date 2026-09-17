"""Application configuration.

Defaults here are development defaults, which is the dangerous part: a default
that is merely inconvenient locally -- a placeholder signing key, debug tracebacks,
an unset admin token -- becomes a vulnerability the moment the same code runs in
production. ``_enforce_production_safety`` turns the ones that matter into a
refusal to boot rather than a quiet downgrade, because a container that fails its
health check is noticed and a container signing JWTs with a public string is not.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
import os
import re

#: The placeholder shipped in .env.example. Signing tokens with it means anyone
#: holding a copy of the repository can mint a token for any account.
PLACEHOLDER_SECRET = "replace-this-with-a-very-secure-random-key"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    APP_NAME: str = Field(default="MOVICO Recommendation Service")
    APP_ENV: str = Field(default="development")
    # Off by default. Debug mode returns exception tracebacks to the client, which
    # leak file paths, library versions and local variables; opting *in* locally is
    # cheap, while opting out in production is the kind of thing that gets missed.
    DEBUG: bool = Field(default=False)
    PORT: int = Field(default=8000)
    SECRET_KEY: str = Field(default=PLACEHOLDER_SECRET)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)
    # Required header value for the destructive maintenance endpoints. Empty
    # disables them entirely, which is the safe default for a public deployment.
    ADMIN_TOKEN: str = Field(default="")
    
    # How much of the catalogue to memory-map, in MB. Mapped pages are clean and
    # reclaimable, so they cannot cause an OOM -- but they do count toward a
    # container's memory limit, and a 256 MB mapping on top of ~250 MB of model
    # artifacts keeps a 512 MB instance permanently in reclaim. 64 MB covers the
    # hot B-tree interior pages, which is where the benefit actually is.
    SQLITE_MMAP_MB: int = Field(default=256)

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
    # The Vercel project slug, e.g. "movico". Every preview deployment gets its own
    # generated subdomain, so they cannot be enumerated as fixed origins -- but they
    # all begin with the project slug, which is enough to match them and nothing
    # else. Leave empty to allow no previews at all.
    VERCEL_PROJECT: str = Field(default="")
    
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
    def is_production(self) -> bool:
        """True when this process is serving real users."""
        return self.APP_ENV.strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        """Refuses to start a production process with development defaults.

        Each of these is silent when wrong -- the app serves traffic perfectly well
        with a known signing key -- so the only place to catch them is boot.
        """
        if not self.is_production:
            return self

        problems: list[str] = []

        if self.SECRET_KEY == PLACEHOLDER_SECRET or len(self.SECRET_KEY) < 32:
            problems.append(
                "SECRET_KEY must be set to a random value of at least 32 characters "
                "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
            )

        if self.DEBUG:
            problems.append("DEBUG must be false in production; it returns tracebacks to clients")

        if not self.CORS_ORIGINS.strip():
            problems.append(
                "CORS_ORIGINS must list the deployed frontend origin, e.g. https://movico.vercel.app"
            )

        if problems:
            raise ValueError(
                "Refusing to start with APP_ENV=production:\n  - " + "\n  - ".join(problems)
            )

        return self

    @property
    def catalogue_url(self) -> str:
        """Where the film catalogue lives.

        Always local SQLite: it ships inside the image as a build artifact and is
        read on nearly every request, so a network round trip per query would be
        the dominant cost of browsing.
        """
        os.makedirs(self.DATA_DIR, exist_ok=True)
        return f"sqlite:///{os.path.join(os.path.abspath(self.DATA_DIR), 'movico.db')}"

    @property
    def user_database_url(self) -> str:
        """Where accounts, ratings and watchlists live.

        ``DATABASE_URL`` in production (Supabase Postgres); the same local SQLite
        file as the catalogue when unset, so a checkout runs with no external
        service. SQLAlchemy 2 needs the ``postgresql+psycopg2`` driver prefix,
        while managed providers hand out ``postgres://``.
        """
        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            return self.catalogue_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

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
        if self.is_production:
            # Localhost is not a trusted origin for a deployed API. Allowing it
            # means a page served from a developer's machine -- or any process that
            # can bind 5173 on a visitor's machine -- can make credentialed calls.
            defaults = []
        return list(dict.fromkeys(defaults + configured))

    @property
    def cors_origin_regex(self) -> str | None:
        """Matches this project's Vercel preview deployments, and only this project's.

        The obvious pattern, ``https://.*\\.vercel\\.app``, is a serious hole when
        paired with ``allow_credentials``: anyone can deploy to vercel.app in
        minutes, and that page would then be allowed to read authenticated
        responses from this API on a logged-in visitor's behalf. Anchoring to the
        project slug closes it -- Vercel derives every preview host from the slug,
        and a slug is unique per account.
        """
        slug = self.VERCEL_PROJECT.strip().lower()
        if not slug:
            return None
        safe = re.escape(slug)
        # e.g. movico.vercel.app, movico-abc123-arya.vercel.app,
        #      movico-git-main-arya.vercel.app
        return rf"^https://{safe}(-[a-z0-9-]+)?\.vercel\.app$"

    # There is deliberately no combined ``database_url``. Before the split it meant
    # "the database"; afterwards that phrase has no referent, and a property that
    # followed DATABASE_URL would hand a Postgres URL to the raw-sqlite3 callers
    # that read the catalogue. Ask for ``catalogue_url`` or ``user_database_url``
    # by name, so the choice is made at the call site where it is understood.


# Global settings instance
settings = Settings()
