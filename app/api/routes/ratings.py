from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.connection import get_db
from app.database.models import Rating, Movie, Watchlist
from app.database.schemas import RatingCreate, RatingResponse, WatchlistResponse
from app.api.auth_helper import get_current_user
from app.database.models import User

router = APIRouter(prefix="/ratings", tags=["User Actions"])

@router.post("/", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
def submit_rating(
    rating_data: RatingCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Submits or updates a rating for a specific movie."""
    # Verify movie exists
    movie = db.query(Movie).filter(Movie.id == rating_data.movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
        
    # Check if rating already exists, update if it does
    existing_rating = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.movie_id == rating_data.movie_id
    ).first()
    
    if existing_rating:
        existing_rating.rating = rating_data.rating
        db.commit()
        db.refresh(existing_rating)
        return existing_rating
        
    # Create new rating
    new_rating = Rating(
        user_id=current_user.id,
        movie_id=rating_data.movie_id,
        rating=rating_data.rating
    )
    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)
    return new_rating

@router.get("/history", response_model=List[RatingResponse])
def get_rating_history(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Retrieves all ratings submitted by the current authenticated user."""
    ratings = db.query(Rating).filter(Rating.user_id == current_user.id).order_by(Rating.timestamp.desc()).all()
    return ratings

@router.post("/watchlist", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    movie_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Adds a movie to the authenticated user's watchlist."""
    # Verify movie exists
    movie = db.query(Movie).filter(Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found"
        )
        
    # Check if already in watchlist
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.movie_id == movie_id
    ).first()
    if existing:
        return existing
        
    new_item = Watchlist(user_id=current_user.id, movie_id=movie_id)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item

@router.get("/watchlist", response_model=List[WatchlistResponse])
def get_watchlist(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Retrieves all movies in the current user's watchlist."""
    watchlist_items = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).order_by(Watchlist.added_at.desc()).all()
    return watchlist_items

@router.delete("/watchlist/{movie_id}", status_code=status.HTTP_200_OK)
def remove_from_watchlist(
    movie_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Removes a movie from the user's watchlist."""
    watchlist_item = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.movie_id == movie_id
    ).first()
    
    if not watchlist_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie not found in watchlist"
        )
        
    db.delete(watchlist_item)
    db.commit()
    return {"success": True, "detail": "Movie removed from watchlist"}
