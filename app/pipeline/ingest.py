"""MovieLens catalogue ingestion.

Two deliberate departures from the original pipeline:

1. **Individual rating rows are never written to the database.** The archive holds
   33.8M of them; inserting those through the ORM is what exhausted memory and
   left the previous database with zero ratings. They are only ever needed for
   *training*, which reads them straight from CSV (see ``app.ml.dataset``), so the
   catalogue stores per-title aggregates instead.

2. **Writes go through the sqlite3 driver with ``executemany``.** Seeding 87k
   movies row-by-row through the ORM spends most of its time constructing objects
   that are discarded immediately.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import zipfile
from typing import Optional

import numpy as np
import requests

from app.config.settings import settings

logger = logging.getLogger(__name__)

CATALOGUE_COLUMNS = (
    "id", "title", "genres", "imdb_id", "tmdb_id", "user_tags",
    "release_year", "rating_count", "rating_mean", "bayes_score",
    "popularity_score", "trending_score",
)


def sqlite_path() -> str:
    """Resolves the on-disk path of the **catalogue**.

    Every raw-sqlite3 caller in the codebase -- this pipeline, the enrichment
    pass, and the ranker's catalogue load -- works on films, which live in the
    catalogue. Resolving from ``settings.database_url`` instead would follow
    ``DATABASE_URL`` to the user database: harmless locally, where both are the
    same file, and fatal in production, where it is a Postgres URL and this raises
    on engine load so every recommendation returns 503.
    """
    url = settings.catalogue_url
    if not url.startswith("sqlite"):
        raise RuntimeError("The catalogue must be SQLite for direct sqlite3 access.")
    return url.split("sqlite:///", 1)[1]


def connect() -> sqlite3.Connection:
    """Opens a sqlite3 connection configured for bulk writes."""
    connection = sqlite3.connect(sqlite_path(), timeout=60.0)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA cache_size=-128000")
    connection.execute("PRAGMA temp_store=MEMORY")
    return connection


class DataPipeline:
    """Downloads the MovieLens archive and seeds the movie catalogue."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or settings.DATA_DIR
        self.zip_path = os.path.join(self.data_dir, "movielens.zip")

    # ------------------------------------------------------------------ download

    def _extract_dir(self) -> str:
        for name in ("ml-latest", "ml-25m", "ml-latest-small"):
            candidate = os.path.join(self.data_dir, name)
            if os.path.isdir(candidate):
                return candidate
        for entry in os.listdir(self.data_dir):
            full = os.path.join(self.data_dir, entry)
            if os.path.isdir(full) and entry.startswith("ml-"):
                return full
        return os.path.join(self.data_dir, "ml-latest")

    def download_dataset(self) -> str:
        os.makedirs(self.data_dir, exist_ok=True)
        extract_dir = self._extract_dir()

        if os.path.isdir(extract_dir) and os.path.exists(os.path.join(extract_dir, "ratings.csv")):
            logger.info("MovieLens archive already extracted at %s", extract_dir)
            return extract_dir

        if not os.path.exists(self.zip_path):
            logger.info("Downloading %s ...", settings.MOVIELENS_DATASET_URL)
            with requests.get(settings.MOVIELENS_DATASET_URL, stream=True, timeout=60) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                written = 0
                next_report = 5 * 1024 * 1024
                with open(self.zip_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        handle.write(chunk)
                        written += len(chunk)
                        if written >= next_report:
                            next_report += 25 * 1024 * 1024
                            pct = f"{written / total * 100:.0f}%" if total else "?"
                            logger.info("  downloaded %d MB (%s)", written // (1 << 20), pct)

        logger.info("Extracting archive ...")
        with zipfile.ZipFile(self.zip_path) as archive:
            archive.extractall(self.data_dir)
        return self._extract_dir()

    # ---------------------------------------------------------------- catalogue

    def build_catalogue(self, extract_dir: str) -> "pd.DataFrame":
        """Joins movies, links and tags into catalogue rows with rating aggregates."""
        import pandas as pd

        from app.ml.dataset import compute_movie_stats

        movies = pd.read_csv(os.path.join(extract_dir, "movies.csv"))
        movies["title"] = movies["title"].astype(str).str.strip()

        links_path = os.path.join(extract_dir, "links.csv")
        if os.path.exists(links_path):
            links = pd.read_csv(links_path)
            links["imdb_id"] = "tt" + links["imdbId"].astype("Int64").astype(str).str.zfill(7)
            links["tmdb_id"] = links["tmdbId"].astype("Int64").astype(str)
            links.loc[links["tmdb_id"] == "<NA>", "tmdb_id"] = None
            movies = movies.merge(links[["movieId", "imdb_id", "tmdb_id"]], on="movieId", how="left")
        else:
            movies["imdb_id"] = None
            movies["tmdb_id"] = None

        tags_path = os.path.join(extract_dir, "tags.csv")
        if os.path.exists(tags_path):
            logger.info("Aggregating user tags ...")
            tags = pd.read_csv(tags_path, usecols=["movieId", "tag"])
            tags["tag"] = tags["tag"].astype(str).str.lower().str.strip()
            top_tags = (
                tags.groupby("movieId")["tag"]
                .apply(lambda series: " ".join(series.value_counts().head(20).index))
                .rename("user_tags")
                .reset_index()
            )
            movies = movies.merge(top_tags, on="movieId", how="left")
        else:
            movies["user_tags"] = None

        # Release year from the "Title (1995)" convention MovieLens uses.
        movies["release_year"] = pd.to_numeric(
            movies["title"].str.extract(r"\((\d{4})\)\s*$", expand=False), errors="coerce"
        ).astype("Int64")

        stats = compute_movie_stats(os.path.join(extract_dir, "ratings.csv"))
        movies = movies.merge(stats, on="movieId", how="left")
        for column in ("rating_count", "rating_mean", "bayes_score", "ml_trending"):
            movies[column] = movies[column].fillna(0.0)

        # Popularity blends the shrunk mean with log volume, so a title needs both
        # a good score and an audience to rank highly. Raw mean alone lets a movie
        # with three 5-star ratings outrank The Godfather.
        movies["popularity_score"] = (
            movies["bayes_score"] * np.log1p(movies["rating_count"])
        ).round(4)
        movies["trending_score"] = movies["ml_trending"].round(4)

        logger.info("Prepared %s catalogue rows", f"{len(movies):,}")
        return movies

    def seed_catalogue(self, catalogue: "pd.DataFrame") -> int:
        """Upserts catalogue rows, preserving any TMDB enrichment already present."""
        import pandas as pd

        records = [
            (
                int(row.movieId),
                str(row.title),
                str(row.genres),
                row.imdb_id if isinstance(row.imdb_id, str) else None,
                row.tmdb_id if isinstance(row.tmdb_id, str) and row.tmdb_id != "nan" else None,
                row.user_tags if isinstance(row.user_tags, str) else None,
                int(row.release_year) if not pd.isna(row.release_year) else None,
                int(row.rating_count),
                float(row.rating_mean),
                float(row.bayes_score),
                float(row.popularity_score),
                float(row.trending_score),
            )
            for row in catalogue.itertuples(index=False)
        ]

        placeholders = ", ".join("?" * len(CATALOGUE_COLUMNS))
        updates = ", ".join(
            f"{col}=excluded.{col}" for col in CATALOGUE_COLUMNS if col != "id"
        )
        statement = (
            f"INSERT INTO movies ({', '.join(CATALOGUE_COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}"
        )

        connection = connect()
        try:
            with connection:
                connection.executemany(statement, records)
            logger.info("Seeded %s catalogue rows", f"{len(records):,}")
        finally:
            connection.close()
        return len(records)

    def run_pipeline(self) -> dict[str, int]:
        from app.pipeline.migrate import reconcile_schema, rebuild_search_index

        reconcile_schema()
        extract_dir = self.download_dataset()
        catalogue = self.build_catalogue(extract_dir)
        seeded = self.seed_catalogue(catalogue)
        indexed = rebuild_search_index()
        return {"movies_seeded": seeded, "search_indexed": indexed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(DataPipeline().run_pipeline())
