import os
import pickle
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.base import BaseRecommender
from app.config.settings import settings
from app.database.models import Movie, Rating
import logging

logger = logging.getLogger(__name__)

class CollaborativeRecommender(BaseRecommender):
    def __init__(self, k_components: int = 50, lr: float = 0.005, reg: float = 0.02, epochs: int = 20):
        self.k_components = k_components
        self.lr = lr
        self.reg = reg
        self.epochs = epochs
        
        # Latent representations
        self.P = None  # User latent matrix
        self.Q = None  # Item latent matrix
        
        # Biases
        self.global_mean = 0.0
        self.user_biases = None
        self.item_biases = None
        
        # Mappings
        self.user_to_idx = {}
        self.idx_to_user = {}
        self.movie_to_idx = {}
        self.idx_to_movie = {}

    def fit(self, csr_matrix, mappings: Dict[str, Any]):
        """Trains the SVD (Funk SVD) model using Stochastic Gradient Descent (SGD) on known ratings."""
        self.user_to_idx = mappings.get("user_to_idx", {})
        self.idx_to_user = mappings.get("idx_to_user", {})
        self.movie_to_idx = mappings.get("movie_to_idx", {})
        self.idx_to_movie = mappings.get("idx_to_movie", {})

        num_users, num_items = csr_matrix.shape
        logger.info(f"Initializing SVD parameters for {num_users} users and {num_items} items (factors={self.k_components})...")
        
        # Initialize latent matrices with random normal values
        self.P = np.random.normal(scale=1.0 / self.k_components, size=(num_users, self.k_components))
        self.Q = np.random.normal(scale=1.0 / self.k_components, size=(num_items, self.k_components))
        
        # Initialize biases
        self.user_biases = np.zeros(num_users)
        self.item_biases = np.zeros(num_items)
        
        # Extract row, col, data from CSR matrix
        coo = csr_matrix.tocoo()
        rows = coo.row
        cols = coo.col
        ratings = coo.data
        
        self.global_mean = float(np.mean(ratings)) if len(ratings) > 0 else 0.0
        
        logger.info("Starting SGD training...")
        for epoch in range(self.epochs):
            # Shuffle training indices
            indices = np.arange(len(ratings))
            np.random.shuffle(indices)
            
            loss = 0.0
            for idx in indices:
                u = rows[idx]
                i = cols[idx]
                r = ratings[idx]
                
                # Predict rating
                pred = self.global_mean + self.user_biases[u] + self.item_biases[i] + np.dot(self.P[u], self.Q[i])
                err = r - pred
                loss += err ** 2
                
                # Update biases
                self.user_biases[u] += self.lr * (err - self.reg * self.user_biases[u])
                self.item_biases[i] += self.lr * (err - self.reg * self.item_biases[i])
                
                # Update latent factors
                p_temp = self.P[u].copy()
                self.P[u] += self.lr * (err * self.Q[i] - self.reg * self.P[u])
                self.Q[i] += self.lr * (err * p_temp - self.reg * self.Q[i])
                
            rmse = np.sqrt(loss / len(ratings))
            logger.info(f"Epoch {epoch + 1}/{self.epochs} - Training RMSE: {rmse:.4f}")

    def predict_rating(self, user_id: int, movie_id: int) -> float:
        """Predicts a rating for a user and movie, falling back to biases or global mean for unseen entities."""
        u_idx = self.user_to_idx.get(user_id)
        i_idx = self.movie_to_idx.get(movie_id)
        
        # Handle cases where user or movie is unseen (Cold start)
        if u_idx is None and i_idx is None:
            return self.global_mean
        elif u_idx is None:  # Unseen user: return global mean + item bias
            return self.global_mean + self.item_biases[i_idx]
        elif i_idx is None:  # Unseen movie: return global mean + user bias
            return self.global_mean + self.user_biases[u_idx]
            
        # Standard prediction formula
        pred = self.global_mean + self.user_biases[u_idx] + self.item_biases[i_idx] + np.dot(self.P[u_idx], self.Q[i_idx])
        # Clip predicted rating to the valid scale [0.5, 5.0]
        return float(np.clip(pred, 0.5, 5.0))

    def recommend(self, user_id: int, top_n: int = 10, db: Session = None, **kwargs) -> List[Dict[str, Any]]:
        """Recommends movies by predicting user ratings for all unrated movies."""
        if db is None:
            raise ValueError("Database session (db) is required for CollaborativeRecommender.")
            
        if self.P is None:
            self.load()

        u_idx = self.user_to_idx.get(user_id)
        
        # If user is not in training set, fallback to popularity recommender
        if u_idx is None:
            logger.warning(f"User {user_id} not found in collaborative model. Falling back to popularity model.")
            from app.models.popularity import PopularityRecommender
            return PopularityRecommender().recommend(user_id, top_n, db)

        # Get list of movies the user has already rated
        watched_movie_ids = {
            r.movie_id for r in db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
        }

        # Predict ratings for all movies in the vocabulary
        predictions = []
        for movie_id, i_idx in self.movie_to_idx.items():
            if movie_id in watched_movie_ids:
                continue
                
            pred_score = self.predict_rating(user_id, movie_id)
            predictions.append((movie_id, pred_score))
            
        # Sort predictions by score descending
        predictions.sort(key=lambda x: x[1], reverse=True)
        top_predictions = predictions[:top_n]
        
        recommendations = []
        for rank, (movie_id, score) in enumerate(top_predictions):
            movie = db.query(Movie).filter(Movie.id == movie_id).first()
            if movie:
                recommendations.append({
                    "movie_id": movie.id,
                    "score": score,
                    "rank": rank + 1,
                    "title": movie.title,
                    "genres": movie.genres
                })
                
        return recommendations

    def recommend_similar_movies(self, movie_id: int, top_n: int = 10, db: Session = None) -> List[Dict[str, Any]]:
        """Finds similar movies in the SVD latent space using cosine similarity."""
        if self.Q is None:
            self.load()
            
        i_idx = self.movie_to_idx.get(movie_id)
        if i_idx is None:
            logger.error(f"Movie ID {movie_id} not found in collaborative mappings.")
            return []

        # Target item latent vector
        target_vector = self.Q[i_idx]
        
        # Compute cosine similarities in the latent space
        norm_Q = np.linalg.norm(self.Q, axis=1)
        norm_target = np.linalg.norm(target_vector)
        
        # Handle zero-norms
        norm_Q[norm_Q == 0] = 1e-9
        norm_target = norm_target if norm_target > 0 else 1e-9
        
        dot_product = np.dot(self.Q, target_vector)
        similarities = dot_product / (norm_Q * norm_target)
        
        # Sort by similarity descending
        candidate_indices = np.argsort(similarities)[::-1]
        
        recommendations = []
        rank = 1
        for idx in candidate_indices:
            curr_movie_id = self.idx_to_movie[idx]
            if curr_movie_id == movie_id:
                continue
                
            score = float(similarities[idx])
            # Filter NaN or extreme values
            if np.isnan(score) or score <= 0.0:
                continue
                
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
        """Serializes current SVD latent weights and entity mappings to file."""
        models_dir = filepath or settings.MODELS_DIR
        os.makedirs(models_dir, exist_ok=True)
        
        model_state = {
            "k_components": self.k_components,
            "lr": self.lr,
            "reg": self.reg,
            "epochs": self.epochs,
            "P": self.P,
            "Q": self.Q,
            "global_mean": self.global_mean,
            "user_biases": self.user_biases,
            "item_biases": self.item_biases,
            "user_to_idx": self.user_to_idx,
            "idx_to_user": self.idx_to_user,
            "movie_to_idx": self.movie_to_idx,
            "idx_to_movie": self.idx_to_movie
        }
        
        with open(os.path.join(models_dir, "svd_model.pkl"), "wb") as f:
            pickle.dump(model_state, f)
        logger.info("Collaborative model SVD weights saved to disk.")

    def load(self, filepath: Optional[str] = None):
        """Deserializes SVD latent weights and mappings from file."""
        models_dir = filepath or settings.MODELS_DIR
        model_path = os.path.join(models_dir, "svd_model.pkl")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Collaborative SVD model files not found in {models_dir}. Train the model first.")
            
        with open(model_path, "rb") as f:
            state = pickle.load(f)
            
        self.k_components = state["k_components"]
        self.lr = state["lr"]
        self.reg = state["reg"]
        self.epochs = state["epochs"]
        self.P = state["P"]
        self.Q = state["Q"]
        self.global_mean = state["global_mean"]
        self.user_biases = state["user_biases"]
        self.item_biases = state["item_biases"]
        self.user_to_idx = state["user_to_idx"]
        self.idx_to_user = state["idx_to_user"]
        self.movie_to_idx = state["movie_to_idx"]
        self.idx_to_movie = state["idx_to_movie"]
        
        logger.info("Collaborative SVD weights successfully loaded from disk.")
