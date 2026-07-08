import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.base import BaseRecommender
from app.database.models import Movie, Rating
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)

class PopularityRecommender(BaseRecommender):
    def __init__(self):
        pass

    def fit(self, db: Session):
        """No training needed for popularity baseline; query directly from metadata."""
        pass

    def recommend(self, user_id: int, top_n: int = 10, db: Session = None, **kwargs) -> List[Dict[str, Any]]:
        """Recommends movies based on overall popularity score, filtering out watched movies if user_id is provided."""
        if db is None:
            raise ValueError("Database session (db) is required for PopularityRecommender inference.")
        
        # Identify movies already rated by the user
        watched_movie_ids = []
        if user_id > 0:
            watched_movie_ids = [
                r.movie_id for r in db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
            ]
            
        # Retrieve movies with highest popularity scores
        query = db.query(Movie)
        if watched_movie_ids:
            query = query.filter(Movie.id.notin_(watched_movie_ids))
            
        top_movies = query.order_by(Movie.popularity_score.desc()).limit(top_n).all()
        
        recommendations = []
        for rank, movie in enumerate(top_movies):
            recommendations.append({
                "movie_id": movie.id,
                "score": movie.popularity_score,
                "rank": rank + 1,
                "title": movie.title,
                "genres": movie.genres
            })
            
        return recommendations

    def save(self, filepath: str):
        pass
        
    def load(self, filepath: str):
        pass
