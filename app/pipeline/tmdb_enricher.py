"""
TMDB Metadata Enrichment Pipeline.

Fetches rich movie metadata (posters, plots, cast, directors, etc.) from The Movie Database (TMDB)
API and stores it locally in the database. This enables the frontend to render complete movie cards
without making any external API calls.

TMDB API docs: https://developer.themoviedb.org/docs
Free API key: https://www.themoviedb.org/settings/api
"""

import time
import logging
import requests
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.database.models import Movie

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# TMDB free tier allows 40 requests/second. We stay conservatively under that.
RATE_LIMIT_DELAY = 0.06  # ~16 requests/second (safe margin)
BATCH_COMMIT_SIZE = 100


def enrich_movies_from_tmdb(db: Session, limit: int = None):
    """
    Fetches metadata from TMDB for all movies that have a tmdb_id but haven't been enriched yet.
    
    Args:
        db: SQLAlchemy database session.
        limit: Maximum number of movies to enrich in this run (None = all unenriched movies).
    """
    api_key = settings.TMDB_API_KEY
    if not api_key or api_key == "your-tmdb-api-key-here":
        logger.warning(
            "TMDB_API_KEY not configured. Skipping TMDB metadata enrichment. "
            "Get a free key at https://www.themoviedb.org/settings/api and add it to your .env file."
        )
        return

    # Find movies with a tmdb_id that haven't been enriched yet (no poster_path set)
    query = db.query(Movie).filter(
        Movie.tmdb_id.isnot(None),
        Movie.tmdb_id != "",
        Movie.tmdb_id != "nan",
        Movie.poster_path.is_(None)
    )
    if limit:
        query = query.limit(limit)
    
    unenriched_movies = query.all()
    total = len(unenriched_movies)
    
    if total == 0:
        logger.info("All movies with TMDB IDs are already enriched. Skipping.")
        return

    logger.info(f"Starting TMDB enrichment for {total} movies...")
    enriched_count = 0
    failed_count = 0
    session = requests.Session()

    for idx, movie in enumerate(unenriched_movies):
        try:
            tmdb_id = movie.tmdb_id.strip()
            if not tmdb_id or tmdb_id == "nan":
                continue

            # Fetch movie details with credits appended
            url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
            params = {
                "api_key": api_key,
                "append_to_response": "credits",
                "language": "en-US"
            }
            
            response = session.get(url, params=params, timeout=10)
            
            if response.status_code == 404:
                # Movie not found on TMDB, mark as attempted by setting empty overview
                movie.overview = ""
                movie.poster_path = ""
                failed_count += 1
                continue
            
            if response.status_code == 429:
                # Rate limited - wait and retry
                logger.warning("TMDB rate limit hit. Waiting 10 seconds...")
                time.sleep(10)
                response = session.get(url, params=params, timeout=10)
            
            response.raise_for_status()
            data = response.json()

            # Extract core metadata
            movie.poster_path = data.get("poster_path", "")
            movie.backdrop_path = data.get("backdrop_path", "")
            movie.overview = data.get("overview", "")
            movie.release_date = data.get("release_date", "")
            movie.runtime = data.get("runtime")
            movie.vote_average = data.get("vote_average")
            movie.original_language = data.get("original_language", "")
            movie.tagline = data.get("tagline", "")

            # Extract director from credits.crew
            credits = data.get("credits", {})
            crew = credits.get("crew", [])
            directors = [c["name"] for c in crew if c.get("job") == "Director"]
            movie.director = ", ".join(directors[:2]) if directors else None

            # Extract top 5 cast members
            cast = credits.get("cast", [])
            top_cast = [c["name"] for c in cast[:5]]
            movie.cast_list = ", ".join(top_cast) if top_cast else None

            enriched_count += 1

            # Periodic batch commit
            if enriched_count % BATCH_COMMIT_SIZE == 0:
                db.commit()
                logger.info(f"  Enriched {enriched_count}/{total} movies...")

            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)

        except requests.exceptions.RequestException as e:
            failed_count += 1
            if idx < 5:
                logger.warning(f"Failed to fetch TMDB data for movie {movie.id} (tmdb_id={movie.tmdb_id}): {e}")
        except Exception as e:
            failed_count += 1
            logger.warning(f"Unexpected error enriching movie {movie.id}: {e}")

    # Final commit
    db.commit()
    logger.info(
        f"TMDB enrichment completed: {enriched_count} enriched, "
        f"{failed_count} failed, out of {total} total."
    )
