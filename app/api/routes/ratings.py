"""Rating and watchlist endpoints.

Three contract bugs from the previous version are fixed here:

* ``POST /api/ratings`` was mounted only at ``/api/ratings/``, so the frontend's
  slashless call took a 307 redirect on every rating submission.
* ``POST /api/ratings/watchlist`` declared ``movie_id: int`` with no body
  annotation, which FastAPI reads as a *query* parameter. The frontend sent JSON,
  so every add-to-watchlist returned 422. It now accepts a JSON body.
* ``DELETE /api/ratings/watchlist/{id}`` was ambiguous about whether ``id`` was the
  watchlist row or the movie; it is documented and handled as the movie id, which
  is what the client has.

Every mutation invalidates the user's cached recommendations, so the next request
reflects the new rating instead of serving a stale list.

Ratings and watchlists live in the user database while films live in the
catalogue, so nothing here can join the two in one statement. Each listing reads
its rows, then hydrates the films by primary key in a second query — an indexed
lookup of at most a page of ids, which costs less than the join it replaces would
have over the network.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.auth_helper import get_current_user
from app.database.connection import get_catalogue, get_db
from app.database.models import Movie, Rating, User, Watchlist
from app.database.schemas import (
    GenreCount,
    MovieCard,
    PaginatedRatedMovies,
    PaginatedWatchlist,
    RatedMovie,
    RatingCreate,
    RatingResponse,
    UserStats,
    WatchlistCreate,
    WatchlistEntry,
    build_pagination_meta,
    split_genres,
)
from app.services.cache import cache

router = APIRouter(prefix="/ratings", tags=["User Actions"])


def _hydrate(catalogue: Session, movie_ids: list[int]) -> dict[int, Movie]:
    """Fetches full film rows for a page of ids, in one query."""
    if not movie_ids:
        return {}
    rows = catalogue.execute(select(Movie).where(Movie.id.in_(set(movie_ids)))).scalars().all()
    return {row.id: row for row in rows}


def _hydrate_columns(catalogue: Session, movie_ids: list[int], columns) -> dict[int, object]:
    """Same, but only the named columns.

    The taste summary touches every film a user has rated, which can be hundreds
    of rows; pulling plot text and cast blobs for all of them to read two fields
    would dominate the request.
    """
    if not movie_ids:
        return {}
    rows = catalogue.execute(select(*columns).where(Movie.id.in_(set(movie_ids)))).all()
    return {row.id: row for row in rows}


@router.post("", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RatingResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def submit_rating(
    payload: RatingCreate,
    db: Session = Depends(get_db),
    catalogue: Session = Depends(get_catalogue),
    current_user: User = Depends(get_current_user),
):
    """Creates or updates the current user's rating for a movie."""
    if catalogue.get(Movie, payload.movie_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    existing = db.execute(
        select(Rating).where(
            Rating.user_id == current_user.id, Rating.movie_id == payload.movie_id
        )
    ).scalar_one_or_none()

    if existing:
        existing.rating = payload.rating
        record = existing
    else:
        record = Rating(
            user_id=current_user.id, movie_id=payload.movie_id, rating=payload.rating
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    cache.invalidate_user(current_user.id)
    return record


@router.post("/batch", response_model=dict, status_code=status.HTTP_201_CREATED)
def submit_ratings_batch(
    ratings: list[RatingCreate] = Body(..., max_length=100),
    db: Session = Depends(get_db),
    catalogue: Session = Depends(get_catalogue),
    current_user: User = Depends(get_current_user),
):
    """Records several ratings at once.

    This backs the onboarding flow, where a new user rates a grid of films in one
    go. Submitting them individually would mean one request and one cache
    invalidation per tile.
    """
    wanted = {item.movie_id for item in ratings}
    existing_movies = set(
        catalogue.execute(select(Movie.id).where(Movie.id.in_(wanted))).scalars().all()
    )

    current = {
        row.movie_id: row
        for row in db.execute(
            select(Rating).where(
                Rating.user_id == current_user.id, Rating.movie_id.in_(wanted)
            )
        ).scalars().all()
    }

    written = 0
    for item in ratings:
        if item.movie_id not in existing_movies:
            continue
        if item.movie_id in current:
            current[item.movie_id].rating = item.rating
        else:
            db.add(
                Rating(
                    user_id=current_user.id, movie_id=item.movie_id, rating=item.rating
                )
            )
        written += 1

    db.commit()
    cache.invalidate_user(current_user.id)
    return {"saved": written, "skipped": len(ratings) - written}


@router.delete("/{movie_id}", status_code=status.HTTP_200_OK)
def delete_rating(
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes the current user's rating for a movie."""
    result = db.execute(
        delete(Rating).where(Rating.user_id == current_user.id, Rating.movie_id == movie_id)
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
    cache.invalidate_user(current_user.id)
    return {"success": True}


@router.get("/history", response_model=PaginatedRatedMovies)
def get_rating_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    catalogue: Session = Depends(get_catalogue),
    current_user: User = Depends(get_current_user),
):
    """The user's ratings, newest first, hydrated with their films."""
    total = db.execute(
        select(func.count(Rating.id)).where(Rating.user_id == current_user.id)
    ).scalar_one()

    rows = db.execute(
        select(Rating.movie_id, Rating.rating, Rating.timestamp)
        .where(Rating.user_id == current_user.id)
        .order_by(Rating.timestamp.desc(), Rating.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    films = _hydrate(catalogue, [row.movie_id for row in rows])

    return PaginatedRatedMovies(
        items=[
            RatedMovie(
                rating=row.rating,
                rated_at=row.timestamp,
                movie=MovieCard.model_validate(films[row.movie_id]),
            )
            for row in rows
            # A rating can outlive its film if the catalogue is rebuilt smaller;
            # skip rather than 500.
            if row.movie_id in films
        ],
        pagination=build_pagination_meta(page, page_size, int(total)),
    )


@router.get("/mine", response_model=dict)
def get_my_ratings_map(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A compact ``{movie_id: rating}`` map.

    The UI needs to show the user's own star rating on every card it renders. Doing
    that from the paginated history would mean fetching every page; this is one
    small response the client can hold and consult locally.
    """
    rows = db.execute(
        select(Rating.movie_id, Rating.rating).where(Rating.user_id == current_user.id)
    ).all()
    return {"ratings": {str(movie_id): value for movie_id, value in rows}}


@router.get("/stats", response_model=UserStats)
def get_rating_stats(
    db: Session = Depends(get_db),
    catalogue: Session = Depends(get_catalogue),
    current_user: User = Depends(get_current_user),
):
    """Taste summary for the profile page."""
    rated = db.execute(
        select(Rating.movie_id, Rating.rating).where(Rating.user_id == current_user.id)
    ).all()

    films = _hydrate_columns(
        catalogue,
        [row.movie_id for row in rated],
        (Movie.id, Movie.genres, Movie.release_year),
    )
    rows = [
        (row.rating, films[row.movie_id].genres, films[row.movie_id].release_year)
        for row in rated
        if row.movie_id in films
    ]

    watchlist_count = db.execute(
        select(func.count(Watchlist.id)).where(Watchlist.user_id == current_user.id)
    ).scalar_one()

    if not rows:
        return UserStats(
            ratings_count=0, watchlist_count=int(watchlist_count),
            average_rating=0.0, top_genres=[], rating_distribution={}, decades={},
        )

    genre_counter: Counter[str] = Counter()
    decade_counter: Counter[str] = Counter()
    distribution: Counter[str] = Counter()
    total = 0.0

    for rating, genres, year in rows:
        total += rating
        distribution[f"{rating:g}"] += 1
        # Only films the user actually liked should shape their taste profile.
        if rating >= 3.5:
            genre_counter.update(split_genres(genres))
        if year:
            decade_counter[f"{int(year) // 10 * 10}s"] += 1

    return UserStats(
        ratings_count=len(rows),
        watchlist_count=int(watchlist_count),
        average_rating=round(total / len(rows), 2),
        top_genres=[
            GenreCount(name=name, movie_count=count)
            for name, count in genre_counter.most_common(8)
        ],
        rating_distribution=dict(sorted(distribution.items(), key=lambda kv: float(kv[0]))),
        decades=dict(sorted(decade_counter.items())),
    )


# ------------------------------------------------------------------- watchlist


@router.post("/watchlist", response_model=WatchlistEntry, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    catalogue: Session = Depends(get_catalogue),
    current_user: User = Depends(get_current_user),
):
    """Adds a movie to the watchlist. Idempotent."""
    movie = catalogue.get(Movie, payload.movie_id)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    existing = db.execute(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id, Watchlist.movie_id == payload.movie_id
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = Watchlist(user_id=current_user.id, movie_id=payload.movie_id)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        cache.invalidate_user(current_user.id)

    return WatchlistEntry(
        added_at=existing.added_at, movie=MovieCard.model_validate(movie)
    )


@router.get("/watchlist", response_model=PaginatedWatchlist)
def get_watchlist(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
    catalogue: Session = Depends(get_catalogue),
    current_user: User = Depends(get_current_user),
):
    """The user's watchlist, newest first."""
    total = db.execute(
        select(func.count(Watchlist.id)).where(Watchlist.user_id == current_user.id)
    ).scalar_one()

    rows = db.execute(
        select(Watchlist.movie_id, Watchlist.added_at)
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc(), Watchlist.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    films = _hydrate(catalogue, [row.movie_id for row in rows])

    return PaginatedWatchlist(
        items=[
            WatchlistEntry(added_at=row.added_at, movie=MovieCard.model_validate(films[row.movie_id]))
            for row in rows
            if row.movie_id in films
        ],
        pagination=build_pagination_meta(page, page_size, int(total)),
    )


@router.get("/watchlist/ids", response_model=dict)
def get_watchlist_ids(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Just the movie ids, so cards can render their saved state without a join."""
    ids = db.execute(
        select(Watchlist.movie_id).where(Watchlist.user_id == current_user.id)
    ).scalars().all()
    return {"movie_ids": [int(value) for value in ids]}


@router.delete("/watchlist/{movie_id}", status_code=status.HTTP_200_OK)
def remove_from_watchlist(
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes a movie from the watchlist by *movie* id."""
    result = db.execute(
        delete(Watchlist).where(
            Watchlist.user_id == current_user.id, Watchlist.movie_id == movie_id
        )
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not in watchlist"
        )
    cache.invalidate_user(current_user.id)
    return {"success": True}
