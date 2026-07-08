import os
import pickle
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.base import BaseRecommender
from app.config.settings import settings
from app.database.models import Movie, Rating
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

class ContentBasedRecommender(BaseRecommender):
    def __init__(self):
        self.tfidf_matrix = None
        self.movie_to_idx = None
        self.idx_to_movie = None
        self.vectorizer = None

    def fit(self, tfidf_matrix, movie_mappings: Dict[str, Dict[int, int]], vectorizer=None):
        """Initializes the recommender with TF-IDF components from the preprocessing step."""
        self.tfidf_matrix = tfidf_matrix
        self.movie_to_idx = movie_mappings.get("movie_to_idx", {})
        self.idx_to_movie = movie_mappings.get("idx_to_movie", {})
        self.vectorizer = vectorizer

    def recommend(self, user_id: int, top_n: int = 10, db: Session = None, **kwargs) -> List[Dict[str, Any]]:
        """Generates recommendations for a user based on their highly rated movies and content similarity."""
        if db is None:
            raise ValueError("Database session (db) is required for ContentBasedRecommender.")
            
        if self.tfidf_matrix is None or not self.movie_to_idx:
            self.load()

        # Get user's ratings
        user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        if not user_ratings:
            logger.warning(f"User {user_id} has no ratings. Returning popularity baseline.")
            from app.models.popularity import PopularityRecommender
            return PopularityRecommender().recommend(user_id, top_n, db)

        # Build user profile from highly rated movies (rating >= 3.5)
        good_ratings = [r for r in user_ratings if r.rating >= 3.5]
        if not good_ratings:
            # Fallback to all ratings if none are >= 3.5
            good_ratings = user_ratings

        user_movie_ids = [r.movie_id for r in good_ratings]
        user_weights = [r.rating for r in good_ratings]

        # Calculate user profile vector (weighted sum of movie TF-IDF vectors)
        profile_vector = np.zeros((1, self.tfidf_matrix.shape[1]))
        valid_movies_count = 0

        for m_id, weight in zip(user_movie_ids, user_weights):
            if m_id in self.movie_to_idx:
                row_idx = self.movie_to_idx[m_id]
                # tfidf_matrix is a sparse matrix; convert row to dense for summation
                profile_vector += self.tfidf_matrix[row_idx].toarray() * weight
                valid_movies_count += 1

        if valid_movies_count == 0:
            logger.warning(f"None of the user's rated movies exist in the index. Returning empty list.")
            return []

        # Calculate cosine similarity of user profile against all movies
        similarities = cosine_similarity(profile_vector, self.tfidf_matrix).flatten()

        # Sort similarities in descending order
        candidate_indices = np.argsort(similarities)[::-1]
        
        # Filter out movies the user has already rated
        rated_movie_ids = {r.movie_id for r in user_ratings}
        
        recommendations = []
        rank = 1
        for idx in candidate_indices:
            movie_id = self.idx_to_movie[idx]
            if movie_id in rated_movie_ids:
                continue
                
            score = float(similarities[idx])
            if score <= 0.0:
                break  # Stop when similarity reaches 0
                
            movie = db.query(Movie).filter(Movie.id == movie_id).first()
            if movie:
                recommendations.append({
                    "movie_id": movie.id,
                    "score": score,
                    "rank": rank,
                    "title": movie.title,
                    "genres": movie.genres
                })
                rank += 1
                if len(recommendations) >= top_n:
                    break

        return recommendations

    def recommend_similar_movies(self, movie_id: int, top_n: int = 10, db: Session = None) -> List[Dict[str, Any]]:
        """Generates a list of movies similar to a target movie using content representation."""
        if self.tfidf_matrix is None or not self.movie_to_idx:
            self.load()
            
        if movie_id not in self.movie_to_idx:
            logger.error(f"Movie ID {movie_id} not found in preprocessed indices.")
            return []

        target_idx = self.movie_to_idx[movie_id]
        target_vector = self.tfidf_matrix[target_idx]
        
        # Compute similarities with all movies
        similarities = cosine_similarity(target_vector, self.tfidf_matrix).flatten()
        
        # Sort indices
        candidate_indices = np.argsort(similarities)[::-1]
        
        recommendations = []
        rank = 1
        for idx in candidate_indices:
            curr_movie_id = self.idx_to_movie[idx]
            if curr_movie_id == movie_id:
                continue # Skip the target movie itself
                
            score = float(similarities[idx])
            if score <= 0.0:
                break
                
            movie = db.query(Movie).filter(Movie.id == curr_movie_id).first() if db else None
            recommendations.append({
                "movie_id": curr_movie_id,
                "score": score,
                "rank": rank,
                "title": movie.title if movie else "Unknown",
                "genres": movie.genres if movie else "Unknown"
            })
            rank += 1
            if len(recommendations) >= top_n:
                break
                
        return recommendations

    def save(self, filepath: Optional[str] = None):
        """Pickle dump of current TF-IDF state."""
        models_dir = filepath or settings.MODELS_DIR
        os.makedirs(models_dir, exist_ok=True)
        
        with open(os.path.join(models_dir, "tfidf_matrix.pkl"), "wb") as f:
            pickle.dump(self.tfidf_matrix, f)
        with open(os.path.join(models_dir, "vectorizer.pkl"), "wb") as f:
            pickle.dump(self.vectorizer, f)
        with open(os.path.join(models_dir, "movie_mappings.pkl"), "wb") as f:
            pickle.dump({"movie_to_idx": self.movie_to_idx, "idx_to_movie": self.idx_to_movie}, f)

    def load(self, filepath: Optional[str] = None):
        """Loads TF-IDF state from disk."""
        models_dir = filepath or settings.MODELS_DIR
        
        tfidf_path = os.path.join(models_dir, "tfidf_matrix.pkl")
        vectorizer_path = os.path.join(models_dir, "vectorizer.pkl")
        mappings_path = os.path.join(models_dir, "movie_mappings.pkl")
        
        if not os.path.exists(tfidf_path) or not os.path.exists(mappings_path):
            raise FileNotFoundError(f"Content-based model files not found in {models_dir}. Train the model first.")

        with open(tfidf_path, "rb") as f:
            self.tfidf_matrix = pickle.load(f)
        with open(vectorizer_path, "rb") as f:
            self.vectorizer = pickle.load(f)
        with open(mappings_path, "rb") as f:
            mappings = pickle.load(f)
            self.movie_to_idx = mappings.get("movie_to_idx", {})
            self.idx_to_movie = mappings.get("idx_to_movie", {})
        
        logger.info("Content-based model TF-IDF matrices loaded from disk.")
