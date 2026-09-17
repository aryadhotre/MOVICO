"""Idempotent schema reconciliation, applied per database.

``Base.metadata.create_all`` only creates missing *tables*; it will not add a
column or an index to a table that already exists. That is why the indexes added
in a previous session never reached ``movico.db``. This module diffs the live
schema against the ORM models and applies the difference, so an existing database
picks up new columns and indexes without being rebuilt.

Since the split there are two targets, and a table belongs to exactly one of
them: ``movies`` to the catalogue, everything else to the user database. Running
every table against every engine would create an empty ``movies`` table in
Postgres that silently shadows the real catalogue, so the routing here is not a
convenience -- it is what keeps the two halves from overlapping.

Both ``ALTER TABLE ... ADD COLUMN`` and ``CREATE INDEX IF NOT EXISTS`` are cheap
and safe to re-run on SQLite and Postgres alike, so this is called on startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database.connection import (
    Base,
    SINGLE_DATABASE,
    catalogue_engine,
    user_engine,
)
from app.database.models import Movie  # noqa: F401  (ensures models are registered)

logger = logging.getLogger(__name__)

#: Tables that live in the catalogue. Everything else in the metadata is user data.
CATALOGUE_TABLES = {"movies"}

# Composite and expression indexes the ORM column definitions cannot express but
# that the endpoints depend on. Each is applied only to the engine that owns its
# table, which _reconcile works out from the table list it was handed.
_EXTRA_INDEXES = [
    ("ix_movies_bayes_desc", "movies", "(bayes_score DESC)"),
    ("ix_movies_trending_desc", "movies", "(trending_score DESC)"),
    ("ix_movies_year_bayes", "movies", "(release_year, bayes_score)"),
    ("ix_movies_poster_bayes", "movies", "(poster_path, bayes_score)"),
    ("ix_ratings_user_movie", "ratings", "(user_id, movie_id)"),
    ("ix_watchlists_user_movie", "watchlists", "(user_id, movie_id)"),
]


def _reconcile(target: Engine, tables) -> dict[str, list[str]]:
    """Adds the ORM columns and indexes missing from one database."""
    tables = list(tables)
    Base.metadata.create_all(bind=target, tables=tables)

    inspector = inspect(target)
    live = set(inspector.get_table_names())
    added_columns: list[str] = []
    added_indexes: list[str] = []

    for table in tables:
        if table.name not in live:
            continue

        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            rendered = column.type.compile(dialect=target.dialect)
            ddl = f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {rendered}'
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

    wanted = {table.name for table in tables}
    for name, table_name, expression in _EXTRA_INDEXES:
        if table_name not in wanted or table_name not in live:
            continue
        with target.begin() as connection:
            connection.execute(
                text(f"CREATE INDEX IF NOT EXISTS {name} ON {table_name} {expression}")
            )
        added_indexes.append(name)

    return {"columns": added_columns, "indexes": added_indexes}


def reconcile_schema(target: Engine | None = None) -> dict[str, list[str]]:
    """Brings the databases up to the ORM definition.

    Passing ``target`` reconciles that one engine with *every* table, which is what
    the tests do against a scratch database and what a single-file deployment
    needs. With no argument it reconciles both halves, each with its own tables.
    """
    everything = Base.metadata.sorted_tables

    if target is not None:
        result = _reconcile(target, everything)
    elif SINGLE_DATABASE:
        result = _reconcile(catalogue_engine, everything)
    else:
        catalogue = [t for t in everything if t.name in CATALOGUE_TABLES]
        users = [t for t in everything if t.name not in CATALOGUE_TABLES]
        result = _reconcile(catalogue_engine, catalogue)
        for key, values in _reconcile(user_engine, users).items():
            result[key] += values

    if result["columns"]:
        logger.info("Schema: added columns %s", ", ".join(result["columns"]))
    if result["indexes"]:
        logger.info("Schema: ensured %d indexes", len(result["indexes"]))

    return result


def normalise_genre_vocabulary(target: Engine | None = None) -> int:
    """Collapses TMDB genre names onto the MovieLens vocabulary in existing rows.

    Titles imported before ``tmdb.normalise_genres`` existed carry TMDB's spelling,
    which splits the catalogue across near-duplicate genres and makes a filter
    return half its films. Idempotent: re-running changes nothing once clean.
    """
    from app.pipeline.tmdb import GENRE_ALIASES

    target = target or catalogue_engine
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
    relevance-ranked search in microseconds.

    The index is **external-content** (``content='movies'``): it stores the
    tokenised terms but not a second copy of the text, reading column values from
    ``movies`` on the rare occasions it needs them. A self-contained index
    duplicated 37 MB of titles and cast lists that already sit two tables away --
    real money when the database ships inside the image.

    The tradeoff is that an external-content index goes stale if ``movies`` is
    written without it being rebuilt. That is acceptable here because the search
    query never reads a column *through* the index: it matches, ranks by BM25 --
    both of which use the index's own storage -- and joins back to ``movies`` by
    rowid for everything it displays. A stale index can therefore miss a
    just-imported film, which the enrichment pipeline fixes by calling this
    function, but it cannot return a wrong row.

    FTS5 is a SQLite feature and the catalogue is always SQLite, so this is never
    asked of Postgres -- but the guard keeps a mis-pointed engine from raising a
    syntax error on startup.
    """
    target = target or catalogue_engine
    if target.dialect.name != "sqlite":
        logger.warning("Search index skipped: %s is not SQLite", target.dialect.name)
        return 0

    with target.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS movies_fts"))
        connection.execute(
            text(
                """
                CREATE VIRTUAL TABLE movies_fts USING fts5(
                    title,
                    director,
                    cast_list,
                    content='movies',
                    content_rowid='id',
                    tokenize = "unicode61 remove_diacritics 2"
                )
                """
            )
        )
        # 'rebuild' populates the index from the content table in one pass; there
        # is no INSERT ... SELECT for an external-content index.
        connection.execute(text("INSERT INTO movies_fts(movies_fts) VALUES('rebuild')"))
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
