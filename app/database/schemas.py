from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import List, Optional, Generic, TypeVar
from datetime import datetime
import math

# Generic type for paginated items
T = TypeVar("T")

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# User Schemas
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

# Movie Schemas
class MovieBase(BaseModel):
    id: int
    title: str
    genres: str
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None

class MovieCreate(MovieBase):
    popularity_score: Optional[float] = 0.0
    trending_score: Optional[float] = 0.0

class MovieResponse(MovieBase):
    popularity_score: float
    trending_score: float

    # TMDB enrichment fields
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[str] = None
    director: Optional[str] = None
    cast_list: Optional[str] = None
    runtime: Optional[int] = None
    vote_average: Optional[float] = None
    original_language: Optional[str] = None
    tagline: Optional[str] = None
    user_tags: Optional[str] = None

    # Computed convenience fields for the frontend
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def compute_image_urls(self) -> "MovieResponse":
        """Computes full poster/backdrop URLs from TMDB paths after validation."""
        TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
        if self.poster_path:
            self.poster_url = f"{TMDB_IMAGE_BASE}/w500{self.poster_path}"
        if self.backdrop_path:
            self.backdrop_url = f"{TMDB_IMAGE_BASE}/original{self.backdrop_path}"
        return self

# Pagination Schema
class PaginationMeta(BaseModel):
    """Pagination metadata included in every paginated response."""
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items matching the query")
    total_pages: int = Field(..., description="Total number of pages available")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")

class PaginatedMovieResponse(BaseModel):
    """Paginated response containing a list of movies with navigation metadata."""
    items: List[MovieResponse]
    pagination: PaginationMeta

class PaginatedRatingResponse(BaseModel):
    """Paginated response containing a list of ratings with navigation metadata."""
    items: List["RatingResponse"]
    pagination: PaginationMeta

class PaginatedWatchlistResponse(BaseModel):
    """Paginated response containing a list of watchlist items with navigation metadata."""
    items: List["WatchlistResponse"]
    pagination: PaginationMeta

# Genre Schemas
class GenreResponse(BaseModel):
    """A single genre with its movie count."""
    name: str = Field(..., description="Genre name (e.g., 'Action', 'Comedy')")
    movie_count: int = Field(..., description="Number of movies in this genre")

class GenreListResponse(BaseModel):
    """Complete list of all genres available in the catalog."""
    genres: List[GenreResponse]
    total_genres: int = Field(..., description="Total number of unique genres")

# Rating Schemas
class RatingBase(BaseModel):
    movie_id: int
    rating: float = Field(..., ge=0.5, le=5.0)

class RatingCreate(RatingBase):
    pass

class RatingResponse(RatingBase):
    id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# Watchlist Schemas
class WatchlistCreate(BaseModel):
    movie_id: int

class WatchlistResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    added_at: datetime
    movie: Optional[MovieResponse] = None

    class Config:
        from_attributes = True

# Recommendation Schemas
class RecommendationExplanation(BaseModel):
    because_watched_id: int
    because_watched_title: str
    similarity_score: float
    reason_type: str  # e.g., "content" or "collaborative"

class RecommendedMovieResponse(MovieResponse):
    explanation: Optional[RecommendationExplanation] = None

class RecommendationResponse(BaseModel):
    recommendation_type: str
    movies: List[RecommendedMovieResponse]
    generated_at: datetime
    execution_time_seconds: float

# Rebuild forward references for paginated schemas
PaginatedRatingResponse.model_rebuild()
PaginatedWatchlistResponse.model_rebuild()


# ---- Utility Functions ----

def build_pagination_meta(page: int, page_size: int, total_items: int) -> PaginationMeta:
    """Helper to construct PaginationMeta from query parameters and total count."""
    total_pages = max(1, math.ceil(total_items / page_size))
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )
