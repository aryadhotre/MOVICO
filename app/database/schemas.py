"""API response models.

Two deliberate choices here, both about payload weight:

**Split card and detail shapes.** The old ``MovieResponse`` was used for both grids
and detail pages, so a 40-card page shipped 40 plot summaries, 40 cast lists and 40
tag blobs -- tens of kilobytes of text that nothing rendered. ``MovieCard`` carries
only what a poster tile draws; ``MovieDetail`` adds the rest.

**Image paths, not image URLs.** The server returns the bare TMDB path and the
client composes the size it actually needs. Returning five pre-built URLs per movie
would trade the text bloat for URL bloat, and hard-coding ``w500`` for every
context is what made small cards download poster art four times larger than the
space they occupy.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field, model_validator

T = TypeVar("T")

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
_YEAR_SUFFIX = re.compile(r"\s*\((\d{4})\)\s*$")


def split_title(title: str) -> tuple[str, Optional[int]]:
    """Separates the MovieLens "Title (1995)" convention into its parts."""
    match = _YEAR_SUFFIX.search(title or "")
    if match:
        return _YEAR_SUFFIX.sub("", title).strip(), int(match.group(1))
    return (title or "").strip(), None


def split_list(value: Optional[str], separator: str = ",") -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(separator) if part.strip()]


# --------------------------------------------------------------------- auth


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int = Field(..., description="Token lifetime in seconds")


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Aggregate taste summary shown on the profile page."""

    ratings_count: int
    watchlist_count: int
    average_rating: float
    top_genres: List["GenreCount"] = Field(default_factory=list)
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    decades: dict[str, int] = Field(default_factory=dict)


# -------------------------------------------------------------------- movies


class MovieCard(BaseModel):
    """Minimal shape for grids, carousels and search results."""

    id: int
    title: str
    year: Optional[int] = None
    genres: List[str] = Field(default_factory=list)
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    bayes_score: Optional[float] = None
    runtime: Optional[int] = None
    rating_count: Optional[int] = None

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def _from_orm_row(cls, data: Any) -> Any:
        """Normalises an ORM row: strips the year from the title, splits genres."""
        if isinstance(data, dict):
            return data
        title, year = split_title(getattr(data, "title", "") or "")
        return {
            "id": getattr(data, "id"),
            "title": title,
            "year": getattr(data, "release_year", None) or year,
            "genres": split_list(getattr(data, "genres", None), "|"),
            "poster_path": getattr(data, "poster_path", None),
            "backdrop_path": getattr(data, "backdrop_path", None),
            "vote_average": getattr(data, "vote_average", None),
            "bayes_score": getattr(data, "bayes_score", None),
            "runtime": getattr(data, "runtime", None),
            "rating_count": getattr(data, "rating_count", None),
        }


class MovieDetail(MovieCard):
    """Full record for the detail page."""

    overview: Optional[str] = None
    tagline: Optional[str] = None
    director: Optional[str] = None
    cast: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    trailer_key: Optional[str] = None
    release_date: Optional[str] = None
    original_language: Optional[str] = None
    vote_count: Optional[int] = None
    rating_mean: Optional[float] = None
    popularity_score: Optional[float] = None
    trending_score: Optional[float] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _from_orm_row(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        title, year = split_title(getattr(data, "title", "") or "")
        return {
            "id": getattr(data, "id"),
            "title": title,
            "year": getattr(data, "release_year", None) or year,
            "genres": split_list(getattr(data, "genres", None), "|"),
            "poster_path": getattr(data, "poster_path", None),
            "backdrop_path": getattr(data, "backdrop_path", None),
            "vote_average": getattr(data, "vote_average", None),
            "bayes_score": getattr(data, "bayes_score", None),
            "runtime": getattr(data, "runtime", None),
            "rating_count": getattr(data, "rating_count", None),
            "overview": getattr(data, "overview", None),
            "tagline": getattr(data, "tagline", None),
            "director": getattr(data, "director", None),
            "cast": split_list(getattr(data, "cast_list", None)),
            "keywords": split_list(getattr(data, "keywords", None)),
            "tags": split_list(getattr(data, "user_tags", None), " ")[:12],
            "trailer_key": getattr(data, "trailer_key", None),
            "release_date": getattr(data, "release_date", None),
            "original_language": getattr(data, "original_language", None),
            "vote_count": getattr(data, "vote_count", None),
            "rating_mean": getattr(data, "rating_mean", None),
            "popularity_score": getattr(data, "popularity_score", None),
            "trending_score": getattr(data, "trending_score", None),
            "imdb_id": getattr(data, "imdb_id", None),
            "tmdb_id": getattr(data, "tmdb_id", None),
        }


# ---------------------------------------------------------------- pagination


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedMovies(BaseModel):
    items: List[MovieCard]
    pagination: PaginationMeta


def build_pagination_meta(page: int, page_size: int, total_items: int) -> PaginationMeta:
    total_pages = max(1, math.ceil(total_items / page_size)) if page_size else 1
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


# -------------------------------------------------------------------- genres


class GenreCount(BaseModel):
    name: str
    movie_count: int


class GenreListResponse(BaseModel):
    genres: List[GenreCount]
    total_genres: int


# ---------------------------------------------------------- ratings/watchlist


class RatingCreate(BaseModel):
    movie_id: int
    rating: float = Field(..., ge=0.5, le=5.0)


class RatingResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    rating: float
    timestamp: datetime

    class Config:
        from_attributes = True


class RatedMovie(BaseModel):
    """A rating joined to its movie, for the ratings page."""

    rating: float
    rated_at: datetime
    movie: MovieCard


class PaginatedRatedMovies(BaseModel):
    items: List[RatedMovie]
    pagination: PaginationMeta


class WatchlistCreate(BaseModel):
    movie_id: int


class WatchlistEntry(BaseModel):
    added_at: datetime
    movie: MovieCard


class PaginatedWatchlist(BaseModel):
    items: List[WatchlistEntry]
    pagination: PaginationMeta


# ----------------------------------------------------------- recommendations


class BecauseOf(BaseModel):
    """One profile title that measurably contributed to a recommendation."""

    movie_id: int
    title: str
    weight: float


class Explanation(BaseModel):
    kind: str = Field(..., description="hybrid | cold_start")
    headline: str
    because_of: List[BecauseOf] = Field(default_factory=list)
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Standardised per-model contributions to the blended score",
    )
    shared_genres: List[str] = Field(default_factory=list)


class RecommendedMovie(MovieCard):
    score: float
    rank: int
    explanation: Optional[Explanation] = None


class RecommendationResponse(BaseModel):
    strategy: str
    movies: List[RecommendedMovie]
    generated_at: datetime
    execution_ms: float
    cached: bool = False


class MovieRow(BaseModel):
    """One titled carousel on the home page."""

    key: str
    title: str
    subtitle: Optional[str] = None
    items: List[MovieCard]


class HomeFeed(BaseModel):
    """Every home-page row in a single response.

    The home page previously issued one request per section. Bundling them removes
    a round trip per row and lets the whole page paint in one pass.
    """

    hero: List[MovieCard] = Field(default_factory=list)
    rows: List[MovieRow] = Field(default_factory=list)
    generated_at: datetime
    execution_ms: float


class CatalogueStats(BaseModel):
    total_movies: int
    with_posters: int
    poster_coverage: float
    total_ratings_modelled: int
    catalogue_years: dict[str, int]
    enrichment_pending: int
    engine: dict[str, Any] = Field(default_factory=dict)


UserStats.model_rebuild()
