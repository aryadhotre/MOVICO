"""Async TMDB API client tuned for bulk catalogue work.

The catalogue needs metadata for tens of thousands of titles, so the client is
built around throughput rather than convenience:

* one HTTP/1.1 connection pool kept warm across the whole run, so TLS and TCP
  setup is paid once instead of per title;
* a token-bucket pacer that holds the request rate just under TMDB's documented
  ceiling, because going over it earns 429s that cost far more than they save;
* bounded concurrency plus exponential backoff with ``Retry-After`` support;
* ``append_to_response`` so credits, videos and keywords arrive with the movie
  record instead of costing three extra round trips each.

TMDB's free tier has no daily quota, only a rate limit, which is what makes
enriching the full catalogue viable at no cost.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Iterable, Optional, Sequence, TypeVar

import httpx

logger = logging.getLogger(__name__)

API_ROOT = "https://api.themoviedb.org/3"
IMAGE_ROOT = "https://image.tmdb.org/t/p"

# TMDB documents ~50 requests/second. Holding just under that keeps the run
# inside the limit while leaving headroom for retries.
DEFAULT_RATE = 36.0
DEFAULT_CONCURRENCY = 24

T = TypeVar("T")


class _TokenBucket:
    """Paces requests to at most ``rate`` per second, shared across tasks."""

    def __init__(self, rate: float):
        self.rate = rate
        self._tokens = rate
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(self.rate, self._tokens + (now - self._updated) * self.rate)
            self._updated = now

            if self._tokens < 1.0:
                delay = (1.0 - self._tokens) / self.rate
                await asyncio.sleep(delay)
                self._tokens = 0.0
                self._updated = time.monotonic()
            else:
                self._tokens -= 1.0


class TMDBClient:
    """A bounded-concurrency, rate-paced TMDB reader."""

    def __init__(
        self,
        api_key: str,
        concurrency: int = DEFAULT_CONCURRENCY,
        rate: float = DEFAULT_RATE,
        timeout: float = 20.0,
        max_attempts: int = 4,
    ):
        if not api_key or api_key == "your-tmdb-api-key-here":
            raise ValueError("A TMDB API key is required. Set TMDB_API_KEY in .env.")
        self.api_key = api_key
        self.max_attempts = max_attempts
        self._semaphore = asyncio.Semaphore(concurrency)
        self._bucket = _TokenBucket(rate)
        self._client = httpx.AsyncClient(
            base_url=API_ROOT,
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=concurrency,
                max_keepalive_connections=concurrency,
                keepalive_expiry=60.0,
            ),
            headers={"Accept": "application/json"},
        )
        self.requests_made = 0
        self.errors = 0

    async def __aenter__(self) -> "TMDBClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, **params: Any) -> Optional[dict]:
        """GETs a TMDB path, returning ``None`` for permanent failures.

        A ``None`` return means "do not ask again": either the resource does not
        exist (404) or every retry was exhausted. Callers use that to mark a row
        as attempted so a resumable run does not loop on dead identifiers.
        """
        params = {"api_key": self.api_key, **params}
        backoff = 1.0

        for attempt in range(1, self.max_attempts + 1):
            await self._bucket.acquire()
            async with self._semaphore:
                try:
                    response = await self._client.get(path, params=params)
                    self.requests_made += 1
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt == self.max_attempts:
                        self.errors += 1
                        logger.warning("TMDB %s failed after %d attempts: %s", path, attempt, exc)
                        return None
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

            if response.status_code == 200:
                return response.json()

            if response.status_code == 404:
                return None

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", backoff))
                await asyncio.sleep(min(retry_after, 30.0))
                continue

            if response.status_code >= 500:
                if attempt == self.max_attempts:
                    self.errors += 1
                    return None
                await asyncio.sleep(backoff)
                backoff *= 2
                continue

            # 401/403 are configuration problems; failing loudly beats a silent
            # run that enriches nothing.
            if response.status_code in (401, 403):
                raise RuntimeError(
                    f"TMDB rejected the API key (HTTP {response.status_code}). Check TMDB_API_KEY."
                )

            self.errors += 1
            return None

        return None

    # ------------------------------------------------------------------ endpoints

    async def movie_detail(self, tmdb_id: int | str) -> Optional[dict]:
        """Full movie record including credits, videos and keywords in one call."""
        return await self.get(
            f"/movie/{tmdb_id}",
            append_to_response="credits,videos,keywords",
            language="en-US",
        )

    async def credits(self, tmdb_id: int | str) -> Optional[dict]:
        """Cast and crew only — a far smaller response than the full record."""
        return await self.get(f"/movie/{tmdb_id}/credits")

    async def discover(
        self,
        page: int = 1,
        sort_by: str = "popularity.desc",
        release_date_gte: Optional[str] = None,
        release_date_lte: Optional[str] = None,
        vote_count_gte: Optional[int] = None,
        with_original_language: Optional[str] = None,
    ) -> Optional[dict]:
        """One page of the discover feed (20 results per page, 500 page ceiling)."""
        params: dict[str, Any] = {
            "page": page,
            "sort_by": sort_by,
            "include_adult": "false",
            "include_video": "false",
            "language": "en-US",
        }
        if release_date_gte:
            params["primary_release_date.gte"] = release_date_gte
        if release_date_lte:
            params["primary_release_date.lte"] = release_date_lte
        if vote_count_gte is not None:
            params["vote_count.gte"] = vote_count_gte
        if with_original_language:
            params["with_original_language"] = with_original_language
        return await self.get("/discover/movie", **params)

    async def map_concurrent(
        self,
        items: Sequence[T],
        worker: Callable[[T], Awaitable[Any]],
    ) -> list[Any]:
        """Runs ``worker`` over ``items``, preserving order.

        Concurrency and pacing are already enforced inside ``get``, so this simply
        lets the event loop interleave the whole batch.
        """
        return await asyncio.gather(*(worker(item) for item in items))


# ---------------------------------------------------------------------- parsing


def _pick_trailer(videos: dict | None) -> Optional[str]:
    """Selects the best YouTube key from a TMDB videos payload.

    Preference order: official trailer, any trailer, teaser. Anything else
    (clips, featurettes, bloopers) makes a poor hero autoplay, so it is skipped.
    """
    if not videos:
        return None
    results = [v for v in videos.get("results", []) if v.get("site") == "YouTube" and v.get("key")]
    if not results:
        return None

    def rank(video: dict) -> tuple[int, int]:
        kind = (video.get("type") or "").lower()
        official = bool(video.get("official"))
        if kind == "trailer":
            return (0 if official else 1, 0)
        if kind == "teaser":
            return (2 if official else 3, 0)
        return (4, 0)

    return min(results, key=rank)["key"]


# TMDB and MovieLens name several genres differently. Left unmapped the catalogue
# ends up with two of each -- "Sci-Fi" holding 4,595 MovieLens titles and "Science
# Fiction" holding 528 TMDB ones -- so a genre filter silently returns half the
# films it should. MovieLens is the canonical vocabulary because it covers the
# overwhelming majority of the catalogue.
GENRE_ALIASES = {
    "Science Fiction": "Sci-Fi",
    "Family": "Children",
    "Music": "Musical",
    # Not a genre, and it has no MovieLens counterpart.
    "TV Movie": None,
}


def normalise_genres(names: Iterable[str]) -> list[str]:
    """Maps TMDB genre names onto the MovieLens vocabulary, preserving order."""
    result: list[str] = []
    for name in names:
        mapped = GENRE_ALIASES.get(name, name)
        if mapped and mapped not in result:
            result.append(mapped)
    return result


def parse_movie_detail(payload: dict, max_cast: int = 12, max_keywords: int = 20) -> dict:
    """Flattens a TMDB movie payload into catalogue column values."""
    credits = payload.get("credits") or {}

    director = next(
        (
            member.get("name")
            for member in credits.get("crew", [])
            if member.get("job") == "Director"
        ),
        None,
    )

    cast = [
        member.get("name")
        for member in sorted(
            credits.get("cast", []), key=lambda m: m.get("order", 9_999)
        )[:max_cast]
        if member.get("name")
    ]

    keyword_block = payload.get("keywords") or {}
    keywords = [
        kw.get("name")
        for kw in (keyword_block.get("keywords") or keyword_block.get("results") or [])[:max_keywords]
        if kw.get("name")
    ]

    release_date = payload.get("release_date") or None
    release_year = None
    if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
        release_year = int(release_date[:4])

    genres = "|".join(
        normalise_genres(g["name"] for g in payload.get("genres", []) if g.get("name"))
    )

    return {
        "tmdb_id": str(payload["id"]),
        "imdb_id": payload.get("imdb_id") or None,
        "title": payload.get("title") or payload.get("original_title") or "Untitled",
        "genres": genres or "(no genres listed)",
        "poster_path": payload.get("poster_path") or None,
        "backdrop_path": payload.get("backdrop_path") or None,
        "overview": (payload.get("overview") or "").strip() or None,
        "tagline": (payload.get("tagline") or "").strip() or None,
        "release_date": release_date,
        "release_year": release_year,
        "runtime": payload.get("runtime") or None,
        "vote_average": payload.get("vote_average") or 0.0,
        "vote_count": payload.get("vote_count") or 0,
        "tmdb_popularity": payload.get("popularity") or 0.0,
        "original_language": (payload.get("original_language") or "").lower() or None,
        "director": director,
        "cast_list": ", ".join(cast) or None,
        "keywords": ", ".join(keywords) or None,
        "trailer_key": _pick_trailer(payload.get("videos")),
    }


def image_url(path: Optional[str], size: str = "w500") -> Optional[str]:
    """Builds a TMDB CDN URL for a stored image path."""
    if not path:
        return None
    return f"{IMAGE_ROOT}/{size}{path}"
