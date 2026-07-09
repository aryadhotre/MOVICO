from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from typing import List, Optional
from app.database.connection import get_db
from app.database.models import Movie
from app.database.schemas import MovieResponse, PaginatedMovieResponse, build_pagination_meta
from app.models.content_based import ContentBasedRecommender
from app.models.collaborative import CollaborativeRecommender

router = APIRouter(prefix="/movies", tags=["Movies"])

# Shared model instances for similar movie retrieval
content_model = ContentBasedRecommender()
collab_model = CollaborativeRecommender()


@router.get("/browse", response_model=PaginatedMovieResponse)
def browse_movies(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("popularity", regex="^(popularity|title|vote_average|release_date)$", description="Sort field"),
    order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """Browse the full movie catalog with pagination and sorting.
    
    Sort options:
    - `popularity` (default) — by computed popularity score
    - `title` — alphabetical
    - `vote_average` — by TMDB community rating
    - `release_date` — by release date
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
    
    # Get total count
    total_items = db.query(sql_func.count(Movie.id)).scalar()
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Fetch paginated results
    movies = db.query(Movie).order_by(sort_column).offset(offset).limit(page_size).all()
    
    return PaginatedMovieResponse(
        items=movies,
        pagination=build_pagination_meta(page, page_size, total_items)
    )


@router.get("/search", response_model=PaginatedMovieResponse)
def search_movies(
    q: str = Query(..., min_length=1, description="Search query string"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Searches the movie database by title matching (case-insensitive) with pagination."""
    # Build base query
    base_query = db.query(Movie).filter(Movie.title.ilike(f"%{q}%"))
    
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
    """Retrieves a single movie by its ID."""
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
    """Returns top N similar movies using either content-based (TF-IDF) or collaborative (SVD latent) similarities."""
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
