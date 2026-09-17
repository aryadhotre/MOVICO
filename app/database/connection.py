"""Database engine and session factory.

The SQLite pragmas matter more than they look:

``journal_mode=WAL``
    Readers no longer block on a writer. Without it, one rating submission stalls
    every concurrent catalogue read.
``foreign_keys=ON``
    SQLite ignores foreign keys unless asked, per connection. The models declare
    ``ondelete="CASCADE"`` throughout, and none of it was being enforced.
``busy_timeout``
    Makes a contended write wait rather than immediately raising
    "database is locked".
``mmap_size``
    Maps the database into the process address space, so warm reads skip the
    syscall path entirely.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config.settings import settings

is_sqlite = settings.database_url.startswith("sqlite")

if is_sqlite:
    engine = create_engine(
        settings.database_url,
        # FastAPI serves requests across a thread pool; SQLite's default
        # same-thread check would reject those connections.
        connect_args={"check_same_thread": False, "timeout": 30.0},
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA cache_size=-131072")  # 128 MB page cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")  # 256 MB
        cursor.close()

else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a session that is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
