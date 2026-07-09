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
        title_cleaned = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
        title_cleaned = re.sub(r"[^\w\s]", "", title_cleaned).lower().strip()
        return title_cleaned

    @staticmethod
    def extract_year(title: str) -> str:
        """Extracts the release year from movie title, returns decade token for era-based matching."""
        match = re.search(r"\((\d{4})\)", title)
        if match:
            year = int(match.group(1))
            decade = (year // 10) * 10
            return f"decade_{decade}s"
        return ""

    @staticmethod
    def build_rich_feature_text(movie) -> str:
        """Constructs a rich multi-signal text document for a single movie.
        
        Combines multiple metadata fields with strategic weighting:
        - Genres (repeated 3x for high importance)
        - Movie title keywords
        - Overview/plot description
        - Director name (repeated 2x)
        - Cast names
        - User-generated tags from MovieLens
        - Release era/decade
        - Original language
        """
        parts = []
        
        # 1. Genres (high weight - repeated 3x)
        genres = getattr(movie, "genres", "") or ""
        if genres and genres != "(no genres listed)":
            genre_text = genres.replace("|", " ")
            parts.extend([genre_text] * 3)
        
        # 2. Clean title keywords
        title = getattr(movie, "title", "") or ""
        clean = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
        clean = re.sub(r"[^\w\s]", "", clean).lower().strip()
        if clean:
            parts.append(clean)
        
        # 3. Overview / plot description (if enriched via TMDB)
        overview = getattr(movie, "overview", "") or ""
        if overview and overview.strip():
            parts.append(overview.lower())
        
        # 4. Director (medium weight - repeated 2x)
        director = getattr(movie, "director", "") or ""
        if director and director.strip():
            director_clean = re.sub(r"[^\w\s]", "", director).lower()
            parts.extend([director_clean] * 2)
        
        # 5. Cast members
        cast = getattr(movie, "cast_list", "") or ""
        if cast and cast.strip():
            cast_clean = re.sub(r"[^\w\s]", "", cast).lower()
            parts.append(cast_clean)
        
        # 6. User-generated tags from MovieLens (high signal)
        tags = getattr(movie, "user_tags", "") or ""
        if tags and tags.strip():
            parts.append(tags.lower())
        
        # 7. Release decade for era-based matching
        era = MoviePreprocessor.extract_year(title)
        if era:
            parts.append(era)
        
        # 8. Original language
        lang = getattr(movie, "original_language", "") or ""
        if lang and lang.strip() and lang != "en":
            parts.append(f"lang_{lang}")
        
        return " ".join(parts)

    def build_content_features(self, db: Session):
        """Builds content-based TF-IDF matrices using rich multi-signal text features.
        
        Feature signals used:
        - Genres (3x weighted)
        - Title keywords
        - Overview/plot (from TMDB enrichment)
        - Director (2x weighted)
        - Cast names
        - User-generated tags (from MovieLens tags.csv)
        - Release decade
        - Original language
        """
        logger.info("Retrieving movies from DB for content feature engineering...")
        movies = db.query(Movie).all()
        if not movies:
            raise ValueError("No movies found in database. Run the ingestion pipeline first.")

        logger.info(f"Building rich text features for {len(movies):,} movies...")
        movie_ids = []
        feature_docs = []
        
        for movie in movies:
            movie_ids.append(movie.id)
            feature_docs.append(self.build_rich_feature_text(movie))
        
        # Count how many movies have enriched data
        enriched_count = sum(1 for m in movies if m.overview and m.overview.strip())
        tagged_count = sum(1 for m in movies if m.user_tags and m.user_tags.strip())
        logger.info(
            f"Feature composition: {len(movies):,} movies total, "
            f"{enriched_count:,} with TMDB overview, "
            f"{tagged_count:,} with user tags."
        )

        logger.info("Computing TF-IDF matrices with rich features...")
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=50000,  # Cap vocabulary for memory efficiency on large catalogs
            min_df=2,            # Ignore terms that appear in fewer than 2 movies
            max_df=0.95,         # Ignore terms that appear in >95% of movies
            sublinear_tf=True    # Apply sublinear TF scaling (1 + log(tf))
        )
        tfidf_matrix = vectorizer.fit_transform(feature_docs)
        
        logger.info(
            f"TF-IDF matrix shape: {tfidf_matrix.shape} "
            f"(vocabulary size: {len(vectorizer.vocabulary_):,})"
        )
        
        # Cache vectors, mappings, and vectorizer
        tfidf_path = os.path.join(self.models_dir, "tfidf_matrix.pkl")
        vectorizer_path = os.path.join(self.models_dir, "vectorizer.pkl")
        mappings_path = os.path.join(self.models_dir, "movie_mappings.pkl")
        
        # Movie ID mapping to sparse matrix row indices
        movie_to_idx = {mid: idx for idx, mid in enumerate(movie_ids)}
        idx_to_movie = {idx: mid for idx, mid in enumerate(movie_ids)}

        with open(tfidf_path, "wb") as f:
            pickle.dump(tfidf_matrix, f)
        with open(vectorizer_path, "wb") as f:
            pickle.dump(vectorizer, f)
        with open(mappings_path, "wb") as f:
            pickle.dump({"movie_to_idx": movie_to_idx, "idx_to_movie": idx_to_movie}, f)
            
        logger.info("Rich content-based TF-IDF matrices generated and saved successfully.")
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
