import redis
import json
import logging
from typing import Optional, List, Dict, Any
from app.config.settings import settings

logger = logging.getLogger(__name__)

class RedisCacheService:
    def __init__(self):
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.db = settings.REDIS_DB
        self.client = None
        self._connect()

    def _connect(self):
        """Attempts connection to Redis. Soft fallbacks on connection failures."""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                socket_timeout=2,
                socket_connect_timeout=2,
                decode_responses=True
            )
            self.client.ping()
            logger.info(f"Connected to Redis cache server at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis cache: {str(e)}. Caching will be disabled and operate in bypass mode.")
            self.client = None

    @property
    def is_available(self) -> bool:
        """Returns True if Redis is initialized and reachable, False otherwise."""
        if self.client is None:
            # Retry connection once in case Redis became available later
            self._connect()
        return self.client is not None

    def get_cached_recommendations(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Fetches cached recommendations for a specific user. Returns None if cache miss or Redis is unavailable."""
        if not self.is_available:
            return None
            
        key = f"movico:recs:{user_id}"
        try:
            data = self.client.get(key)
            if data:
                logger.info(f"Cache HIT for user {user_id}")
                return json.loads(data)
            logger.info(f"Cache MISS for user {user_id}")
        except Exception as e:
            logger.warning(f"Error reading from Redis cache: {str(e)}")
            
        return None

    def set_cached_recommendations(self, user_id: int, recommendations: List[Dict[str, Any]], expire: int = None) -> bool:
        """Stores recommendation results in Redis with an optional expiration time."""
        if not self.is_available:
            return False
            
        key = f"movico:recs:{user_id}"
        exp_time = expire or settings.CACHE_EXPIRE_SECONDS
        
        try:
            self.client.setex(
                name=key,
                time=exp_time,
                value=json.dumps(recommendations)
            )
            logger.info(f"Cached {len(recommendations)} recommendations for user {user_id} (TTL: {exp_time}s)")
            return True
        except Exception as e:
            logger.warning(f"Error writing to Redis cache: {str(e)}")
            return False

    def clear_user_cache(self, user_id: int) -> bool:
        """Clears cached recommendations for a user (useful when a user rates a movie)."""
        if not self.is_available:
            return False
            
        key = f"movico:recs:{user_id}"
        try:
            deleted = self.client.delete(key)
            logger.info(f"Cleared cache for user {user_id} (count: {deleted})")
            return True
        except Exception as e:
            logger.warning(f"Error clearing cache for user {user_id}: {str(e)}")
            return False
