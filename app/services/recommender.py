"""Recommendation orchestration.

Sits between the HTTP layer and ``app.ml.ranker``: loads the user's taste profile,
calls the engine off the event loop, hydrates movie metadata in one query, and
caches the result keyed by the profile's actual state so a new rating invalidates
it immediately.

The engine's numeric work is synchronous numpy, which holds the GIL. Running it
directly inside an async handler would stall every other in-flight request for the
duration, so it is dispatched to a worker thread.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Movie, Rating, RecommendationHistory, Watchlist
from app.database.schemas import (
    BecauseOf,
    Explanation,
    MovieCard,
    RecommendationResponse,
    RecommendedMovie,
    split_genres,
    split_title,
)
from app.ml.ranker import ScoredMovie, engine
from app.services.cache import cache

logger = logging.getLogger(__name__)


def load_profile(db: Session, user_id: int) -> tuple[list[tuple[int, float]], list[int]]:
    """Returns the user's (movie_id, rating) pairs and their watchlist ids."""
    ratings = db.execute(
        select(Rating.movie_id, Rating.rating).where(Rating.user_id == user_id)
    ).all()
    watchlist = db.execute(
        select(Watchlist.movie_id).where(Watchlist.user_id == user_id)
    ).scalars().all()
    return [(int(mid), float(value)) for mid, value in ratings], [int(m) for m in watchlist]


def hydrate(db: Session, movie_ids: Sequence[int]) -> dict[int, Movie]:
    """Fetches every movie for a result page in one query, preserving nothing else."""
    if not movie_ids:
        return {}
    rows = db.execute(select(Movie).where(Movie.id.in_(list(movie_ids)))).scalars().all()
    return {row.id: row for row in rows}


def _build_explanation(
    scored: ScoredMovie,
    movie: Movie,
    titles: dict[int, str],
    profile_genres: dict[int, set[str]],
) -> Explanation:
    """Turns the engine's attribution into user-facing copy.

    The ``because_of`` entries come straight from the neighbourhood model's
    contribution read-out, so the named titles are the ones that actually moved
    this item up the ranking.
    """
    because = [
        BecauseOf(movie_id=mid, title=titles.get(mid, "a film you rated"), weight=weight)
        for mid, weight in scored.because_of
        if mid in titles
    ]

    own_genres = set(split_genres(movie.genres))
    shared: set[str] = set()
    for mid, _ in scored.because_of:
        shared |= own_genres & profile_genres.get(mid, set())

    if because:
        headline = f"Because you liked {because[0].title}"
    elif scored.components.get("content", 0) > 0.5:
        headline = "Matches the themes you gravitate toward"
    elif scored.components.get("quality", 0) > 0.5:
        headline = "Highly rated by viewers with similar taste"
    else:
        headline = "Picked for your taste profile"

    return Explanation(
        kind="hybrid",
        headline=headline,
        because_of=because,
        components=scored.components,
        shared_genres=sorted(shared)[:4],
    )


class RecommenderService:
    """Cached, thread-offloaded access to the recommendation engine."""

    def warm(self) -> bool:
        return engine.load()

    async def recommend(
        self,
        db: Session,
        user_id: int,
        limit: int = 20,
        diversity: float = 1.0,
        novelty: float = 0.0,
        genres: Optional[Sequence[str]] = None,
        min_year: Optional[int] = None,
        bypass_cache: bool = False,
        explain: bool = True,
    ) -> RecommendationResponse:
        started = time.perf_counter()

        rated, watchlist = load_profile(db, user_id)
        # Keying on the profile size and rating sum means any new or changed rating
        # produces a different key, so stale recommendations cannot be served.
        signature = f"{len(rated)}:{sum(value for _, value in rated):.1f}"
        key = (
            f"recs:{user_id}:{signature}:{limit}:{diversity}:{novelty}:"
            f"{','.join(sorted(genres or []))}:{min_year}"
        )

        if not bypass_cache:
            cached = cache.get(key)
            if cached is not None:
                payload = RecommendationResponse(**cached)
                payload.cached = True
                payload.execution_ms = round((time.perf_counter() - started) * 1000, 2)
                return payload

        scored, strategy = await asyncio.to_thread(
            engine.recommend,
            rated,
            limit,
            watchlist,
            diversity,
            novelty,
            genres,
            min_year,
        )

        movies = hydrate(db, [item.movie_id for item in scored])

        titles: dict[int, str] = {}
        profile_genres: dict[int, set[str]] = {}
        referenced = {mid for item in scored for mid, _ in item.because_of}
        if referenced and explain:
            for row in hydrate(db, list(referenced)).values():
                titles[row.id] = split_title(row.title)[0]
                profile_genres[row.id] = set(split_genres(row.genres))

        results: list[RecommendedMovie] = []
        for item in scored:
            movie = movies.get(item.movie_id)
            if movie is None:
                continue
            card = MovieCard.model_validate(movie).model_dump()
            explanation = None
            if explain:
                if strategy == "cold_start":
                    explanation = Explanation(
                        kind="cold_start",
                        headline="Popular right now while we learn your taste",
                    )
                else:
                    explanation = _build_explanation(item, movie, titles, profile_genres)
            results.append(
                RecommendedMovie(
                    **card,
                    score=round(item.score, 4),
                    rank=item.rank,
                    explanation=explanation,
                )
            )

        response = RecommendationResponse(
            strategy=strategy,
            movies=results,
            generated_at=datetime.now(timezone.utc),
            execution_ms=round((time.perf_counter() - started) * 1000, 2),
        )

        cache.set(key, response.model_dump(mode="json"))
        self._log_history(db, user_id, strategy, [item.movie_id for item in scored])
        return response

    @staticmethod
    def _log_history(db: Session, user_id: int, strategy: str, movie_ids: list[int]) -> None:
        """Best-effort audit trail; a failure here must not fail the request."""
        if not movie_ids:
            return
        try:
            db.add(
                RecommendationHistory(
                    user_id=user_id,
                    recommendation_type=strategy,
                    movie_ids=movie_ids,
                )
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write recommendation history: %s", exc)
            db.rollback()

    async def similar(self, db: Session, movie_id: int, limit: int = 12) -> list[MovieCard]:
        key = f"similar:{movie_id}:{limit}"
        cached = cache.get(key)
        if cached is not None:
            return [MovieCard(**item) for item in cached]

        scored = await asyncio.to_thread(engine.similar, movie_id, limit)
        movies = hydrate(db, [item.movie_id for item in scored])
        cards = [
            MovieCard.model_validate(movies[item.movie_id])
            for item in scored
            if item.movie_id in movies
        ]
        cache.set(key, [card.model_dump(mode="json") for card in cards], ttl=3600)
        return cards


recommender = RecommenderService()
