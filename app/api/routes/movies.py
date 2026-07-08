from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.connection import get_db
from app.database.models import Movie
from app.database.schemas import MovieResponse
from app.models.content_based import ContentBasedRecommender
from app.models.collaborative import CollaborativeRecommender

router = APIRouter(prefix="/movies", tags=["Movies"])

# Shared model instances for similar movie retrieval
content_model = ContentBasedRecommender()
collab_model = CollaborativeRecommender()

@router.get("/search", response_model=List[MovieResponse])
def search_movies(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Searches the movie database by title matching (case-insensitive)."""
    # Simple search: matching title substring
    results = db.query(Movie).filter(Movie.title.ilike(f"%{q}%")).limit(limit).all()
    return results

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
