"""
TMDB Importer Pipeline for Recent Movies (2024 - 2025+).

Fetches popular recent movies released between 2024 and 2025 from The Movie Database (TMDB) API
and inserts them directly into the local database with full metadata (posters, cast, directors, plots),
making them immediately available for catalog browsing, searching, and recommendation scoring.
"""

import time
import logging
import requests
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.database.models import Movie

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
RATE_LIMIT_DELAY = 0.06  # Conservative delay for TMDB rate limits

# TMDB Genre ID to Name Mapping
TMDB_GENRE_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western"
}


def import_recent_movies_from_tmdb(db: Session, max_pages: int = 5, start_year: int = 2024, end_year: int = 2025):
    """
    Imports popular movies released between start_year and end_year directly from TMDB Discover API.

    Args:
        db: SQLAlchemy database session.
        max_pages: Number of TMDB discover pages to fetch (20 movies per page).
        start_year: Start release year (e.g., 2024).
        end_year: End release year (e.g., 2025).
    """
    api_key = settings.TMDB_API_KEY
    if not api_key or api_key == "your-tmdb-api-key-here":
        logger.warning(
            "TMDB_API_KEY not configured. Cannot import recent movies from TMDB. "
            "Please set TMDB_API_KEY in your .env file."
        )
        return {"status": "error", "imported_count": 0, "message": "TMDB_API_KEY not configured"}

    # Find the current max movie ID to assign new auto-incremented integer IDs safely
    max_id = db.query(func.max(Movie.id)).scalar() or 0
    next_id = max_id + 1

    session = requests.Session()
    imported_count = 0
    skipped_count = 0

    logger.info(f"Starting TMDB import for movies released between {start_year} and {end_year}...")

    for page in range(1, max_pages + 1):
        url = f"{TMDB_BASE_URL}/discover/movie"
        params = {
            "api_key": api_key,
            "primary_release_date.gte": f"{start_year}-01-01",
            "primary_release_date.lte": f"{end_year}-12-31",
            "sort_by": "popularity.desc",
            "language": "en-US",
            "page": page
        }

        try:
            resp = session.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"TMDB discover page {page} returned status {resp.status_code}")
                break

            data = resp.json()
            results = data.get("results", [])

            for item in results:
                tmdb_id = str(item.get("id"))
                if not tmdb_id:
                    continue

                # Check if movie with this tmdb_id already exists in local DB
                existing = db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
                if existing:
                    skipped_count += 1
                    continue

                # Fetch detailed metadata (credits for director & cast)
                details_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
                details_params = {
                    "api_key": api_key,
                    "append_to_response": "credits",
                    "language": "en-US"
                }
                
                details_resp = session.get(details_url, params=details_params, timeout=10)
                if details_resp.status_code == 200:
                    d_data = details_resp.json()
                else:
                    d_data = item

                # Map TMDB genre IDs to pipe-separated genre string
                genre_ids = d_data.get("genre_ids") or [g.get("id") for g in d_data.get("genres", [])]
                genre_names = [TMDB_GENRE_MAP[gid] for gid in genre_ids if gid in TMDB_GENRE_MAP]
                genres_str = "|".join(genre_names) if genre_names else "Drama"

                release_date = d_data.get("release_date", "")
                year = release_date[:4] if release_date else str(start_year)
                raw_title = d_data.get("title", "Untitled")
                formatted_title = f"{raw_title} ({year})"

                # Extract Director & Top Cast
                credits = d_data.get("credits", {})
                crew = credits.get("crew", [])
                directors = [c["name"] for c in crew if c.get("job") == "Director"]
                director_str = ", ".join(directors[:2]) if directors else None

                cast = credits.get("cast", [])
                top_cast = [c["name"] for c in cast[:5]]
                cast_list_str = ", ".join(top_cast) if top_cast else None

                # Compute baseline popularity & trending scores
                tmdb_pop = float(d_data.get("popularity", 10.0))
                tmdb_vote = float(d_data.get("vote_average", 7.0))
                
                # Create new Movie record
                new_movie = Movie(
                    id=next_id,
                    title=formatted_title,
                    genres=genres_str,
                    tmdb_id=tmdb_id,
                    popularity_score=round(tmdb_pop, 2),
                    trending_score=round(tmdb_pop * (tmdb_vote / 5.0), 2),
                    poster_path=d_data.get("poster_path", ""),
                    backdrop_path=d_data.get("backdrop_path", ""),
                    overview=d_data.get("overview", ""),
                    release_date=release_date,
                    director=director_str,
                    cast_list=cast_list_str,
                    runtime=d_data.get("runtime"),
                    vote_average=tmdb_vote,
                    original_language=d_data.get("original_language", "en"),
                    tagline=d_data.get("tagline", "")
                )

                db.add(new_movie)
                next_id += 1
                imported_count += 1
                time.sleep(RATE_LIMIT_DELAY)

            db.commit()

        except Exception as e:
            logger.error(f"Error importing page {page} from TMDB: {e}")
            break

    logger.info(f"TMDB Import Complete: {imported_count} new 2024-2025 movies added, {skipped_count} skipped.")
    return {
        "status": "success",
        "imported_count": imported_count,
        "skipped_count": skipped_count
    }
