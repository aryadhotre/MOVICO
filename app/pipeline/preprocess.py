import re
import os
import pickle
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.database.models import Movie, Rating

logger = logging.getLogger(__name__)

class MoviePreprocessor:
    def __init__(self):
        self.models_dir = settings.MODELS_DIR
        os.makedirs(self.models_dir, exist_ok=True)

    @staticmethod
    def clean_title(title: str) -> str:
        """Removes the year suffix (e.g. '(1995)') and special characters from movie titles."""
        # Remove trailing year: e.g. "Toy Story (1995)" -> "Toy Story"
        title_cleaned = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
        # Remove punctuation and lowercase
        title_cleaned = re.sub(r"[^\w\s]", "", title_cleaned).lower().strip()
        return title_cleaned

    def build_content_features(self, db: Session):
        """Builds content-based TF-IDF matrices based on titles and genres."""
        logger.info("Retrieving movies from DB for preprocessing...")
        movies = db.query(Movie).all()
        if not movies:
            raise ValueError("No movies found in database. Run the ingestion pipeline first.")

        df = pd.DataFrame([{
            "id": m.id,
            "title": m.title,
            "genres": m.genres
        } for m in movies])

        # Clean titles and format genres for TF-IDF
        # Replace '|' separator with space so genres act as distinct tokens, e.g., "Action Adventure"
        df["clean_genres"] = df["genres"].str.replace("|", " ", regex=False)
        df["clean_title"] = df["title"].apply(self.clean_title)
        
        # Combine title and genres for the final text representation
        df["combined_features"] = df["clean_title"] + " " + df["clean_genres"]

        logger.info("Computing TF-IDF matrices for content similarity...")
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(df["combined_features"])
        
        # Cache vectors, mappings, and vectorizer
        tfidf_path = os.path.join(self.models_dir, "tfidf_matrix.pkl")
        vectorizer_path = os.path.join(self.models_dir, "vectorizer.pkl")
        mappings_path = os.path.join(self.models_dir, "movie_mappings.pkl")
        
        # Movie ID mapping to sparse matrix row indices
        movie_to_idx = {row["id"]: idx for idx, row in df.iterrows()}
        idx_to_movie = {idx: row["id"] for idx, row in df.iterrows()}

        with open(tfidf_path, "wb") as f:
            pickle.dump(tfidf_matrix, f)
        with open(vectorizer_path, "wb") as f:
            pickle.dump(vectorizer, f)
        with open(mappings_path, "wb") as f:
            pickle.dump({"movie_to_idx": movie_to_idx, "idx_to_movie": idx_to_movie}, f)
            
        logger.info("Content-based TF-IDF matrices generated and saved successfully.")
        return tfidf_matrix, movie_to_idx

    def build_rating_matrix(self, db: Session):
        """Constructs a Compressed Sparse Row (CSR) matrix of user-movie ratings."""
        logger.info("Retrieving ratings from DB for matrix preparation...")
        ratings = db.query(Rating).all()
        if not ratings:
            raise ValueError("No ratings found in database. Run the ingestion pipeline first.")

        df = pd.DataFrame([{
            "user_id": r.user_id,
            "movie_id": r.movie_id,
            "rating": r.rating
        } for r in ratings])

        # Map active users and movies to contiguous indices starting from 0
        user_ids = df["user_id"].unique()
        movie_ids = df["movie_id"].unique()

        user_to_idx = {uid: idx for idx, uid in enumerate(user_ids)}
        idx_to_user = {idx: uid for idx, uid in enumerate(user_ids)}
        movie_to_idx = {mid: idx for idx, mid in enumerate(movie_ids)}
        idx_to_movie = {idx: mid for idx, mid in enumerate(movie_ids)}

        # Map coordinates
        rows = df["user_id"].map(user_to_idx).values
        cols = df["movie_id"].map(movie_to_idx).values
        data = df["rating"].values

        # Build sparse matrix
        csr_data = csr_matrix((data, (rows, cols)), shape=(len(user_ids), len(movie_ids)))
        
        # Save mappings and matrix
        matrix_path = os.path.join(self.models_dir, "ratings_csr.pkl")
        mappings_path = os.path.join(self.models_dir, "ratings_mappings.pkl")
        
        with open(matrix_path, "wb") as f:
            pickle.dump(csr_data, f)
        with open(mappings_path, "wb") as f:
            pickle.dump({
                "user_to_idx": user_to_idx,
                "idx_to_user": idx_to_user,
                "movie_to_idx": movie_to_idx,
                "idx_to_movie": idx_to_movie
            }, f)
            
        logger.info(f"User-Item sparse matrix built. Shape: {csr_data.shape}, Sparsity: {100 * (1 - csr_data.nnz / (csr_data.shape[0] * csr_data.shape[1])):.2f}%")
        return csr_data, user_to_idx, movie_to_idx
