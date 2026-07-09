from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, and_
from typing import List, Optional
from collections import Counter
from app.database.connection import get_db
from app.database.models import Movie
from app.database.schemas import (
    MovieResponse, PaginatedMovieResponse, GenreListResponse, GenreResponse,
    build_pagination_meta
)
from app.models.content_based import ContentBasedRecommender
from app.models.collaborative import CollaborativeRecommender

router = APIRouter(prefix="/movies", tags=["Movies"])

# Shared model instances for similar movie retrieval
content_model = ContentBasedRecommender()
collab_model = CollaborativeRecommender()

# In-memory genre cache (rebuilt on first request or via /genres endpoint)
_genre_cache: Optional[GenreListResponse] = None


def _build_genre_cache(db: Session) -> GenreListResponse:
    """Scans all movies and builds a sorted genre catalog with movie counts.
    
    MovieLens stores genres as pipe-separated strings (e.g., "Action|Adventure|Sci-Fi").
    This function splits them, counts occurrences, and returns a sorted list.
    """
    global _genre_cache
    
    # Fetch all genre strings in a single lightweight query
    genre_strings = db.query(Movie.genres).all()
    
    genre_counter = Counter()
    for (genres_str,) in genre_strings:
        if genres_str and genres_str != "(no genres listed)":
            for genre in genres_str.split("|"):
                genre = genre.strip()
                if genre:
                    genre_counter[genre] += 1
    
    # Sort alphabetically
    genre_list = sorted(
        [GenreResponse(name=name, movie_count=count) for name, count in genre_counter.items()],
        key=lambda g: g.name
    )
    
    _genre_cache = GenreListResponse(
        genres=genre_list,
        total_genres=len(genre_list)
    )
    return _genre_cache


def _apply_genre_filter(query, genre: Optional[str], genres: Optional[str]):
    """Applies genre filtering to a SQLAlchemy query.
    
    Supports two filter modes:
    - Single genre: ?genre=Action
    - Multiple genres (comma-separated, AND logic): ?genres=Action,Sci-Fi
      → Returns movies that contain ALL specified genres
    """
    if genre:
        # Single genre filter — match movies containing this genre
        query = query.filter(Movie.genres.contains(genre))
    
    if genres:
        # Multi-genre filter — match movies containing ALL specified genres
        genre_list = [g.strip() for g in genres.split(",") if g.strip()]
        for g in genre_list:
            query = query.filter(Movie.genres.contains(g))
    
    return query


@router.get("/genres", response_model=GenreListResponse)
def get_genres(
    db: Session = Depends(get_db)
):
    """Returns all available genres in the movie catalog with movie counts.
    
    Response is cached in memory after first call for fast subsequent retrieval.
    Use this endpoint to populate genre filter dropdowns in the frontend.
    """
    global _genre_cache
    if _genre_cache is not None:
        return _genre_cache
    return _build_genre_cache(db)


@router.get("/browse", response_model=PaginatedMovieResponse)
def browse_movies(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("popularity", regex="^(popularity|title|vote_average|release_date)$", description="Sort field"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    genre: Optional[str] = Query(None, description="Filter by a single genre (e.g., 'Action')"),
    genres: Optional[str] = Query(None, description="Filter by multiple genres, comma-separated AND logic (e.g., 'Action,Sci-Fi')"),
    language: Optional[str] = Query(None, description="Filter by original language code (e.g., 'en', 'fr', 'ja')"),
    year: Optional[str] = Query(None, regex=r"^\d{4}$", description="Filter by release year extracted from title (e.g., '1995')"),
    db: Session = Depends(get_db)
):
    """Browse the full movie catalog with pagination, sorting, and filtering.
    
    **Sort options:** popularity, title, vote_average, release_date  
    **Filter options:** genre, genres (multi), language, year  
    
    Examples:
    - Browse Action movies: `?genre=Action`
    - Browse Action + Sci-Fi movies: `?genres=Action,Sci-Fi`
    - Browse French movies: `?language=fr`
    - Browse 1990s movies: `?year=1995`
    - Combine filters: `?genre=Comedy&year=2010&sort_by=vote_average&order=desc`
    """
    # Map sort_by to column
    sort_column_map = {
        "popularity": Movie.popularity_score,
        "title": Movie.title,
        "vote_average": Movie.vote_average,
        "release_date": Movie.release_date,
    }
    sort_column = sort_column_map[sort_by]
    
    if order == "desc":
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()
    
    # Build filtered query
    base_query = db.query(Movie)
    base_query = _apply_genre_filter(base_query, genre, genres)
    
    if language:
        base_query = base_query.filter(Movie.original_language == language.lower())
    
    if year:
        # Filter by year in the title string (e.g., "(1995)")
        base_query = base_query.filter(Movie.title.like(f"%({year})%"))
    
    # Get total count after filters
    total_items = base_query.count()
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Fetch paginated results
    movies = base_query.order_by(sort_column).offset(offset).limit(page_size).all()
    
    return PaginatedMovieResponse(
        items=movies,
        pagination=build_pagination_meta(page, page_size, total_items)
    )


@router.get("/search", response_model=PaginatedMovieResponse)
def search_movies(
    q: str = Query(..., min_length=1, description="Search query string"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    genre: Optional[str] = Query(None, description="Filter results by a single genre"),
    genres: Optional[str] = Query(None, description="Filter results by multiple genres, comma-separated AND logic"),
    db: Session = Depends(get_db)
):
    """Searches movies by title (case-insensitive) with optional genre filtering and pagination.
    
    Examples:
    - Search for "Star": `?q=Star`
    - Search for "Star" in Sci-Fi genre: `?q=Star&genre=Sci-Fi`
    - Search with multi-genre: `?q=Star&genres=Action,Sci-Fi`
    """
    # Build base query
    base_query = db.query(Movie).filter(Movie.title.ilike(f"%{q}%"))
    
    # Apply genre filter
    base_query = _apply_genre_filter(base_query, genre, genres)
    
    # Get total count for this search
    total_items = base_query.count()
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Fetch paginated results, ordered by popularity
    results = base_query.order_by(Movie.popularity_score.desc()).offset(offset).limit(page_size).all()
    
    return PaginatedMovieResponse(
        items=results,
        pagination=build_pagination_meta(page, page_size, total_items)
    )


@router.get("/{movie_id}", response_model=MovieResponse)
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    """Retrieves a single movie by its ID with full metadata."""
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
    return movie

@router.get("/{movie_id}/similar", response_model=List[dict])
def get_similar_movies(
    movie_id: int,
    method: str = Query("content", regex="^(content|collaborative)$", description="Similarity computation method"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Returns top N similar movies using either content-based (8-channel TF-IDF) or collaborative (SVD latent) similarities."""
    # Verify movie exists
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
        
    try:
        if method == "content":
            recs = content_model.recommend_similar_movies(movie_id, top_n=limit, db=db)
        else: # collaborative
            recs = collab_model.recommend_similar_movies(movie_id, top_n=limit, db=db)
            
        return recs
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Recommender model not initialized/trained. Details: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving similar movies: {str(e)}"
        )
