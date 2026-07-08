import os
import random
import time
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
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
    """Orchestrates model data partitioning, training, validation, evaluation, and serialization.
    
    For large datasets (25M+ ratings), this function intelligently samples a configurable
    subset of ratings for SVD training while still using the complete movie catalog for
    content-based features.
    """
    opened_db = False
    if db is None:
        db = SessionLocal()
        opened_db = True

    try:
        start_time = time.time()
        logger.info("Starting model training pipeline...")

        # 1. Count total ratings & movies
        total_ratings = db.query(sql_func.count(Rating.id)).scalar()
        movies = db.query(Movie).all()

        if total_ratings == 0 or not movies:
            raise ValueError("Insufficient database records. Please run the data ingestion pipeline first.")

        all_movie_ids = {m.id for m in movies}
        logger.info(f"Database contains {total_ratings:,} ratings and {len(movies):,} movies.")

        # 2. Determine sampling strategy for large datasets
        sample_size = settings.TRAINING_SAMPLE_SIZE
        use_sampling = sample_size > 0 and total_ratings > sample_size

        if use_sampling:
            logger.info(
                f"Large dataset detected ({total_ratings:,} ratings). "
                f"Sampling {sample_size:,} ratings for SVD training."
            )
            # Fetch a random sample using database-level offset/limit for memory efficiency
            # We'll fetch in chunks to avoid loading everything into memory
            ratings_list = _fetch_sampled_ratings(db, sample_size)
        else:
            logger.info(f"Loading all {total_ratings:,} ratings for training...")
            ratings = db.query(Rating).yield_per(50000).all()
            ratings_list = [{
                "user_id": r.user_id,
                "movie_id": r.movie_id,
                "rating": r.rating,
                "timestamp": r.timestamp
            } for r in ratings]

        logger.info(f"Working with {len(ratings_list):,} ratings for model training.")

        # 3. Train-Test Split (80/20)
        random.seed(42)
        random.shuffle(ratings_list)
        split_idx = int(len(ratings_list) * 0.8)
        train_ratings = ratings_list[:split_idx]
        test_ratings = ratings_list[split_idx:]

        logger.info(f"Split data into {len(train_ratings):,} training and {len(test_ratings):,} testing samples.")

        # 4. Fit content-based vectors on complete catalog
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

        # 5. Construct user-movie sparse matrices for SVD model using training data only
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

        # 6. Fit Collaborative SVD model with configurable hyperparameters
        logger.info(f"Training SVD with {settings.SVD_FACTORS} factors, {settings.SVD_EPOCHS} epochs...")
        collab_mappings = {
            "user_to_idx": user_to_idx,
            "idx_to_user": idx_to_user,
            "movie_to_idx": movie_to_idx_train,
            "idx_to_movie": idx_to_movie_train
        }
        collab_model = CollaborativeRecommender(epochs=settings.SVD_EPOCHS, k_components=settings.SVD_FACTORS)
        collab_model.fit(csr_train, collab_mappings)
        collab_model.save()

        # 7. Initialize Hybrid model for evaluation
        hybrid_model = HybridRecommender()
        # Overwrite internal SVD and Content modules with our training split instances
        hybrid_model.collab_model = collab_model
        hybrid_model.content_model = content_model

        # 8. Evaluate Performance
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
        metrics["total_ratings_in_db"] = total_ratings
        metrics["ratings_used_for_training"] = len(ratings_list)
        metrics["svd_factors"] = settings.SVD_FACTORS
        metrics["svd_epochs"] = settings.SVD_EPOCHS

        # Save metrics to models directory
        import json
        with open(os.path.join(settings.MODELS_DIR, "evaluation_metrics.json"), "w") as f:
            json.dump(metrics, f, indent=4)

        logger.info(f"Training completed successfully in {metrics['training_duration_seconds']}s.")
        logger.info(f"Evaluation Metrics: {json.dumps(metrics, indent=2)}")

        # 9. Re-fit collaborative SVD on the ENTIRE working set for production inference
        logger.info("Re-fitting collaborative SVD on the full working set for production inference...")
        full_df = pd.DataFrame(ratings_list)
        
        full_user_ids = full_df["user_id"].unique()
        full_movie_ids = full_df["movie_id"].unique()
        
        full_user_to_idx = {uid: idx for idx, uid in enumerate(full_user_ids)}
        full_idx_to_user = {idx: uid for idx, uid in enumerate(full_user_ids)}
        full_movie_to_idx = {mid: idx for idx, mid in enumerate(full_movie_ids)}
        full_idx_to_movie = {idx: mid for idx, mid in enumerate(full_movie_ids)}
        
        full_rows = full_df["user_id"].map(full_user_to_idx).values
        full_cols = full_df["movie_id"].map(full_movie_to_idx).values
        full_data = full_df["rating"].values
        
        full_csr = csr_matrix((full_data, (full_rows, full_cols)), shape=(len(full_user_ids), len(full_movie_ids)))
        
        full_mappings = {
            "user_to_idx": full_user_to_idx,
            "idx_to_user": full_idx_to_user,
            "movie_to_idx": full_movie_to_idx,
            "idx_to_movie": full_idx_to_movie
        }
        
        # Save mappings for the recommender service
        import pickle
        os.makedirs(settings.MODELS_DIR, exist_ok=True)
        with open(os.path.join(settings.MODELS_DIR, "ratings_csr.pkl"), "wb") as f:
            pickle.dump(full_csr, f)
        with open(os.path.join(settings.MODELS_DIR, "ratings_mappings.pkl"), "wb") as f:
            pickle.dump(full_mappings, f)
        
        prod_collab = CollaborativeRecommender(epochs=settings.SVD_EPOCHS, k_components=settings.SVD_FACTORS)
        prod_collab.fit(full_csr, full_mappings)
        prod_collab.save()  # Overwrites svd_model.pkl with the production SVD weights

        return metrics

    except Exception as e:
        logger.exception(f"Error in trainer pipeline: {e}")
        raise e
    finally:
        if opened_db:
            db.close()


def _fetch_sampled_ratings(db: Session, sample_size: int) -> list:
    """Fetches a random sample of ratings using streaming probabilistic sampling.
    
    Avoids ORDER BY RANDOM() which requires sorting all 33M+ rows (extremely slow on SQLite).
    Instead, streams through the table once and probabilistically keeps each row.
    """
    from sqlalchemy import func as sql_func
    import random
    
    total = db.query(sql_func.count(Rating.id)).scalar()
    # Oversample by 10% to account for probabilistic variance, then trim
    sample_ratio = min(1.0, (sample_size * 1.1) / total)
    
    logger.info(f"Streaming {total:,} ratings with {sample_ratio:.4f} sample ratio...")
    
    result = []
    batch_count = 0
    for rating in db.query(Rating).yield_per(50000):
        if random.random() < sample_ratio:
            result.append({
                "user_id": rating.user_id,
                "movie_id": rating.movie_id,
                "rating": rating.rating,
                "timestamp": rating.timestamp
            })
        batch_count += 1
        if batch_count % 5000000 == 0:
            logger.info(f"  Scanned {batch_count:,}/{total:,} ratings, collected {len(result):,} samples...")
        if len(result) >= int(sample_size * 1.1):
            break
    
    # Shuffle and trim to exact sample size
    random.shuffle(result)
    result = result[:sample_size]
    logger.info(f"Sampling complete: {len(result):,} ratings selected.")
    return result


if __name__ == "__main__":
    train_and_evaluate_models()
