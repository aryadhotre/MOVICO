import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.base import BaseRecommender
from app.models.collaborative import CollaborativeRecommender
from app.models.content_based import ContentBasedRecommender
from app.models.popularity import PopularityRecommender
from app.database.models import Movie, Rating
from app.config.settings import settings

logger = logging.getLogger(__name__)

class HybridRecommender(BaseRecommender):
    def __init__(self, w_collab: float = 0.7, w_content: float = 0.3, cold_start_threshold: int = 5):
        self.w_collab = w_collab
        self.w_content = w_content
        self.cold_start_threshold = cold_start_threshold
        
        self.collab_model = CollaborativeRecommender()
        self.content_model = ContentBasedRecommender()
        self.popularity_model = PopularityRecommender()

    def fit(self, *args, **kwargs):
        """Not called directly; SVD and Content models are trained via their respective routines."""
        pass

    def recommend(self, user_id: int, top_n: int = 10, db: Session = None, **kwargs) -> List[Dict[str, Any]]:
        """Intelligently integrates SVD collaborative filtering, content-based similarities, and popularity fallbacks."""
        if db is None:
            raise ValueError("Database session (db) is required for HybridRecommender.")

        # 1. Check for Cold Start User
        user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        user_ratings_count = len(user_ratings)
        
        if user_ratings_count < self.cold_start_threshold:
            logger.info(f"User {user_id} has {user_ratings_count} ratings (< threshold {self.cold_start_threshold}). Triggering Cold-Start Popularity fallback.")
            return self.popularity_model.recommend(user_id, top_n, db)

        # 2. Try loading SVD and Content models if not already loaded in memory
        try:
            if self.collab_model.P is None:
                self.collab_model.load()
            if self.content_model.tfidf_matrix is None:
                self.content_model.load()
        except FileNotFoundError as e:
            logger.warning(f"Trained model files missing. Falling back to popularity model. Details: {e}")
            return self.popularity_model.recommend(user_id, top_n, db)

        # Ensure user exists in collaborative mappings
        if user_id not in self.collab_model.user_to_idx:
            logger.info(f"User {user_id} not found in collaborative model mappings. Falling back to popularity model.")
            return self.popularity_model.recommend(user_id, top_n, db)

        # 3. Retrieve User's Watched Movies
        watched_movie_ids = {r.movie_id for r in user_ratings}

        # 4. Generate Content-based Similarities
        # Get content similarities (returns list of movie info containing 'score')
        content_recs = self.content_model.recommend(user_id, top_n=100, db=db)
        content_scores = {rec["movie_id"]: rec["score"] for rec in content_recs}

        # 5. Hybrid Scoring Loop
        hybrid_candidates = []
        
        # We iterate over all movies in our SVD vocabulary
        for movie_id, i_idx in self.collab_model.movie_to_idx.items():
            if movie_id in watched_movie_ids:
                continue
                
            # Collaborative rating prediction [0.5, 5.0]
            collab_rating = self.collab_model.predict_rating(user_id, movie_id)
            # Normalize to [0, 1] range
            collab_norm = (collab_rating - 0.5) / 4.5
            
            # Content similarity [0, 1]
            content_sim = content_scores.get(movie_id, 0.0)
            
            # Compute blended score
            hybrid_score = self.w_collab * collab_norm + self.w_content * content_sim
            
            hybrid_candidates.append({
                "movie_id": movie_id,
                "score": hybrid_score,
                "collab_rating": collab_rating,
                "content_score": content_sim
            })

        # Sort candidate movies by hybrid score descending
        hybrid_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = hybrid_candidates[:top_n]

        # 6. Populate final movie metadata
        recommendations = []
        for rank, item in enumerate(top_candidates):
            movie = db.query(Movie).filter(Movie.id == item["movie_id"]).first()
            if movie:
                recommendations.append({
                    "movie_id": movie.id,
                    "score": item["score"],
                    "rank": rank + 1,
                    "title": movie.title,
                    "genres": movie.genres,
                    "metadata": {
                        "collab_rating_prediction": round(item["collab_rating"], 2),
                        "content_similarity": round(item["content_score"], 3)
                    }
                })

        return recommendations

    def save(self, filepath: Optional[str] = None):
        """Passes save instructions down to sub-modules."""
        self.collab_model.save(filepath)
        self.content_model.save(filepath)

    def load(self, filepath: Optional[str] = None):
        """Passes load instructions down to sub-modules."""
        self.collab_model.load(filepath)
        self.content_model.load(filepath)
