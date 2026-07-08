import os
import zipfile
import requests
import pandas as pd
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
        self.zip_path = os.path.join(self.data_dir, "ml-latest-small.zip")
        self.extract_dir = os.path.join(self.data_dir, "ml-latest-small")

    def download_dataset(self) -> str:
        """Downloads the MovieLens dataset from GroupLens if it does not already exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.zip_path):
            logger.info(f"Downloading dataset from {settings.MOVIELENS_DATASET_URL}...")
            response = requests.get(settings.MOVIELENS_DATASET_URL, stream=True)
            response.raise_for_status()
            with open(self.zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info("Download completed successfully.")
        else:
            logger.info("Dataset zip already exists. Skipping download.")
            
        if not os.path.exists(self.extract_dir):
            logger.info("Extracting dataset...")
            with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
                zip_ref.extractall(self.data_dir)
            logger.info("Extraction completed.")
        else:
            logger.info("Dataset already extracted.")
            
        return self.extract_dir

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
        ratings_df = pd.read_csv(ratings_path)
        
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
        agg_stats = ratings_df.groupby("movieId").agg(
            mean_rating=("rating", "mean"),
            vote_count=("rating", "count")
        )
        # Scale count logarithmically to not let massive blockbusters skew too high
        import numpy as np
        agg_stats["popularity_score"] = agg_stats["mean_rating"] * np.log1p(agg_stats["vote_count"])
        movies_df = pd.merge(movies_df, agg_stats["popularity_score"], left_on="movieId", right_index=True, how="left")
        movies_df["popularity_score"] = movies_df["popularity_score"].fillna(0.0)

        return movies_df, ratings_df

    def seed_database(self, movies_df: pd.DataFrame, ratings_df: pd.DataFrame, db: Session):
        """Seeds the PostgreSQL database with movies and ratings using fast batch inserts."""
        # 1. Seed Movies
        movie_count = db.query(Movie).count()
        if movie_count == 0:
            logger.info("Seeding movies table...")
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
            
            # Batch insertion
            db.bulk_insert_mappings(Movie, movie_records)
            db.commit()
            logger.info(f"Seeded {len(movie_records)} movies successfully.")
        else:
            logger.info(f"Movies table already contains {movie_count} records. Skipping seeding.")

        # 2. Seed Ratings
        rating_count = db.query(Rating).count()
        if rating_count == 0:
            logger.info("Seeding ratings table... This may take a few seconds.")
            # Convert timestamp to datetime objects
            ratings_df["datetime"] = pd.to_datetime(ratings_df["timestamp"], unit="s")
            
            # Group ratings into chunks to avoid memory bottlenecks
            chunk_size = 25000
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
                    rating_records = []
                    
            if rating_records:
                db.bulk_insert_mappings(Rating, rating_records)
                db.commit()
                
            logger.info(f"Seeded {len(ratings_df)} ratings successfully.")
        else:
            logger.info(f"Ratings table already contains {rating_count} records. Skipping seeding.")

    def run_pipeline(self):
        """Runs the entire download, merge, and seeding pipeline."""
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        db = SessionLocal()
        try:
            extract_dir = self.download_dataset()
            movies_df, ratings_df = self.load_and_preprocess_dfs(extract_dir)
            self.seed_database(movies_df, ratings_df, db)
            logger.info("Data Pipeline execution completed successfully.")
        except Exception as e:
            logger.exception(f"Error executing data pipeline: {e}")
            raise e
        finally:
            db.close()

if __name__ == "__main__":
    pipeline = DataPipeline()
    pipeline.run_pipeline()
