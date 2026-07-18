import logging
import numpy as np
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

    def _generate_explanations(self, user_id: int, rec_movie_ids: List[int], db: Session, candidate_scores: Dict[int, Dict[str, float]] = None) -> Dict[int, Dict[str, Any]]:
        """Generates content-similarity-based explanations for recommendations.
        
        For each recommended movie, finds the movie that the user rated highly (>= 4.0)
        which is most similar to it in the TF-IDF space.
        """
        explanations = {}
        if not self.content_model.movie_to_idx or self.content_model.tfidf_matrix is None:
            try:
                self.content_model.load()
            except Exception:
                return explanations

        # Get user's high-rated movies
        high_ratings = db.query(Rating).filter(
            Rating.user_id == user_id,
            Rating.rating >= 4.0
        ).all()
        
        if not high_ratings:
            # Fallback to rating >= 3.0 if no 4.0+ ratings
            high_ratings = db.query(Rating).filter(
                Rating.user_id == user_id,
                Rating.rating >= 3.0
            ).all()

        if not high_ratings:
            return explanations

        watched_movie_ids = [r.movie_id for r in high_ratings]
        
        # Filter to those available in tfidf mappings
        valid_watched_ids = [mid for mid in watched_movie_ids if mid in self.content_model.movie_to_idx]
        valid_rec_ids = [mid for mid in rec_movie_ids if mid in self.content_model.movie_to_idx]
        
        if not valid_watched_ids or not valid_rec_ids:
            return explanations

        # Fetch watched and recommended movie objects to compare metadata
        from sklearn.metrics.pairwise import cosine_similarity
        watched_movies_map = {
            m.id: m for m in db.query(Movie).filter(Movie.id.in_([int(x) for x in valid_watched_ids])).all()
        }
        rec_movies_map = {
            m.id: m for m in db.query(Movie).filter(Movie.id.in_([int(x) for x in valid_rec_ids])).all()
        }

        # Build vectors
        watched_indices = [self.content_model.movie_to_idx[mid] for mid in valid_watched_ids]
        rec_indices = [self.content_model.movie_to_idx[mid] for mid in valid_rec_ids]

        # Extract rows from tfidf_matrix
        watched_vecs = self.content_model.tfidf_matrix[watched_indices]
        rec_vecs = self.content_model.tfidf_matrix[rec_indices]

        # Compute similarity matrix
        sim_matrix = cosine_similarity(rec_vecs, watched_vecs)

        # For each recommended movie, find the index of the most similar watched movie
        for i, rec_id in enumerate(valid_rec_ids):
            best_idx = int(np.argmax(sim_matrix[i]))
            best_score = float(sim_matrix[i, best_idx])
            
            if best_score > 0.05:  # Require a minimum similarity threshold to explain
                watched_id = valid_watched_ids[best_idx]
                rec_movie = rec_movies_map.get(rec_id)
                watched_movie = watched_movies_map.get(watched_id)
                
                # Calculate Genre Match (Jaccard Similarity)
                g_rec = set(rec_movie.genres.split('|')) if rec_movie and rec_movie.genres else set()
                g_wat = set(watched_movie.genres.split('|')) if watched_movie and watched_movie.genres else set()
                genre_match_score = len(g_rec.intersection(g_wat)) / len(g_rec.union(g_wat)) if g_rec.union(g_wat) else 0.0
                
                # Calculate Director Match
                director_match_score = 0.0
                if rec_movie and watched_movie and getattr(rec_movie, 'director', None) and getattr(watched_movie, 'director', None):
                    if rec_movie.director and watched_movie.director:
                        director_match_score = 1.0 if rec_movie.director.strip().lower() == watched_movie.director.strip().lower() else 0.0

                # Calculate Cast Match
                cast_rec = set(c.strip().lower() for c in rec_movie.cast_list.split(',')) if rec_movie and rec_movie.cast_list else set()
                cast_wat = set(c.strip().lower() for c in watched_movie.cast_list.split(',')) if watched_movie and watched_movie.cast_list else set()
                cast_match_score = len(cast_rec.intersection(cast_wat)) / len(cast_rec.union(cast_wat)) if cast_rec.union(cast_wat) else 0.0

                # Calculate Tag Match
                tag_rec = set(t.strip().lower() for t in rec_movie.user_tags.split()) if rec_movie and rec_movie.user_tags else set()
                tag_wat = set(t.strip().lower() for t in watched_movie.user_tags.split()) if watched_movie and watched_movie.user_tags else set()
                tag_match_score = len(tag_rec.intersection(tag_wat)) / len(tag_rec.union(tag_wat)) if tag_rec.union(tag_wat) else 0.0

                # Calculate Dynamic collab/content weight contribution
                collab_weight = self.w_collab
                content_weight = self.w_content
                if candidate_scores and rec_id in candidate_scores:
                    scores = candidate_scores[rec_id]
                    collab_contribution = self.w_collab * scores["collab_norm"]
                    content_contribution = self.w_content * scores["content_sim"]
                    total = collab_contribution + content_contribution
                    collab_weight = round(collab_contribution / total, 3) if total > 0 else 0.0
                    content_weight = round(content_contribution / total, 3) if total > 0 else 0.0

                explanations[rec_id] = {
                    "because_watched_id": watched_id,
                    "because_watched_title": watched_movie.title if watched_movie else "a movie you rated",
                    "similarity_score": round(best_score, 3),
                    "reason_type": "content",
                    "genre_match": round(genre_match_score, 3),
                    "director_match": director_match_score,
                    "theme_match": round(best_score, 3),
                    "collab_weight": collab_weight,
                    "content_weight": content_weight,
                    "cast_match": round(cast_match_score, 3),
                    "tag_match": round(tag_match_score, 3)
                }

        return explanations

    def recommend(self, user_id: int, top_n: int = 10, db: Session = None, include_explanations: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """Intelligently integrates SVD collaborative filtering, content-based similarities, and popularity fallbacks."""
        if db is None:
            raise ValueError("Database session (db) is required for HybridRecommender.")

        # 1. Check for Cold Start User
        user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        user_ratings_count = len(user_ratings)
        
        if user_ratings_count < self.cold_start_threshold:
            logger.info(f"User {user_id} has {user_ratings_count} ratings (< threshold {self.cold_start_threshold}). Triggering Cold-Start Popularity fallback.")
            recs = self.popularity_model.recommend(user_id, top_n, db)
            # Attach cold-start explanation to each returned item
            for item in recs:
                item["explanation"] = {
                    "reason_type": "popularity",
                    "message": "Recommended because it's currently popular"
                }
            return recs

        # 2. Try loading SVD and Content models if not already loaded in memory
        try:
            if self.collab_model.P is None:
                self.collab_model.load()
            if self.content_model.tfidf_matrix is None:
                self.content_model.load()
        except FileNotFoundError as e:
            logger.warning(f"Trained model files missing. Falling back to popularity model. Details: {e}")
            recs = self.popularity_model.recommend(user_id, top_n, db)
            for item in recs:
                item["explanation"] = {
                    "reason_type": "popularity",
                    "message": "Recommended because it's currently popular"
                }
            return recs

        # Ensure user exists in collaborative mappings
        if user_id not in self.collab_model.user_to_idx:
            logger.info(f"User {user_id} not found in collaborative model mappings. Falling back to popularity model.")
            recs = self.popularity_model.recommend(user_id, top_n, db)
            for item in recs:
                item["explanation"] = {
                    "reason_type": "popularity",
                    "message": "Recommended because it's currently popular"
                }
            return recs

        # 3. Retrieve User's Watched Movies
        watched_movie_ids = {r.movie_id for r in user_ratings}

        # 4. Generate Content-based Similarities
        content_recs = self.content_model.recommend(user_id, top_n=100, db=db)
        content_scores = {rec["movie_id"]: rec["score"] for rec in content_recs}

        # 5. Hybrid Scoring Loop
        hybrid_candidates = []
        candidate_scores = {}
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
            candidate_scores[movie_id] = {
                "collab_norm": collab_norm,
                "content_sim": content_sim
            }

        # Sort candidate movies by hybrid score descending
        hybrid_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = hybrid_candidates[:top_n]

        # 6. Populate explanations if requested
        rec_ids = [item["movie_id"] for item in top_candidates]
        explanations = self._generate_explanations(user_id, rec_ids, db, candidate_scores) if include_explanations else {}

        # 7. Populate final movie metadata
        recommendations = []
        for rank, item in enumerate(top_candidates):
            movie = db.query(Movie).filter(Movie.id == int(item["movie_id"])).first()
            if movie:
                recommendations.append({
                    "movie_id": movie.id,
                    "score": item["score"],
                    "rank": rank + 1,
                    "title": movie.title,
                    "genres": movie.genres,
                    "explanation": explanations.get(movie.id),
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
