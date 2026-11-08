"""
Vanta: Semantic Similarity with Transformers (Layer 4 Enhancement)
Sentence transformers for cross-language semantic matching
"""

import logging
from typing import List, Dict, Any, Tuple
import numpy as np

logger = logging.getLogger("Vanta.NLP.SemanticSimilarity")


class SemanticSimilarity:
    """
    Semantic similarity using sentence-transformers
    Supports cross-language matching (Bengali ↔ English)
    """
    
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Initialize with multilingual sentence transformer
        
        Available models:
        - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (recommended)
        - sentence-transformers/paraphrase-multilingual-mpnet-base-v2
        - sentence-transformers/distiluse-base-multilingual-cased-v2
        """
        self.model = None
        self.model_name = model_name
        
    def load_model(self):
        """
        Load the sentence transformer model
        """
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded sentence transformer: {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load sentence transformer: {e}")
            return False
    
    def encode_texts(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts to embeddings
        """
        if self.model is None:
            if not self.load_model():
                raise Exception("Failed to load sentence transformer model")
        
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            raise
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts
        """
        try:
            embeddings = self.encode_texts([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0
    
    def calculate_similarity_batch(self, queries: List[str], targets: List[str]) -> np.ndarray:
        """
        Calculate similarity matrix between queries and targets
        """
        try:
            query_embeddings = self.encode_texts(queries)
            target_embeddings = self.encode_texts(targets)
            
            # Normalize embeddings
            query_embeddings = query_embeddings / np.linalg.norm(query_embeddings, axis=1, keepdims=True)
            target_embeddings = target_embeddings / np.linalg.norm(target_embeddings, axis=1, keepdims=True)
            
            # Calculate cosine similarity matrix
            similarity_matrix = np.dot(query_embeddings, target_embeddings.T)
            
            return similarity_matrix
        except Exception as e:
            logger.error(f"Batch similarity calculation failed: {e}")
            return np.zeros((len(queries), len(targets)))
    
    def find_most_similar(self, query: str, candidates: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find most similar candidates to query
        """
        try:
            similarity_matrix = self.calculate_similarity_batch([query], candidates)
            similarities = similarity_matrix[0]
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                results.append({
                    "text": candidates[idx],
                    "similarity": float(similarities[idx]),
                    "rank": len(results) + 1
                })
            
            return results
        except Exception as e:
            logger.error(f"Most similar search failed: {e}")
            return []
    
    def cross_language_similarity(self, text_en: str, text_bn: str) -> float:
        """
        Calculate similarity between English and Bengali texts
        using multilingual sentence transformer
        """
        return self.calculate_similarity(text_en, text_bn)


def create_semantic_similarity(model_name: str = None) -> SemanticSimilarity:
    """
    Factory function for semantic similarity
    """
    if model_name:
        return SemanticSimilarity(model_name)
    return SemanticSimilarity()