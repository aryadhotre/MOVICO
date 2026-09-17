"""ORM models, split across two databases.

``Movie`` lives in the catalogue (local SQLite, shipped in the image). Everything
else lives in the user database (Postgres in production). See
``app.database.connection`` for why.

The consequence visible here: ``movie_id`` on Rating, Watchlist and
RecommendationHistory is a plain indexed integer, not a ForeignKey. A foreign key
cannot reference a table in another database, and declaring one would either fail
at create_all or be silently inert. The route layer verifies the film exists
before writing, which is where that check has to happen anyway to return a 404.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text, UniqueConstraint
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
    tmdb_id = Column(String(20), nullable=True, index=True)
    popularity_score = Column(Float, default=0.0, index=True)
    trending_score = Column(Float, default=0.0, index=True)

    # TMDB enrichment metadata
    poster_path = Column(String(255), nullable=True)
    backdrop_path = Column(String(255), nullable=True)
    overview = Column(Text, nullable=True)
    release_date = Column(String(20), nullable=True)
    director = Column(String(255), nullable=True)
    cast_list = Column(Text, nullable=True)  # Comma-separated top cast names
    # Structured billing: [{"n": name, "c": character, "p": profile_path}].
    # cast_list stays for search indexing and plain-text display; this carries the
    # portrait paths the detail page needs, which names alone cannot provide.
    cast_json = Column(Text, nullable=True)
    runtime = Column(Integer, nullable=True)
    vote_average = Column(Float, nullable=True, index=True)  # TMDB community vote average
    original_language = Column(String(10), nullable=True, index=True)
    tagline = Column(String(500), nullable=True)
    user_tags = Column(Text, nullable=True)  # Aggregated user-generated tags from MovieLens

    # MovieLens rating aggregates. Individual rating rows stay out of the
    # database (33M of them); only these per-title summaries are stored.
    rating_count = Column(Integer, default=0, index=True)
    rating_mean = Column(Float, default=0.0)
    # Shrunk mean (IMDb weighted-rating form) -- the default catalogue ranking.
    bayes_score = Column(Float, default=0.0, index=True)

    # Additional TMDB fields used for ranking, filtering and the detail page.
    vote_count = Column(Integer, default=0)
    tmdb_popularity = Column(Float, default=0.0, index=True)
    release_year = Column(Integer, nullable=True, index=True)
    trailer_key = Column(String(32), nullable=True)  # YouTube key from TMDB /videos
    keywords = Column(Text, nullable=True)  # Comma-separated TMDB keywords
    enriched_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # No relationship to Rating or Watchlist: those tables live in the user
    # database and SQLAlchemy cannot traverse a relationship across engines.

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Plain integer, not a ForeignKey: movies live in the other database.
    movie_id = Column(Integer, nullable=False, index=True)
    rating = Column(Float, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    user = relationship("User", back_populates="ratings")

    # One rating per user per film. submit_rating checks for an existing row
    # first, but two concurrent submissions can both pass that check and insert.
    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_rating_user_movie"),)

class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Plain integer, not a ForeignKey: movies live in the other database.
    movie_id = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="watchlist")

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="uq_watchlist_user_movie"),)

class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_type = Column(String(50), nullable=False)  # e.g., "hybrid", "collaborative", etc.
    movie_ids = Column(JSON, nullable=False)  # List of recommended movie IDs
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="recommendation_histories")
