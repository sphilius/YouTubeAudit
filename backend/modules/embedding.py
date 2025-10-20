from abc import ABC, abstractmethod
from typing import List, Any, Dict
import numpy as np
from backend.utils.logging_config import get_logger
from backend.exceptions import (
    EmbeddingError,
    ModelLoadError,
    VectorStoreError,
    DimensionMismatchError
)

log = get_logger(__name__)

# Conditional import for FAISS to allow the application to run without it for now
try:
    import faiss
except ImportError:
    faiss = None
    log.warning("FAISS not available - vector store functionality will be limited")

class VectorStore(ABC):
    """Abstract base class for a vector store."""

    @abstractmethod
    def upsert(self, vectors: np.ndarray, ids: List[str]):
        """Upsert vectors into the store."""
        pass

    @abstractmethod
    def query(self, vector: np.ndarray, k: int) -> List[Any]:
        """Query the store for the k nearest neighbors."""
        pass

class FaissVectorStore(VectorStore):
    """A local vector store implementation using FAISS."""

    def __init__(self, dimension: int = 768):
        if not faiss:
            log.error("FAISS not installed")
            raise ModelLoadError(
                model_name="FAISS",
                reason="FAISS is not installed. Please run 'pip install faiss-cpu' to use it."
            )

        log.info("Initializing FAISS vector store", dimension=dimension)
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.id_map = []
        log.debug("FAISS vector store initialized successfully")

    def upsert(self, vectors: np.ndarray, ids: List[str]):
        """Adds vectors to the index."""
        log.debug("Upserting vectors to FAISS", vector_count=len(vectors), dimension=vectors.shape[1])

        if vectors.shape[1] != self.dimension:
            log.error("Dimension mismatch", expected=self.dimension, actual=vectors.shape[1])
            raise DimensionMismatchError(expected=self.dimension, actual=vectors.shape[1])

        try:
            self.index.add(vectors.astype('float32'))
            self.id_map.extend(ids)
            log.info("Vectors upserted successfully", count=len(vectors), total_vectors=len(self.id_map))
        except Exception as e:
            log.error("Failed to upsert vectors", error=str(e))
            raise VectorStoreError(operation="upsert", reason=str(e))

    def query(self, vector: np.ndarray, k: int) -> List[Any]:
        """
        Searches the index for the k nearest neighbors.

        Returns:
            A list of tuples containing (id, distance).
        """
        log.debug("Querying FAISS index", k=k)

        try:
            distances, indices = self.index.search(vector.astype('float32'), k)
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1:
                    results.append((self.id_map[idx], float(distances[0][i])))

            log.debug("Query completed", results_found=len(results))
            return results
        except Exception as e:
            log.error("Failed to query FAISS index", error=str(e))
            raise VectorStoreError(operation="query", reason=str(e))

def get_video_embeddings(video_metadata: List[Dict[str, Any]]) -> np.ndarray:
    """
    Generates embeddings for a list of video metadata.
    In a real implementation, this would call an embedding model (e.g., Gemini).
    For now, this is a placeholder.

    Args:
        video_metadata: A list of dictionaries, each containing video metadata.

    Returns:
        A numpy array of embeddings.

    Raises:
        EmbeddingError: If embedding generation fails

    Note:
        This is currently a placeholder implementation returning random embeddings.
        Real implementation will use sentence-transformers or similar.
    """
    log.info("Starting embedding generation", video_count=len(video_metadata))

    try:
        # Placeholder implementation
        # TODO: Implement real embedding generation using sentence-transformers
        embedding_dimension = 768  # Example dimension
        embeddings = np.random.rand(len(video_metadata), embedding_dimension).astype('float32')

        log.info("Embedding generation complete",
                 video_count=len(video_metadata),
                 embedding_dimension=embedding_dimension,
                 embeddings_shape=embeddings.shape)
        return embeddings

    except Exception as e:
        log.error("Embedding generation failed", error=str(e), video_count=len(video_metadata))
        raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")