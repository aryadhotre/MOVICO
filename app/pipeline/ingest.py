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
        tags_path = os.path.join(extract_dir, "tags.csv")

        # Check local fallbacks if extracted paths don't exist
        fallback_dir = r"Movie-Recommendation-System-MOVICO-main\MOVICO\dataset"
        if not os.path.exists(movies_path):
            movies_path = os.path.join(fallback_dir, "movies.csv")
            ratings_path = os.path.join(fallback_dir, "ratings.csv")
            links_path = None
            tags_path = None

        logger.info(f"Loading files: movies={movies_path}, ratings={ratings_path}")
        movies_df = pd.read_csv(movies_path)
        
        # For large datasets, log progress
        logger.info(f"Loading ratings file (this may take a moment for large datasets)...")
        ratings_df = pd.read_csv(ratings_path)
        logger.info(f"Loaded {len(movies_df):,} movies and {len(ratings_df):,} ratings from CSV.")
        
        # Parse links if available
        if links_path and os.path.exists(links_path):
            logger.info(f"Loading links from {links_path}")
            links_df = pd.read_csv(links_path)
            links_df["imdbId"] = links_df["imdbId"].astype(str).str.replace(".0", "", regex=False).str.zfill(7)
            links_df["tmdbId"] = links_df["tmdbId"].astype(str).str.replace(".0", "", regex=False)
            movies_df = pd.merge(movies_df, links_df, on="movieId", how="left")
        else:
            movies_df["imdbId"] = None
            movies_df["tmdbId"] = None

        # Load and aggregate user-generated tags per movie
        if tags_path and os.path.exists(tags_path):
            logger.info(f"Loading user-generated tags from {tags_path}...")
            tags_df = pd.read_csv(tags_path)
            tags_df["tag"] = tags_df["tag"].astype(str).str.lower().str.strip()
            # Aggregate unique tags per movie, take top 15 most frequent
            tag_agg = tags_df.groupby("movieId")["tag"].apply(
                lambda tags: " ".join(tags.value_counts().head(15).index.tolist())
            ).reset_index()
            tag_agg.columns = ["movieId", "user_tags"]
            movies_df = pd.merge(movies_df, tag_agg, on="movieId", how="left")
            logger.info(f"Aggregated tags for {len(tag_agg):,} movies.")
        else:
            movies_df["user_tags"] = None

        # Basic Validation
        assert "movieId" in movies_df.columns, "Missing movieId column in movies"
        assert "title" in movies_df.columns, "Missing title column in movies"
        assert "genres" in movies_df.columns, "Missing genres column in movies"
        assert "userId" in ratings_df.columns, "Missing userId column in ratings"
        assert "movieId" in ratings_df.columns, "Missing movieId column in ratings"
        assert "rating" in ratings_df.columns, "Missing rating column in ratings"
        
        # Clean title column
        movies_df["title"] = movies_df["title"].str.strip()
        
        # Extract release year from title (e.g., "Toy Story (1995)" -> 1995)
        import re
        movies_df["release_year"] = movies_df["title"].str.extract(r"\((\d{4})\)$", expand=False)
        
        # Calculate popularity scores for movies (mean rating * log(count + 1))
        logger.info("Computing popularity scores...")
        agg_stats = ratings_df.groupby("movieId").agg(
            mean_rating=("rating", "mean"),
            vote_count=("rating", "count")
        )
        agg_stats["popularity_score"] = agg_stats["mean_rating"] * np.log1p(agg_stats["vote_count"])
        movies_df = pd.merge(movies_df, agg_stats["popularity_score"], left_on="movieId", right_index=True, how="left")
        movies_df["popularity_score"] = movies_df["popularity_score"].fillna(0.0)

        # Calculate time-weighted trending score (recent ratings decay less)
        logger.info("Computing trending scores (time-decayed popularity)...")
        max_time = ratings_df["timestamp"].max()
        # Difference in years (using 365.25 days per year)
        ratings_df["delta_years"] = (max_time - ratings_df["timestamp"]) / (365.25 * 24 * 3600)
        # Half-life of 1 year: weight = 2^(-delta_years)
        ratings_df["weight"] = 2.0 ** (-ratings_df["delta_years"])
        ratings_df["weighted_rating"] = ratings_df["rating"] * ratings_df["weight"]
        
        agg_trending = ratings_df.groupby("movieId").agg(
            sum_weight=("weight", "sum"),
            sum_weighted_rating=("weighted_rating", "sum")
        )
        agg_trending["weighted_mean"] = agg_trending["sum_weighted_rating"] / agg_trending["sum_weight"]
        agg_trending["trending_score"] = agg_trending["weighted_mean"] * np.log1p(agg_trending["sum_weight"])
        agg_trending["trending_score"] = agg_trending["trending_score"].fillna(0.0)
        
        movies_df = pd.merge(movies_df, agg_trending["trending_score"], left_on="movieId", right_index=True, how="left")
        movies_df["trending_score"] = movies_df["trending_score"].fillna(0.0)

        # Clean up temporary columns to save memory
        ratings_df.drop(columns=["delta_years", "weight", "weighted_rating"], inplace=True)

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
                    "popularity_score": float(row["popularity_score"]),
                    "trending_score": float(row["trending_score"]),
                    "user_tags": str(row["user_tags"]) if pd.notna(row.get("user_tags")) else None
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
            
            # Use chunked itertuples for ultra-fast, memory-efficient bulk insertion
            chunk_size = 100000
            total_rows = len(ratings_df)
            
            for i in range(0, total_rows, chunk_size):
                chunk_df = ratings_df.iloc[i:i + chunk_size]
                records = [
                    {
                        "user_id": int(r.userId),
                        "movie_id": int(r.movieId),
                        "rating": float(r.rating),
                        "timestamp": r.datetime
                    }
                    for r in chunk_df.itertuples(index=False)
                ]
                db.bulk_insert_mappings(Rating, records)
                db.commit()
                logger.info(f"  Seeded {min(i + chunk_size, total_rows):,}/{total_rows:,} ratings...")
                
            logger.info(f"Seeded {total_rows:,} ratings successfully.")
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
