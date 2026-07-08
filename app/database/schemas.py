from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

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

class MovieResponse(MovieBase):
    popularity_score: float

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

    # Computed convenience fields for the frontend
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Override from_orm to compute full poster/backdrop URLs from TMDB paths."""
        TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
        instance = super().from_orm(obj)
        if instance.poster_path:
            instance.poster_url = f"{TMDB_IMAGE_BASE}/w500{instance.poster_path}"
        if instance.backdrop_path:
            instance.backdrop_url = f"{TMDB_IMAGE_BASE}/original{instance.backdrop_path}"
        return instance

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
class RecommendationResponse(BaseModel):
    recommendation_type: str
    movies: List[MovieResponse]
    generated_at: datetime
    execution_time_seconds: float
