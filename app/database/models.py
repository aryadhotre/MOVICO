from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ratings = relationship("Rating", back_populates="user", cascade="all, delete-orphan")
    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    recommendation_histories = relationship("RecommendationHistory", back_populates="user", cascade="all, delete-orphan")

class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True) # Direct MovieLens id or standard PK
    title = Column(String(255), index=True, nullable=False)
    genres = Column(String(255), nullable=False)
    imdb_id = Column(String(20), nullable=True)
    tmdb_id = Column(String(20), nullable=True)
    popularity_score = Column(Float, default=0.0)
    trending_score = Column(Float, default=0.0)

    # TMDB enrichment metadata
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    overview = Column(Text, nullable=True)
    release_date = Column(String(20), nullable=True)
    director = Column(String(255), nullable=True)
    cast_list = Column(Text, nullable=True)  # Comma-separated top cast names
    runtime = Column(Integer, nullable=True)
    vote_average = Column(Float, nullable=True)  # TMDB community vote average
    original_language = Column(String(10), nullable=True)
    tagline = Column(String(500), nullable=True)
    user_tags = Column(Text, nullable=True)  # Aggregated user-generated tags from MovieLens

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ratings = relationship("Rating", back_populates="movie", cascade="all, delete-orphan")
    watchlist = relationship("Watchlist", back_populates="movie", cascade="all, delete-orphan")

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="ratings")
    movie = relationship("Movie", back_populates="ratings")

class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watchlist")
    movie = relationship("Movie", back_populates="watchlist")

class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_type = Column(String(50), nullable=False)  # e.g., "hybrid", "collaborative", etc.
    movie_ids = Column(JSON, nullable=False)  # List of recommended movie IDs
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="recommendation_histories")
