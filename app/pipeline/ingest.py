import os
import zipfile
import requests
import pandas as pd
import numpy as np
import logging
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.database.connection import SessionLocal, engine, Base
from app.database.models import Movie, Rating

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self):
        self.data_dir = settings.DATA_DIR
        self.zip_path = os.path.join(self.data_dir, "movielens.zip")

    def _detect_extract_dir(self) -> str:
        """Auto-detects the extracted folder name inside data_dir.
        
        MovieLens zips extract to different folder names depending on the dataset:
        - ml-latest-small/
        - ml-25m/
        - ml-latest/
        """
        for name in ["ml-latest-small", "ml-25m", "ml-latest"]:
            candidate = os.path.join(self.data_dir, name)
            if os.path.exists(candidate) and os.path.isdir(candidate):
                return candidate
        # Fallback: find any directory starting with 'ml-'
        for entry in os.listdir(self.data_dir):
            full = os.path.join(self.data_dir, entry)
            if os.path.isdir(full) and entry.startswith("ml-"):
                return full
        return os.path.join(self.data_dir, "ml-latest")

    def download_dataset(self) -> str:
        """Downloads the MovieLens dataset from GroupLens if it does not already exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.zip_path):
            logger.info(f"Downloading dataset from {settings.MOVIELENS_DATASET_URL}...")
            logger.info("This may take a few minutes for large datasets (25M/latest)...")
            response = requests.get(settings.MOVIELENS_DATASET_URL, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        if downloaded % (5 * 1024 * 1024) < 65536:  # Log every ~5MB
                            logger.info(f"  Download progress: {pct:.1f}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                            
            logger.info("Download completed successfully.")
        else:
            logger.info("Dataset zip already exists. Skipping download.")
        
        # Extract if needed
        extract_dir = self._detect_extract_dir()
        if not os.path.exists(extract_dir):
            logger.info("Extracting dataset...")
            with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
                zip_ref.extractall(self.data_dir)
            extract_dir = self._detect_extract_dir()
            logger.info(f"Extraction completed. Dataset folder: {extract_dir}")
        else:
            logger.info(f"Dataset already extracted at {extract_dir}.")
            
        return extract_dir

    def load_and_preprocess_dfs(self, extract_dir: str):
        """Loads CSVs from the extracted directory, merges them, and cleans metadata."""
        movies_path = os.path.join(extract_dir, "movies.csv")
        ratings_path = os.path.join(extract_dir, "ratings.csv")
        links_path = os.path.join(extract_dir, "links.csv")

        # Check local fallbacks if extracted paths don't exist
        fallback_dir = r"Movie-Recommendation-System-MOVICO-main\MOVICO\dataset"
        if not os.path.exists(movies_path):
            movies_path = os.path.join(fallback_dir, "movies.csv")
            ratings_path = os.path.join(fallback_dir, "ratings.csv")
            # Links file doesn't exist in fallback, we'll construct mock links or search for it.
            links_path = None

        logger.info(f"Loading files: movies={movies_path}, ratings={ratings_path}")
        movies_df = pd.read_csv(movies_path)
        
        # For large datasets, log progress
        logger.info(f"Loading ratings file (this may take a moment for large datasets)...")
        ratings_df = pd.read_csv(ratings_path)
        logger.info(f"Loaded {len(movies_df)} movies and {len(ratings_df):,} ratings from CSV.")
        
        # Parse links if available
        if links_path and os.path.exists(links_path):
            logger.info(f"Loading links from {links_path}")
            links_df = pd.read_csv(links_path)
            # Ensure proper string format, pad with leading zeros for IMDb if needed
            links_df["imdbId"] = links_df["imdbId"].astype(str).str.replace(".0", "", regex=False).str.zfill(7)
            links_df["tmdbId"] = links_df["tmdbId"].astype(str).str.replace(".0", "", regex=False)
            movies_df = pd.merge(movies_df, links_df, on="movieId", how="left")
        else:
            movies_df["imdbId"] = None
            movies_df["tmdbId"] = None

        # Basic Validation
        assert "movieId" in movies_df.columns, "Missing movieId column in movies"
        assert "title" in movies_df.columns, "Missing title column in movies"
        assert "genres" in movies_df.columns, "Missing genres column in movies"
        assert "userId" in ratings_df.columns, "Missing userId column in ratings"
        assert "movieId" in ratings_df.columns, "Missing movieId column in ratings"
        assert "rating" in ratings_df.columns, "Missing rating column in ratings"
        
        # Clean title column (e.g., stripping whitespace)
        movies_df["title"] = movies_df["title"].str.strip()
        
        # Calculate popularity scores for movies (mean rating * log(count + 1))
        # This provides a balanced measure of rating volume and average sentiment.
        logger.info("Computing popularity scores...")
        agg_stats = ratings_df.groupby("movieId").agg(
            mean_rating=("rating", "mean"),
            vote_count=("rating", "count")
        )
        # Scale count logarithmically to not let massive blockbusters skew too high
        agg_stats["popularity_score"] = agg_stats["mean_rating"] * np.log1p(agg_stats["vote_count"])
        movies_df = pd.merge(movies_df, agg_stats["popularity_score"], left_on="movieId", right_index=True, how="left")
        movies_df["popularity_score"] = movies_df["popularity_score"].fillna(0.0)

        return movies_df, ratings_df

    def seed_database(self, movies_df: pd.DataFrame, ratings_df: pd.DataFrame, db: Session):
        """Seeds the database with movies and ratings using fast batch inserts."""
        # 1. Seed Movies
        movie_count = db.query(Movie).count()
        if movie_count == 0:
            logger.info(f"Seeding movies table with {len(movies_df)} movies...")
            movie_records = []
            for _, row in movies_df.iterrows():
                movie_records.append({
                    "id": int(row["movieId"]),
                    "title": str(row["title"]),
                    "genres": str(row["genres"]),
                    "imdb_id": str(row["imdbId"]) if pd.notna(row["imdbId"]) else None,
                    "tmdb_id": str(row["tmdbId"]) if pd.notna(row["tmdbId"]) else None,
                    "popularity_score": float(row["popularity_score"])
                })
            
            # Batch insertion in chunks for large datasets
            chunk_size = 10000
            for i in range(0, len(movie_records), chunk_size):
                chunk = movie_records[i:i + chunk_size]
                db.bulk_insert_mappings(Movie, chunk)
                db.commit()
                if len(movie_records) > chunk_size:
                    logger.info(f"  Seeded {min(i + chunk_size, len(movie_records))}/{len(movie_records)} movies...")
                    
            logger.info(f"Seeded {len(movie_records)} movies successfully.")
        else:
            logger.info(f"Movies table already contains {movie_count} records. Skipping seeding.")

        # 2. Seed Ratings
        rating_count = db.query(Rating).count()
        if rating_count == 0:
            logger.info(f"Seeding ratings table with {len(ratings_df):,} ratings... This may take a few minutes for large datasets.")
            # Convert timestamp to datetime objects
            ratings_df["datetime"] = pd.to_datetime(ratings_df["timestamp"], unit="s")
            
            # Group ratings into chunks to avoid memory bottlenecks
            chunk_size = 50000
            rating_records = []
            
            for idx, row in ratings_df.iterrows():
                rating_records.append({
                    "user_id": int(row["userId"]),
                    "movie_id": int(row["movieId"]),
                    "rating": float(row["rating"]),
                    "timestamp": row["datetime"]
                })
                
                if len(rating_records) >= chunk_size:
                    db.bulk_insert_mappings(Rating, rating_records)
                    db.commit()
                    logger.info(f"  Seeded {idx + 1:,}/{len(ratings_df):,} ratings...")
                    rating_records = []
                    
            if rating_records:
                db.bulk_insert_mappings(Rating, rating_records)
                db.commit()
                
            logger.info(f"Seeded {len(ratings_df):,} ratings successfully.")
        else:
            logger.info(f"Ratings table already contains {rating_count:,} records. Skipping seeding.")

    def run_pipeline(self):
        """Runs the entire download, merge, seeding, and TMDB enrichment pipeline."""
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        try:
            extract_dir = self.download_dataset()
            movies_df, ratings_df = self.load_and_preprocess_dfs(extract_dir)
            self.seed_database(movies_df, ratings_df, db)
            
            # Run TMDB metadata enrichment
            logger.info("Starting TMDB metadata enrichment phase...")
            from app.pipeline.tmdb_enricher import enrich_movies_from_tmdb
            enrich_movies_from_tmdb(db)
            
            logger.info("Data Pipeline execution completed successfully.")
        except Exception as e:
            logger.exception(f"Error executing data pipeline: {e}")
            raise e
        finally:
            db.close()

if __name__ == "__main__":
    pipeline = DataPipeline()
    pipeline.run_pipeline()
