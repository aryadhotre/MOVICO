"""Catalogue endpoints.

Performance notes, since this is the hot path for every page:

* **Column-selective reads.** Card grids select only the eight columns a poster
  tile draws. Selecting whole ``Movie`` rows pulled plot summaries, cast lists and
  tag blobs for every tile, which dominated both query time and response size.
* **Cached counts.** ``COUNT(*)`` over a filtered catalogue cannot use a covering
  index and was re-run on every page change. Totals are cached per filter
  combination, which is safe because the catalogue only changes when a pipeline
  runs.
* **FTS5 search.** ``title LIKE '%q%'`` cannot use an index and full-scanned 86k
  rows per keystroke. The virtual table answers prefix queries in microseconds.
* **One request per page, not per row.** ``/home`` returns every carousel in a
  single response.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database.connection import get_catalogue
from app.database.models import Movie
from app.database.schemas import (
    GenreCount,
    GenreListResponse,
    HomeFeed,
    MovieCard,
    MovieDetail,
    MovieRow,
    PaginatedMovies,
    build_pagination_meta,
    split_genres,
    split_list,
    split_title,
)
from app.services.cache import cache
from app.services.recommender import recommender

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/movies", tags=["Movies"])

# Exactly the columns a poster tile renders.
CARD_COLUMNS = (
    Movie.id, Movie.title, Movie.release_year, Movie.genres, Movie.poster_path,
    Movie.backdrop_path, Movie.vote_average, Movie.bayes_score, Movie.runtime,
    Movie.rating_count,
)

SORT_COLUMNS = {
    "popularity": Movie.popularity_score,
    "trending": Movie.trending_score,
    "rating": Movie.bayes_score,
    "vote_average": Movie.vote_average,
    "title": Movie.title,
    "release_date": Movie.release_year,
    "year": Movie.release_year,
    "votes": Movie.rating_count,
}

# FTS5 treats these as operators; a user typing them means them literally.
_FTS_SPECIALS = re.compile(r'["*():^\-]')

BROWSE_CACHE_TTL = 300.0
HOME_CACHE_TTL = 300.0


def row_to_card(row: Any) -> dict:
    """Builds a card payload from a column tuple."""
    title, year_from_title = split_title(row.title)
    return {
        "id": row.id,
        "title": title,
        "year": row.release_year or year_from_title,
        "genres": split_genres(row.genres),
        "poster_path": row.poster_path,
        "backdrop_path": row.backdrop_path,
        "vote_average": row.vote_average,
        "bayes_score": row.bayes_score,
        "runtime": row.runtime,
        "rating_count": row.rating_count,
    }


def _apply_filters(
    statement,
    genre: Optional[str] = None,
    genres: Optional[str] = None,
    language: Optional[str] = None,
    year: Optional[int] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    min_rating: Optional[float] = None,
    min_votes: Optional[int] = None,
    require_poster: bool = True,
):
    if require_poster:
        statement = statement.where(Movie.poster_path.isnot(None))
    if min_votes:
        statement = statement.where(Movie.vote_count >= min_votes)
    if genre:
        statement = statement.where(Movie.genres.contains(genre))
    if genres:
        for value in (part.strip() for part in genres.split(",") if part.strip()):
            statement = statement.where(Movie.genres.contains(value))
    if language:
        statement = statement.where(Movie.original_language == language.lower())
    if year:
        statement = statement.where(Movie.release_year == year)
    if year_from:
        statement = statement.where(Movie.release_year >= year_from)
    if year_to:
        statement = statement.where(Movie.release_year <= year_to)
    if min_rating:
        statement = statement.where(Movie.bayes_score >= min_rating)
    return statement


@router.get("/genres", response_model=GenreListResponse)
def get_genres(response: Response, db: Session = Depends(get_catalogue)):
    """Genre catalogue with counts, restricted to displayable titles."""
    response.headers["Cache-Control"] = "public, max-age=3600"

    def build() -> dict:
        rows = db.execute(
            select(Movie.genres).where(Movie.poster_path.isnot(None))
        ).scalars().all()
        counts: dict[str, int] = {}
        for value in rows:
            for genre in split_list(value, "|"):
                if genre != "(no genres listed)":
                    counts[genre] = counts.get(genre, 0) + 1
        ordered = sorted(counts.items(), key=lambda pair: -pair[1])
        return GenreListResponse(
            genres=[GenreCount(name=name, movie_count=count) for name, count in ordered],
            total_genres=len(ordered),
        ).model_dump()

    return GenreListResponse(**cache.get_or_set("genres:v2", build, ttl=3600))


@router.get("/browse", response_model=PaginatedMovies)
def browse_movies(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sort_by: str = Query("popularity"),
    order: str = Query("desc"),
    genre: Optional[str] = Query(None),
    genres: Optional[str] = Query(None, description="Comma-separated, AND logic"),
    language: Optional[str] = Query(None),
    year: Optional[int] = Query(None, ge=1874, le=2100),
    year_from: Optional[int] = Query(None, ge=1874, le=2100),
    year_to: Optional[int] = Query(None, ge=1874, le=2100),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    require_poster: bool = Query(True, description="Hide titles with no artwork"),
    db: Session = Depends(get_catalogue),
):
    """Paginated catalogue browse with filtering and sorting."""
    response.headers["Cache-Control"] = "public, max-age=120"

    column = SORT_COLUMNS.get(sort_by, Movie.popularity_score)
    direction = column.asc() if str(order).lower() == "asc" else column.desc()

    filters = dict(
        genre=genre, genres=genres, language=language, year=year,
        year_from=year_from, year_to=year_to, min_rating=min_rating,
        min_votes=None, require_poster=require_poster,
    )

    count_key = "browse:count:" + ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
    total = cache.get(count_key)
    if total is None:
        total = db.execute(
            _apply_filters(select(func.count(Movie.id)), **filters)
        ).scalar_one()
        cache.set(count_key, total, ttl=BROWSE_CACHE_TTL)

    statement = _apply_filters(select(*CARD_COLUMNS), **filters)
    # A stable tiebreaker keeps pagination from repeating or skipping rows when
    # many titles share a sort value.
    rows = db.execute(
        statement.order_by(direction, Movie.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedMovies(
        items=[MovieCard(**row_to_card(row)) for row in rows],
        pagination=build_pagination_meta(page, page_size, int(total)),
    )


@router.get("/trending", response_model=PaginatedMovies)
def get_trending(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    genre: Optional[str] = Query(None),
    db: Session = Depends(get_catalogue),
):
    """Titles with the strongest current momentum."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return browse_movies(
        response=response, page=page, page_size=page_size, sort_by="trending",
        order="desc", genre=genre, genres=None, language=None, year=None,
        year_from=None, year_to=None, min_rating=None, require_poster=True, db=db,
    )


@router.get("/search", response_model=PaginatedMovies)
def search_movies(
    response: Response,
    q: str = Query(..., min_length=1, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    genre: Optional[str] = Query(None),
    db: Session = Depends(get_catalogue),
):
    """Full-text title/cast/director search via FTS5.

    Ranking blends BM25 with catalogue popularity. Pure BM25 answers "nolan" with
    documentaries that have Nolan in the *title*, because a title hit outweighs a
    director hit no matter how obscure the film. Subtracting a popularity term
    (BM25 is negative, better matches more so) surfaces Inception and Memento
    instead, which is what someone typing a director's name is asking for.

    Falls back to a LIKE scan if the FTS table has not been built, so search keeps
    working on a database that has not run the migration yet.
    """
    response.headers["Cache-Control"] = "public, max-age=60"

    cleaned = _FTS_SPECIALS.sub(" ", q).strip()
    if not cleaned:
        return PaginatedMovies(items=[], pagination=build_pagination_meta(page, page_size, 0))

    # Prefix-match the final token so results appear while the user is still typing.
    # The asterisk must sit outside the quotes -- inside, FTS5 reads it as a literal
    # character and "incep*" matches nothing.
    tokens = [token for token in cleaned.split() if token]
    expression = " ".join([f'"{token}"' for token in tokens[:-1]] + [f'"{tokens[-1]}"*'])

    offset = (page - 1) * page_size
    try:
        matches = db.execute(
            text(
                """
                SELECT f.rowid
                FROM movies_fts f
                JOIN movies m ON m.id = f.rowid
                WHERE movies_fts MATCH :expression
                  AND m.poster_path IS NOT NULL
                ORDER BY
                    bm25(movies_fts, 10.0, 3.0, 1.5) - (m.popularity_score / 8.0) ASC,
                    m.popularity_score DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"expression": expression, "limit": page_size + 1, "offset": offset},
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001 - FTS table absent or malformed query
        logger.warning("FTS search unavailable (%s); falling back to LIKE", exc)
        statement = (
            select(*CARD_COLUMNS)
            .where(Movie.title.ilike(f"%{cleaned}%"), Movie.poster_path.isnot(None))
            .order_by(Movie.popularity_score.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = db.execute(statement).all()
        return PaginatedMovies(
            items=[MovieCard(**row_to_card(row)) for row in rows],
            pagination=build_pagination_meta(page, page_size, offset + len(rows)),
        )

    has_more = len(matches) > page_size
    matches = matches[:page_size]
    if not matches:
        return PaginatedMovies(items=[], pagination=build_pagination_meta(page, page_size, offset))

    if genre:
        rows = db.execute(
            select(*CARD_COLUMNS).where(
                Movie.id.in_(matches), Movie.genres.contains(genre)
            )
        ).all()
    else:
        rows = db.execute(select(*CARD_COLUMNS).where(Movie.id.in_(matches))).all()

    # Preserve BM25 ordering, which the IN query does not guarantee.
    by_id = {row.id: row for row in rows}
    ordered = [by_id[mid] for mid in matches if mid in by_id]

    # Exact total would need a full FTS scan; the page-ahead probe is enough to
    # drive "next page" without paying for it.
    total = offset + len(ordered) + (1 if has_more else 0)
    return PaginatedMovies(
        items=[MovieCard(**row_to_card(row)) for row in ordered],
        pagination=build_pagination_meta(page, page_size, total),
    )


@router.get("/home", response_model=HomeFeed)
def get_home_feed(response: Response, db: Session = Depends(get_catalogue)):
    """Every home-page carousel in one response.

    Identical for all visitors, so it is cached process-wide and served with a
    public cache header. Personalised rows come from ``/api/recommendations``.
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    started = time.perf_counter()

    cached = cache.get("home:v2")
    if cached is not None:
        feed = HomeFeed(**cached)
        feed.execution_ms = round((time.perf_counter() - started) * 1000, 2)
        return feed

    current_year = datetime.now(timezone.utc).year

    def fetch(limit: int = 20, **filters) -> list[MovieCard]:
        order = filters.pop("order_by", Movie.popularity_score.desc())
        statement = _apply_filters(select(*CARD_COLUMNS), **filters)
        rows = db.execute(statement.order_by(order).limit(limit)).all()
        return [MovieCard(**row_to_card(row)) for row in rows]

    hero = db.execute(
        select(*CARD_COLUMNS)
        .where(
            Movie.backdrop_path.isnot(None),
            Movie.poster_path.isnot(None),
            Movie.bayes_score >= 3.4,
            Movie.release_year >= current_year - 2,
        )
        .order_by(Movie.trending_score.desc())
        .limit(6)
    ).all()

    rows: list[MovieRow] = [
        MovieRow(
            key="trending",
            title="Trending this week",
            subtitle="What the world is watching right now",
            # The vote floor keeps this row to titles with a real audience. Without
            # it, upcoming releases with a few hundred votes outrank everything,
            # and "trending" becomes indistinguishable from "not out yet".
            items=fetch(min_votes=800, order_by=Movie.trending_score.desc()),
        ),
        MovieRow(
            key="new_releases",
            title=f"Best of {current_year - 1}-{current_year}",
            subtitle="Recent releases that landed well",
            # Ordered by quality rather than momentum. Ordering recent films by
            # trending reproduces the row above exactly, since the same handful of
            # current blockbusters top both.
            items=fetch(
                year_from=current_year - 1, min_rating=3.5, min_votes=400,
                order_by=Movie.bayes_score.desc(),
            ),
        ),
        MovieRow(
            key="acclaimed",
            title="Critically acclaimed",
            subtitle="The highest-rated films in the catalogue",
            items=fetch(min_rating=4.0, order_by=Movie.popularity_score.desc()),
        ),
        MovieRow(
            key="modern_classics",
            title="Modern classics",
            subtitle="The best of the last decade",
            items=fetch(
                year_from=current_year - 11, year_to=current_year - 1, min_rating=3.9,
                order_by=Movie.popularity_score.desc(),
            ),
        ),
        MovieRow(
            key="hidden_gems",
            title="Hidden gems",
            subtitle="Superb films that slipped past the crowds",
            items=_hidden_gems(db),
        ),
    ]

    for genre in ("Sci-Fi", "Thriller", "Animation", "Documentary"):
        items = fetch(genre=genre, min_rating=3.6, order_by=Movie.popularity_score.desc())
        if len(items) >= 8:
            rows.append(
                MovieRow(key=f"genre_{genre.lower().replace(' ', '_')}",
                         title=f"Essential {genre}", items=items)
            )

    feed = HomeFeed(
        hero=[MovieCard(**row_to_card(row)) for row in hero],
        rows=[row for row in rows if row.items],
        generated_at=datetime.now(timezone.utc),
        execution_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    cache.set("home:v2", feed.model_dump(mode="json"), ttl=HOME_CACHE_TTL)
    return feed


def _hidden_gems(db: Session, limit: int = 20) -> list[MovieCard]:
    """Well-loved titles with modest audiences.

    The band on ``rating_count`` is what makes this a discovery row rather than a
    second popularity list: high enough that the score is trustworthy, low enough
    that most people have not seen it.
    """
    rows = db.execute(
        select(*CARD_COLUMNS)
        .where(
            Movie.poster_path.isnot(None),
            Movie.bayes_score >= 3.85,
            Movie.rating_count.between(300, 6000),
        )
        .order_by(Movie.bayes_score.desc())
        .limit(limit)
    ).all()
    return [MovieCard(**row_to_card(row)) for row in rows]


@router.get("/{movie_id}", response_model=MovieDetail)
def get_movie(movie_id: int, response: Response, db: Session = Depends(get_catalogue)):
    """Full record for one title."""
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    response.headers["Cache-Control"] = "public, max-age=600"
    return MovieDetail.model_validate(movie)


@router.get("/{movie_id}/similar", response_model=list[MovieCard])
async def get_similar_movies(
    movie_id: int,
    response: Response,
    limit: int = Query(12, ge=1, le=40),
    db: Session = Depends(get_catalogue),
):
    """Similar titles, blending collaborative neighbourhood and content signal."""
    if db.get(Movie, movie_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    response.headers["Cache-Control"] = "public, max-age=600"
    try:
        return await recommender.similar(db, movie_id, limit)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
