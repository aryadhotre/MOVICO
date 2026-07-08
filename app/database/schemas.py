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
    created_at: datetime

    class Config:
        from_attributes = True

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
