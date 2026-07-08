from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseRecommender(ABC):
    
    @abstractmethod
    def fit(self, *args, **kwargs):
        """Fits the recommender model on the input dataset/matrix."""
        pass
    
    @abstractmethod
    def recommend(self, user_id: int, top_n: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Generates recommendations for a specific user."""
        pass
    
    @abstractmethod
    def save(self, filepath: str):
        """Serializes the model weights/parameters to disk."""
        pass
        
    @abstractmethod
    def load(self, filepath: str):
        """Loads model weights/parameters from disk."""
        pass
