"""Database engines and session factories.

The application runs against **two** databases, split by how the data behaves
rather than by what it is about:

``catalogue`` — SQLite, shipped inside the container image
    95,947 films, their artwork, credits and ranking scores. Written only by the
    offline pipelines and read on nearly every request. Keeping it local means
    browse and search stay single-digit milliseconds instead of paying a network
    round trip per query, the FTS5 index keeps working, and the catalogue cannot
    be taken offline by a managed database pausing or hitting a connection cap.
    It is effectively a build artifact, like the model pickles beside it.

``users`` — Postgres in production, SQLite locally
    Accounts, password hashes, ratings, watchlists, recommendation history. Small,
    mutable and irreplaceable, so it lives in a managed database that survives a
    redeploy. Free-tier hosts give a container no persistent disk, so anything
    written to local storage is lost on every restart.

The cost of the split is that no single SQL statement can join a rating to a
movie. The three places that did now fetch ids from one database and hydrate from
the other, which is a cheap indexed lookup either way.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config.settings import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


def _sqlite_engine(url: str, *, read_mostly: bool):
    """Builds a SQLite engine tuned for this workload.

    The pragmas matter more than they look:

    ``journal_mode=WAL``
        Readers stop blocking on a writer. Without it one rating submission
        stalls every concurrent catalogue read.
    ``foreign_keys=ON``
        SQLite ignores foreign keys unless asked, per connection. Every
        ``ondelete="CASCADE"`` in the models was silently inert.
    ``busy_timeout``
        A contended write waits rather than immediately raising
        "database is locked".
    ``mmap_size``
        Maps the file into the address space so warm reads skip the syscall path.
        Sized by ``SQLITE_MMAP_MB`` because mapped pages count toward a
        container's memory limit even though they are reclaimable.
    """
    engine = create_engine(
        url,
        # FastAPI serves across a thread pool; SQLite's same-thread check would
        # reject those connections.
        connect_args={"check_same_thread": False, "timeout": 30.0},
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        # The catalogue is read on every request and worth caching generously;
        # the user database is small and mutated, so it gets a modest slice.
        cursor.execute("PRAGMA cache_size=-131072" if read_mostly else "PRAGMA cache_size=-16384")
        if read_mostly and settings.SQLITE_MMAP_MB > 0:
            cursor.execute(f"PRAGMA mmap_size={settings.SQLITE_MMAP_MB * 1024 * 1024}")
        cursor.close()

    return engine


def _postgres_engine(url: str):
    """Builds a Postgres engine sized for a pooled, serverless-style connection.

    ``NullPool`` is deliberate. Supabase's transaction pooler already multiplexes
    connections server-side, and a free project allows only 60 direct sessions.
    Holding a client-side pool open on top of that is how a single restarting
    container exhausts the limit for every other one.
    """
    return create_engine(
        url,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            # Identifies the app in Supabase's connection log.
            "application_name": "movico-api",
        },
    )


def _build(url: str, *, read_mostly: bool):
    if url.startswith("sqlite"):
        return _sqlite_engine(url, read_mostly=read_mostly)
    return _postgres_engine(url)


catalogue_engine = _build(settings.catalogue_url, read_mostly=True)
user_engine = _build(settings.user_database_url, read_mostly=False)

#: True when both halves resolve to the same file, which is the local default.
SINGLE_DATABASE = settings.catalogue_url == settings.user_database_url

CatalogueSession = sessionmaker(autocommit=False, autoflush=False, bind=catalogue_engine)
UserSession = sessionmaker(autocommit=False, autoflush=False, bind=user_engine)

# Kept so existing imports of SessionLocal continue to mean "the user database".
SessionLocal = UserSession


def get_db():
    """FastAPI dependency yielding a session against the **user** database."""
    db = UserSession()
    try:
        yield db
    finally:
        db.close()


def get_catalogue():
    """FastAPI dependency yielding a session against the **catalogue**."""
    db = CatalogueSession()
    try:
        yield db
    finally:
        db.close()
