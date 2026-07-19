import numpy as np
from typing import List, Dict, Any, Set
import logging
from sqlalchemy.orm import Session
from app.database.models import Movie, Rating
from app.models.base import BaseRecommender

logger = logging.getLogger(__name__)

class ModelEvaluator:
    def __init__(self, k: int = 10, relevance_threshold: float = 3.5):
        self.k = k
        self.relevance_threshold = relevance_threshold

    def evaluate_regression(self, recommender: BaseRecommender, test_ratings: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculates regression metrics: RMSE and MAE on test ratings."""
        errors = []
        absolute_errors = []
        
        for record in test_ratings:
            user_id = record["user_id"]
            movie_id = record["movie_id"]
            actual = record["rating"]
            
            # Collaborative prediction (or baseline predictions)
            if hasattr(recommender, "predict_rating"):
                pred = recommender.predict_rating(user_id, movie_id)
            elif hasattr(recommender, "collab_model") and hasattr(recommender.collab_model, "predict_rating"):
                pred = recommender.collab_model.predict_rating(user_id, movie_id)
            else:
                pred = 3.0  # Fallback
                
            err = actual - pred
            errors.append(err ** 2)
            absolute_errors.append(abs(err))
            
        rmse = np.sqrt(np.mean(errors)) if errors else 0.0
        mae = np.mean(absolute_errors) if absolute_errors else 0.0
        
        return {"rmse": float(rmse), "mae": float(mae)}

    def evaluate_ranking_and_catalog(
        self, 
        recommender: BaseRecommender, 
        test_ratings_by_user: Dict[int, List[Dict[str, Any]]], 
        db: Session,
        all_movie_ids: Set[int],
        train_popularity: Dict[int, int]  # movieId -> count of ratings in training
    ) -> Dict[str, float]:
        """Computes ranking (Precision@K, Recall@K, MAP, NDCG), Coverage, Diversity, and Novelty."""
        precisions = []
        recalls = []
        average_precisions = []
        ndcgs = []
        
        recommended_items = set()
        list_diversities = []
        list_novelties = []
        
        total_users = len(test_ratings_by_user)
        total_ratings_count = sum(train_popularity.values()) or 1
        
        # Load genres for all movies once to speed up diversity calculations
        movies = db.query(Movie.id, Movie.genres).all()
        movie_genres = {m.id: set(m.genres.split("|")) for m in movies}
        
        for user_id, ratings in test_ratings_by_user.items():
            # Get actual relevant movies for this user (rating >= threshold)
            relevant_movies = {r["movie_id"] for r in ratings if r["rating"] >= self.relevance_threshold}
            if not relevant_movies:
                continue # Skip users with no relevant items in test set
                
            # Get all movies watched by user in DB, and subtract their test movies
            watched_in_db = {r[0] for r in db.query(Rating.movie_id).filter(Rating.user_id == int(user_id)).all()}
            test_movies = {r["movie_id"] for r in ratings}
            exclude_movie_ids = watched_in_db - test_movies

            # Get top K recommendations without explanation or metadata queries to speed up evaluation
            recs = recommender.recommend(user_id, top_n=self.k, db=db, include_explanations=False, exclude_movie_ids=exclude_movie_ids, include_metadata=False)
            rec_ids = [r["movie_id"] for r in recs]
            
            # Update overall catalog coverage set
            recommended_items.update(rec_ids)
            
            # Calculate Precision and Recall
            hits = [r_id for r_id in rec_ids if r_id in relevant_movies]
            precision = len(hits) / self.k
            recall = len(hits) / len(relevant_movies)
            
            precisions.append(precision)
            recalls.append(recall)
            
            # Calculate Average Precision (AP) for MAP
            ap = 0.0
            hit_count = 0
            for rank, r_id in enumerate(rec_ids):
                if r_id in relevant_movies:
                    hit_count += 1
                    ap += hit_count / (rank + 1)
            if relevant_movies:
                average_precisions.append(ap / min(self.k, len(relevant_movies)))
                
            # Calculate NDCG@K
            dcg = 0.0
            idcg = 0.0
            # DCG calculation
            for rank, r_id in enumerate(rec_ids):
                if r_id in relevant_movies:
                    dcg += 1.0 / np.log2(rank + 2)
            # Ideal DCG calculation
            for rank in range(min(self.k, len(relevant_movies))):
                idcg += 1.0 / np.log2(rank + 2)
            
            ndcgs.append(dcg / idcg if idcg > 0.0 else 0.0)
            
            # Calculate Intralist Diversity (based on genre Jaccard distance)
            jaccard_distances = []
            for i in range(len(rec_ids)):
                for j in range(i + 1, len(rec_ids)):
                    g1 = movie_genres.get(rec_ids[i], set())
                    g2 = movie_genres.get(rec_ids[j], set())
                    union = g1.union(g2)
                    intersection = g1.intersection(g2)
                    jaccard_sim = len(intersection) / len(union) if union else 0.0
                    jaccard_distances.append(1.0 - jaccard_sim)
            if jaccard_distances:
                list_diversities.append(np.mean(jaccard_distances))
                
            # Calculate Novelty (average self-information of items)
            user_novelty = []
            for r_id in rec_ids:
                count = train_popularity.get(r_id, 0)
                # Popularity probability: add 1 smoothing to prevent log(0)
                prob = (count + 1) / (total_ratings_count + len(all_movie_ids))
                user_novelty.append(-np.log2(prob))
            if user_novelty:
                list_novelties.append(np.mean(user_novelty))

        coverage = len(recommended_items) / len(all_movie_ids) if all_movie_ids else 0.0
        
        return {
            f"precision_at_{self.k}": float(np.mean(precisions)) if precisions else 0.0,
            f"recall_at_{self.k}": float(np.mean(recalls)) if recalls else 0.0,
            "map": float(np.mean(average_precisions)) if average_precisions else 0.0,
            f"ndcg_at_{self.k}": float(np.mean(ndcgs)) if ndcgs else 0.0,
            "catalog_coverage": float(coverage),
            "intralist_diversity": float(np.mean(list_diversities)) if list_diversities else 0.0,
            "novelty": float(np.mean(list_novelties)) if list_novelties else 0.0
        }
