import os
import random
import time
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from scipy.sparse import csr_matrix
from app.config.settings import settings
from app.database.connection import SessionLocal, engine
from app.database.models import Movie, Rating
from app.pipeline.preprocess import MoviePreprocessor
from app.models.collaborative import CollaborativeRecommender
from app.models.content_based import ContentBasedRecommender
from app.models.hybrid import HybridRecommender
from app.models.evaluator import ModelEvaluator
import logging

logger = logging.getLogger(__name__)

def train_and_evaluate_models(db: Session = None) -> dict:
    """Orchestrates model data partitioning, training, validation, evaluation, and serialization."""
    opened_db = False
    if db is None:
        db = SessionLocal()
        opened_db = True

    try:
        start_time = time.time()
        logger.info("Starting model training pipeline...")

        # 1. Fetch ratings and movies from database
        ratings = db.query(Rating).all()
        movies = db.query(Movie).all()

        if not ratings or not movies:
            raise ValueError("Insufficient database records. Please run the data ingestion pipeline first.")

        all_movie_ids = {m.id for m in movies}
        logger.info(f"Loaded {len(ratings)} ratings and {len(movies)} movies from DB.")

        # Convert ratings to a list of dicts for splitting
        ratings_list = [{
            "user_id": r.user_id,
            "movie_id": r.movie_id,
            "rating": r.rating,
            "timestamp": r.timestamp
        } for r in ratings]

        # 2. Train-Test Split (80/20)
        random.seed(42)
        random.shuffle(ratings_list)
        split_idx = int(len(ratings_list) * 0.8)
        train_ratings = ratings_list[:split_idx]
        test_ratings = ratings_list[split_idx:]

        logger.info(f"Split data into {len(train_ratings)} training and {len(test_ratings)} testing samples.")

        # 3. Fit content-based vectors on complete catalog
        logger.info("Fitting content-based TF-IDF features...")
        preprocessor = MoviePreprocessor()
        tfidf_matrix, movie_to_idx = preprocessor.build_content_features(db)

        # Reload mapping configurations saved by the preprocessor
        import pickle
        with open(os.path.join(settings.MODELS_DIR, "movie_mappings.pkl"), "rb") as f:
            movie_mappings = pickle.load(f)
        with open(os.path.join(settings.MODELS_DIR, "vectorizer.pkl"), "rb") as f:
            vectorizer = pickle.load(f)

        content_model = ContentBasedRecommender()
        content_model.fit(tfidf_matrix, movie_mappings, vectorizer)
        content_model.save()

        # 4. Construct user-movie sparse matrices for SVD model using training data only
        logger.info("Building User-Item rating matrix on training partition...")
        train_df = pd.DataFrame(train_ratings)
        
        train_user_ids = train_df["user_id"].unique()
        train_movie_ids = train_df["movie_id"].unique()

        user_to_idx = {uid: idx for idx, uid in enumerate(train_user_ids)}
        idx_to_user = {idx: uid for idx, uid in enumerate(train_user_ids)}
        movie_to_idx_train = {mid: idx for idx, mid in enumerate(train_movie_ids)}
        idx_to_movie_train = {idx: mid for idx, mid in enumerate(train_movie_ids)}

        rows = train_df["user_id"].map(user_to_idx).values
        cols = train_df["movie_id"].map(movie_to_idx_train).values
        data = train_df["rating"].values

        csr_train = csr_matrix((data, (rows, cols)), shape=(len(train_user_ids), len(train_movie_ids)))
        
        # Build training popularity index (needed for novelty metrics)
        train_popularity = train_df["movie_id"].value_counts().to_dict()

        # 5. Fit Collaborative SVD model
        collab_mappings = {
            "user_to_idx": user_to_idx,
            "idx_to_user": idx_to_user,
            "movie_to_idx": movie_to_idx_train,
            "idx_to_movie": idx_to_movie_train
        }
        collab_model = CollaborativeRecommender(epochs=15, k_components=20)
        collab_model.fit(csr_train, collab_mappings)
        collab_model.save()

        # 6. Initialize Hybrid model for evaluation
        hybrid_model = HybridRecommender()
        # Overwrite internal SVD and Content modules with our training split instances
        hybrid_model.collab_model = collab_model
        hybrid_model.content_model = content_model

        # 7. Evaluate Performance
        logger.info("Running validation and evaluation metrics...")
        evaluator = ModelEvaluator(k=10, relevance_threshold=3.5)
        
        # Group test ratings by user for ranking calculations
        test_ratings_by_user = {}
        for r in test_ratings:
            u_id = r["user_id"]
            if u_id not in test_ratings_by_user:
                test_ratings_by_user[u_id] = []
            test_ratings_by_user[u_id].append(r)

        # Run evaluation
        regression_metrics = evaluator.evaluate_regression(collab_model, test_ratings)
        ranking_metrics = evaluator.evaluate_ranking_and_catalog(
            hybrid_model, 
            test_ratings_by_user, 
            db, 
            all_movie_ids, 
            train_popularity
        )

        metrics = {**regression_metrics, **ranking_metrics}
        metrics["training_duration_seconds"] = round(time.time() - start_time, 2)
        metrics["trained_at"] = pd.Timestamp.now().isoformat()

        # Save metrics to models directory
        import json
        with open(os.path.join(settings.MODELS_DIR, "evaluation_metrics.json"), "w") as f:
            json.dump(metrics, f, indent=4)

        logger.info(f"Training completed successfully in {metrics['training_duration_seconds']}s.")
        logger.info(f"Evaluation Metrics: {json.dumps(metrics, indent=2)}")

        # Save the production SVD model fitted on the ENTIRE dataset (to provide best inference ratings)
        logger.info("Re-fitting collaborative SVD on the full ratings dataset for production inference...")
        preprocessor.build_rating_matrix(db) # Creates the full dataset csr matrix and mappings
        
        # Load full matrix mappings
        with open(os.path.join(settings.MODELS_DIR, "ratings_csr.pkl"), "rb") as f:
            full_csr = pickle.load(f)
        with open(os.path.join(settings.MODELS_DIR, "ratings_mappings.pkl"), "rb") as f:
            full_mappings = pickle.load(f)
            
        prod_collab = CollaborativeRecommender(epochs=15, k_components=20)
        prod_collab.fit(full_csr, full_mappings)
        prod_collab.save() # Overwrites svd_model.pkl with the production SVD weights

        return metrics

    except Exception as e:
        logger.exception(f"Error in trainer pipeline: {e}")
        raise e
    finally:
        if opened_db:
            db.close()

if __name__ == "__main__":
    train_and_evaluate_models()
