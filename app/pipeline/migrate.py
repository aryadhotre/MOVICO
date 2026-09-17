"""Idempotent schema reconciliation for the live SQLite database.

``Base.metadata.create_all`` only creates missing *tables*; it will not add a
column or an index to a table that already exists. That is why the indexes added
in the previous session never reached ``movico.db``. This module diffs the live
schema against the ORM models and applies the difference, so an existing database
picks up new columns and indexes without being rebuilt.

SQLite's ``ALTER TABLE ... ADD COLUMN`` is a cheap metadata-only operation, and
``CREATE INDEX IF NOT EXISTS`` is safe to re-run, so this can be called on every
startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database.connection import Base, engine
from app.database.models import Movie  # noqa: F401  (ensures models are registered)

logger = logging.getLogger(__name__)

# Composite and expression indexes that the ORM column definitions cannot express
# but that the catalogue endpoints depend on.
_EXTRA_INDEXES = [
    ("ix_movies_bayes_desc", "movies", "(bayes_score DESC)"),
    ("ix_movies_trending_desc", "movies", "(trending_score DESC)"),
    ("ix_movies_year_bayes", "movies", "(release_year, bayes_score)"),
    ("ix_movies_poster_bayes", "movies", "(poster_path, bayes_score)"),
    ("ix_ratings_user_movie", "ratings", "(user_id, movie_id)"),
    ("ix_watchlists_user_movie", "watchlists", "(user_id, movie_id)"),
]


def _sqlite_type(column) -> str:
    """Renders a column's type for an ALTER TABLE statement."""
    return column.type.compile(dialect=engine.dialect)


def reconcile_schema(target: Engine | None = None) -> dict[str, list[str]]:
    """Adds any ORM columns and indexes missing from the live database."""
    target = target or engine
    Base.metadata.create_all(bind=target)

    inspector = inspect(target)
    added_columns: list[str] = []
    added_indexes: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue

        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl = f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {_sqlite_type(column)}'
            with target.begin() as connection:
                connection.execute(text(ddl))
            added_columns.append(f"{table.name}.{column.name}")

        # Single-column indexes declared via index=True on the model.
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(table.name)}
        for column in table.columns:
            if not column.index:
                continue
            name = f"ix_{table.name}_{column.name}"
            if name in existing_indexes:
                continue
            with target.begin() as connection:
                connection.execute(
                    text(f'CREATE INDEX IF NOT EXISTS {name} ON {table.name} ("{column.name}")')
                )
            added_indexes.append(name)

    for name, table_name, expression in _EXTRA_INDEXES:
        if table_name not in inspector.get_table_names():
            continue
        with target.begin() as connection:
            connection.execute(
                text(f"CREATE INDEX IF NOT EXISTS {name} ON {table_name} {expression}")
            )
        added_indexes.append(name)

    if added_columns:
        logger.info("Schema: added columns %s", ", ".join(added_columns))
    if added_indexes:
        logger.info("Schema: ensured %d indexes", len(added_indexes))

    return {"columns": added_columns, "indexes": added_indexes}


def normalise_genre_vocabulary(target: Engine | None = None) -> int:
    """Collapses TMDB genre names onto the MovieLens vocabulary in existing rows.

    Titles imported before ``tmdb.normalise_genres`` existed carry TMDB's spelling,
    which splits the catalogue across near-duplicate genres and makes a filter
    return half its films. Idempotent: re-running changes nothing once clean.
    """
    from app.pipeline.tmdb import GENRE_ALIASES

    target = target or engine
    changed = 0

    with target.begin() as connection:
        for tmdb_name, canonical in GENRE_ALIASES.items():
            rows = connection.execute(
                text("SELECT id, genres FROM movies WHERE genres LIKE :pattern"),
                {"pattern": f"%{tmdb_name}%"},
            ).fetchall()

            updates = []
            for movie_id, genres in rows:
                parts = [part.strip() for part in (genres or "").split("|") if part.strip()]
                # Guard against substring collisions, e.g. "Science Fiction" matching
                # a LIKE for a shorter alias.
                if tmdb_name not in parts:
                    continue
                rebuilt: list[str] = []
                for part in parts:
                    replacement = canonical if part == tmdb_name else part
                    if replacement and replacement not in rebuilt:
                        rebuilt.append(replacement)
                updates.append(
                    {"id": movie_id, "genres": "|".join(rebuilt) or "(no genres listed)"}
                )

            if updates:
                connection.execute(
                    text("UPDATE movies SET genres = :genres WHERE id = :id"), updates
                )
                changed += len(updates)
                logger.info(
                    "Genres: %s -> %s on %s titles",
                    tmdb_name, canonical or "(removed)", f"{len(updates):,}",
                )

    return changed


def rebuild_search_index(target: Engine | None = None) -> int:
    """(Re)builds an FTS5 virtual table for title search.

    ``LIKE '%query%'`` cannot use a B-tree index, so the previous search endpoint
    full-scanned 86k rows on every keystroke. FTS5 gives prefix-matched,
    relevance-ranked search in microseconds. The table is content-less
    (``content=''`` is avoided deliberately) and mirrors only what search needs.
    """
    target = target or engine
    with target.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS movies_fts"))
        connection.execute(
            text(
                """
                CREATE VIRTUAL TABLE movies_fts USING fts5(
                    title,
                    director,
                    cast_list,
                    movie_id UNINDEXED,
                    tokenize = "unicode61 remove_diacritics 2"
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO movies_fts (title, director, cast_list, movie_id)
                SELECT title, COALESCE(director, ''), COALESCE(cast_list, ''), id FROM movies
                """
            )
        )
        count = connection.execute(text("SELECT count(*) FROM movies_fts")).scalar_one()

    logger.info("Rebuilt FTS5 search index over %s titles", f"{count:,}")
    return int(count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = reconcile_schema()
    print("Added columns:", result["columns"] or "none")
    print("Indexes ensured:", len(result["indexes"]))
    print("Genre rows normalised:", normalise_genre_vocabulary())
    rebuild_search_index()
